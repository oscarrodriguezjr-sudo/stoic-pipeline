# Stoic Channels Video Pipeline — Build Plan for Claude Code

Owner: Oscar Rodriguez. Put this file in the root of a new project folder (e.g. `stoic-pipeline/`) and open that folder in Claude Code. Claude Code reads `CLAUDE.md` automatically at the start of every session.

---

## 1. Goal

Build a program that turns a topic into a finished, upload-ready YouTube video for two faceless stoicism channels, with minimal human work:

**topic → script → voiceover → scene images → on-screen text → rendered 1080p video → thumbnail + metadata → YouTube upload (private, for approval)**

| Channel | Handle | Language | Icon | Banner tagline |
|---|---|---|---|---|
| Stoic Leader Mind | @StoicLeaderMind | English | Marcus Aurelius marble bust | Ancient wisdom. Modern leadership. |
| Estoicismo Para Líderes | @EstoicismoParaLideres | Spanish | Seneca marble bust | Sabiduría antigua. Liderazgo moderno. |

Target cadence: 3 long-form videos per week per channel (Mon/Wed/Fri), 12–14 minutes each (English), plus Shorts later. The Spanish channel is not yet phone-verified, so keep Spanish videos **under 15 minutes** until it is.

Business goal: YouTube Partner Program on both channels (1,000 subs + 4,000 watch hours), then ~$5K/month each.

---

## 2. Working rules for Claude Code

- **Subagents:** always use a lower-tier model (Haiku) for subagents to save tokens. Define them in `.claude/agents/*.md` with `model: haiku`. Reserve the main model for architecture, debugging, and script writing.
- Build in the phases in Section 10, in order. Do not start a phase until the previous phase's acceptance test passes.
- Every stage must be **idempotent and resumable**: if an output file already exists, skip it. A crash must never require regenerating paid assets.
- Save every paid-API task ID and result to disk immediately (see Section 8). Runway output URLs expire; download right away.
- Never commit secrets. All keys live in `.env` (add `.env` to `.gitignore`).
- Keep a human approval step before anything is published.
- Oscar runs Windows. Use Python 3.11+, ffmpeg installed via `winget install Gyan.FFmpeg`, and paths via `pathlib`. Test that commands work in PowerShell.

---

## 3. Tech stack

| Need | Tool | Notes |
|---|---|---|
| Language | Python 3.11+ | `requests`, `Pillow`, `python-dotenv`, `pydantic`, `anthropic`, `google-api-python-client`, `google-auth-oauthlib` |
| Script writing | Anthropic API | Writes and adapts scripts as structured JSON (Section 5) |
| Voiceover | Runway API (`dev.runwayml.com`), ElevenLabs models, preset voice **"James"** | Or call ElevenLabs directly with Oscar's own key — see Section 6 |
| Scene images | Runway API, model `gen4_image`, ratio `1920:1080` | ~8 credits per image |
| Video render | ffmpeg (local) | Recipe in Section 7 |
| Text overlays | Pillow | Fonts in Section 7 |
| Upload | YouTube Data API v3 | One OAuth token per channel (both are Brand Accounts) |
| Scheduling (later) | Windows Task Scheduler first; Render cron job later | Same pattern as Oscar's existing F1 automation on Render |

`.env` keys: `ANTHROPIC_API_KEY`, `RUNWAY_API_KEY`, `ELEVENLABS_API_KEY` (optional), YouTube OAuth client file path.

Look up current endpoint details in the official docs (`docs.dev.runwayml.com`, ElevenLabs API docs, YouTube Data API docs) rather than guessing. APIs change. **See Section 14 — this already bit us once.**

---

## 4. Project structure

