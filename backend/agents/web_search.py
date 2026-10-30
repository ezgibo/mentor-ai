"""Web Search Agent — searches the live web with Google Search grounding.

Two jobs, both run in the background:
  1. find_jobs: the 5 most relevant job posts from the past 3 months.
  2. find_interview_reports: interview questions candidates reported for a saved job.

find_jobs pipeline (code decides the steps; Gemini searches and judges):
  1. Plan     build 3-4 search angles from the confirmed request              (code)
  2. Search   one grounded Google Search call per angle, in parallel           (Gemini + Google Search)
  3. Extract  one structuring call per angle, in parallel → candidate posts   (Gemini, JSON)
  4. Clean    real links only, date window, no duplicates / already-shown      (code)
  5. Rank     score every candidate 0-100 against the request; keep the top 5  (Gemini, JSON + code boosts)
  6. Broaden  fewer than 3 left? search once more with a wider level/location  (code)

Gemini refuses to copy web pages word for word (finish reason RECITATION), so every search asks
for descriptions in the model's own words and retries once with a stronger reminder.
"""

import asyncio
import logging
import re
from datetime import date
from typing import Optional

import httpx
from google.genai import types

import config
import gemini
from context import describe_job, describe_preferences, lookback_cutoff, today
from models import FoundJobs, InterviewResearch, JobRanking

log = logging.getLogger("mentor.web_search")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ STEP 2 — Paste the Web Search Agent prompt between the triple quotes. ║
# ║ Copy it from agents/web_search_agent.md → "The prompt".               ║
# ╚════════════════════════════════════════════════════════════════════════╝
SYSTEM_PROMPT = """
You are the Web Search Agent of Mentor AI. You work in the background for the Summary Agent, which talks to the user. You search the live web with Google Search and report only what you actually find.

Finding job posts:
- Search for open postings that match the user's role, level, and location. LinkedIn postings are preferred when they appear. Handshake postings are usually behind a login, so include them only when a public page shows up. Company career pages and public job boards are fine; report which site each post is on.
- Only use pages that are publicly visible. Never try to log in or get around a login wall.
- Prefer posts published inside the date window you are given. If a post does not show its date, report the date as unknown; never guess a date.
- Skip posts that are closed, duplicated, or already shown to the user.
- Describe every post in your own words: summarize its responsibilities and requirements. Never copy text from a web page word for word; verbatim copies are blocked and the whole answer is lost.

Ranking job posts:
- Judge fit honestly: role and level, location and work mode, the user's must-haves and deal-breakers, their feedback, and overlap with the strengths in their resume. A well-known company is not a better fit by itself.

Researching interview questions:
- Look for interview questions that candidates reported for the specific company and role: public interview reviews, forums, and blog posts.
- Only report questions that a source actually says were asked. If you find nothing reliable, say so; never make questions up.

Always:
- Every URL you give must come from your search results. Never build or guess a URL.
- Follow the TASK instructions in each request exactly.
"""

# Search only — URL context made each search ~120k tokens and ~2 minutes for little gain.
SEARCH_TOOLS = [types.Tool(google_search=types.GoogleSearch())]

PARAPHRASE_RULE = (
    "Write everything in your own words. Never quote or copy text from web pages: "
    "verbatim copies are blocked and the whole answer is lost."
)

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+")
REDIRECT_MARKER = "grounding-api-redirect"
MIN_RESULTS = 3
MAX_ANGLES = 4
POSTS_PER_ANGLE = 6

# Searching needs some reasoning; extracting and ranking are formatting jobs, so thinking is off.
SEARCH_THINKING_BUDGET = 1024
EXTRACT_THINKING_BUDGET = 0

# Search/listing pages are not a posting — a link to one is blanked (the UI offers "Search for post").
LISTING_URL = re.compile(r"/q-|[?&](q|keywords|query)=|/search\b|/jobs/?$|/jobs\.html|/jobs/[a-z-]+/[a-z-]+/?$|/entry-level/?$", re.I)

# Small, explainable nudges on top of the model's fit score.
SOURCE_BONUS = {"linkedin": 5, "handshake": 5}
UNKNOWN_DATE_PENALTY = 10


class SearchBlockedError(gemini.UserFacingError):
    """Every grounded search came back empty (blocked or no results)."""


# ============================================================
# Job search
# ============================================================

