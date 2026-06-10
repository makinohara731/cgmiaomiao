// /api/chat-stream — Server-Sent Events streaming chat.
//
// The model produces JSON like {"reply":"喵～...","animation":"happy",...}.
// If we forwarded every Qwen delta raw, the client's speech bubble would
// fill with `{"reply":"喵～...` — readable garbage. Instead we run each
// incoming chunk through ReplyTextExtractor, a tiny streaming parser that
// emits ONLY characters inside the "reply" string value.
//
// Frame schema (all text/event-stream):
//   data: {"type":"text","content":"喵～"}              (many of these — bubble characters)
//   data: {"type":"envelope","reply":"...","animation":"happy",...}
//   data: {"type":"done"}
//   data: {"type":"error","code":"upstream","message":"..."}

import { streamHeaders, jsonError } from "../util/response.js";
import { callQwenChatStream } from "../services/dashscope.js";
import { buildSystemPrompt } from "../services/persona.js";
import { parseChatReply } from "./chat.js";

function pickHistory(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((t) => t && (t.role === "user" || t.role === "assistant") && typeof t.content === "string")
    .slice(-6);
}

const ENC = new TextEncoder();
function sseFrame(obj) {
  return ENC.encode(`data: ${JSON.stringify(obj)}\n\n`);
}

// Streaming JSON parser that emits ONLY characters inside the "reply" string
// value. Tolerates the model occasionally producing whitespace, prose
// preamble, or trailing commentary outside the JSON object.
//
// States:
//   scan      — outside any string; accumulate keyChars to detect "reply"
//   awaitColon— matched "reply", now skipping ": "
//   awaitOpen — past the colon, waiting for the opening '"' of the value
//   inValue   — emit every char; handle escapes; end on unescaped '"'
//   done      — already extracted the reply; discard everything else
class ReplyTextExtractor {
  constructor() {
    this.state = "scan";
    this.keyTail = "";     // last few non-string chars, to spot "reply"
    this.escaped = false;
    this.uHex = null;      // when collecting a \uXXXX escape, the digits so far
  }
  feed(s, emit) {
    for (let i = 0; i < s.length; i++) {
      const ch = s[i];
      if (this.state === "scan") {
        this.keyTail = (this.keyTail + ch).slice(-12);
        if (this.keyTail.endsWith('"reply"')) {
          this.state = "awaitColon";
          this.keyTail = "";
        }
      } else if (this.state === "awaitColon") {
        if (ch === ":") this.state = "awaitOpen";
      } else if (this.state === "awaitOpen") {
        if (ch === '"') this.state = "inValue";
        // else: whitespace before the opening quote — keep waiting
      } else if (this.state === "inValue") {
        // Mid-\uXXXX: accumulate exactly 4 hex digits, then emit the code point.
        if (this.uHex !== null) {
          this.uHex += ch;
          if (this.uHex.length === 4) {
            const code = parseInt(this.uHex, 16);
            if (!Number.isNaN(code)) emit(String.fromCharCode(code));
            this.uHex = null;
          }
          continue;
        }
        if (this.escaped) {
          this.escaped = false;
          if (ch === "u") { this.uHex = ""; continue; }     // start a \uXXXX run
          const decoded = { n: "\n", t: "\t", r: "", '"': '"', "\\": "\\", "/": "/", b: "", f: "" }[ch];
          if (decoded !== undefined) { if (decoded) emit(decoded); }
          else emit(ch);
        } else if (ch === "\\") {
          this.escaped = true;
        } else if (ch === '"') {
          this.state = "done";
        } else {
          emit(ch);
        }
      }
      // done: drop on the floor
    }
  }
}

export async function handleChatStream(request, env, origin) {
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

  const upstream = await callQwenChatStream(env, messages);
  if (!upstream.ok || !upstream.body) {
    const txt = upstream.body ? await upstream.text() : "no body";
    return jsonError("upstream", `DashScope stream ${upstream.status}: ${txt.slice(0, 200)}`, 502, origin);
  }

  // Re-encode upstream OpenAI-style deltas into our own SSE frame schema.
  const stream = new ReadableStream({
    async start(controller) {
      const reader = upstream.body.getReader();
      const decoder = new TextDecoder();
      const extractor = new ReplyTextExtractor();
      let buf = "";
      let assembled = "";        // all chunks concatenated for the envelope parse
      let textBuf = "";          // batched reply chars for fewer frames

      const flushText = () => {
        if (!textBuf) return;
        controller.enqueue(sseFrame({ type: "text", content: textBuf }));
        textBuf = "";
      };

      let finished = false;       // upstream emitted [DONE]
      try {
        while (!finished) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let nl;
          while ((nl = buf.indexOf("\n")) >= 0) {
            const line = buf.slice(0, nl).trim();
            buf = buf.slice(nl + 1);
            if (!line.startsWith("data:")) continue;
            const data = line.slice(5).trim();
            if (data === "[DONE]") { finished = true; break; }   // stop the OUTER loop too
            try {
              const json = JSON.parse(data);
              const delta = json.choices?.[0]?.delta?.content;
              if (typeof delta === "string" && delta) {
                assembled += delta;
                extractor.feed(delta, (ch) => { textBuf += ch; });
                // Flush every few chars so the client sees motion but we
                // don't pay an SSE frame per character.
                if (textBuf.length >= 3) flushText();
              }
            } catch (_) { /* skip malformed delta — Qwen sometimes pads */ }
          }
        }
        flushText();
        // Stream ended — parse the assembled JSON envelope and emit it
        // so the client gets a clean { animation, emote, mood } in one frame.
        const env1 = parseChatReply(assembled);
        controller.enqueue(sseFrame({ type: "envelope", ...env1 }));
        controller.enqueue(sseFrame({ type: "done" }));
      } catch (e) {
        controller.enqueue(sseFrame({ type: "error", code: "stream_io", message: e?.message || String(e) }));
      } finally {
        // Release the upstream connection promptly instead of waiting for GC.
        try { await reader.cancel(); } catch (_) {}
        try { reader.releaseLock(); } catch (_) {}
        controller.close();
      }
    },
  });

  return new Response(stream, { status: 200, headers: streamHeaders(origin) });
}