```
stoic-pipeline/
  CLAUDE.md
  .env                      # never committed
  config/
    channels.yaml           # per-channel: language, voice, fonts, colors, max length, OAuth token path
    style.yaml              # image prompt style, overlay timings, render settings
  assets/
    fonts/                  # Cinzel[wght].ttf, CormorantGaramond-Italic[wght].ttf
    brand/                  # banners, icons (already created)
  pipeline/
    script_gen.py           # topic -> scenes.json
    voice.py                # scenes.json -> vo/*.mp3
    images.py               # scenes.json -> img/*.png
    overlays.py              # scenes.json -> overlays/*.png
    render.py                # all of the above -> video.mp4
    thumbnail.py
    metadata.py              # title, description, tags, chapters
    upload.py
    state.py                 # task-ID ledger, resume logic, cost tracking
    run.py                   # CLI: python -m pipeline.run --channel en --topic "..."
  videos/
    2026-10-01_calm-under-pressure/
      scenes.json
      state.json            # every task ID, status, cost
      vo/  img/  overlays/  segments/
      final.mp4  thumbnail.png  metadata.json
  .claude/agents/           # Haiku subagents
```

---

## 5. The scene format (the heart of the system)

Every video is a list of scenes. Each scene becomes one rendered segment. This format was proven in testing.

```json
{
  "title": "10 Stoic Rules to Stay Calm Under Pressure",
  "channel": "en",
  "scenes": [
    {"key": "A",  "image": "camp-night",  "zoom": "in",  "overlay": {"type": "caption", "text": "DANUBE FRONTIER, 170 AD"},
     "narration": "In the winter of the year 170, the Roman Empire was on fire. ..."},
    {"key": "C",  "image": "tent-lamp",   "zoom": "out", "overlay": {"type": "titlecard", "line1": "10 STOIC RULES", "line2": "to stay calm under pressure"},
     "narration": "Today, we'll turn his words ... into ten rules ..."},
    {"key": "1a", "image": "epictetus",   "zoom": "in",  "overlay": {"type": "title", "label": "RULE 1", "text": "Know what is yours to control"},
     "narration": "Rule one. Know what is yours to control. ..."},
    {"key": "1q", "image": "epictetus",   "zoom": "in2", "overlay": {"type": "quote", "lines": ["“Some things are within our power,", "while others are not.”"], "author": "EPICTETUS"},
     "narration": "Some things are within our power... while others are not."},
    {"key": "1b", "image": "epictetus",   "zoom": "out", "overlay": {"type": "takeaway", "text": "Control what you can. Release what you can't."},
     "narration": "Your judgments, your choices ..."}
  ],
  "images": {
    "camp-night": "Roman legion winter camp on the Danube frontier at night, heavy rain, torches ...",
    "epictetus": "The Greek Stoic philosopher Epictetus, an older bearded man with a cane, teaching students in a sunlit courtyard ..."
  }
}
```

Scene pattern per rule: `Na` (title + setup) → `Nq` (quote, if the rule has one) → `Nb` (explanation + takeaway). Two images per rule is the target (one for a/q, one for b) — **the worked example above doesn't actually follow that (it reuses "epictetus" for all three) — pick one convention and be consistent; the built Spanish fixture (Section 14) uses one image for a+q and a second for b, matching the ~20-image cost estimate in Section 12.** The complete English script for video 1 already exists in `Script_10_Stoic_Rules_Calm_Under_Pressure.md`. Convert it to this format as the first test fixture.

**Script generation (`script_gen.py`):** give Claude the topic, the channel voice (Section 9), and this schema. Require JSON output validated with pydantic. Rules for the writer:
- 1,700–1,900 words for 12–13 minutes. Each narration chunk must stay under 1,000 characters.
- Quotes must be real and correctly attributed (Marcus Aurelius, Seneca, Epictetus). Prefer well-known public-domain translations. Hedge legends ("it's said", "according to one ancient story").
- Use ellipses (`...`) for dramatic pauses. The voice honors them.
- Leave one `[PERSONAL STORY]` slot for Oscar to fill with a real leadership story. This matters for monetization (Section 11).

---

## 6. Voiceover

**CLAUDE.md's original assumption here (preset "James", model "eleven_v3", language_code/stability/speed params) does not match the live API — see Section 14 before writing code against this section.**

**Originally assumed:** Runway API, preset voice **James**. Prefer model `eleven_v3` with `stability 0.5`, `speed 0.95`, `language_code "en"`. `eleven_multilingual_v2` also works.

