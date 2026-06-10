# Gotchas — hard-won, verify before debugging

Relocated out of `CLAUDE.md` (which was too long to load every session). These are
all still load-bearing; CLAUDE.md keeps only a short "top gotchas" list and points
here for the full set.

## Rebuild gotchas (three.js / AR / VN / story)

- **mind-ar 1.2.5 is incompatible with three ≥0.160** — its `mindar-image-three` build
  imports the removed `sRGBEncoding`, so it link-errors. Use mind-ar's three-free low-level
  `Controller` (`ar/public/vendor/mindar/mindar-image.prod.js`, **vendored** + lazy-loaded only
  on enter-AR via `src/ar/mindar-runtime.ts`) and feed the tracked `worldMatrix` into our own
  three scene. Vendored, not `npm install`ed — its `canvas` native dep won't build on Windows,
  and tfjs (~2.2MB) must stay out of the main bundle.
- **Compiling a `.mind` marker needs a REAL GPU.** MindAR's tfjs feature-extraction kernel
  (`BinomialFilter`) is missing from the CPU backend, so headless puppeteer with
  `--use-gl=swiftshader` stalls at 0%; **drop that flag** to compile on the real GPU
  (`dev/compile-mind.mjs`, ~12s). But KEEP `--use-gl=swiftshader` for ordinary headless
  screenshots — it renders stably there. Marker card synthesized by `dev/make-marker-card.py`.
- **Load the vendored mind-ar runtime via a `<script type="module">` tag, NOT `import()`.**
  A dynamic `import()` of a `public/` URL works in the static prod build but **500s under the
  Vite dev server** — Vite rewrites the request to `…?import` and runs the 2.2MB tfjs bundle
  through its module pipeline. `src/ar/mindar-runtime.ts` injects a script tag; the bundle sets
  `window.MINDAR.IMAGE` on execute. Still lazy (first enter-AR only), never enters main bundle.
- **DEFAULT desktop AR is GREEN-COLOUR-BLOCK detection, not MindAR.** On the first hardware test
  MindAR's image-marker never locked (a marker card on a phone screen — glare/moiré/small/angled
  — defeats feature matching; symptom: `#arHint` stays up, `onFound` never fires). Default backend
  is **`GreenBlobSession`** (`src/ar/GreenBlobSession.ts` + pure, unit-tested `src/ar/green-detect.ts`):
  each frame downsample camera to 192px, HSV-threshold green, take the **largest connected component**,
  map centroid through the `object-fit:cover` crop to viewport NDC, drive an `anchor` Object3D —
  position + a FIXED size, **no rotation** (cat faces viewer; 2-DoF). MindAR (`MindArSession`) is
  still reachable via **`?ar=mind`**. Both implement the same **`ArSession`** interface, so
  `ThreeCatRenderer.enterAR()` reparents the SAME `CatModel` under `session.anchor()`, puts the
  camera at origin with `session.cameraProjectionMatrix()`, and `exitAR()` reverses it. Show the
  marker via `dev/make-green.py` → `public/targets/green.png`. **Seating** (`EnterArOpts
  {scale,rotXDeg,rotYDeg,lift}`): green defaults `1/0/22/0` (upright, slight 3/4 yaw); cat size is
  a FIXED `baseScale` (default **2.2** after the "too small" hardware test — green-area coupling
  once made it tiny on a dark marker). All tunable LIVE: `?sc=`(mount size) `?bs=`(baseScale)
  `?ry=`/`?rx=`(yaw/pitch) `?lift=`; bake chosen values into `main.js` `AR_SEATING` green branch /
  `GreenBlobSession` `baseScale`. Hit-testing for petting/look uses `GreenBlobSession.screenPos()`
  so an off-centre cat is tappable; contact shadow hidden in green mode. No tfjs/worker/`.mind`.
