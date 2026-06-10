// /api/asr — synchronous speech-to-text. Accepts a multipart form upload
// with an "audio" file field, base64-encodes it, and forwards to a
// synchronous DashScope ASR model. Returns { ok: true, text }.

import { jsonOk, jsonError } from "../util/response.js";
import { callQwenASR } from "../services/dashscope.js";

// Chunked base64 — building one giant binary string char-by-char is O(n)
// concatenation that also risks a huge intermediate string on long clips.
// Convert 0x8000-byte windows with apply(), then btoa the joined chunks.
function bufferToBase64(buf) {
  const bytes = new Uint8Array(buf);
  const CHUNK = 0x8000;
  let bin = "";
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

// Pull the transcription text out of an OpenAI-compatible chat response.
// content can be a plain string or an array of typed parts.
function extractASRText(result) {
  const msg = result?.choices?.[0]?.message;
  if (!msg) return result?.output?.text || "";
  if (typeof msg.content === "string") return msg.content.trim();
  if (Array.isArray(msg.content)) {
    return msg.content
      .map((p) => (typeof p === "string" ? p : p?.text || ""))
      .join("")
      .trim();
  }
  return "";
}

export async function handleASR(request, env, origin) {
  if (!env.DASHSCOPE_API_KEY) {
    return jsonError("no_key", "DASHSCOPE_API_KEY not configured", 500, origin);
  }
  let form;
  try { form = await request.formData(); }
  catch (_) { return jsonError("bad_body", "multipart parse failed", 400, origin); }
  const audio = form.get("audio");
  if (!audio || !(audio instanceof Blob)) {
    return jsonError("no_audio", "audio blob required", 400, origin);
  }
  const arrayBuf = await audio.arrayBuffer();
  const audioB64 = bufferToBase64(arrayBuf);

  const resp = await callQwenASR(env, audioB64, { format: "webm" });
  if (!resp.ok) {
    const txt = await resp.text();
    return jsonError("upstream", `ASR ${resp.status}: ${txt.slice(0, 200)}`, 502, origin);
  }
  const result = await resp.json();
  const text = extractASRText(result);
  return jsonOk({ text }, origin);
}