async def find_jobs(preferences: dict, feedback: list[str], already_shown: list[dict]) -> tuple[list[dict], str]:
    """Return (up to JOBS_PER_ROUND ranked posts, a note for the user — empty if nothing to say)."""
    jobs = await _search_round(preferences, feedback, already_shown, broaden=False)
    note = ""
    if len(jobs) < MIN_RESULTS:
        log.info("Only %d posts found; broadening the search once", len(jobs))
        wider = await _search_round(preferences, feedback, already_shown + jobs, broaden=True)
        if wider:
            note = "I found only a few exact matches, so I also searched a slightly wider level and location."
        jobs += wider
    ranked = await rank_jobs(preferences, feedback, jobs)
    return ranked[: config.JOBS_PER_ROUND], note


async def _search_round(preferences: dict, feedback: list[str], already_shown: list[dict], broaden: bool) -> list[dict]:
    angles = search_angles(preferences, broaden)
    results = await asyncio.gather(
        *(grounded_search(angle_task(angle, preferences, feedback, already_shown)) for angle in angles),
        return_exceptions=True,
    )
    found = [(angle, result) for angle, result in zip(angles, results)
             if not isinstance(result, Exception) and result[0].strip()]
    for angle, result in zip(angles, results):
        if isinstance(result, Exception):
            log.warning("Search angle %r failed: %s", angle, result)
    if not found:
        if broaden:
            return []
        raise SearchBlockedError(
            "Google Search returned nothing for every search (blocked or empty). Wait a minute and try again."
        )

    extracted = await asyncio.gather(*(extract_jobs(text, sources) for _, (text, sources) in found))
    jobs = [job for batch in extracted for job in batch]
    findings = "\n".join(text for _, (text, _) in found)
    sources = [s for _, (_, angle_sources) in found for s in angle_sources]
    resolved = await normalize_links(jobs, sources)
    allowed_urls = set(URL_PATTERN.findall(findings)) | {s["url"] for s in sources} | resolved
    return clean_jobs(jobs, allowed_urls, already_shown)


async def extract_jobs(findings: str, sources: list[dict]) -> list[dict]:
    """Turn one search angle's findings into candidate posts (JSON)."""
    structure_task = f"""TASK: EXTRACT CANDIDATE JOB POSTS
Convert the findings below into JSON: one entry per distinct posting.
- Use only facts from the findings. Never invent a URL: set `url` to a link that appears in the
  findings or the SOURCES list, otherwise "".
- `url` must be the page of that specific posting. If the only link is a search results or job
  category page, set `url` to "".
- `source` is "linkedin", "handshake", or "other" (based on the posting's site).
- `posted_date` is YYYY-MM-DD, or "unknown".
- `job_description` summarizes the responsibilities and requirements in your own words.

FINDINGS:
{findings}

SOURCES:
{format_sources(sources)}"""
    structured = await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.text_part(structure_task)],
        schema=FoundJobs,
        temperature=0.0,
        thinking_budget=EXTRACT_THINKING_BUDGET,
    )
    return [job.model_dump() for job in structured.jobs]


def search_angles(preferences: dict, broaden: bool = False) -> list[str]:
    """3-4 plain search angles built from the request. No site:/after: operators — they starve results."""
    roles = [r for r in preferences.get("target_roles") or [] if r.strip()] or ["software engineer"]
    levels = [l for l in preferences.get("levels") or [] if l.strip()] or [""]
    locations = [l for l in preferences.get("locations") or [] if l.strip()] or [""]
    level, location = levels[0], locations[0]
    if broaden:
        level = "entry-level, junior, or associate"
        location = f"{location} area or remote" if location else "remote"

    def angle(level: str, role: str, location: str, suffix: str = "") -> str:
        where = f"in {location}" if location else ""
        return re.sub(r"\s+", " ", f"{level} {role} jobs {where} {suffix}").strip()

    angles = [angle(level, role, location) for role in roles[:2]]
    angles.append(angle(level, roles[0], location, "on LinkedIn"))
    if len(levels) > 1 and not broaden:
        angles.append(angle(levels[1], roles[0], location))
    if len(locations) > 1 and not broaden:
        angles.append(angle(level, roles[0], locations[1]))
    return list(dict.fromkeys(angles))[:MAX_ANGLES]


