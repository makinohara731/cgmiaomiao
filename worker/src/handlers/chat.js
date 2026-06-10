// /api/chat — non-streaming. Returns a single JSON envelope:
//   { ok: true, reply, animation, emote, mood }
// or
//   { ok: false, error: { code, message, status } }

import { jsonOk, jsonError } from "../util/response.js";
import { extractJSON } from "../util/json.js";
import { callQwenChat } from "../services/dashscope.js";
import { ANIMATIONS, buildSystemPrompt } from "../services/persona.js";

function pickHistory(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((t) => t && (t.role === "user" || t.role === "assistant") && typeof t.content === "string")
    .slice(-6);
}

// Parse the model output into the structured envelope. Defensive against
// markdown-wrapped JSON, trailing prose, and truly off-format replies.
// Sanitise the optional LLM-offered reply suggestions: keep ≤3 short, non-empty
// strings (the user's possible next lines), each capped so a runaway model can't
// blow up the choice UI. Always returns an array (empty when none/invalid).
function sanitizeChoices(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  for (const c of raw) {
    if (typeof c !== "string") continue;
    const t = c.trim().replace(/\s+/g, " ");
    if (!t) continue;
    out.push(t.length > 12 ? t.slice(0, 12) : t);
    if (out.length >= 3) break;
  }
  return out;
}

export function parseChatReply(content) {
  let parsed = extractJSON(content || "");
  let reply, animation = null, emote = null, mood = "none", choices = [];
  if (parsed && parsed.reply) {
    reply = String(parsed.reply).trim();
    if (ANIMATIONS.includes(parsed.animation)) animation = parsed.animation;
    if (typeof parsed.emote === "string" && parsed.emote.trim()) emote = parsed.emote.trim();
    if (["up", "down", "none"].includes(parsed.mood)) mood = parsed.mood;
    choices = sanitizeChoices(parsed.choices);
  } else {
    reply = (content || "").replace(/[{}"]/g, "").trim() || "喵？";
    // Derive the fallback allowlist from ANIMATIONS so it can never drift
    // (the old hardcoded list silently omitted "eat").
    const m = reply.match(new RegExp(`\\b(${ANIMATIONS.join("|")})\\b`, "i"));
    if (m) animation = m[1].toLowerCase();
  }
  return { reply, animation, emote, mood, choices };
}

export async function handleChat(request, env, origin) {
  if (!env.DASHSCOPE_API_KEY) {
    return jsonError("no_key", "DASHSCOPE_API_KEY not configured", 500, origin);
  }
  let body;
  try { body = await request.json(); }
  catch (_) { return jsonError("bad_body", "request body is not JSON", 400, origin); }

  const message = body && body.message;
  if (!message || typeof message !== "string") {
    return jsonError("no_message", "message is required", 400, origin);
  }

  const history = pickHistory(body.history);
  const memory  = typeof body.memory === "string" ? body.memory : "";
  const story   = typeof body.story === "string" ? body.story : "";
  const system  = buildSystemPrompt(body.state, memory, story);
  const messages = [
    { role: "system", content: system },
    ...history,
    { role: "user", content: message },
  ];

  let resp = await callQwenChat(env, messages);
  if (!resp.ok) {
    const txt = await resp.text();
    return jsonError("upstream", `DashScope Chat ${resp.status}: ${txt.slice(0, 200)}`, 502, origin);
  }
  let result = await resp.json();
  let content = result.choices?.[0]?.message?.content || "";
  let env1 = parseChatReply(content);

  // Single-shot length retry — only when reply is way too long (>50).
  if (env1.reply && env1.reply.length > 50) {
    const retryMsgs = messages.concat([
      { role: "assistant", content },
      { role: "user", content: "太长啦，请用不超过 30 个字重说一遍，仍按 JSON 输出。" },
    ]);
    try {
      const r2 = await callQwenChat(env, retryMsgs, { maxTokens: 140 });
      if (r2.ok) {
        const j2 = await r2.json();
        const c2 = j2.choices?.[0]?.message?.content || "";
        const env2 = parseChatReply(c2);
        if (env2.reply && env2.reply.length <= env1.reply.length) env1 = env2;
      }
    } catch (_) { /* keep original */ }
  }

  return jsonOk(env1, origin);
}
