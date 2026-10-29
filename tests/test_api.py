"""HTTP API: health, resume upload, locked agents, and the job search flow over HTTP."""

import time

from agents import summary, web_search
from models import JobPick, JobPreferences, JobPresentation, UnderstandingReply
from tests.conftest import sample_job


def wait_for(client, url, status, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(url).json()
        if data["status"] == status:
            return data
        time.sleep(0.05)
    raise AssertionError(f"{url} never reached {status}: {data}")


def test_health_lists_agents_and_settings(client):
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert [a["name"] for a in data["agents"]] == ["summary", "web_search", "mock_interview", "review"]
    assert data["question_count"] == 7


def test_upload_resume_validates_type(client):
    response = client.post("/api/profile/resume", files={"file": ("resume.docx", b"x", "application/msword")})
    assert response.status_code == 400


def test_upload_and_sample_resume(client):
    response = client.post("/api/profile/resume", files={"file": ("me.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert response.json() == {"has_resume": True, "resume_filename": "me.pdf"}
    assert client.post("/api/profile/sample-resume").json()["has_resume"] is True
    assert client.get("/api/profile/resume").content.startswith(b"%PDF")


def test_locked_agent_returns_423_with_instructions(client):
    response = client.post("/api/search", json={"message": "backend jobs"})
    assert response.status_code == 423
    assert response.json()["agent"] == "summary"


def test_unknown_ids_return_404(client):
    assert client.get("/api/jobs/999").status_code == 404
    assert client.get("/api/interviews/999").status_code == 404


def test_job_search_over_http(client, active_agents, resume, monkeypatch):
    prefs = JobPreferences(target_roles=["SWE"], levels=["Entry"], locations=["NYC"], work_mode="any",
                           must_haves=[], deal_breakers=[], resume_highlights=[], search_keywords=[])

    async def understand_request(profile, conversation):
        return UnderstandingReply(reply="Did I get this right?", understanding=prefs, ready_to_confirm=True)

    async def find_jobs(preferences, feedback, already_shown):
        return [sample_job(fit_score=80)], ""

    async def present_jobs(profile, preferences, jobs, search_note=""):
        return JobPresentation(message="Found one.", jobs=[JobPick(index=1, summary="s", why_relevant="w")])

    monkeypatch.setattr(summary, "understand_request", understand_request)
    monkeypatch.setattr(summary, "present_jobs", present_jobs)
    monkeypatch.setattr(web_search, "find_jobs", find_jobs)

    search = client.post("/api/search", json={"message": "SWE in NYC"}).json()
    assert search["status"] == "collecting"
    assert [m["role"] for m in search["messages"]] == ["user", "summary"]

    assert client.post(f"/api/search/{search['id']}/confirm").json()["status"] == "searching"
    ready = wait_for(client, f"/api/search/{search['id']}", "results_ready")
    assert ready["results"][0]["why_relevant"] == "w"
    assert ready["results"][0]["fit_score"] == 80

    assert client.post(f"/api/search/{search['id']}/confirm").status_code == 409

    saved = client.post(f"/api/search/{search['id']}/save", json={"result_ids": [ready["results"][0]["id"]]}).json()
    job = client.get(f"/api/jobs/{saved['saved_job_ids'][0]}").json()
    assert job["fit_score"] == 80
    assert job["has_description"] is True and job["topics"] == [] and job["interview"] is None


def test_paste_job_description(client):
    import db
    request_id = db.create_search_request()
    job_id = db.save_jobs(request_id, db.add_search_results(request_id, 1, [sample_job(job_description="")]))[0]
    assert client.get(f"/api/jobs/{job_id}").json()["has_description"] is False
    response = client.patch(f"/api/jobs/{job_id}", json={"job_description": "x" * 250})
    assert response.json()["has_description"] is True
