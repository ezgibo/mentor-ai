"""Shared fixtures: a throwaway data directory per test, agent prompts on/off, and a test client."""

import shutil

import pytest
from fastapi.testclient import TestClient

import config
import db
from agents import mock_interview, review, summary, web_search

AGENT_MODULES = [summary, web_search, mock_interview, review]


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Point the database and uploads at a temp folder so tests never touch data/."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "mentor.db")
    db.init_db()
    return tmp_path


@pytest.fixture
def active_agents(monkeypatch):
    """Pretend every prompt has been pasted."""
    for module in AGENT_MODULES:
        monkeypatch.setattr(module, "SYSTEM_PROMPT", f"Test prompt for {module.__name__}. " * 3)


@pytest.fixture
def resume(data_dir):
    path = data_dir / "uploads" / "resume.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config.SAMPLE_RESUME, path)
    db.set_resume(str(path), "application/pdf", "sample_resume.pdf")
    return path


@pytest.fixture
def client():
    from main import app
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


LONG_DESCRIPTION = (
    "We are hiring an entry-level backend engineer to build Python APIs with FastAPI and PostgreSQL. "
    "You will design REST endpoints, write tests with pytest, deploy with Docker on Google Cloud, "
    "and work with product managers on new features. Requirements: CS degree, Python, SQL, Git."
)


def sample_job(**overrides) -> dict:
    job = {
        "title": "Backend Engineer, New Grad",
        "company": "Acme Corp",
        "location": "New York, NY",
        "level": "Entry-level",
        "url": "https://www.linkedin.com/jobs/view/123",
        "source": "linkedin",
        "posted_date": "unknown",
        "job_description": LONG_DESCRIPTION,
        "summary": "Build Python APIs.",
        "why_relevant": "You built FastAPI services at your internship.",
    }
    job.update(overrides)
    return job