Lessons learned (enforce these in code):
- **One generation at a time per model**, and **50 generations per model per day**. Submit sequentially: submit, poll every 5 seconds until SUCCEEDED, download, then submit the next. Track daily counts in `state.py`.
- Runway sometimes rejects a line ("content moderation" or "rejected the text-to-speech request"). If a request is rejected, first check the credit balance (Runway rejects when credits run out), then retry once, then rephrase slightly and retry.
- **Runway API credits are separate from the Runway app subscription.** Buy them at dev.runwayml.com → Billing. Check the balance at the start of every run and stop early with a clear message if it's too low for the whole video.
- Cost observed: 3–7 credits per segment, about 130–180 credits (~$1.50) per 12-minute video.

**Alternative (cheaper and higher quality at scale):** call the ElevenLabs API directly with Oscar's key. Direct API calls work fine outside Claude's connectors. Requires a paid ElevenLabs plan (Starter or higher) for commercial rights. Make the voice provider a config setting so switching is one line.

Spanish: test several Runway presets with `language_code "es"` (or an ElevenLabs Spanish voice) and let Oscar pick. Aim for a neutral Latin American accent. **Per Section 14, there's no `language_code` param on the real endpoint — language comes from the text itself, so this may mean picking ONE preset that sounds right in both languages. Confirm with a real side-by-side listen.**

---

## 7. Render recipe (proven; reproduce exactly)

**Images:** generate at 1920×1080, then upscale to 2560×1440 (or 2112×1188 on low-memory machines) before zooming, to avoid jitter.

Image prompt suffix (append to every prompt):
> Cinematic painting, epic historical film still, ancient Rome, warm amber light against deep shadows, rich detail, no text, no letters, no watermark.

**Fonts:** Cinzel (variable, weight 600–700) for labels and titles; Cormorant Garamond Italic (weight 500) for quotes and takeaways. Download from `github.com/google/fonts` (`ofl/cinzel`, `ofl/cormorantgaramond`). Colors: gold `(232,200,140)`, ivory `(245,240,228)`. All text gets a soft drop shadow (Gaussian blur 6, black at alpha 200).

**Overlay types** (1920×1080 transparent PNGs):

| Type | Layout | Appears |
|---|---|---|
| `caption` | Lower-left Cinzel 46, letter-spacing 6, gold underline; bottom gradient | 1.0s after start |
| `capend` | Same as caption | last 7s |
| `titlecard` | Centered "10 STOIC RULES" Cinzel 120 + italic subtitle 84; black veil alpha 150 | 0.3s |
| `title` | Centered gold "RULE N" Cinzel 64 + ivory italic 88; veil 110 | 0.2s → fades out at 5.5s |
| `quote` | Two centered italic lines at 74 + author in Cinzel 40 gold; veil 150 | 0.3s, whole scene |
| `takeaway` | Bottom-center italic 64 + short gold rule; bottom gradient | last 6.5s |
| `center` | Two large centered italic lines (closing message) | last 7s |
| `sub` | "SUBSCRIBE" + channel name | last 8s |

**Per-scene ffmpeg** (one overlay input per scene keeps memory low):
- Duration T = voice length + padding (1.6s default, 2.4s quotes, 3.0s closing scenes). Voice starts after a 0.7s delay.
- Zoom (Ken Burns), with `on` = output frame number:
  - `in`: `z='1+0.0006*on'`
  - `out`: `z='1.15-0.0006*on'`
  - `in2` (continuation): `z='1.12+0.0005*on'`
  - Always use `x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30`.
- Overlay fades in/out with `fade=...:alpha=1`. The whole segment gets a 0.5s fade in and out.
- Encode: `libx264 -preset veryfast -crf 23`, AAC 160k, 48 kHz stereo.

**Final assembly:** concat all segments (concat demuxer, `-c copy`). Add a quiet ambient bed:
```
aevalsrc='0.5*sin(2*PI*55*t)+0.35*sin(2*PI*82.41*t)+0.25*sin(2*PI*110*t)+0.12*sin(2*PI*164.8*t)',
tremolo=f=0.15:d=0.4, lowpass=f=400, volume=0.05, 4s fade in/out
```
Mix it under the voice (`amix normalize=0`), then `loudnorm=I=-14:TP=-1.5:LRA=11` (YouTube loudness) and `-movflags +faststart`.

