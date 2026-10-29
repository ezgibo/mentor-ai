# Mentor AI — Engineering Design Doc

**Status:** Ready for Coding Jam (v1.0)
**Last updated:** October 28, 2026
**Pattern reference:** `reference/resume-tailor/` (same stack, single-agent predecessor)

---

## 1. Summary

Mentor AI is a FastAPI app with a vanilla HTML/CSS/JS frontend and a local SQLite database. Four Gemini-powered agents —
Summary, Web Search, Mock Interview, Review — are plain Python modules, each with a `SYSTEM_PROMPT` that ships empty
and a set of pre-written task functions. A small orchestrator owns all status transitions and starts background agents
with `asyncio`. The voice interview runs over the Gemini Live API through a WebSocket relay in FastAPI, with a
turn-by-turn fallback over HTTP. One process, one command: `uv run uvicorn main:app --app-dir backend --reload`.

## 2. Assumptions

- **Scale:** a workshop room — one user per laptop, local only.
- **Runtime:** Python 3.11+ with `uv`; modern Chrome / Edge / Safari / Firefox with microphone access.
- **Credentials:** each participant's own `GEMINI_API_KEY` (or Vertex AI via `GOOGLE_CLOUD_PROJECT`).
- **Models:** the Gemini 2.5 family by default, every name overridable in `.env`.

## 3. Goals & non-goals

**Goals**
- Participants build each agent by pasting one prompt; the app runs (with locked features) at every step.
- Code, not the model, decides every next step — deterministic and testable.
- Long-running agents (search ~40–90 s, review 10–20 s) never block an HTTP request.
- A 7-question voice interview survives Live API session and connection limits.
- `uv run pytest` passes with no network.

**Non-goals**
- Multi-user, auth, deployment, horizontal scaling, task queues (Celery/Redis), an agent framework (plain
  `google-genai` was chosen to keep every call visible).

## 4. Architecture

```mermaid
flowchart LR
  subgraph Browser
    UI[index.html / app.js]
    AUDIO[audio.js<br/>mic 16 kHz · speaker 24 kHz]
  end
  subgraph FastAPI["FastAPI (backend/main.py)"]
    API[REST /api/*]
    WS[WebSocket /ws/interviews/:id]
    ORCH[orchestrator.py<br/>status transitions + background tasks]
    subgraph Agents["backend/agents/"]
      S[summary.py 🧭]
      W[web_search.py 🔎]
      M[mock_interview.py 🎙️]
      R[review.py 📝]
    end
    DB[(SQLite<br/>data/mentor.db)]
  end
  subgraph Gemini
    FLASH[gemini-2.5-flash<br/>+ Google Search]
    LIVE[gemini-2.5-flash-native-audio<br/>(preview-12-2025) Live API]
    TTS[gemini-2.5-flash-preview-tts]
  end
  UI --> API --> ORCH
  ORCH --> S & W & R
  AUDIO <--> WS --> M
  S & W & R --> FLASH
  M --> LIVE
  M --> TTS
  ORCH <--> DB
  WS --> DB
```

**What's deliberately NOT here:** no Node build step, no ORM, no message broker, no agent framework, no browser access
to the API key.

## 5. Key components

| Component | File | Responsibility |
|---|---|---|
| API server | `backend/main.py` | Routes, error → status-code mapping (423 locked, 409 wrong state, 404, 400, 502 Gemini), static frontend, WebSocket route |
| Orchestrator | `backend/orchestrator.py` | Every status change; starts background agents via `asyncio.create_task`; records failures for the UI |
| Agent registry | `backend/agents/__init__.py` | `is_active` (prompt pasted?), `require()` → `AgentLockedError` |
| Summary Agent | `backend/agents/summary.py` | 6 foreground tasks; resume attached as a PDF/image part |
| Web Search Agent | `backend/agents/web_search.py` | Plan 3–4 search angles → parallel grounded searches → parallel extraction → code cleaning → fit ranking → broaden once if < 3 |
| Mock Interview Agent | `backend/agents/mock_interview.py` | Live config + tools; turn-by-turn line, TTS, transcription |
| Review Agent | `backend/agents/review.py` | Rubric scores per question; fails loudly if a question is skipped |
| Live relay | `backend/voice/live_proxy.py` | Browser ⇄ Gemini Live audio, transcript capture, reconnect with resumption handle |
| Turn-by-turn | `backend/voice/turn_based.py` | `GET` question (text + audio), `POST` answer (WAV → transcript) |
| Storage | `backend/db.py` | SQLite schema + helpers (see `db.md`) |
| Shared Gemini helpers | `backend/gemini.py` | Client, `generate_json`, `generate_text`, resume part, friendly errors |
| Context builders | `backend/context.py` | Rows → text blocks used inside task prompts |
| Catch-up script | `scripts/catch_up.py` | Pastes (or resets) prompts from `agents/*.md` |

