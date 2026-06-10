# CLAUDE.md

Guidance for Claude Code working in this repo. **Detailed gotchas live in
`docs/gotchas.md`** — read it before debugging the pipeline or AR app.

## What this is

A pipeline that turns an AI-generated 3D model of a chibi cat sprite
("**喵喵咕咯精灵**") into a rigged, animated GLB and serves it in an AR web app.
No build system or test suite for the pipeline — the "code" is headless-Blender
Python scripts; verification is visual (scripts render PNGs into `verify/`). The
web app (`ar/`) is a Vite + TypeScript project with its own dev/build.

**The canonical name is `喵喵咕咯精灵`** (not `咕咕`, not `骨咯`). Use this exact
form in all UI titles, the worker persona, and docs.

The web app has a **"soul layer"** on top of the animation engine: cat naming,
long-term memory, proactive speech, daily mood + diary, narrative onboarding,
bond-stage unlocks, generative BGM, an LLM persona, and a galgame VN layer
(typewriter dialogue, choices, affection/route story). The Blender pipeline and
the web app can be touched independently.

## Active rebuild (branch `galgame-rebuild`) — read progress first

Mid-rebuild into an **AR-first visual-novel pet**: desktop webcam + **real AR**
(WebXR is unavailable on desktop) via **green-colour-block detection by default**
(MindAR image-target behind `?ar=mind` — it lost the marker on real hardware),
the live AR cat as the on-screen character with a Q-cute galgame layer on top of
the soul layer. Renderer unified on **three.js** (model-viewer kept only for the
mobile QR/Quick-Look page); app is **Vite + TypeScript**.

Progress lives in **files + git, not any one conversation**. Read in order:
1. `docs/进度.md` — live progress, decisions, next-step spec
2. `docs/计划.md` — the full approved plan (phases P0–P6)
3. `git log --oneline` on this branch AND inside `ar/` (its own separate repo)

P0–P6 are essentially done (VN dialogue + choices, story routes 日常/羁绊/浪漫 +
endings + 3 save slots + 回廊 gallery, P5 Blender anims/faces). The latest pass
added: a **fresh light "清新" theme** + self-hosted display fonts (LXGW 霞鹜文楷 /
Nunito) + a **custom line-icon set replacing all emoji** (`src/ui/icons.js`);
**autonomous idle routines** (the cat chains clips into self-directed sequences,
personality-biased); the **日记本 / 记忆板 / 羁绊之路 + 心意收藏** highlight
surfaces; **soul layer surfaced in AR** (affection ribbon + bottom-sheet panels +
`#arCaption` callouts); **gesture/face/volume + new full-body pose recognition
wired into the real green-block AR** (P2.5/P2.6, MediaPipe, real-device-only);
and **per-route TTS voice + a read-through audio cache**. Desktop AR still needs
real-hardware placement tuning (`?sc=&bs=&ry=&rx=&lift=`).

Key consequences a future instance must know (detail in `docs/gotchas.md`):
- `ar/` is **Vite + TS**: `cd ar && npm run dev` (`http://127.0.0.1:8765/`),
  `npm run build` → `ar/dist/`. Runtime assets live in **`ar/public/`** (so
  `animate_v2.py`/`export_usd_v2.py` copy the GLB/usdz there). The Bash cwd resets
  to the main-repo root after a `cd`, so prefix npm commands with `cd /…/ar &&`.
- **three.js is the DESKTOP DEFAULT renderer** (mobile keeps model-viewer).
  Everything funnels through the **`CatRenderer`** interface; `ModelViewerRenderer`
  + `ThreeCatRenderer` are the backends (`RendererFactory` + `capabilities.ts`
  pick one; force with `?renderer=three`/`?renderer=mv`). The animated cat is
  **`CatModel`** (GLB + AnimationMixer + face-texture swaps + face-toward + contact
  shadow) under one `object3D`, reused in AR by attaching to a marker anchor.
- **Default desktop AR = `GreenBlobSession`** (colour-block); MindAR is `?ar=mind`.
  Both implement `ArSession`; `ThreeCatRenderer.enterAR()` reparents the same
  `CatModel`. (Full green-blob + seating detail in `docs/gotchas.md`.)
- `life.busyUntil` is now a `CatStateMachine` (`src/anim/CatState.ts`); the
  autonomous loop gates on `catState.isBusy()`.