**Performance lessons:**
- Render **one segment at a time**. Running many ffmpeg jobs in parallel ran out of memory in testing.
- Needs about 2 GB free RAM. On Oscar's PC this should take a few minutes per video.
- Write each finished segment to disk immediately so a crash only loses one segment.

**Confirmed working (Section 14):** this exact recipe (zoompan + overlay fade + adelay + concat + ambient bed + loudnorm) has been implemented in `pipeline/render.py` and smoke-tested end-to-end with placeholder assets — the ffmpeg filter graph itself is solid. What's untested is real Runway output feeding into it.

---

## 8. State, cost, and reliability (`state.py`)

`videos/<id>/state.json` records, for every asset: provider, task ID, status, cost, local path, and timestamps.
- On start: load state, skip anything already on disk, poll any in-flight task IDs before submitting new ones.
- Retry with exponential backoff and jitter on 429 or capacity errors.
- Print a summary at the end: credits used, dollars spent, time taken, assets generated.
- Store a daily usage counter per model to respect the 50-per-day limits.
- `python -m pipeline.run --resume <video-id>` continues any interrupted video.

---

## 9. Channel content rules

**Stoic Leader Mind (English):** stoicism for leaders, founders, and executives. Calm, authoritative tone. Draw on Oscar's 20+ years as a CEO/COO for examples. Video 1 is "10 Stoic Rules to Stay Calm Under Pressure."

**Estoicismo Para Líderes (Spanish):** broader everyday angle (work, money, family, heartbreak, discipline). **Adapt** each script with Claude, rewriting idioms and examples for Latin American viewers, never translating literally. A native speaker should review scripts before publishing.

First 20 topics (EN / ES):
1. 10 Stoic Rules to Stay Calm Under Pressure / 10 Reglas Estoicas Para Mantener la Calma
2. Marcus Aurelius: How to Handle Disrespect / Marco Aurelio: Cómo Responder a la Falta de Respeto
3. When You Go Silent, Everything Changes / Cuando Te Quedas en Silencio, Todo Cambia
4. 7 Stoic Habits of Leaders Who Never Break / 7 Hábitos Estoicos de Quienes Nunca Se Rinden
5. Seneca on Wasting Time / Séneca: Deja de Perder el Tiempo
6. How to Never Be Bothered by Anyone / Cómo Hacer Que Nada Te Afecte
7. Epictetus: Control Only What You Can / Epicteto: Controla Solo Lo Que Depende de Ti
8. 10 Stoic Rules for Money and Wealth / 10 Reglas Estoicas Sobre el Dinero
9. Being Alone Makes You Stronger / La Soledad Te Hace Más Fuerte
10. The Stoic Morning Routine / La Rutina Matutina Estoica
11. Stop Explaining Yourself to People / Deja de Dar Explicaciones
12. How Stoics Handle Betrayal / Cómo Enfrentan los Estoicos la Traición
13. Marcus Aurelius on Leading People / Marco Aurelio: Cómo Liderar a Otros
14. 8 Signs You Are Becoming Mentally Strong / 8 Señales de Que Eres Mentalmente Fuerte
15. Amor Fati: Turn Every Setback Into Strength / Amor Fati: Convierte Cada Caída en Fuerza
16. Stoic Rules for Difficult Family Members / Reglas Estoicas Para Familiares Difíciles
17. Why Discipline Beats Motivation / Por Qué la Disciplina Vence a la Motivación
18. Seneca on Anger / Séneca: Cómo Dominar la Ira
19. Detach From Outcomes and Win / Suelta el Resultado y Ganarás
20. The Stoic Guide to Starting Over / Guía Estoica Para Empezar de Nuevo

**Metadata (`metadata.py`):** SEO title (under 60 characters, benefit-led, following the proven patterns "10 Stoic Rules to…", "How to Never…"), a description with chapter timestamps generated from the actual scene start times, 10–15 tags, and 3 hashtags.

**Thumbnail (`thumbnail.py`):** 1280×720, one strong scene image, 3–5 words of large Cinzel text, high contrast. Make 2 variants per video for A/B testing.

