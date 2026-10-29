"""Both flows end to end with every agent mocked: statuses move only the way db.md says."""

import asyncio

import pytest

import db
import orchestrator
from agents import AgentLockedError, review, summary, web_search
from models import (
    InterviewPlan, InterviewReview, JobPick, JobPreferences, JobPresentation, PlanItem, PlannedQuestion,
    QuestionReview, ReviewPresentation, RubricScores, StudyPlan, TopicItem, TopicList, UnderstandingReply,
)
from tests.conftest import sample_job

PREFS = JobPreferences(target_roles=["Backend Engineer"], levels=["Entry-level"], locations=["New York"],
                       work_mode="hybrid", must_haves=[], deal_breakers=[], resume_highlights=["FastAPI"],
                       search_keywords=["python"])


async def drain():
    """Wait for background agents started by the orchestrator."""
    while orchestrator._background:
        await asyncio.gather(*list(orchestrator._background), return_exceptions=True)


@pytest.fixture
def mocked(monkeypatch, active_agents):
    calls = {"find_jobs": []}

    async def understand_request(profile, conversation):
        return UnderstandingReply(reply="- Backend, NYC. Did I get this right?", understanding=PREFS,
                                  ready_to_confirm=True)

    async def find_jobs(preferences, feedback, already_shown):
        calls["find_jobs"].append({"feedback": feedback, "shown": len(already_shown)})
        n = len(calls["find_jobs"])
        return [sample_job(title=f"Engineer {n}-{i}", fit_score=90 - i) for i in range(1, 3)], ""

    async def present_jobs(profile, preferences, jobs, search_note=""):
        return JobPresentation(message="Here are your matches.",
                               jobs=[JobPick(index=i, summary=f"S{i}", why_relevant=f"W{i}")
                                     for i in range(1, len(jobs) + 1)])

    async def list_topics(profile, job):
        return TopicList(message="Rate these.", topics=[
            TopicItem(name="SQL", why_needed="JD", resume_evidence="ETL"),
            TopicItem(name="System design", why_needed="JD", resume_evidence="None found"),
        ])

    async def make_study_plan(profile, job, topics):
        return StudyPlan(message="Study design first.", items=[
            PlanItem(topic_number=1, priority="review_later", plan="Skim"),
            PlanItem(topic_number=2, priority="study_first", plan="Practice"),
        ])

    async def find_interview_reports(job):
        return {"questions": [], "process_notes": "", "search_notes": "nothing found"}

    async def compose_interview(profile, job, research):
        return InterviewPlan(message="7 questions.", questions=[
            PlannedQuestion(question=f"Q{i}", source="jd_concept", source_url="", what_it_tests="x")
            for i in range(1, 8)
        ])

    async def review_interview(profile, job, questions):
        return InterviewReview(
            reviews=[QuestionReview(question_number=q["position"],
                                    rubric=RubricScores(accuracy=8, depth=6, structure=7, communication=9),
                                    strengths="clear", improvements="numbers", senior_lens="impact")
                     for q in questions],
            overall_summary="Solid.", top_strengths=["clarity"], focus_areas=["depth"])

    async def present_review(job, result, scores):
        calls["scores"] = scores
        return ReviewPresentation(message="Nice job.", prepare_next=["Quantify impact"])

    for module, name, fn in [
        (summary, "understand_request", understand_request), (summary, "present_jobs", present_jobs),
        (summary, "list_topics", list_topics), (summary, "make_study_plan", make_study_plan),
        (summary, "compose_interview", compose_interview), (summary, "present_review", present_review),
        (web_search, "find_jobs", find_jobs), (web_search, "find_interview_reports", find_interview_reports),
        (review, "review_interview", review_interview),
    ]:
        monkeypatch.setattr(module, name, fn)
    return calls


async def test_job_search_flow_with_feedback_round(mocked, resume):
    request_id = await orchestrator.start_search("Backend roles in NYC")
    assert db.get_search_request(request_id)["status"] == "collecting"

    orchestrator.confirm_search(request_id)
    assert db.get_search_request(request_id)["status"] == "searching"
    await drain()
    request = db.get_search_request(request_id)
    assert request["status"] == "results_ready" and request["round"] == 1
    first_round = db.list_search_results(request_id, 1)
    assert [r["why_relevant"] for r in first_round] == ["W1", "W2"]
    assert [r["fit_score"] for r in first_round] == [89, 88]

    orchestrator.give_feedback(request_id, "More data roles please")
    await drain()
    assert mocked["find_jobs"][1] == {"feedback": ["More data roles please"], "shown": 2}
    second_round = db.list_search_results(request_id, 2)

    job_ids = orchestrator.save_jobs(request_id, [second_round[0]["id"]])
    assert db.get_search_request(request_id)["status"] == "saved"
    assert db.get_job(job_ids[0])["title"] == "Engineer 2-1"


async def test_cannot_confirm_twice(mocked, resume):
    request_id = await orchestrator.start_search("Backend roles")
    orchestrator.confirm_search(request_id)
    with pytest.raises(orchestrator.StateError):
        orchestrator.confirm_search(request_id)
    await drain()


