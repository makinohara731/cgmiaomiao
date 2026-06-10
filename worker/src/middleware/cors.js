// CORS middleware — strict allowlist. Any origin not on the list gets
// no Access-Control-Allow-Origin header at all (browser blocks the
// response). /health works for all origins because it's intentionally
// unauthenticated.

export const ALLOWED_ORIGINS = [
  "https://makinohara731.github.io",
  "http://127.0.0.1:8765",
  "http://localhost:8765",
  "http://127.0.0.1:8000",
  "http://localhost:8000",
];

export function pickOrigin(origin) {
  if (!origin) return null;
  if (ALLOWED_ORIGINS.includes(origin)) return origin;
  return null;
}

export function corsHeaders(origin) {
  const allowed = pickOrigin(origin);
  return {
    ...(allowed ? { "Access-Control-Allow-Origin": allowed, "Vary": "Origin" } : {}),
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
  };
}

export function preflight(origin) {
  return new Response(null, { status: 204, headers: corsHeaders(origin) });
}