- **The god-file `ar/main.js` is GONE** (Svelte rebuild, ar/ branch
  `svelte-rebuild`): `index.html` → `src/app/main.ts` (App.svelte +
  bootstrap.ts); behaviour lives in plain-TS `src/engine/**` + `src/stores/*`,
  Svelte components are view-only. Imports stay **extensionless**. The v1 Tripo
  pipeline + big binaries live in a gitignored `_archive/`; `verify/` and
  `_archive/` aren't git-tracked.

The pipeline sections below are the **stable v2 baseline** the rebuild builds on.

## Commands

Blender: `D:\Program Files\Blender Foundation\Blender 5.0\blender.exe`.

```sh
# 1. Rig: import the PBR GLB, reshape legs, build armature, skin, save .blend
blender --background --python rig_pipeline_v2.py
# 2. Animate + export: author actions into NLA, render verify frames,
#    export character_v2.glb, auto-copy into ar/public/
blender --background --python animate_v2.py
# 2b. (iOS) Refresh the Quick-Look usdz from the animated blend (NOT auto-rebuilt)
blender --background --python export_usd_v2.py
# 2c. (3D print) watertight STL (fdm+resin) + full-colour set; opens the SKINNED
#     blend (rest pose), independent of the AR exports
blender --background --python export_print_v2.py        # → print/miaomiao_v2_{fdm,resin}.stl
blender --background --python export_print_color_v2.py  # → print/miaomiao_v2_color.{obj,mtl,png,glb}

# 3. AR app (Vite + TS — `python -m http.server` no longer works)
cd ar && npm install && npm run dev   # http://127.0.0.1:8765/
#   npm run build → ar/dist/; npm run preview; npm run typecheck
```

Always run step 1 before step 2 (`animate_v2.py` opens the blend that
`rig_pipeline_v2.py` saves). The legacy `export_usd.py` + `make_usdz.py` pair
opened the **stale v1 Tripo** blend — don't use them.

Headless-Chrome screenshots of the local AR page need the proxy
`--proxy-server=http://127.0.0.1:10808` (model-viewer + fonts load from a CDN);
global puppeteer is at `C:/Users/Lenovo/AppData/Roaming/npm/node_modules` (run
with `NODE_PATH` set, or `createRequire` to it). Keep `--use-gl=swiftshader` for
ordinary screenshots. `dev/anim-probe.mjs` boots the three cat + checks it
animates; seed state via `page.evaluateOnNewDocument` (see the persistAll gotcha).

## Architecture

```
_new_asset_inspect/base_basic_pbr.glb   (AI-generated PBR source, 9 parts)
        │  rig_pipeline_v2.py
        ▼
miaomoaguge_v2_skinned.blend            (13-bone armature, rigid-skinned; REST pose)
        │  animate_v2.py (authors actions into NLA)
        ├─ export_print_v2.py       → print/miaomiao_v2_{fdm,resin}.stl   (3D print, mono)
        ├─ export_print_color_v2.py → print/miaomiao_v2_color.*           (3D print, colour)
        ▼
miaomoaguge_v2_animated.blend           (live source for the AR exports)
        ├─ animate_v2.py  → character_v2.glb ──copied──▶ ar/public/character_v2.glb
        └─ export_usd_v2.py → ar/character_v2.usdz                        (iOS Quick Look)
```

The two output families branch from **different** blends: AR exports (GLB/USDZ)
carry the rig + animations from the *animated* blend; 3D-print exports take the
*skinned* blend's rest geometry, drop the rig, and fuse the 9 parts into one
watertight solid.

**The v2 model**: 9 mesh parts `root.0`..`root.8` (0=EarL 1=ArmL 2=LegL 3=Head
4=Body 5=ArmR 6=LegR 7=Tail 8=EarR), faces **-Y**, **~1.9 units tall**, full PBR
pack. **Rigging is rigid**: each mesh 100%-weighted to one of 13 bones
(`Hips→Spine→Head→EarL/EarR`, `Hips→ArmL/ArmR/LegL/LegR/Tail1→2→3→4`; tail split
by Y). No auto-weights — chibi parts move as units.