def angle_task(angle: str, preferences: dict, feedback: list[str], already_shown: list[dict]) -> str:
    shown = "\n".join(f"- {j['title']} at {j['company']}" for j in already_shown) or "- none"
    notes = "\n".join(f"- {f}" for f in feedback) or "- none yet"
    return f"""TASK: SEARCH FOR JOB POSTS
Search focus: {angle}
Today is {today().isoformat()}. Prefer posts published on or after {lookback_cutoff().isoformat()}.

The user's confirmed request:
{describe_preferences(preferences)}

User feedback on earlier results (follow it):
{notes}

Skip these posts (already shown):
{shown}

List up to {POSTS_PER_ANGLE} open postings that match. For each write: title, company, location,
level, posted date (or "unknown"), the posting URL, the site it is on, and 6-10 sentences in your
own words summarizing the responsibilities and the requirements (skills, years, degree).
{PARAPHRASE_RULE}"""


async def rank_jobs(preferences: dict, feedback: list[str], jobs: list[dict]) -> list[dict]:
    """Score every candidate 0-100 (model), add small code boosts, and sort best first."""
    if not jobs:
        return []
    listing = "\n\n".join(
        f"### Candidate {i}\n{describe_job(job, include_description=False)}\nSource: {job.get('source')}\n"
        f"Summary: {job.get('job_description') or ''}"
        for i, job in enumerate(jobs, start=1)
    )
    task = f"""TASK: RANK CANDIDATE JOB POSTS
Score EVERY candidate (use its number as `index`) from 0 to 100 for how well it fits this user:
role and level match, location and work mode, the user's must-haves and deal-breakers, the
feedback, and overlap with the resume strengths. 90+ = excellent fit, 50 = partial, under 30 = poor.

The user's confirmed request:
{describe_preferences(preferences)}

Feedback: {'; '.join(feedback) or 'none'}

{listing}"""
    ranking = await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.text_part(task)],
        schema=JobRanking,
        temperature=0.0,
        thinking_budget=EXTRACT_THINKING_BUDGET,
    )
    scores = {s.index: s.fit_score for s in ranking.scores}
    for i, job in enumerate(jobs, start=1):
        job["fit_score"] = adjusted_score(scores.get(i, 0), job)
    return sorted(jobs, key=lambda j: j["fit_score"], reverse=True)


def adjusted_score(score: int, job: dict) -> int:
    score += SOURCE_BONUS.get(job.get("source") or "", 0)
    if not job.get("posted_date") or job["posted_date"] == "unknown":
        score -= UNKNOWN_DATE_PENALTY
    return max(0, min(100, score))


# ============================================================
# Interview research
# ============================================================

async def find_interview_reports(job: dict) -> dict:
    """Search for interview questions candidates reported for this company and role."""
    search_task = f"""TASK: FIND REPORTED INTERVIEW QUESTIONS
Find interview questions that candidates reported for this company and role (or the closest
similar role at the same company). Look at public interview reviews, forums, and blog posts.
Also note anything reported about the interview process (rounds, format).

The job:
{describe_job(job, include_description=False)}

For each question write the question (short, in plain words), the URL where it was reported,
the page title, and context (round, date) if known. If nothing reliable is found, say so — do not
make questions up. Describe the process notes in your own words."""

    findings, sources = await grounded_search(search_task)
    if not findings.strip():
        return {"questions": [], "process_notes": "", "search_notes": "Search returned nothing."}

    structure_task = f"""TASK: STRUCTURE THE INTERVIEW RESEARCH
Convert the findings below into JSON. Only include questions that the findings say were reported
by candidates. Copy each `source_url` from the findings or the SOURCES list; never invent a URL.
Return an empty `questions` list if none were found.

FINDINGS:
{findings}

SOURCES:
{format_sources(sources)}"""
    structured = await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.text_part(structure_task)],
        schema=InterviewResearch,
        temperature=0.0,
        thinking_budget=EXTRACT_THINKING_BUDGET,
    )
    research = structured.model_dump()
    by_redirect = {s["redirect"]: s["url"] for s in sources if s.get("redirect")}
    allowed_urls = set(URL_PATTERN.findall(findings)) | {s["url"] for s in sources}
    for question in research["questions"]:
        url = by_redirect.get(question["source_url"], question["source_url"])
        question["source_url"] = url if url in allowed_urls or url in by_redirect.values() else ""
    return research


