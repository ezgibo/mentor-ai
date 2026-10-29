"""Web Search Agent helpers: grounding sources, link filtering, date window, de-duplication."""

from datetime import timedelta
from types import SimpleNamespace

from agents import web_search
from context import lookback_cutoff, today


def job(**overrides):
    base = {"title": "Backend Engineer", "company": "Acme", "url": "https://acme.com/jobs/1",
            "posted_date": today().isoformat()}
    base.update(overrides)
    return base


def test_clean_jobs_blanks_links_not_from_search():
    cleaned = web_search.clean_jobs([job(url="https://made-up.example/x")], {"https://acme.com/jobs/1"}, [])
    assert cleaned[0]["url"] == ""


def test_clean_jobs_drops_posts_older_than_window():
    old = (lookback_cutoff() - timedelta(days=1)).isoformat()
    assert web_search.clean_jobs([job(posted_date=old)], set(), []) == []


def test_clean_jobs_keeps_unknown_dates():
    cleaned = web_search.clean_jobs([job(posted_date="sometime last week")], {"https://acme.com/jobs/1"}, [])
    assert cleaned[0]["posted_date"] == "unknown"


def test_clean_jobs_skips_already_shown_and_duplicates():
    shown = [{"title": "backend engineer ", "company": "ACME", "url": None}]
    jobs = [job(), job(title="Data Engineer", url=""), job(title="Data Engineer", url="")]
    cleaned = web_search.clean_jobs(jobs, {"https://acme.com/jobs/1"}, shown)
    assert [j["title"] for j in cleaned] == ["Data Engineer"]


def test_grounding_sources_reads_web_chunks():
    chunk = SimpleNamespace(web=SimpleNamespace(title="LinkedIn", uri="https://x/redirect"))
    response = SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(grounding_chunks=[chunk]))])
    assert web_search.grounding_sources(response) == [{"title": "LinkedIn", "url": "https://x/redirect"}]


def test_grounding_sources_handles_missing_metadata():
    response = SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=None)])
    assert web_search.grounding_sources(response) == []


async def test_resolve_sources_leaves_normal_urls_alone():
    sources = [{"title": "a", "url": "https://acme.com/jobs/1"}]
    assert await web_search.resolve_sources(sources) == sources


# ---------- search pipeline ----------

import pytest

import gemini
from models import FoundJob, FoundJobs, JobRanking, JobScore

PREFS = {"target_roles": ["Software Engineer", "Backend Engineer"], "levels": ["Entry-level", "New Grad"],
         "locations": ["New York City"], "work_mode": "any"}


def fake_response(text, reason="STOP", chunks=()):
    web_chunks = [SimpleNamespace(web=SimpleNamespace(title=t, uri=u)) for t, u in chunks]
    candidate = SimpleNamespace(finish_reason=SimpleNamespace(name=reason),
                                grounding_metadata=SimpleNamespace(grounding_chunks=web_chunks))
    return SimpleNamespace(text=text, candidates=[candidate])


def test_search_angles_are_plain_and_capped():
    angles = web_search.search_angles(PREFS)
    assert angles[0] == "Entry-level Software Engineer jobs in New York City"
    assert "Entry-level Software Engineer jobs in New York City on LinkedIn" in angles
    assert len(angles) <= web_search.MAX_ANGLES
    assert not any("site:" in a or "after:" in a for a in angles)


def test_broadened_angles_widen_level_and_location():
    angles = web_search.search_angles(PREFS, broaden=True)
    assert all("junior" in a and "area or remote" in a for a in angles)


def test_search_angles_handle_empty_request():
    assert web_search.search_angles({}) == ["software engineer jobs", "software engineer jobs on LinkedIn"]


def test_adjusted_score_nudges_and_clamps():
    assert web_search.adjusted_score(80, {"source": "linkedin", "posted_date": "2026-10-01"}) == 85
    assert web_search.adjusted_score(80, {"source": "other", "posted_date": "unknown"}) == 70
    assert web_search.adjusted_score(98, {"source": "handshake", "posted_date": "2026-10-01"}) == 100
    assert web_search.adjusted_score(5, {"source": "other", "posted_date": None}) == 0