---

## 10. Build phases (each ends with an acceptance test)

| Phase | Build | Done when |
|---|---|---|
| 0. Setup | Folder structure, venv, ffmpeg check, `.env`, fonts, `channels.yaml` | `python -m pipeline.run --check` confirms ffmpeg, fonts, keys, and Runway credit balance |
| 1. Render engine | `overlays.py` + `render.py` from a scenes.json using placeholder images and silent audio | A 60-second test video renders on Oscar's PC and matches the style in Section 7 |
| 2. Assets | `voice.py` + `images.py` + `state.py` with resume and cost tracking | Kill the process mid-run, rerun, and it finishes without regenerating anything |
| 3. Video 1 end-to-end | Convert the existing script to scenes.json and produce the full 12-minute video | Oscar watches and approves `final.mp4` |
| 4. Script generation | `script_gen.py` for new topics, with the personal-story slot | Topic 2 script generated, Oscar edits it, video produced |
| 5. Upload | `upload.py`: private upload + metadata + thumbnail, one OAuth token per channel | Video appears as Private in the right channel's Studio |
| 6. Spanish | Spanish adaptation, Spanish voice selection, under-15-minute check | First Spanish video approved |
| 7. Batch + schedule | `run.py --week` produces 3 videos per channel; Task Scheduler (later Render) | A full week queued, waiting for approval |
| 8. Shorts | Cut 30–45s vertical clips (1080×1920) from each long video | 5 Shorts per long video |

**Status as of Section 14: Phase 0 code exists but hasn't passed its acceptance test (no machine has yet reached Runway with a real key). Phase 1 has passed on synthetic assets. Phases 2–3 are written but unrun for real.**

---

## 11. Monetization guardrails (originally non-negotiable — see Section 16 for the override)

- **YouTube "inauthentic content" policy:** mass-produced, repetitive AI videos get rejected for monetization. Every video needs original commentary, distinct structure, and ideally one real story from Oscar. Never publish near-duplicate videos.
- Turn on the **"altered or synthetic content"** disclosure in Studio when realistic AI imagery is used.
- Use only licensed or original assets: AI images Oscar owns, public-domain quotes, and the generated ambient bed. No film clips and no copyrighted music.
- Voice rights: use a paid plan that grants commercial use (Runway API credits, or ElevenLabs Starter+).
- **YouTube API note:** videos uploaded through an unverified Google Cloud API project may be locked to Private until the project passes Google's audit. Plan to upload as Private and publish manually from Studio, or apply for the audit early.
- YouTube API quota: an upload costs about 1,600 of the default 10,000 daily units, so about 6 uploads a day at most.
- Keep Oscar's approval step before publishing, always.

---

## 12. Cost per video (estimate)

| Item | Credits | ≈ USD |
|---|---|---|
| ~20 scene images × 8 | 160 | $1.60 |
| ~32 voice segments × ~5 | 160 | $1.60 |
| Script (Anthropic API) | — | $0.10–0.30 |
| **Total** | | **≈ $3–4 per video** |

Six videos a week comes to about $20–25 a week in API costs, before any savings from reusing images across Shorts.

---

## 13. Assets that already exist

- Channel banners (marble style) and icons (Marcus Aurelius and Seneca busts). The icons are in Oscar's Cloudinary under `stoic-leader-mind/`.
- Full video-1 script: `Script_10_Stoic_Rules_Calm_Under_Pressure.md`.
- Four test scene images in Cloudinary: `stoic-leader-mind/v1/` (camp, tent, Epictetus, tablet).
- Channel descriptions (EN/ES) and the plan doc from the planning session.

The 19 extra scene images and James voice clips generated during testing live in a temporary remote workspace and should be treated as lost. Regenerate them in Phase 3.

---

## 14. Build status & Runway API corrections (added 2026-09-23)

A first build pass happened in a cloud sandbox with **no network access to api.dev.runwayml.com** (org egress policy blocked it outright — confirmed via a 403 on the CONNECT tunnel, not a transient error). Everything that didn't need live network access got built and smoke-tested; everything that needs a real Runway call needs to run on Oscar's actual PC, where the network is unrestricted. This section is what a fresh Claude Code session needs to know before continuing.