**Animations** (`animate_v2.py`): **27 actions** — idle, walk, run, attack, hurt,
wave, happy, jump, spin, backflip, twirl, lookaround, groom, stretch, sleep,
sniff, eat, (v5) headtilt, sit, lickpaw, pounce, playbow, (v6) nod, shy, ponder,
adore, headpat — keyframed, pushed to NLA, exported `ACTIONS` mode. idle/walk/
run/sleep loop; the rest are one-shots the app returns to idle after. glTF drops
animated bone *scale* → translation + rotation only. A new clip must be added to
the NLA push list + a render block, AND registered client-side in
`ar/src/engine/clips.ts` (CLIPS) + `engine/emote-art.ts` (EMOTE_FOR) +
`engine/voice-input.ts` (VOICE_MAP) + `components/AnimBar.svelte` + the
autonomy idle pool (`engine/autonomy.ts`).

The GLB ships all 27 clips but **the LLM may only request the ~17 on the worker's
`ANIMATIONS` allowlist** (`worker/src/services/persona.js`; `handlers/chat.js`
validates against it). The v5/v6 clips are client-only (gestures, VOICE_MAP,
idle pool, pose) — add one to that list to let the cat *choose* it in chat.

**3D-print pipeline** (`export_print_*_v2.py`): voxel-remeshes the 9 stubs into
one watertight 2-manifold solid (printers reject open/multi-shell), re-poses the
arms geometrically, scales STL units = mm. The colour script additionally
Smart-UV-projects + bakes the diffuse → OBJ+MTL+PNG + GLB. Self-checks
watertight/manifold/single-piece; renders to `verify/v2_print_*`. (Bake gotchas
in `docs/gotchas.md`.)

**The old pipeline** (`rig_pipeline.py`, `animate_and_export.py`) on the Tripo
model is superseded and moved to gitignored `_archive/_root_2026/` — don't edit.

**`ar/` is a separate git repo** (remote `makinohara731/cgmiaomiao-ar`); the main
repo `.gitignore`s it. Commit AR changes inside `ar/`, pipeline/worker/docs in the
main repo.

## Module map

```
worker/src/
  worker.js            entry: routing + middleware only
  middleware/          cors (strict allowlist) · rate-limit (30/min/IP) · log
  util/                response (jsonOk/jsonError) · json (extractJSON)
  services/
    dashscope.js       Qwen chat/stream/ASR/TTS client; pickVoice + moodInstructions (TTS)
    persona.js         CAT_PERSONA + describeState + memoryBlock + ANIMATIONS allowlist
  handlers/            asr · chat (+parseChatReply) · chat-stream (ReplyTextExtractor) ·
                       tts (per-route voice + Cache-API read-through)
ar/
  index.html           the Svelte entry (loads src/app/main.ts; legacy main.js deleted)
  src/
    app/               main.ts (mount + SW reg) · App.svelte · bootstrap.ts (DI wiring +
                       idempotent onModelLoaded funnel + 15s safety net)
    engine/            plain-TS behaviour: CatController (single owner of "what's playing",
                       return-to-idle off the mixer 'finished' event) · autonomy · actions ·
                       chat · voice (TTS) · voice-input (ASR+VOICE_MAP) · ar · vision ·
                       ar-overlay · expression · face-toward · petting · feed · persistence ·
                       saves-bridge · time-of-day · device · hints-session · errors · wiring ·
                       vn · runtime · clips · emote-art · soul/{life,bond,daily,diary,memory,
                       naming,proactive,questions}
    stores/            soul (life/cfg/mem/diary/daily + STAGES; persist IMPERATIVELY, never
                       from store.subscribe) · session · ui
    components/        view-only Svelte: Scene · EnvLayer · Hud · AnimBar · VnLayer ·
                       Status/Diary/Memory/Settings/Gallery panels · Onboarding · ChatPanel ·
                       QrModal · Loader
    bus.ts  audio.ts  chat-stream.ts  particles.ts  hints.ts
    composites.ts      macro actions + autonomous idle routines (cancellable scheduler)
    ui/icons.js        custom line-icon set + mountIcons() (replaces all emoji)
    anim/CatState.ts   CatStateMachine
    renderer/          CatRenderer + CatModel + ThreeCatRenderer (desktop, hosts AR) +
                       ModelViewerRenderer (mobile) + RendererFactory + capabilities
    ar/                ArSession + GreenBlobSession (+ green-detect) + MindArSession + mindar-runtime
    vn/                DialogueBox + Choices + vn-styles.css
    story/             StoryEngine + Route + saves
```

