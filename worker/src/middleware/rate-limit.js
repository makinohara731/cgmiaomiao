// In-memory rate limiter — 30 requests / minute / IP. Per-worker
// isolate, so this is a soft guard; survives the duration of one
// isolate's lifetime. Cloudflare Durable Objects or KV would be the
// hard option if abuse becomes a real concern.

const RL_LIMIT = 30;
const RL_WINDOW_MS = 60 * 1000;
const rlMap = new Map();

export function rateLimit(ip) {
  const now = Date.now();
  const arr = rlMap.get(ip) || [];
  const fresh = arr.filter((t) => now - t < RL_WINDOW_MS);
  if (fresh.length >= RL_LIMIT) {
    rlMap.set(ip, fresh);
    return false;
  }
  fresh.push(now);
  rlMap.set(ip, fresh);
  // Opportunistic GC — prune entries whose newest hit is outside the window.
  if (rlMap.size > 500) {
    for (const [k, v] of rlMap) {
      if (!v.length || now - v[v.length - 1] > RL_WINDOW_MS) rlMap.delete(k);
    }
  }
  return true;
}

// Read the rolling window count for an IP without mutating state — useful
// for the X-RateLimit-Remaining header.
export function rateLimitRemaining(ip) {
  const now = Date.now();
  const fresh = (rlMap.get(ip) || []).filter((t) => now - t < RL_WINDOW_MS);
  return Math.max(0, RL_LIMIT - fresh.length);
}