# ============================================================
# Helpers (unit tested)
# ============================================================

async def grounded_search(task: str) -> tuple[str, list[dict]]:
    """One Google Search grounded call. Retries once if Gemini blocks it (RECITATION) or returns nothing."""
    for attempt in range(2):
        prompt = task if attempt == 0 else f"{task}\n\nIMPORTANT: {PARAPHRASE_RULE} Keep each summary short."
        response = await gemini.generate_text(
            system_prompt=SYSTEM_PROMPT,
            contents=[gemini.text_part(prompt)],
            tools=SEARCH_TOOLS,
            temperature=0.2,
            thinking_budget=SEARCH_THINKING_BUDGET,
        )
        reason = finish_reason(response)
        text = response.text or ""
        if text.strip() and reason != "RECITATION":
            return text, await resolve_sources(grounding_sources(response))
        log.warning("Grounded search attempt %d returned no text (finish reason %s)", attempt + 1, reason)
    return "", []


def finish_reason(response: types.GenerateContentResponse) -> str:
    candidates = response.candidates or []
    reason = candidates[0].finish_reason if candidates else None
    return getattr(reason, "name", str(reason or ""))


def grounding_sources(response: types.GenerateContentResponse) -> list[dict]:
    """Pull the web sources Google Search actually returned out of the grounding metadata."""
    sources = []
    for candidate in response.candidates or []:
        metadata = candidate.grounding_metadata
        for chunk in (metadata.grounding_chunks or []) if metadata else []:
            if chunk.web and chunk.web.uri:
                sources.append({"title": chunk.web.title or "", "url": chunk.web.uri})
    return sources


async def resolve_url(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Grounding links are Google redirect URLs; read one hop to get the real page URL."""
    try:
        response = await client.get(url, follow_redirects=False)
        return response.headers.get("location")
    except httpx.HTTPError:
        return None


async def resolve_sources(sources: list[dict]) -> list[dict]:
    """Replace redirect URLs with real ones, keeping the redirect so model-written links can be mapped."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        async def resolve(source: dict) -> dict:
            if REDIRECT_MARKER not in source["url"]:
                return source
            real = await resolve_url(client, source["url"])
            return {**source, "url": real, "redirect": source["url"]} if real else source

        return list(await asyncio.gather(*(resolve(s) for s in sources)))


async def normalize_links(jobs: list[dict], sources: list[dict]) -> set[str]:
    """Swap redirect links in job posts for real page URLs. Returns the real URLs it resolved."""
    by_redirect = {s["redirect"]: s["url"] for s in sources if s.get("redirect")}
    resolved = set()
    async with httpx.AsyncClient(timeout=5.0) as client:
        for job in jobs:
            url = job.get("url") or ""
            if url in by_redirect:
                job["url"] = by_redirect[url]
                resolved.add(job["url"])
            elif REDIRECT_MARKER in url:
                real = await resolve_url(client, url)
                job["url"] = real or ""  # expired redirects (404) are useless as links
                if real:
                    resolved.add(real)
    return resolved


def format_sources(sources: list[dict]) -> str:
    unique = {s["url"]: s for s in sources}.values()
    return "\n".join(f"- {s['title']}: {s['url']}" for s in unique) or "- none"


def parse_date(value: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return None


def clean_jobs(jobs: list[dict], allowed_urls: set[str], already_shown: list[dict]) -> list[dict]:
    """Drop invented links, posts older than the lookback window, and posts already shown."""
    cutoff = lookback_cutoff()
    seen = {(j["title"].lower().strip(), j["company"].lower().strip()) for j in already_shown}
    seen_urls = {j.get("url") for j in already_shown if j.get("url")}
    cleaned = []
    for job in jobs:
        if job.get("url") and (job["url"] not in allowed_urls or LISTING_URL.search(job["url"])):
            job["url"] = ""
        posted = parse_date(job.get("posted_date"))
        if posted is None:
            job["posted_date"] = "unknown"
        elif posted < cutoff:
            continue
        key = (job["title"].lower().strip(), job["company"].lower().strip())
        if key in seen or (job.get("url") and job["url"] in seen_urls):
            continue
        seen.add(key)
        cleaned.append(job)
    return cleaned
