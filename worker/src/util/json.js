// Resilient JSON extraction — the LLM occasionally wraps its JSON in
// prose, markdown code fences, or trailing commentary. Pull out the
// first balanced {...} block and try to parse that.
export function extractJSON(text) {
  if (!text || typeof text !== "string") return null;
  const s = text.indexOf("{");
  const e = text.lastIndexOf("}");
  if (s >= 0 && e > s) {
    try { return JSON.parse(text.slice(s, e + 1)); } catch (_) {}
  }
  return null;
}