**What's done and tested:**
- Full project scaffold: `config/channels.yaml`, `config/style.yaml`, all of `pipeline/`.
- `pipeline/overlays.py` — all 8 overlay types build correctly (tested against all 31 real scenes below with stand-in fonts).
- `pipeline/render.py` — the full ffmpeg chain (Ken Burns zoom, overlay fade, voice delay, concat, ambient bed, loudnorm, faststart) ran successfully end-to-end on placeholder image + silent audio and produced a valid 1920x1080 h264/aac mp4. **The render engine itself is solid.**
- `videos/reglas-estoicas-calma/scenes.json` — the full Spanish video-1 script converted to the scene schema: 31 scenes, 23 unique images, all narration chunks under the 1000-char limit. Built by `scripts/build_scenes_es.py` from `Script_10_Reglas_Estoicas_Para_Mantener_la_Calma.md`.
- `.env` has a real `RUNWAY_API_KEY` (Oscar's).

**What's NOT done — this is the actual remaining work:**
1. **Fonts are missing.** `assets/fonts/` needs the real `Cinzel[wght].ttf` and `CormorantGaramond-Italic[wght].ttf` from github.com/google/fonts (`ofl/cinzel`, `ofl/cormorantgaramond`). The sandbox that built this couldn't reach GitHub either. This is a two-file download on any normal internet connection.
2. **`config/channels.yaml` has placeholder `preset_id: "REPLACE_ME"` for both channels.** Run `python -m pipeline.run --list-voices` first — it hits `GET /v1/voices` and prints every real preset name. Pick one (ideally test it reads naturally in Spanish before locking in the `es` channel, since language is implied by the text, not a separate parameter — see the correction below).
3. **No real Runway call has ever been made against this code.** Run `python -m pipeline.run --check` first on a machine with real internet — it validates ffmpeg, fonts, the API key, and reachability in one shot.
4. **Then:** `python -m pipeline.run --channel es --scenes videos/reglas-estoicas-calma/scenes.json --video-id reglas-estoicas-calma` generates all images, all voiceover, renders every segment, concatenates, and writes `thumbnail_a/b.png` + `metadata.json`. It's fully resumable — if it dies partway (rate limit, network blip, laptop sleeps), rerun the exact same command and it picks up where it left off via `state.json`.
5. **`upload.py` was never written** — Phase 5 in the table above. Not needed to get a finished video file; needed before automated YouTube upload.
6. **`script_gen.py` was never written** — Phase 4. Only needed once you're generating new topics beyond video 1.

**Runway API corrections (the actual live schema, checked against Runway's own docs/SDK source on 2026-09-23 — Section 3 and Section 6 above describe the ORIGINAL, now-outdated assumption):**
- Base URL `https://api.dev.runwayml.com/v1`, headers `Authorization: Bearer <key>` + `X-Runway-Version: 2024-11-06`.
- `POST /text_to_speech` does **not** have a preset called "James" and does **not** accept `model: "eleven_v3"`. It accepts exactly two shapes: `{"model": "eleven_multilingual_v2", "prompt_text": "...", "voice": {"type": "runway-preset", "preset_id": "<name>"}}` or a `seed_audio`/reference-audio variant. **There is no `language_code`, `stability`, or `speed` parameter on this endpoint at all** — language is inferred from the text you send.
- `POST /text_to_image` takes `{"promptText": ..., "model": "gen4_image", "ratio": "1920:1080"}` — this part matched the original assumption.
- `GET /tasks/{id}` polls a task; `GET /voices` lists presets.
- **Not independently verified:** the exact field names in a completed task's response JSON (this build assumes `{"status": "SUCCEEDED", "output": [...]}`) — `pipeline/runway_client.py` is written to print the raw response if it doesn't recognize the shape, rather than fail silently. If the very first real API call throws in `extract_output_urls`, read that printed JSON and fix the two small helper functions in `runway_client.py` — don't guess further, the live response will just tell you.

**Cost note:** nothing above has spent a single Runway credit. The ~$3–4 in Section 12 hasn't been touched yet; it gets spent the first time step 4 above actually runs.

---

## 15. Automation: Phases 4, 5, 7 (added after video 1 ES rendered successfully)

Video 1 (Spanish) rendered end-to-end for real on Oscar's PC. Built on top of that, to get to scheduled unattended production:

- **`pipeline/script_gen.py`** (Phase 4) — topic string -> full scenes.json via the Anthropic API, validated with pydantic against the exact schema (rejects bad overlay types, over-length narration, dangling image references before a single Runway credit gets spent on a broken script). Needs `ANTHROPIC_API_KEY` in `.env` — a plain console.anthropic.com key, unrelated to any Claude subscription. Tested against a synthetic response (JSON extraction + validation logic all pass); **never called the real Anthropic API** — that domain happened to be reachable from the build sandbox, so if you want to sanity-check it before trusting it unattended, run `python -m pipeline.script_gen` interactively on one topic first, actually read the output, before letting `batch.py` run it 20 times unsupervised.
- **`config/topics.yaml`** — all 20 topics from Section 9, with per-language `status_en`/`status_es` (`pending`/`done`). Topic 1 ES is marked `done`. `pipeline/batch.py` reads this and only flips a topic to `done` after its `final.mp4` actually exists.
- **`pipeline/batch.py`** (Phase 7) — `python -m pipeline.batch --channel es --count 3` produces the next 3 pending Spanish topics: generates each script, runs the full existing render pipeline, and (only with `--upload`) uploads as Private. This is the Render cron job's entry point. Tested: topic-selection and the done/pending file-rewrite logic (confirmed it doesn't disturb comments or other topics) — not tested with a real script_gen/Runway run.
- **`pipeline/upload.py`** (Phase 5) — YouTube Data API v3 private upload + thumbnail. Requires a one-time, human, per-channel browser consent (`python -m pipeline.upload --authorize --channel en`) — this cannot be automated away, Google requires it. Uploads are **always** `privacyStatus: private`; nothing in this codebase publishes a video. Untested end-to-end (needs a Google Cloud OAuth client + real consent flow, neither of which exist yet).
- **`Dockerfile` + `render.yaml`** — a Render Blueprint with two cron jobs (en/es), matching the pattern from the F1 automation project. Read the comments in `render.yaml` before deploying — in particular, Render cron jobs are ephemeral between runs by default, so a persistent disk is mounted at `/app/videos` to keep `state.json`/`topics.yaml`-equivalent progress; decide where `config/topics.yaml` itself and the OAuth tokens live before your first unattended week, not after. The Dockerfile deliberately does NOT try to re-download the fonts — it just copies whatever's already in your local `assets/fonts/`, so make sure those two files are actually committed to the repo you connect to Render.

**Update 2026-09-23 — this section is now historical.** Oscar explicitly asked to remove the human-review gate entirely; see Section 16. `batch.py --upload` now publishes videos live with no review step.

---

## 16. Full automation override (2026-09-23)

Oscar was told plainly, twice, what this removes: an occasional bad Runway image, a mispronounced line, or a factual slip goes straight to a live public video with nobody watching first; and if a run of near-duplicate, unreviewed AI videos trips YouTube's "inauthentic content" detection (Section 11), it risks both channels at once, not just one video. He confirmed he wants it anyway — fully public, no review.

What changed in code:
- `upload.py`'s `PUBLISH_STATUS = "public"` (was implicitly "private"). A `--privacy-status` CLI flag can still override per-call if you ever want to test one upload without going public.
- `render.yaml`'s both cron jobs now run `batch.py ... --upload`, so every scheduled run renders AND publishes, unattended, on the schedule in that file (Mondays, 3 topics per channel).
- A second persistent disk (`/app/config`) was added so `topics.yaml`'s done/pending state survives between Render deploys — this matters more now, since a config reset that makes an already-published topic look "pending" again means producing and publishing a duplicate live video, not just wasted API spend.

If this decision changes: delete `--upload` from `render.yaml`'s two `startCommand` lines (stops publishing, keeps rendering), or change `PUBLISH_STATUS` back to `"private"` in `upload.py` (keeps uploading, stops going live) — either is a one-line change, not a rebuild.
