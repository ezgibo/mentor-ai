# Mentor AI

Mentor AI is a local web application for job discovery and interview preparation. It brings resume context, job research, study planning, spoken practice, and answer feedback into one workflow. A FastAPI backend coordinates four specialized Gemini agents, while a browser interface handles chat, saved jobs, preparation tasks, and audio interviews.

## Key features

- Upload a resume as PDF, PNG, JPG, JPEG, or TXT, or use the included fictional sample.
- Confirm role, level, and location preferences before starting a job search.
- Search public job postings with Google Search grounding, rank matches, refine results with feedback, and save selected jobs.
- Identify preparation topics, record self-assessments, and create a study plan for a saved job.
- Research publicly reported interview questions and prepare a job-specific mock interview.
- Practice through the Gemini Live API or a turn-by-turn voice fallback.
- Review answers using accuracy, depth, structure, and communication scores, with strengths and suggested improvements.
- Store profiles, saved jobs, preparation progress, interview transcripts, and reviews in local SQLite storage.

Search results, study content, and interview feedback depend on model responses and available sources. These features do not establish job suitability, guarantee current openings, or predict hiring outcomes.

## Technical approach

The Summary Agent handles user-facing conversation and explains results. The Web Search Agent gathers job postings and interview reports. The Mock Interview Agent conducts spoken practice, and the Review Agent evaluates answer transcripts.

`backend/orchestrator.py` coordinates state transitions and background work rather than having agents call each other directly. Pydantic models define structured payloads. FastAPI provides REST endpoints, serves the static frontend, and relays live interview audio over WebSocket. SQLite stores application state.

The four agent prompts are already populated in this checkout.

## Technologies

| Area | Technologies |
| --- | --- |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| AI | Google Gen AI SDK, Gemini, Google Search grounding, Gemini Live API |
| Voice | Live audio, text-to-speech, transcription, Web Audio API, WebSocket |
| Storage | SQLite |
| Frontend | HTML, CSS, JavaScript |
| Dependencies and tests | uv, pytest, pytest-asyncio |

## Installation

Requirements: Python 3.11 or later, `uv`, and access to the configured Gemini models with sufficient quota. Voice interviews require a microphone and browser audio permissions.

```bash
git clone https://github.com/ezgibo/mentor-ai.git
cd mentor-ai
uv sync --extra dev
cp .env.example .env
```

Set `GEMINI_API_KEY` in your local `.env` file. Keep this file out of Git. Review `.env.example` for model, voice, and storage configuration. Model identifiers are configurable; confirm their availability in your own account before using the application.

Start the server:

```bash
uv run uvicorn main:app --app-dir backend --reload
```

Open `http://localhost:8000`. `run.sh` provides the same local startup workflow. On macOS, `Başlat.command` also opens the browser.

## Usage

1. Upload a resume or select the fictional sample.
2. Describe the jobs you want and confirm the application's interpretation.
3. Review search results, provide feedback if needed, and save relevant postings.
4. Open a saved job, review its preparation topics, rate your familiarity, and work through the study plan.
5. Start a mock interview. Use headphones for live audio or select turn-by-turn mode through `VOICE_MODE=turn` in `.env` and restart the server.
6. Review the transcript-based scores and preparation suggestions after the interview.

The default interview length is seven questions, configurable from five to ten. Uploaded resumes are limited to 10 MB.

## Project structure

```text
backend/                 API, orchestration, agents, models, and database access
backend/voice/           Live interview relay and turn-by-turn audio
frontend/                Browser interface and audio handling
agents/                  Agent guides and prompt references
samples/                 Fictional sample resume
scripts/                 Local setup and workshop utility scripts
tests/                   Application tests
reference/resume-tailor/ Related workshop reference application
.agent/skills/           Bundled development guidance and third-party notices
```

Product, engineering, database, and interface notes remain in the repository. Workshop utility scripts can fill or reset agent prompts; resetting them disables the corresponding features.

## Validation

Run the existing test suite with:

```bash
uv run pytest -q
```

During portfolio preparation, the local suite returned **74 passed and 7 failed**. The seven failures assert the original starter's empty-prompt or locked-agent behavior, including prompt-reset comparisons. This checkout has populated prompts, so those expectations differ from its current state. Application code and tests were preserved.

This result does not verify live Gemini calls, current search quality, microphone behavior, or a complete interview session. No end-to-end success or performance benchmark is claimed.

## Data and privacy

The default `data/` directory contains the SQLite database and uploaded resumes. It is excluded from version control, along with environment files, caches, logs, and local runtime artifacts. If `MENTOR_DATA_DIR` points elsewhere, keep that directory outside Git as well.

Resume content, conversation context, and interview audio or transcripts are processed by the configured AI services when those features run. Local storage does not mean offline processing. The included sample resume is explicitly fictional.

The application has no account system and is intended for local use. Review deployment and access controls before making a server reachable by others.

## Source and licensing

This repository retains the Git history of the [Mentor AI Coding Jam starter](https://github.com/harrisonahn1129/Mentor_AI), along with its workshop materials, reference application, and bundled third-party notices. The existing source remote is preserved.

The bundled Gemini skills include an [Apache 2.0 license](.agent/skills/gemini-skills/LICENSE). That license applies to the corresponding bundled material. No root project license was present, and this repository does not assign a new license to the application or claim exclusive authorship.