- **AR is only headless-verifiable up to `prepare()`.** `dev/ar-smoke.{html,ts}` +
  `ar-smoke-probe.mjs` is two-track: (A) `enterAR/exitAR` plumbing via a stub session, (B) real
  `MindArSession.prepare()` (camera + runtime + Controller + `.mind` + projection). It **stops
  before** `start()`'s `controller.dummyRun()`/`processVideo()` — tfjs GPU warmup + marker lock
  need a real GPU **and** a physical card, untestable headless. Run on a **real GPU** (no
  `--use-gl=swiftshader`). The probe asserts the GLB clip count (currently **27**). MediaPipe
  gesture/face/pose recognition (now wired into AR) is likewise real-device-only.
- **The VN layer (`src/vn/`) is the galgame dialogue system (P3).** `DialogueBox.ts` is the
  primary speech surface — a bottom typewriter box with a name tab (`catNameDisplay`); the old
  floating `#sayBubble` is retired (`display:none`). `sayLine(text, mood)` → `dialogue.say()`;
  streaming chat → `dialogue.beginStream()`/`setText()`/`end()` (the network paces the text —
  `say()` has the typewriter, `beginStream()` does not). `Choices.ts` generalizes option/input UI
  (`show()` + `showInput()`), used by `askQuestion`/`openNicknameDialog`/`offerReplyChoices()`.
  The LLM may return an optional `choices[]` — server-sanitized in `worker/.../chat.js`
  `sanitizeChoices` (≤3 items, ≤12 chars, always an array); client renders quick-reply chips.
  `src/vite-env.d.ts` lets tsc accept the `import "./vn-styles.css"` side-effect imports.
- **Dev-only `window` hooks** (`__dialogue`/`__choices`/`__offerChoices`) are gated by
  `import.meta.env.DEV` (tree-shaken from prod). AR-mode CSS: `body.ar-mode` (drops the storybook
  env layer; in soul-layer mode also restyles the bond chip into a top affection ribbon + panels
  into translucent bottom sheets + `#arCaption` floating callouts), `#scene video.ar-feed`
  (live feed behind the transparent canvas), `#arHint` (marker-card overlay).
- **The story layer (`src/story/`, P4) is local-scripted (LLM gets only a 【剧情】 mood label).**
  `StoryEngine` (singleton `story`, persists `miaomiao.story.v1`) is injected with host fns via
  `story.configure()`; main.js calls one-line hooks (`onAffection`/`onBondStage`/`onDailyRoll`/
  `onNameLearned`/`onOnboardComplete`/`maybeBeat`). **Invariants to keep** (each was an
  adversarial-review bug): the on\* hooks only RECORD — beats play ONLY via `maybeBeat()` on an
  idle proactive turn (gated on `isBusy()` + `choices.isOpen()`); CHOICE beats are `manualSeen`
  and mark seen ONLY in their `onPick` (a missed offer must re-fire, else the 浪漫 route locks
  out); `save()` no-ops while `saves.isSuppressed()` AND before `load()`; slot-restore
  (`doLoadSlot`) runs `story.load()` BEFORE `dailyRoll()` inside `saves.withSuppressed`, and every
  persist path honors `isSuppressed`. Routes/beats/endings live in `Route.ts`; `story.route()`
  returns 日常/羁绊/浪漫 (used by the TTS voice picker). `saves.ts` snapshots the 6 soul keys +
  story into `miaomiao.saves.v1`.

## Pipeline / Blender / AR gotchas

- **glTF/three.js skinning ignores animated bone *scale*.** A blink built by squashing eye bones
  renders fine in Blender but does nothing downstream. Only bone translation + rotation survive
  the GLB round-trip. **Facial expressions are NOT morph targets either** — the shipped solution
  is a runtime **baseColorTexture swap** on the Head material (`CatModel`/`ModelViewerRenderer`
  `loadFaces`/`setFace`/`flashExpression`): the `face_*.webp` variants (blink/happy/sad/surprise/
  love/cry + v6 blush/think, in `ar/public/textures/`, generated by `_archive/make_faces_v*.py`)
  swap the head `.map`. Each load is try/catch'd so a missing webp degrades to neutral. (These
  webp faces are loaded by the in-page viewer, never baked into the GLB, so the Scene-Viewer
  "no WebP in GLB" rule below doesn't apply.)
