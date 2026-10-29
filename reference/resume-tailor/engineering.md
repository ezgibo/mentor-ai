# Resume Tailor — Engineering Design Doc

**Author:** Senior Staff Engineer  
**Status:** Ready for Review (v1.0)  
**Last updated:** October 16, 2026  
**Reviewers:** Engineering Team  

---

## 1. Summary

Resume Tailor is a focused, single-screen web application that takes raw resume bullets and a target job description, analyzes keyword overlap and skill requirements, and generates 3–5 high-impact, tailored resume bullets using Google Gemini AI. Following the proven reference pattern from `reference/moodjar-example/`, the system consists of a lightweight Python FastAPI backend powered by the official `google-genai` SDK (targeting `gemini-2.5-flash` with structured Pydantic JSON output), serving a high-performance Vanilla HTML/CSS/JavaScript frontend directly as static files. The entire application runs out of a single process managed by `uv`.

## 2. Assumptions

The product-level constraints this doc assumes:

- **Target scale:** Prototyping and workshop build (<500 DAU, single-node deployment).
- **Latency budget:** End-to-end p95 response time < 3.0s (including Gemini API inference).
- **Platform:** Cross-platform responsive web (modern Evergreen browsers: Chrome, Safari, Firefox, Edge).
- **Runtime & Tooling:** Python 3.12+ managed via `uv`, with dependencies pinned in `pyproject.toml`.
- **Cost ceiling:** Under $0.005 per tailoring request on Google Gemini Flash tier.
- **Out of scope:** User authentication, remote database storage, file uploads, PDF generation, multi-region clustering.

## 3. Goals & non-goals

### Goals (v1)
- Accept plain text inputs for both resume bullets and job posting descriptions with input validation and character safety limits (max 10,000 chars each).
- Invoke Gemini AI (`gemini-2.5-flash`) via `google-genai` using structured JSON output to return 3–5 bullets following the X-Y-Z formula with extracted keyword badges.
- Deliver an end-to-end latency of p95 < 3.0s and p99 < 5.0s on standard broadband connections.
- Serve the static frontend directly from FastAPI so the entire app runs with a single command (`uv run uvicorn main:app`).
- Provide an automated test suite via `pytest` adhering to the required `test-driven-dev` discipline.

### Non-goals (v1)
- **No PDF or DOCX file parsing:** Text extraction from binary formats introduces parsing failures, native C dependencies, and security vulnerabilities. Text paste is resilient and universal.
- **No persistent database:** Resumes contain sensitive PII. Storing them requires auth, encryption at rest, GDPR compliance, and database maintenance. All state is strictly ephemeral and in-memory.
- **No user accounts or authentication:** Zero-login architecture ensures zero onboarding drop-off.
- **No background task queues (Celery/Redis):** Gemini Flash responds synchronously in 1.5–2s. A queuing system adds operational overhead without benefit.

## 4. Architecture

```mermaid
flowchart LR
    subgraph Browser ["Frontend (Browser)"]
        UI[Vanilla HTML5 / CSS3 / ES6]
        Clipboard[Navigator Clipboard API]
    end

    subgraph Server ["FastAPI Server (uvicorn)"]
        Static[Static File Mount /]
        API[API Endpoint POST /api/tailor]
        PromptService[Prompt & Validation Service]
    end

    subgraph AI ["Google Gemini AI"]
        Gemini[gemini-2.5-flash<br/>Structured JSON]
    end

    UI -->|GET /| Static
    UI -->|POST /api/tailor<br/>{resume_text, job_text}| API
    API --> PromptService
    PromptService -->|Structured Call| Gemini
    Gemini -->|JSON Bullet List| PromptService
    PromptService -->|TailorResponse| UI
    UI -->|1-Click Copy| Clipboard
```

### What's here:
- **FastAPI Application (`backend/main.py`):** Handles static file serving and exposes the single POST API endpoint.
- **AI Prompt & Engine (`backend/tailor_service.py` / `prompts.py`):** Formulates few-shot prompt instructions, validates inputs, and invokes Gemini via `google.genai.Client`.
- **Vanilla Frontend (`frontend/index.html`, `style.css`, `app.js`):** Lightweight client delivering instant UI rendering, animations, and clipboard integration without build steps or Node.js toolchains.
- **Project & Environment Manager (`pyproject.toml`):** Managed seamlessly via `uv`.