API response envelope: success `{ ok:true, ...payload }` / failure
`{ ok:false, error:{ code, message, status } }`. Streaming chat frames
(`text/event-stream`): `{type:"text",content}` · `{type:"envelope",reply,
animation,emote,mood,choices}` · `{type:"done"}` · `{type:"error",code,message}`.

## Soul layer (in `ar/src/engine/soul/*` + `src/stores/soul.ts`)

Autonomous-pet behaviours; each system has its own localStorage key (wipe one to
reset cleanly):

| Key                     | Stores                                                          |
|-------------------------|----------------------------------------------------------------|
| `miaomiao.life.v1`      | needs, affection, bornAt, catName, userName, unlocks[]          |
| `miaomiao.mem.v1`       | `facts:[{k,v,ts}]` + `topics` (≤12 facts, ≤180-char LLM block)  |
| `miaomiao.diary.v1`     | append-only diary `[{ymd,text,tag,ts}]`                         |
| `miaomiao.daily.v1`     | today's `{ymd, theme, moodBias}`                                |
| `miaomiao.cfg.v1`       | personality / proactive / nightSleep / cloudVoice / bgm         |
| `miaomiao.onboarded.v1` | flag set when the 4-beat cutscene completes                     |
| `miaomiao.hints.v1`     | seen-state for one-time gesture-tip chips (`src/hints.js`)      |
| `miaomiao.story.v1` / `.saves.v1` | route/beats/endings · 3 save slots (`src/story/`)     |

Key surfaces (line numbers drift — grep): naming (`applyNaming`,
`catNameDisplay`); memory (`extractFacts`/`buildMemoryBlock`, viewable in the
**记忆板** `renderMemory`); proactive speech (`proactiveSpeak`, throttled);
autonomous idle (`runBehavior` — single micro-actions + personality-biased
multi-clip **routines** in `composites.ts`); daily roll (`dailyRoll`); diary
(`writeDiary`, the **日记本** `renderDiary`); affection (`STAGES`, `addAffection`,
the **羁绊之路** ladder + **心意收藏** in `renderStatusPanel`); unlocks
(`STAGE_UNLOCK`/`grantUnlock`, surfaced in AR via `soulNotice`/`#arCaption`);
BGM/SFX (all in `src/audio.js`, procedural Web Audio); onboarding cutscene
(`runOnboardingCutscene`). Voice: `sayLine(text, mood)` → `speak(text, mood)`,
which sends mood + `story.route()` + bond stage to `/api/tts` (per-route voice +
mood-tinted playback rate).

## Top gotchas (full list → `docs/gotchas.md`)

- **glTF/three.js ignores animated bone *scale*** — translation + rotation only;
  facial expressions are runtime head-texture swaps, not morph targets.
- **Never export WebP in the GLB** — Scene Viewer (Android AR) refuses the whole
  asset. Use `export_image_format="AUTO"`. Draco is fine.
- **Chinese-localized Blender** — find nodes by `node.type`, not display name.
  Engine is `BLENDER_EEVEE` (not `_NEXT`); actions are slot-based (`ACTIONS` mode).
- **`CatModel.playClip` hard-cuts one-shots** (full weight from frame 0) so
  amplitude reads at 100%; loops keep the 0.25 s cross-fade.
- **`composites` uses a cancellable scheduler** — steps via `at()`, `play()`
  claims `catState` before step 0 + cancels stale timers; `cancel()` on user taps.
  Each composite returns total ms. VOICE_MAP composites precede single-clip entries.
- **`persistAll()` runs on visibilitychange** — seed test localStorage via
  `page.evaluateOnNewDocument`, never between two `page.goto`s.
- **All user-facing emoji are gone** — UI icons come from `src/ui/icons.js`
  (`mountIcons` injects `[data-icon]`); emote bubble falls back through
  `EMOTE_ART`. Keep new UI emoji-free.
- **Camera (📸) needs a secure context** — `navigator.mediaDevices` is undefined
  on `http://<LAN-IP>`; use the HTTPS Pages URL on a phone.
- **Worker CORS is strict** — add any new test port to `ALLOWED_ORIGINS`.