- **Pose-bone `.location` is in the bone's local space.** For vertical bones (Hips, Spine, Head)
  the bone's local **Y** axis is world-up, not Z. Vertical motion (jump arc, breathing bob, hip
  dip) must keyframe `location` index **Y (1)**; index Z (2) moves the bone horizontally.
- **Bone local axes vary per bone** — always probe (`bone.matrix_local` columns) before assuming
  which rotation/translation index does what. Arm bones are horizontal, leg bones point down.
- **This is a Chinese-localized Blender.** Node *display names* are translated (Principled BSDF =
  "原理化 BSDF"). Find nodes by `node.type` (`'BSDF_PRINCIPLED'`), never by name.
- **Blender 5.0 render engine** is `BLENDER_EEVEE`, not `BLENDER_EEVEE_NEXT` — wrap in try/except.
- **Blender 5 actions are slot-based.** Legacy `action.fcurves` returns empty; bone values still
  evaluate via the NLA. Export uses `ACTIONS` mode; `NLA_TRACKS` merges same-named tracks across
  datablocks (needed if bundling a mesh-morph animation into a skeletal clip).
- When a source mesh is fundamentally broken (the Tripo tail was an open sheet), prefer
  regenerating from a better source over endless in-pipeline geometry surgery.
- **Never export WebP textures in the GLB for an AR app.** Blender's `export_image_format="WEBP"`
  writes `EXT_texture_webp` into glTF `extensionsRequired`; Google **Scene Viewer (Android native
  AR) does NOT implement it and refuses the whole asset** — AR shows nothing, even though the
  in-page WebGL viewer decodes WebP fine. Use `export_image_format="AUTO"` (jpg/png). Draco
  (`KHR_draco_mesh_compression`) is fine — keep it.
- **iOS Quick Look needs a USDZ.** `ar-modes` listing `quick-look` isn't enough — set
  `ios-src="character_v2.usdz"`. The committed usdz can lag the GLB clip set — refresh via
  `export_usd_v2.py` (opens the **current** animated blend, isolates idle, drops EXR/WebP, embeds
  textures). The legacy `export_usd.py` + `make_usdz.py` opened the **stale v1 Tripo blend** — do
  not use for v2.
- **Camera-passthrough (📸) needs a secure context.** `navigator.mediaDevices` is undefined on
  `http://<LAN-IP>` — localhost/https are secure, a bare LAN IP over http is not. Test camera mode
  on a phone via the HTTPS Pages URL. `enterCamMode` checks `window.isSecureContext`.

## Soul-layer (v3) gotchas

- **Proactive throttle.** `PROACTIVE_MIN_GAP` 90 s, `PROACTIVE_HOUR_CAP` 4/h. Ring buffer is
  in-memory only (reload resets — fine). When throttled, `proactiveSpeak()` falls back to a small
  ambient action so the loop rhythm stays alive.
- **Memory size caps.** `MEM_FACT_CAP=12`, `MEM_VAL_MAX=24`, `MEM_BLOCK_MAX=180`. Fact extraction
  is regex-only on the client (no LLM call per turn). **Longer alternation prefixes must come
  first** in `FACT_PATTERNS` — `不喜欢` before `不`, else "我不喜欢香菜" matches `不`.
- **Daily roll is local-time keyed.** `localYMD()` uses the device clock; UTC midnight doesn't
  trigger a roll. Derive test dates from `localYMD()` or the dedupe won't fire.
- **The cat name is just a string.** Cute "喵" sounds + persona lines stay hardcoded;
  `catNameDisplay()` is used only where the name addresses the cat. Don't bulk-replace 喵喵.
- **BGM is procedural.** No mp3 ships; `startBGM()` builds the chord pad from `BGM_CHORDS`. Don't
  add an `<audio>` tag — it breaks the duck-on-speak + time-of-day swap.
