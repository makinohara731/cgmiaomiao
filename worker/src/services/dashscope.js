// Thin DashScope (Qwen) client. Centralized so handlers don't have to
// know the OpenAI-compatible URL or the auth header dance.

const CHAT_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions";
const TTS_URL  = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation";

function authHeaders(env) {
  return {
    "Authorization": `Bearer ${env.DASHSCOPE_API_KEY}`,
    "Content-Type": "application/json",
  };
}

// ---- Chat (qwen-turbo) ----
export async function callQwenChat(env, messages, opts = {}) {
  return fetch(CHAT_URL, {
    method: "POST",
    headers: authHeaders(env),
    body: JSON.stringify({
      model: opts.model || "qwen-turbo",
      messages,
      temperature: opts.temperature ?? 0.85,
      max_tokens: opts.maxTokens ?? 220,
    }),
  });
}

// Streaming variant — yields server-sent-events from the OpenAI-compat
// endpoint. The OpenAI-compat path supports `stream: true` and emits
// `data: {choices: [{delta: {content: "..."}}]}` frames.
export async function callQwenChatStream(env, messages, opts = {}) {
  return fetch(CHAT_URL, {
    method: "POST",
    headers: authHeaders(env),
    body: JSON.stringify({
      model: opts.model || "qwen-turbo",
      messages,
      temperature: opts.temperature ?? 0.85,
      max_tokens: opts.maxTokens ?? 220,
      stream: true,
      stream_options: { include_usage: false },
    }),
  });
}

// ---- ASR — synchronous, single HTTP call over the OpenAI-compatible
//      endpoint. The previous implementation POSTed inline base64 to the
//      ASYNC file-transcription REST path with X-DashScope-Async:enable —
//      an internally inconsistent combination that always returned an empty
//      PENDING task envelope, so voice input never produced text.
//
//      This path sends the recorded clip as an input_audio content part to a
//      synchronous ASR model and reads choices[0].message.content in one call.
//
//      ⚠ RESIDUAL RISK (needs a live-key smoke test — cannot verify offline):
//        - model availability on the account ("qwen3-asr-flash"); and
//        - whether the model accepts the browser's webm/opus container. If it
//          rejects webm, transcode client-side to wav/pcm or pick a supported
//          MediaRecorder mimeType. A 502 from here now surfaces a real error
//          envelope to the client instead of a silent "没听清".
export async function callQwenASR(env, audioBase64, opts = {}) {
  const format = opts.format || "webm";
  const dataUri = `data:audio/${format};base64,${audioBase64}`;
  return fetch(CHAT_URL, {
    method: "POST",
    headers: authHeaders(env),
    body: JSON.stringify({
      model: opts.model || "qwen3-asr-flash",
      messages: [
        {
          role: "user",
          content: [
            { type: "input_audio", input_audio: { data: dataUri, format } },
          ],
        },
      ],
    }),
  });
}

// ---- TTS (qwen-tts via multimodal endpoint). voice is selected per story
//      route / bond stage; the optional instruct model (env.TTS_MODEL =
//      "qwen3-tts-instruct-flash") additionally honours a natural-language
//      `instructions` string for true emotion. Plain qwen-tts takes only voice. ----
export async function callQwenTTS(env, text, opts = {}) {
  const model = opts.model || "qwen-tts";
  const input = { text, voice: opts.voice || "Cherry" };
  if (opts.instructions && model !== "qwen-tts") input.instructions = opts.instructions;
  return fetch(TTS_URL, {
    method: "POST",
    headers: authHeaders(env),
    body: JSON.stringify({ model, input }),
  });
}

// Pick a qwen-tts voice from the story route / bond stage. Voice stays STABLE
// per route (so the timbre doesn't flip mid-conversation); mood is expressed via
// client playback-rate + the instruct model's instructions, not by swapping voice.
export function pickVoice({ route } = {}) {
  if (route === "浪漫") return "Serena";   // gentle, intimate
  if (route === "羁绊") return "Chelsie";  // warm companion
  return "Cherry";                          // 日常 / default — sunny & friendly
}

// Natural-language style note for the instruct TTS model, from the reply mood.
export function moodInstructions(mood) {
  if (mood === "up")   return "语气欢快上扬，俏皮可爱一点";
  if (mood === "down") return "语气柔和、放慢一些，带一点撒娇";
  return "";
}
