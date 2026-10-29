# ◆ Mentor AI — GDG Brooklyn Coding Jam

**A multimodal AI agent for job searching and mock interviewing.** Mentor AI reads your resume, finds live job posts
that fit you, builds a study plan for the one you pick, interviews you **out loud** as a senior employee of that
company, and grades every answer.

In this Coding Jam you build it **one agent at a time**. The app is already wired up; each agent ships with an empty
prompt. For each agent you learn what it does and how it talks to the others, then paste its prompt into one marked
line of code — and watch that part of the app come alive.

---

## What you'll build

```
                         ┌──────────────────────────────┐
     You ◀──── chat ────▶│   🧭 Summary Agent (Mentor)  │  the only agent that talks to you
     (resume PDF, text)  └──────────────┬───────────────┘
                     confirmed request  │  ▲  results to explain
                                        ▼  │
                         ┌──────────────────────────────┐
                         │   🔎 Web Search Agent         │  live Google Search, in the background
                         └──────────────────────────────┘
                     7 interview questions │
                                        ▼
     You ◀──── voice ───▶┌──────────────────────────────┐
                         │   🎙️ Mock Interview Agent    │  Gemini Live API: real-time voice
                         └──────────────┬───────────────┘
                     question + transcript pairs
                                        ▼
                         ┌──────────────────────────────┐
                         │   📝 Review Agent            │  rubric scores, in the background
                         └──────────────────────────────┘  → back to Mentor → you
```

The agents never call each other directly: `backend/orchestrator.py` moves each flow to its next status and hands one
agent's output to the next. The Summary Agent answers while you wait; the others work in the background while you keep
using the app.

## Features (the prototype)

**1 · Find Jobs**
- Upload your resume (PDF, PNG, JPG, or TXT) — Gemini reads the file directly — or click **Use sample resume**.
- Tell Mentor what you want (role, level, location). It restates it and asks *"Did I get this right?"* until you
  press **Yes, search**.
- The Web Search Agent finds the **5 most relevant posts from the past 3 months** (LinkedIn and Handshake first),
  and Mentor explains why each one fits your resume.
- Not happy? Give feedback and it searches again. Happy? Tick and **save** the posts you like.

**2 · Saved Jobs** — every saved post with its study and interview status.

**3 · Interview Prep** (for one saved job)
- **Know the topics:** Mentor lists what the job expects you to know; you rate yourself 1–5 on each.
- **Study plan:** what to study first vs. review later, with a checkbox per topic. Press **I'm done studying**.
- **Interview research:** the Web Search Agent looks for questions real candidates reported for that company.
- **Mock interview:** Mentor writes **7 questions** (reported + job description + deep-dives on your resume); the
  Mock Interview Agent asks them out loud and transcribes your answers. Live conversation or turn-by-turn.
- **Review:** each answer scored 1–10 on a 4-part rubric, with strengths, what to prepare, and what a senior
  interviewer listens for — plus Mentor's *prepare next* list.

Everything is stored in a local SQLite file (`data/mentor.db`). No accounts, no cloud database.

## The four agents

| Step | Agent | What it does | Runs | Paste into | Guide |
|---|---|---|---|---|---|
| 1 | 🧭 **Summary** | Talks to you; confirms your request; explains results; writes the study plan and the interview; presents the review | Foreground | `backend/agents/summary.py` | [agents/summary_agent.md](agents/summary_agent.md) |
| 2 | 🔎 **Web Search** | Finds job posts and reported interview questions on the live web | Background | `backend/agents/web_search.py` | [agents/web_search_agent.md](agents/web_search_agent.md) |
| 3 | 🎙️ **Mock Interview** | Interviews you by voice as a senior employee; transcribes your answers | Live | `backend/agents/mock_interview.py` | [agents/mock_interview_agent.md](agents/mock_interview_agent.md) |
| 4 | 📝 **Review** | Grades each answer with a rubric and comments like a senior interviewer | Background | `backend/agents/review.py` | [agents/review_agent.md](agents/review_agent.md) |

## Before the session (5 minutes)

1. Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
2. Get a Gemini API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and make sure the project
   has quota/credits (the Live API voice interview uses the most).