async def test_search_failure_is_recorded_and_retryable(mocked, resume, monkeypatch):
    async def broken(*args):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")
    monkeypatch.setattr(web_search, "find_jobs", broken)
    request_id = await orchestrator.start_search("Backend roles")
    orchestrator.confirm_search(request_id)
    await drain()
    request = db.get_search_request(request_id)
    assert request["status"] == "failed" and "rate limit" in request["error"]
    orchestrator.confirm_search(request_id)  # retry allowed from failed
    await drain()


async def test_empty_search_fails_with_helpful_message(mocked, resume, monkeypatch):
    async def nothing(*args):
        return [], ""
    monkeypatch.setattr(web_search, "find_jobs", nothing)
    request_id = await orchestrator.start_search("Backend roles")
    orchestrator.confirm_search(request_id)
    await drain()
    assert "even after widening" in db.get_search_request(request_id)["error"]


async def test_search_needs_resume(mocked):
    with pytest.raises(ValueError, match="Upload your resume"):
        await orchestrator.start_search("Backend roles")


async def test_locked_web_search_blocks_confirm(mocked, resume, monkeypatch):
    request_id = await orchestrator.start_search("Backend roles")
    monkeypatch.setattr(web_search, "SYSTEM_PROMPT", "")
    with pytest.raises(AgentLockedError):
        orchestrator.confirm_search(request_id)


def saved_job_id(**overrides):
    request_id = db.create_search_request()
    return db.save_jobs(request_id, db.add_search_results(request_id, 1, [sample_job(**overrides)]))[0]


async def test_interview_prep_flow(mocked, resume):
    job_id = saved_job_id()
    await orchestrator.load_topics(job_id)
    topics = db.list_topics(job_id)
    assert [t["name"] for t in topics] == ["SQL", "System design"]

    await orchestrator.rate_topics(job_id, {topics[0]["id"]: 4, topics[1]["id"]: 1})
    job = db.get_job(job_id)
    assert job["study_status"] == "studying"
    assert [t["priority"] for t in db.list_topics(job_id)] == ["review_later", "study_first"]

    session_id = orchestrator.finish_studying(job_id)
    job = db.get_job(job_id)
    assert (job["study_status"], job["interview_status"]) == ("done", "started")
    await drain()
    assert db.get_interview(session_id)["status"] == "ready"
    assert len(db.list_questions(session_id)) == 7

    orchestrator.begin_interview(session_id)
    assert db.get_interview(session_id)["status"] == "in_progress"
    with pytest.raises(ValueError, match="No answers"):
        orchestrator.finish_interview(session_id)
    for q in db.list_questions(session_id)[:3]:
        db.update_question(q["id"], transcript=f"answer {q['position']}")

    orchestrator.finish_interview(session_id)
    await drain()
    session = db.get_interview(session_id)
    assert session["status"] == "done" and session["summary_message"] == "Nice job."
    assert db.get_job(job_id)["interview_status"] == "done"
    assert mocked["scores"] == [8] * 7
    assert len(db.list_reviews(session_id)) == 7


async def test_topics_need_a_job_description(mocked, resume):
    job_id = saved_job_id(job_description="Too short")
    with pytest.raises(ValueError, match="job description"):
        await orchestrator.load_topics(job_id)


async def test_finish_studying_requires_a_plan(mocked, resume):
    with pytest.raises(orchestrator.StateError):
        orchestrator.finish_studying(saved_job_id())


async def test_retry_after_failed_review(mocked, resume, monkeypatch):
    job_id = saved_job_id()
    db.update_job(job_id, study_status="done", interview_status="started")
    session_id = db.create_interview(job_id, "live")
    db.add_questions(session_id, [{"question": "Q1", "source": "jd_concept"}])
    db.update_question(db.get_question(session_id, 1)["id"], transcript="my answer")
    db.update_interview(session_id, status="failed", error="boom")

    orchestrator.retry_interview(session_id)
    assert db.get_interview(session_id)["status"] == "reviewing"
    await drain()
    assert db.get_interview(session_id)["status"] == "done"


def test_restart_recovery_turns_stuck_work_into_retryable_failures():
    request_id = db.create_search_request()
    db.update_search_request(request_id, status="searching")
    job_id = saved_job_id()
    stuck = [db.create_interview(job_id, "live") for _ in range(3)]
    for session_id, status in zip(stuck, ["researching", "composing", "reviewing"]):
        db.update_interview(session_id, status=status)
    live = db.create_interview(job_id, "live")
    db.update_interview(live, status="in_progress")  # a live interview can simply be resumed

    assert orchestrator.recover_interrupted_work() == 4
    assert db.get_search_request(request_id)["status"] == "failed"
    assert all(db.get_interview(s)["status"] == "failed" for s in stuck)
    assert "Retry" in db.get_interview(stuck[2])["error"]
    assert db.get_interview(live)["status"] == "in_progress"
