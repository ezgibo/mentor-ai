"""SQLite layer: schema, profile upsert, search results → saved jobs, interviews and reviews."""

import db
from tests.conftest import sample_job


def test_profile_upsert_keeps_single_row():
    db.set_resume("/tmp/a.pdf", "application/pdf", "a.pdf")
    db.set_resume("/tmp/b.png", "image/png", "b.png")
    assert db.query("SELECT COUNT(*) AS n FROM profile")[0]["n"] == 1
    assert db.get_profile()["resume_filename"] == "b.png"


def test_messages_are_threaded_in_order():
    db.add_message("search:1", "user", "hello")
    db.add_message("search:2", "user", "other thread")
    db.add_message("search:1", "summary", "hi!")
    assert [m["content"] for m in db.list_messages("search:1")] == ["hello", "hi!"]


def test_save_jobs_copies_results_and_marks_them_saved():
    request_id = db.create_search_request()
    ids = db.add_search_results(request_id, 1, [sample_job(), sample_job(title="Data Engineer")])
    job_ids = db.save_jobs(request_id, [ids[1]])
    assert len(job_ids) == 1
    job = db.get_job(job_ids[0])
    assert job["title"] == "Data Engineer"
    assert job["study_status"] == "not_started" and job["interview_status"] == "not_started"
    statuses = {r["id"]: r["status"] for r in db.list_search_results(request_id)}
    assert statuses == {ids[0]: "shown", ids[1]: "saved"}


def test_save_jobs_ignores_results_from_other_searches():
    first = db.create_search_request()
    second = db.create_search_request()
    ids = db.add_search_results(first, 1, [sample_job()])
    assert db.save_jobs(second, ids) == []


def test_reviews_join_questions_by_position():
    request_id = db.create_search_request()
    result_ids = db.add_search_results(request_id, 1, [sample_job()])
    job_id = db.save_jobs(request_id, result_ids)[0]
    session_id = db.create_interview(job_id, "live")
    db.add_questions(session_id, [
        {"question": "Q1", "source": "resume_deep_dive"},
        {"question": "Q2", "source": "jd_concept"},
    ])
    q2 = db.get_question(session_id, 2)
    db.save_review(q2["id"], 7, {"accuracy": 7}, "good", "more depth", "trade-offs")
    db.save_review(q2["id"], 8, {"accuracy": 8}, "better", "", "")  # upsert
    reviews = db.list_reviews(session_id)
    assert len(reviews) == 1 and reviews[0]["position"] == 2 and reviews[0]["score"] == 8


def test_deleting_job_cascades_to_topics_and_interviews():
    request_id = db.create_search_request()
    job_id = db.save_jobs(request_id, db.add_search_results(request_id, 1, [sample_job()]))[0]
    db.replace_topics(job_id, [{"name": "SQL"}])
    db.create_interview(job_id, "live")
    db.delete_job(job_id)
    assert db.list_topics(job_id) == []
    assert db.latest_interview_for_job(job_id) is None


def test_init_db_adds_new_columns_to_an_old_database(data_dir):
    import sqlite3
    db_file = data_dir / "old.db"
    old = sqlite3.connect(db_file)
    old.execute("CREATE TABLE saved_jobs (id INTEGER PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL)")
    old.execute("CREATE TABLE search_results (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
    old.commit()
    old.close()
    import config
    config.DB_PATH = db_file
    db.init_db()
    for table in ("saved_jobs", "search_results"):
        columns = {row["name"] for row in db.query(f"PRAGMA table_info({table})")}
        assert "fit_score" in columns