### What's deliberately NOT here:
- **No Node.js / npm build step:** The frontend uses native modern JavaScript (ES Modules, Fetch, Clipboard API) and vanilla CSS with variables, eliminating `node_modules` completely.
- **No SQL/NoSQL Database:** Eliminates ORM migrations, connection pooling, and credential storage.
- **No Redis / Celery broker:** Synchronous request-response cycle is fast enough for Gemini Flash.
- **No Docker requirement for local dev:** Runs directly via `uv run uvicorn main:app --reload`.

## 5. Key components

### 1. API Server (`backend/main.py`)
- **Responsibility:** Exposes the REST API, applies CORS/security headers, serves static assets, and coordinates error handling.
- **Tech choice:** FastAPI + Uvicorn.
- **Why this choice:** Follows the project reference pattern, provides automatic OpenAPI documentation, high async throughput, and native Pydantic validation.
- **Interface:** `POST /api/tailor`, `GET /health`, `GET /` (serves `frontend/index.html`).

### 2. Tailor Service (`backend/tailor_service.py`)
- **Responsibility:** Validates text lengths, builds the tailoring prompt with X-Y-Z formula instructions, communicates with Gemini via `google-genai`, and parses the structured response.
- **Tech choice:** `google-genai` SDK with `gemini-2.5-flash`.
- **Why this choice:** Official Google SDK supporting native Pydantic structured output (`response_mime_type="application/json"`) with sub-2s generation latency.
- **Interface:** `tailor_bullets(resume_text: str, job_text: str) -> TailorResponse`.

### 3. Prompt Engine (`backend/prompts.py`)
- **Responsibility:** Enforces the prompt engineering contract: action verbs, Google X-Y-Z formula, truthful alignment to user's raw experience, and keyword extraction from the job description.
- **Tech choice:** Pure Python constant templates with structured system instructions.
- **Why this choice:** Zero dependencies, easy to test, version-controlled alongside code.

### 4. Client Controller (`frontend/app.js`)
- **Responsibility:** Coordinates input capture, validation, sample prefilling, async API fetching, DOM rendering of tailored cards, and clipboard copying.
- **Tech choice:** Modern Vanilla JavaScript (ES6+).
- **Why this choice:** Zero runtime dependencies, instant execution, ultra-fast load time (<50ms).

## 6. Data model

The data model uses Pydantic v2 schemas in Python and clean JSON structures over the wire.

```python
# backend/models.py
from pydantic import BaseModel, Field
from typing import List

class TailorRequest(BaseModel):
    resume_text: str = Field(
        ..., 
        min_length=10, 
        max_length=10000, 
        description="Raw resume bullets or experience summary"
    )
    job_text: str = Field(
        ..., 
        min_length=10, 
        max_length=10000, 
        description="Target job description and requirements"
    )

class TailoredBullet(BaseModel):
    original_bullet: str = Field(
        default="", 
        description="The source bullet point or topic addressed"
    )
    tailored_bullet: str = Field(
        ..., 
        description="Upgraded bullet using action verbs and quantified impact"
    )
    matched_keywords: List[str] = Field(
        default_factory=list, 
        description="Specific skills or keywords aligned with the job posting"
    )
    impact_metric_type: str = Field(
        default="Quantified Result", 
        description="Type of metric framed (e.g., Performance, Scale, Efficiency)"
    )

class TailorResponse(BaseModel):
    bullets: List[TailoredBullet] = Field(
        ..., 
        min_length=1, 
        max_length=5, 
        description="List of tailored resume bullets"
    )
    summary_insight: str = Field(
        default="", 
        description="Brief 1-sentence note on how the bullets were aligned"
    )
```

## 7. API surface

### `POST /api/tailor`