- **Worker CORS is strict.** `ALLOWED_ORIGINS` = Pages domain + local-dev ports. A new test port
  must be added there or chat/ASR/TTS are silently blocked by the browser.
- **`persistAll()` runs on every visibilitychange.** A second `page.goto` fires
  `visibilitychange:hidden` on the OLD page → `persistAll()` overwrites freshly seeded
  `mem`/`diary`/`life` with the old page's empty in-memory state. **Seed localStorage via
  `page.evaluateOnNewDocument()` (runs before page scripts), not between navigations.**
- **`life.catName` empty string = "use the default".** Don't store the literal "喵喵" — the
  empty-string sentinel is how onboarding knows whether to show the naming step on return visits.

## Architecture / streaming / touch (v4) gotchas

- **`main.js` is an ES module.** Top-level `let`/`const` are NOT on `window`. E2E scripts that
  call internal fns via `page.evaluate` won't reach them; route through bus events / DOM / seeded
  localStorage instead.
- **The service worker bypasses `/api/*`.** A SW buffering an event-stream would break SSE; the
  fetch handler short-circuits on `/api/` so the network reaches the Cloudflare Worker directly.
- **`audio.configure()` runs before any play\* call.** main.js wires it right after import; moving
  it later makes the first `playMeow` hit the default-noop `isMuted` config and play when muted.
- **Composites: the scheduler owns cancellable timers.** Each composite SCHEDULES its steps via
  the internal `at(ms, fn)` (not bare `setTimeout`); `composites.play()` `clearPending()`s the
  previous routine + bumps a token (stale timers no-op) + claims `catState` busy via `busyUntil`
  BEFORE step 0. Each composite returns total ms. `composites.cancel()` (called from `userPlay`)
  interrupts a running routine so a single-clip tap doesn't get stamped over. A composite that
  returns no number breaks the busy window.
- **VOICE_MAP composites must precede single-clip entries.** "跳一下舞" hits `跳`→`jump` before
  the `dance` composite otherwise. The map is order-sensitive.
- **Streaming reply text comes from `ReplyTextExtractor`, not raw JSON.** If you nest the reply
  differently in the LLM prompt, the extractor still looks for the bare `"reply"` key and emits
  no text. Update its state machine if the schema moves.
- **Long-press is 350 ms with a 14 px movement cancel threshold.** If users find petting hard to
  trigger, raise the threshold to ~22 px before touching the timer.
- **Particles are DOM elements.** The CSS `contain: layout style paint` on `#particleLayer` is
  load-bearing — without it every spawn triggers a full scene-tree layout.

## v4.1 gotchas

- **`faceToward` got a 2nd arg (clientY).** Existing call sites still work (defaults to "don't
  change pitch"); new code should pass clientY so the cat looks at the tap point.
- **SSE retry only fires when zero chars emitted.** A mid-reply upstream death keeps the partial
  bubble (a retry would duplicate chars). Fix only by switching to a transactional protocol.
- **`navigator.onLine` is best-effort** (captive portals report online). The streamChat retry +
  offline-reply fallback handles the real failure; the offline pill is decorative.
- **Hints fire from bus events.** Stop emitting `EVT.AnimPlayed` / `EVT.BondUnlock` and the
  reactive hints never fire. Seen-state is shared across reloads — clear `miaomiao.hints.v1` to
  re-trigger in dev.
- **Mic peak is unreliable for <350 ms recordings.** `stopMicMeter` returns 0.5 (neutral) for
  very short takes so a finger slip doesn't trigger shout/whisper.
- **CSS `--mic-amp` only resets when `stopMicMeter` runs.** A page-hide mid-recording leaves the
  glow ring at the last amp until the next record. Acceptable rare-edge artefact.

## v4.2 (review-driven) gotchas

- **ASR uses the OpenAI-compatible synchronous path, not the async file API.** `callQwenASR`
  posts inline `input_audio` (base64 data URI) to `compatible-mode/v1/chat/completions` with
  `qwen3-asr-flash`. **NOT verified against a live key** — if voice errors, check (a) the model is
  enabled on the account and (b) it accepts the browser's webm/opus (else transcode to wav / pick
  a supported `MediaRecorder` mimeType).
