// Cloudflare Worker entry — routing only. Business logic lives in
// handlers/, services/, middleware/, util/.
//
// Routes:
//   POST /api/asr          multipart audio   → { ok, text }
//   POST /api/chat         { message, ... }  → { ok, reply, animation, emote, mood }
//   POST /api/chat-stream  same body, SSE    → text/event-stream of {chunk, envelope, done, error}
//   POST /api/tts          { text }          → audio/mpeg
//   GET  /health                             → { ok, ts }

import { preflight, pickOrigin } from "./middleware/cors.js";
import { rateLimit, rateLimitRemaining } from "./middleware/rate-limit.js";
import { withLogging, logAccess } from "./middleware/log.js";
import { jsonOk, jsonError } from "./util/response.js";
import { handleASR } from "./handlers/asr.js";
import { handleChat } from "./handlers/chat.js";
import { handleChatStream } from "./handlers/chat-stream.js";
import { handleTTS } from "./handlers/tts.js";

const RATE_LIMITED_PREFIX = "/api/";

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin");
    if (request.method === "OPTIONS") return preflight(origin);

    const url = new URL(request.url);
    const route = url.pathname;
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";

    // Origin guard — reject API calls from non-allowlisted origins early so
    // we don't burn rate-limit budget on them.
    if (route.startsWith(RATE_LIMITED_PREFIX) && origin && !pickOrigin(origin)) {
      logAccess({ route, ip, status: 403, reason: "origin" });
      return jsonError("origin", "origin not allowed", 403, origin);
    }

    if (route.startsWith(RATE_LIMITED_PREFIX)) {
      if (!rateLimit(ip)) {
        logAccess({ route, ip, status: 429, reason: "rate_limit" });
        return jsonError("rate_limit", "30 req/min cap", 429, origin);
      }
    }

    return withLogging(route, ip, async () => {
      if (route === "/api/asr" && request.method === "POST") {
        return await handleASR(request, env, origin);
      }
      if (route === "/api/chat" && request.method === "POST") {
        return await handleChat(request, env, origin);
      }
      if (route === "/api/chat-stream" && request.method === "POST") {
        return await handleChatStream(request, env, origin);
      }
      if (route === "/api/tts" && request.method === "POST") {
        return await handleTTS(request, env, origin, ctx);
      }
      if (route === "/health") {
        const resp = jsonOk({ ts: Date.now(), rateRemaining: rateLimitRemaining(ip) }, origin);
        return resp;
      }
      return jsonError("not_found", `no route for ${request.method} ${route}`, 404, origin);
    }).catch((e) => {
      console.error("Unhandled worker error:", e);
      return jsonError("internal", e?.message || "internal error", 500, origin);
    });
  },
};