### Prompt = persona, task = instructions

Each agent call is `system_instruction = SYSTEM_PROMPT` (pasted by participants: who the agent is and its rules) plus
a `TASK:` message written in code (what to do now) plus a Pydantic `response_schema` (the exact JSON shape). Participants
change behavior by changing one string; the app can rely on the JSON shape regardless.

### Background agents

`orchestrator.run_in_background()` keeps a reference to each task (so it isn't garbage-collected) and every background
coroutine catches its own errors and writes `status='failed'` + a friendly `error`. The frontend polls
`GET /api/search/:id` or `GET /api/jobs/:id` every 2–2.5 s only while status is `searching`, `researching`,
`composing`, or `reviewing`.

## 6. Data model

See `db.md` for tables and status diagrams. Agent I/O schemas live in `backend/models.py`.

## 7. API surface

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Agent status (locked/active), voice mode, question count, models |
| `GET /api/profile` · `POST /api/profile/resume` · `POST /api/profile/sample-resume` · `GET /api/profile/resume` | Resume |
| `POST /api/search` | Start a search with the first message (Summary Agent replies) |
| `GET /api/search/latest` · `GET /api/search/:id` | Search with messages and current-round results |
| `POST /api/search/:id/messages` | Correct the understanding (Summary Agent) |
| `POST /api/search/:id/confirm` | `collecting/failed → searching` (Web Search in background) |
| `POST /api/search/:id/feedback` | `results_ready → searching` (next round) |
| `POST /api/search/:id/save` | `results_ready → saved`; copies chosen results to `saved_jobs` |
| `GET /api/jobs` · `GET/PATCH/DELETE /api/jobs/:id` | Saved jobs; `PATCH` pastes a job description |
| `POST /api/jobs/:id/topics` | Summary Agent lists topics |
| `POST /api/jobs/:id/ratings` | Self-ratings → study plan; `study_status = studying` |
| `PATCH /api/topics/:id` | Topic done / studying |
| `POST /api/jobs/:id/study-done` | `study → done`, `interview → started`, research + compose in background |
| `POST /api/jobs/:id/interviews` | Retake: new session with new questions |
| `GET /api/interviews/:id` | Session, questions, transcripts, reviews |
| `WS /ws/interviews/:id` | Live interview relay (protocol in `voice/live_proxy.py`) |
| `GET /api/interviews/:id/turn/:n` · `POST …/turn/:n/answer` | Turn-by-turn fallback |
| `POST /api/interviews/:id/finish` | `in_progress → reviewing` (Review in background) |
| `POST /api/interviews/:id/retry` | Re-run the failed background step |

## 8. Key trade-offs (with rejected alternatives)

1. **Code-driven orchestration vs. an LLM router / agent framework.** Chose explicit status transitions in
   `orchestrator.py`. A router model deciding "what next" is less predictable, harder to test, and hides the
   multi-agent idea behind framework abstractions. ADK was considered and rejected for the workshop.
2. **Search wide, then rank.** One grounded search returns 0–6 posts — too few to pick "the most relevant". Code
   plans 3–4 plain search angles (no `site:`/`after:` operators, which starve results), runs them in parallel,
   extracts each angle's findings in parallel (JSON, thinking off), cleans in code (real links only, no search/category
   pages, 90-day window, no duplicates or already-shown posts), then one ranking call scores every candidate 0–100;
   code adds small nudges (+5 LinkedIn/Handshake, −10 unknown date) and keeps the top 5. Fewer than 3 left → one
   broadened round. Searching and extracting are separate calls because Gemini 2.5 does not combine Google Search
   with a forced JSON schema.
   - *Rejected:* one search call asking for 5 posts (returned nothing or too few); the URL context tool (~120k tokens
     and ~2 minutes per search); site-restricted queries for LinkedIn/Handshake (Handshake is not indexed).