- **Chat owns `catState`/busy for its whole in-flight window.** `sendChat` claims it up front;
  the streaming / non-streaming terminals reset it to a short read-tail on success and ~+400 ms on
  every error path. A new chat terminal branch must reset it too, or the loop stays suppressed
  (cat goes silent) — or, without the up-front claim, the loop fires `sayLine` mid-stream and
  clobbers the streaming bubble + double-fires TTS.
- **`cancelPress()` clears gesture state; `endPress()` snapshots first.** A short tap reaches
  `pointerup` while the long-press timer is pending, so `endPress` reads `pressStart`/`pressIsLong`
  into locals BEFORE calling `cancelPress()` (which nulls them) — else every tap is swallowed.
- **model-viewer `orientation` is "roll pitch yaw" — yaw is the THIRD slot.** Keep roll 0.
- **`stopBGM` snapshots its nodes to locals before the fade timeout.** `startBGM` calls
  `stopBGM(0)` then installs new nodes on the shared `bgm` object; a teardown reading `bgm.*`
  inside the timeout would kill the NEW bgm.
- **`onModelLoaded` is idempotent (guarded by `initDone`).** It runs from `load`, the cached-GLB
  fast path, and a 15 s safety-net. Keep it idempotent; degraded-mode init (no animations) is a
  valid fallback and `playAnim` no-ops when there are no clips.
- **`CatModel.playClip` HARD-CUTS one-shots.** One-shot clips `stop()` every other action + play
  at full weight from frame 0 (no fade-in), so anticipation/peak frames read at 100% amplitude —
  fixing "动作幅度变小". Only loops (idle/walk/run/sleep) keep the 0.25 s cross-fade.

## 3D-print pipeline gotchas (`export_print_*_v2.py`)

- **Re-assigning an image's `colorspace_settings`/`alpha_mode`/`generated_color` AFTER baking
  regenerates its buffer from `generated_color` and SILENTLY DISCARDS the bake.** Set all image
  properties at `images.new(...)` time; after baking touch ONLY `filepath_raw` + `file_format`,
  then `save()`. Verify by reloading the saved PNG and counting opaque/coloured texels.
- **A diffuse COLOUR-only bake writes RGB but leaves ALPHA at 0** → premultiplies to BLACK in
  glTF/EEVEE, reads as empty to print bureaus. Create the bake image with `alpha=False` +
  `alpha_mode='NONE'` so it saves fully opaque. (Per-pixel alpha writeback is unreliable for a 2K
  image in `--background`.)
- **Texture bakes REQUIRE Cycles** (`scene.render.engine='CYCLES'`); `bpy.ops.object.bake`
  no-ops/errors under EEVEE. Set `view_transform='Standard'`. Selected-to-active: select all
  sources, then the target, make the target ACTIVE last; the target needs a UV map (Smart-UV the
  remesh) and an Image Texture node that is BOTH `.select=True` and `nodes.active`.
- **Voxel remesh is the watertight guarantee — and it destroys UVs** (hence the colour path bakes
  onto a fresh Smart-UV map). It fuses overlapping stubs into one piece, so always self-check
  `pieces==1`; a limb not overlapping the body within one voxel becomes a detached island.
- **STL has no unit — slicers read it as mm.** The model is ~1.9 Blender units, so export-time
  scaling to `TARGET_HEIGHT_MM` is mandatory or the print is ~2 mm tall.
- **Arm pose is geometric, not rig-driven.** The print scripts rotate the arm *mesh* about its
  shoulder pivot in the X–Z plane. 60° droop tucks hands into the body → "looks armless"; ~22° +
  `ARM_RAISE` to shoulder height reads as proper arms. Whiskers remesh into thin fragile spikes —
  thicken/engrave before an FDM run; resin prints them fine.