- **Description:** Takes resume text and job posting description, generates 3–5 tailored bullet points.
- **Request Body (`application/json`):**
  ```json
  {
    "resume_text": "Built backend APIs using Python. Made database queries faster.",
    "job_text": "Looking for a Backend Engineer with FastAPI, PostgreSQL, and high-concurrency optimization experience."
  }
  ```
- **Response Body (`application/json`):**
  ```json
  {
    "bullets": [
      {
        "original_bullet": "Built backend APIs using Python.",
        "tailored_bullet": "Architected high-throughput backend services using FastAPI and Python, handling 15,000+ daily requests with 99.9% uptime.",
        "matched_keywords": ["FastAPI", "High-Concurrency", "Python"],
        "impact_metric_type": "Reliability & Scale"
      },
      {
        "original_bullet": "Made database queries faster.",
        "tailored_bullet": "Optimized complex PostgreSQL database queries and indexes, reducing p95 query latency by 45% across critical customer endpoints.",
        "matched_keywords": ["PostgreSQL", "Query Optimization", "Latency"],
        "impact_metric_type": "Performance"
      }
    ],
    "summary_insight": "Aligned backend experience with required FastAPI and PostgreSQL concurrency performance."
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: Missing or invalid input payload (<10 chars or empty).
  - `422 Unprocessable Entity`: Exceeded maximum character limits (10,000 chars).
  - `500 Internal Server Error`: Gemini API communication failure or model timeout.
  - `503 Service Unavailable`: Missing `GEMINI_API_KEY` configuration.
- **Latency Budget:** Total roundtrip p95 < 3.0s (FastAPI overhead < 15ms, Gemini Flash generation ~ 1.8s).

### `GET /api/health`
- **Response:** `{"status": "ok", "model": "gemini-2.5-flash"}`

---

## 8. Key trade-offs (with rejected alternatives)

### Decision 1: Direct Text Paste vs. PDF/Docx File Parsing
- **Chose:** Direct text area paste.
- **Considered:** `pdfplumber`, `PyPDF2`, or OCR parsing.
- **Why we picked this:** Parsing PDFs introduces font-encoding bugs, multi-column layout garbling, heavy binary dependencies, and file size upload limits. Direct paste gives the user complete transparency and zero parsing failures.

### Decision 2: Gemini 2.5 Flash vs. Gemini Pro
- **Chose:** `gemini-2.5-flash`.
- **Considered:** `gemini-1.5-pro` / `gemini-2.5-pro`.
- **Why we picked this:** Flash has a p95 latency under 2 seconds, which is essential to achieve the "instant magical upgrade" feeling. Pro models take 5–8 seconds, which makes the app feel sluggish, and Flash is more than capable of high-quality resume bullet restructuring.

### Decision 3: Vanilla JS/CSS vs. React/Vite/Next.js
- **Chose:** Vanilla HTML5, modern CSS3, and ES6 JavaScript.
- **Considered:** Vite + React + TailwindCSS.
- **Why we picked this:** Eliminates Node.js runtime and `package.json` dependencies, avoiding version conflicts, build steps, and asset bundlers. The entire frontend is served directly by FastAPI as static assets.

---

## 9. Risks & unknowns

- **Model Hallucination of False Experience:**
  - *Likelihood:* Medium.
  - *Mitigation:* System prompt strictly enforces: *"Do not invent new companies, degrees, or unmentioned tools. Enhance phrasing and quantify impact using brackets like [X%] if metrics are not specified."*
- **Gemini API Rate Limiting / Quota Exhaustion:**
  - *Likelihood:* Low for workshop scale.
  - *Mitigation:* Graceful error handling in FastAPI returning friendly error JSON with HTTP 429/500 rather than crashing.
- **Missing API Key on Initial Run:**
  - *Likelihood:* Medium.
  - *Mitigation:* Explicit server startup check that warns immediately if `GEMINI_API_KEY` is not present in `.env`, providing actionable instructions.

---

## 10. Testing strategy

This testing strategy is the formal specification consumed by the **`test-driven-dev`** skill. All tests will be implemented in Python using **`pytest`** and **`httpx`** (FastAPI TestClient) under `tests/`.

### Unit tests (must have):
1. **`test_tailor_request_validation` (`tests/test_models.py`):**
   - Validates that `TailorRequest` accepts valid text and rejects empty strings or strings shorter than 10 characters with a `ValidationError`.
   - Validates that text exceeding 10,000 characters is rejected.
2. **`test_prompt_construction` (`tests/test_prompts.py`):**
   - Asserts that `build_tailor_prompt(resume_text, job_text)` correctly embeds both user inputs into the prompt template without escaping anomalies.
   - Verifies the inclusion of X-Y-Z formula instructions and strict anti-hallucination rules.
3. **`test_structured_output_parsing` (`tests/test_services.py`):**
   - Feeds a mock Gemini JSON response string into the parser and asserts that it cleanly constructs a valid `TailorResponse` object with expected fields (`bullets`, `matched_keywords`, `impact_metric_type`).

### Integration tests (one per major flow):
1. **`test_api_tailor_success_flow` (`tests/test_api.py`):**
   - Mocks the Gemini SDK response and executes a full HTTP `POST /api/tailor` call via FastAPI TestClient.
   - Verifies status code `200 OK`, valid JSON response structure matching `TailorResponse`, and non-empty bullet list.
2. **`test_api_validation_error_flow` (`tests/test_api.py`):**
   - Executes `POST /api/tailor` with an empty payload or missing fields.
   - Verifies status code `422 Unprocessable Entity` with clean error details.
3. **`test_health_check_endpoint` (`tests/test_api.py`):**
   - Executes `GET /api/health` and verifies status code `200 OK` and `status == "ok"`.

### Deliberately not tested (and why):
- **Live Gemini API calls in CI/test runs:** Testing live LLM generation incurs network costs, latency, and non-deterministic text variation. Gemini client calls are mocked using fixtures.
- **CSS styling and micro-animations:** Visual appearance and transitions are verified through browser inspection rather than fragile brittle unit tests.
- **System clipboard API:** The browser `navigator.clipboard` is an external browser API and will be manually verified in the client.

### Stack defaults:
- Framework: `pytest`
- Async client: `httpx`
- Directory: `tests/`
- Command: `uv run pytest`

---

## 11. Rollout & monitoring

- **Local Execution:** Managed via `uv`:
  ```bash
  uv run pytest                 # Run automated test suite
  uv run uvicorn main:app --reload  # Start server on http://localhost:8000
  ```
- **Monitoring Signals:**
  - API status code distribution (200 vs 4xx vs 5xx).
  - Model latency histogram (monitoring p95 under 3.0s).
  - Client copy event tracking (via browser console logs or optional telemetry).

## 12. Cost & capacity

- **Model:** `gemini-2.5-flash`
- **Cost per generation:**
  - Input tokens: ~800 tokens (prompt + resume + job description) @ $0.075 / 1M tokens ≈ $0.00006
  - Output tokens: ~350 tokens @ $0.30 / 1M tokens ≈ $0.00010
  - Total per request: **~$0.00016** (approx. 6,000 tailored resumes per $1.00).
- **Workshop Budget (500 runs):** Less than $0.10 total.
- **Scaling ceiling:** A single Uvicorn instance handles ~200 concurrent async requests before needing gunicorn workers.

## 13. Open questions

- [ ] Should the Gemini client fallback to `gemini-1.5-flash` if `gemini-2.5-flash` is unavailable in the user's Google Cloud project quota? *(Owner: Eng Lead)*
- [ ] Should we provide a secondary "Bullet Tone" selector (e.g., "Leadership", "Technical Depth", "Startup/Scrappy") in v1.1? *(Owner: Product/Eng)*

## 14. Out of scope (will not do)

- **No file upload endpoints:** No multipart/form-data endpoints or file storage.
- **No authentication / database tables:** No user sessions, passwords, or stored resumes.
- **No WebSocket connection:** Standard HTTP POST is simpler, cacheable, and fully sufficient for sub-3s response times.
- **No PDF generator engine:** Output is plain text optimized for clipboard transfer.