async def test_grounded_search_retries_after_recitation(monkeypatch):
    calls = []

    async def generate_text(**kwargs):
        calls.append(kwargs["contents"][0].text)
        if len(calls) == 1:
            return fake_response(None, reason="RECITATION")
        return fake_response("1. Backend Engineer at Acme", chunks=[("acme.com", "https://acme.com/jobs/1")])

    monkeypatch.setattr(gemini, "generate_text", generate_text)
    text, sources = await web_search.grounded_search("TASK")
    assert text.startswith("1. Backend")
    assert sources == [{"title": "acme.com", "url": "https://acme.com/jobs/1"}]
    assert "own words" in calls[1] and "own words" not in calls[0]


async def test_grounded_search_gives_up_after_two_empty_answers(monkeypatch):
    async def generate_text(**kwargs):
        return fake_response("", reason="RECITATION")
    monkeypatch.setattr(gemini, "generate_text", generate_text)
    assert await web_search.grounded_search("TASK") == ("", [])


async def test_rank_jobs_sorts_by_adjusted_fit(monkeypatch):
    async def generate_json(**kwargs):
        return JobRanking(scores=[JobScore(index=1, fit_score=60, reason=""), JobScore(index=2, fit_score=58, reason="")])
    monkeypatch.setattr(gemini, "generate_json", generate_json)
    jobs = [{"title": "A", "company": "x", "source": "other", "posted_date": "unknown"},
            {"title": "B", "company": "y", "source": "linkedin", "posted_date": "2026-10-01"}]
    ranked = await web_search.rank_jobs(PREFS, [], jobs)
    assert [(j["title"], j["fit_score"]) for j in ranked] == [("B", 63), ("A", 50)]


def found(title, url="https://acme.com/jobs/1"):
    return FoundJob(title=title, company="Acme", location="NYC", level="Entry", url=url, source="other",
                    posted_date="unknown", job_description="Build APIs.", key_requirements=[])


async def test_find_jobs_broadens_when_too_few(monkeypatch):
    searched = []

    async def grounded_search(task):
        searched.append(task)
        return "findings https://acme.com/jobs/1 https://acme.com/jobs/9", []

    async def generate_json(**kwargs):
        if kwargs["schema"] is JobRanking:
            return JobRanking(scores=[])
        broad = "junior" in searched[-1]
        job = found("Wide Role", "https://acme.com/jobs/9") if broad else found("Exact Role")
        return FoundJobs(jobs=[job], search_notes="")

    monkeypatch.setattr(web_search, "grounded_search", grounded_search)
    monkeypatch.setattr(gemini, "generate_json", generate_json)
    jobs, note = await web_search.find_jobs(PREFS, [], [])
    assert {j["title"] for j in jobs} == {"Exact Role", "Wide Role"}
    assert "wider" in note


async def test_find_jobs_reports_blocked_search(monkeypatch):
    async def grounded_search(task):
        return "", []
    monkeypatch.setattr(web_search, "grounded_search", grounded_search)
    with pytest.raises(web_search.SearchBlockedError):
        await web_search.find_jobs(PREFS, [], [])
    assert "Google Search returned nothing" in gemini.friendly_error(web_search.SearchBlockedError(
        "Google Search returned nothing for every search (blocked or empty)."))


async def test_normalize_links_maps_redirects_to_real_urls():
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"
    jobs = [{"url": redirect}, {"url": "https://acme.com/jobs/2"}]
    sources = [{"title": "acme", "url": "https://acme.com/jobs/1", "redirect": redirect}]
    resolved = await web_search.normalize_links(jobs, sources)
    assert jobs[0]["url"] == "https://acme.com/jobs/1" and jobs[1]["url"] == "https://acme.com/jobs/2"
    assert resolved == {"https://acme.com/jobs/1"}


def test_clean_jobs_blanks_search_and_category_pages():
    listing = "https://www.indeed.com/q-new-grad-software-engineer-l-new-york,-ny-jobs.html"
    posting = "https://www.linkedin.com/jobs/view/4012345678"
    cleaned = web_search.clean_jobs([job(url=listing), job(title="Other", url=posting)], {listing, posting}, [])
    assert [j["url"] for j in cleaned] == ["", posting]