3. Bring **headphones** — the interviewer must not hear itself through your speakers.
4. Use Chrome, Edge, Safari, or Firefox and allow microphone access when asked.

## Run it

```bash
uv sync --extra dev
cp .env.example .env            # then put your key in GEMINI_API_KEY
uv run uvicorn main:app --app-dir backend --reload
```

Open **http://localhost:8000**. All four agent chips in the header are grey and locked — that's expected.

## Build it: one agent at a time

For each step:
1. Open the agent's guide in `agents/` (or follow the slide).
2. Copy the prompt from **The prompt** section.
3. Paste it between the triple quotes of `SYSTEM_PROMPT` in the matching `backend/agents/*.py` file and save.
4. The server reloads; within a few seconds the agent's chip turns green and its features unlock.

```python
SYSTEM_PROMPT = """
← paste the prompt here
"""
```

Fell behind? `uv run python scripts/catch_up.py <summary|web_search|mock_interview|review|all>` pastes it for you.

## Project structure

```
mentor_AI/
├── README.md  BRIEF.md  product.md  ui.md  engineering.md  db.md
├── agents/                       # one guide per agent — includes the prompt to paste
├── backend/
│   ├── main.py                   # FastAPI routes + WebSocket + static frontend
│   ├── orchestrator.py           # status transitions; starts background agents
│   ├── agents/                   # summary.py · web_search.py · mock_interview.py · review.py  ← paste slots
│   ├── voice/                    # live_proxy.py (Live API relay) · turn_based.py (fallback)
│   ├── db.py  models.py  gemini.py  context.py  config.py
├── frontend/                     # index.html · style.css · app.js · audio.js (no build step)
├── samples/sample_resume.pdf     # fictional resume for following along
├── scripts/                      # catch_up.py · make_sample_resume.py
├── tests/                        # pytest, Gemini mocked
├── reference/resume-tailor/      # the previous Coding Jam app: same stack, pattern reference
└── .agent/skills/                # agent skills: gemini-api-dev, gemini-live-api-dev, design docs, TDD
```

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn, `uv` |
| AI | `google-genai` SDK — `gemini-2.5-flash` (+ Google Search), `gemini-2.5-flash-native-audio-preview-12-2025` (Live API), `gemini-2.5-flash-preview-tts` |
| Storage | SQLite (Python `sqlite3`) |
| Frontend | Vanilla HTML / CSS / JS, Web Audio API (AudioWorklet), WebSocket |
| Tests | pytest, pytest-asyncio |

All settings (models, question count, voice mode) are in `.env.example`.

## Organizer checklist

- [ ] `uv run pytest` passes.
- [ ] `uv run python scripts/catch_up.py all`, then run both flows end to end with a real key: search → save →
      topics → plan → study done → **live** interview (with headphones) → review. Repeat once in **turn by turn**.
- [ ] `uv run python scripts/catch_up.py all --reset` before publishing — the starter must ship with empty prompts
      (`tests/test_agents.py` checks this).
- [ ] Confirm the default models are still available for the event date (`GEMINI_*` in `.env.example`).

## Privacy

Your resume and interview answers stay in `data/` on your computer (git-ignored) and are sent only to the Gemini API.
Free-tier and paid-tier Gemini API data handling differ — see Google's Gemini API terms.

## Troubleshooting

| Problem | Fix |
|---|---|
| Chip says **Fix the paste** | You copied the whole guide page. Paste only the text inside the prompt box (between the ``` lines) |
| Job search finds nothing | Check the server log for `finish reason`; wait a minute and retry, or try a different role title/location |
| Chip stays grey after pasting | Save the file; the prompt must be between the `"""` quotes; check the server log for a syntax error |
| "API key is missing or invalid" | Put `GEMINI_API_KEY` in `.env` and restart the server |
| "no credits left" / rate limit | Check billing/quota at [ai.studio/projects](https://ai.studio/projects); wait a minute |
| Job has no description | Open the post and paste the description into the job's prep page |
| Interviewer keeps interrupting itself | Use headphones, or switch to **Turn by turn** |
| Live interview won't connect | Switch to **Turn by turn**; check `GEMINI_LIVE_MODEL` is available to your key |
| Start over | Stop the server and delete `data/` |
