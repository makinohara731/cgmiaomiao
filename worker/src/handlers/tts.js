// /api/tts — sweet female TTS (Cherry voice). Returns audio bytes
// directly when DashScope serves them inline; falls back to fetching
// the temporary URL it sometimes returns in JSON instead.

import { jsonError } from "../util/response.js";
import { corsHeaders } from "../middleware/cors.js";
import { callQwenTTS, pickVoice, moodInstructions } from "../services/dashscope.js";

function sanitize(text) {
  return text
    .replace(/[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, "")
    .replace(/[\[\]{}]/g, "")
    .trim()
    .slice(0, 200);
}

async function sha256Hex(s) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function handleTTS(request, env, origin, ctx) {
  if (!env.DASHSCOPE_API_KEY) {
    return jsonError("no_key", "DASHSCOPE_API_KEY not configured", 500, origin);
  }
  let body;
  try { body = await request.json(); }
  catch (_) { return jsonError("bad_body", "request body is not JSON", 400, origin); }
  const raw = body && body.text;
  if (!raw || typeof raw !== "string") {
    return jsonError("no_text", "text is required", 400, origin);
  }
  const clean = sanitize(raw);
  if (!clean) return jsonError("empty", "text empty after sanitize", 400, origin);

  // voice from route/stage; emotion (instruct model only) from mood
  const voice = pickVoice({ route: body.route, stage: body.stage });
  const instructions = env.TTS_MODEL ? moodInstructions(body.mood) : "";

  // Re-attach THIS origin's CORS to a CORS-free cached/built response, so the
  // strict allowlist stays intact while the immutable audio is shared by origin.
  const withCors = (resp) => {
    const h = new Headers(resp.headers);
    for (const [k, v] of Object.entries(corsHeaders(origin))) h.set(k, v);
    return new Response(resp.body, { status: resp.status, headers: h });
  };

  // Read-through cache: identical (text, voice, instructions) → instant replay,
  // no re-synth (the canned greeting/pet/hint pools repeat a lot). Replaces the
  // old `Cache-Control: no-store`.
  const cache = caches.default;
  const cacheKey = new Request("https://tts.cache/" + (await sha256Hex(clean + "|" + voice + "|" + instructions)));
  const hit = await cache.match(cacheKey);
  if (hit) return withCors(hit);

  const upstream = await callQwenTTS(env, clean, { voice, instructions, model: env.TTS_MODEL });
  if (!upstream.ok) {
    const t = await upstream.text();
    return jsonError("upstream", `TTS ${upstream.status}: ${t.slice(0, 200)}`, 502, origin);
  }

  // qwen-tts returns either inline audio or JSON with a temporary url.
  let buf, ct;
  const upCt = upstream.headers.get("content-type") || "";
  if (upCt.startsWith("audio/")) {
    buf = await upstream.arrayBuffer();
    ct = upCt;
  } else {
    const data = await upstream.json().catch(() => null);
    const audioUrl = data && data.output && data.output.audio && data.output.audio.url;
    if (!audioUrl) return jsonError("no_audio", "no audio in upstream response", 502, origin);
    const a = await fetch(audioUrl);
    buf = await a.arrayBuffer();
    ct = a.headers.get("content-type") || "audio/mpeg";
  }

  const cacheable = new Response(buf, {
    headers: { "Content-Type": ct, "Cache-Control": "public, max-age=31536000, immutable" },
  });
  if (ctx && ctx.waitUntil) ctx.waitUntil(cache.put(cacheKey, cacheable.clone()));
  return withCors(cacheable);
}