3. **Server-side Live relay vs. browser → Gemini with ephemeral tokens.** The relay keeps the key on the server and
   lets the server save transcripts directly; cost is one extra hop of latency.
4. **`next_question(n)` tool vs. guessing question boundaries from the transcript.** A tool call is an exact marker,
   so every answer lands on the right question even with follow-ups.
5. **SQLite (stdlib `sqlite3`) vs. PostgreSQL / ORM.** Zero setup in a workshop; schema is readable SQL in `db.py`.
6. **Overall score computed in code.** The model scores four criteria; `RubricScores.overall()` averages them so the
   headline number is consistent.
7. **Live search only (no sample job data).** Real results are the point; variance is handled with "date unknown",
   verified-link filtering, feedback rounds, and the paste-description fallback.

## 9. Risks & unknowns

| Risk | Mitigation |
|---|---|
| Gemini blocks verbatim copies of web pages (`finish_reason = RECITATION`, empty answer) | Every search asks for descriptions in the model's own words; a blocked/empty answer is retried once with a stronger reminder; all-empty → `SearchBlockedError` with a clear message |
| LinkedIn/Handshake pages not public or not indexed | LinkedIn preferred (+5) when it appears; Handshake is login-only, so users paste its descriptions; everything else is `source=other` |
| Expired grounding redirect links (404) and links to search/category pages | Redirects resolved to real URLs or dropped; listing pages blanked → UI shows *Search for post* |
| Missing or truncated job descriptions | `has_description` check (≥200 chars); paste box; interview steps require it |
| Live session > 15 min audio / ~10 min connection | `context_window_compression` (sliding window) + `session_resumption`; relay reconnects up to 5 times |
| Echo makes the interviewer interrupt itself | Headphones hint, browser echo cancellation, turn-by-turn toggle |
| Model returns malformed JSON or skips a question | `generate_json` raises a 502-style error; review raises on missing questions; **Retry** |
| Rate limits / no credits in a full room | Friendly error messages; pre-session checklist in README |
| Live session closes with `1007 audio content type is not supported` | On Gemini 2.5 native audio with function tools, a session whose **first turn is started by text** dies a few seconds in (with or without the candidate speaking), and the `-latest` alias is worse. The relay never injects text: each session starts with a short **spoken cue** (`backend/voice/cues/ready.wav` / `back.wav`, built by `scripts/make_voice_cues.py`), and "start at question N" goes in the session instructions. The Live model is pinned to `…-preview-12-2025`. If a connection still drops, the relay reconnects (up to 3 times), resumes at the first unanswered question, and tells the user if it gives up |
| Interviewer forgets to call `next_question` | Speech is attached to the first unanswered question from the start; each tool response reminds the model to keep calling it |
| Gemini 2.5 model retirement | All model names are env vars |

## 10. Testing strategy

`uv run pytest` — Gemini is always mocked; tests use a temp data directory.

| File | Covers |
|---|---|
| `tests/test_db.py` | Schema, profile upsert, save-jobs copy, review upsert, cascade delete |
| `tests/test_models.py` | Rubric overall score, ratings validation |
| `tests/test_gemini.py` | Fenced JSON parsing, resume part, friendly errors |
| `tests/test_agents.py` | Starter ships with empty prompts; locked errors; whole-page paste detected; every doc prompt is paste-safe; catch-up fills/resets |
| `tests/test_web_search.py` | Search angles, RECITATION retry, blocked-search error, broadening, ranking + nudges, redirect mapping, link/date/duplicate filtering |
| `tests/test_orchestrator.py` | Both flows end to end with mocked agents, failure + retry, locked agents |
| `tests/test_api.py` | Health, upload validation, 423/404/409, job search over HTTP |
| `tests/test_live_proxy.py` | Transcript → question attribution, resume at first unanswered question, spoken-cue start (no injected text), cue audio not mixed with the mic or saved as an answer, tool responses |

**Not automated:** live Gemini calls, real microphone audio, visual styling. Verify these manually before the session
(see README → *Organizer checklist*).

## 11. Rollout

```bash
uv sync --extra dev
uv run pytest
uv run uvicorn main:app --app-dir backend --reload   # http://localhost:8000
```

## 12. Cost (rough, per participant)

A full run is ~25 text calls (each job search round: 4 grounded searches + 4 extractions + 1 ranking, ~25k tokens) plus 15–20 minutes of Live API audio. Check current Gemini
pricing before the session; the Live audio minutes dominate the cost.
