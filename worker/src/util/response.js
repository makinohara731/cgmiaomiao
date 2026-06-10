// Shared response builders. Every API call returns either jsonOk or
// jsonError so client-side parsing has a stable envelope shape.
import { corsHeaders } from "../middleware/cors.js";

function baseHeaders(origin, extra = {}) {
  return { "Content-Type": "application/json", ...corsHeaders(origin), ...extra };
}

export function jsonResponse(body, status = 200, origin = null, headers = {}) {
  return new Response(JSON.stringify(body), { status, headers: baseHeaders(origin, headers) });
}

export function jsonOk(payload, origin = null) {
  return jsonResponse({ ok: true, ...payload }, 200, origin);
}

// Structured error envelope — { ok: false, error: { code, message, status } }
// Code is a short stable identifier; message is the long form (may include
// safe upstream text). The HTTP status mirrors error.status so client code
// can short-circuit before parsing.
export function jsonError(code, message, status = 500, origin = null) {
  return jsonResponse(
    { ok: false, error: { code, message: String(message).slice(0, 300), status } },
    status, origin
  );
}

export function streamHeaders(origin) {
  // NB: "Connection" is a forbidden response header — fetch/Workers silently
  // drop it. Cache-Control: no-transform + X-Accel-Buffering: no are what
  // actually prevent intermediary buffering of the event stream.
  return {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    ...corsHeaders(origin),
  };
}
