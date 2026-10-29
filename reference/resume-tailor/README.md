# Resume Tailor — Reference App

The previous GDG Brooklyn Coding Jam project, kept here as the **pattern reference** for Mentor AI.
It is a complete, single-call Gemini app: paste resume bullets + a job post → get 3–5 tailored bullets.

Mentor AI reuses these patterns (look here first when changing the starter):

| Pattern | Where |
|---|---|
| Gemini client setup (API key or Vertex AI) | `backend/tailor_service.py` → `create_gemini_client()` |
| Prompts kept in their own module | `backend/prompts.py` |
| Structured JSON output + Pydantic validation | `backend/tailor_service.py`, `backend/models.py` |
| FastAPI serving the vanilla frontend | `backend/main.py` |
| Tests with Gemini mocked | `tests/` |

Design docs: `BRIEF.md` → `product.md`, `ui.md`, `engineering.md`.

## Run it

```bash
cd reference/resume-tailor
uv sync --extra dev
cp .env.example .env            # add GEMINI_API_KEY
uv run pytest
uv run uvicorn main:app --app-dir backend --reload
```
