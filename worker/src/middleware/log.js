// Structured per-request access log. One line of JSON to console
// (Cloudflare Logpush / wrangler tail picks this up). Body content is
// never logged — only shapes and sizes. Latency in ms.

export function logAccess(rec) {
  try { console.log(JSON.stringify({ t: Date.now(), ...rec })); } catch (_) {}
}

// Wrap a handler so it auto-logs route, ip, status, ms — and exceptions
// become structured 500 responses with a stable code.
export async function withLogging(route, ip, handler) {
  const start = Date.now();
  try {
    const resp = await handler();
    logAccess({ route, ip, status: resp.status, ms: Date.now() - start });
    return resp;
  } catch (e) {
    const ms = Date.now() - start;
    logAccess({ route, ip, status: 500, ms, err: e?.message || String(e) });
    throw e;
  }
}
