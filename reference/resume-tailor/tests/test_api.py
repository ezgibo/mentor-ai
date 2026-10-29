"""Integration tests for FastAPI endpoints in main.py."""

from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from models import TailorResponse, TailoredBullet

client = TestClient(app)


def test_health_check_endpoint():
    """Verify that GET /api/health returns 200 OK and status 'ok'."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model" in data


def test_api_validation_error_flow_empty_body():
    """Verify that POST /api/tailor with empty body returns 422 Unprocessable Entity."""
    response = client.post("/api/tailor", json={})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_api_validation_error_flow_short_fields():
    """Verify that inputs shorter than 10 chars return 422 Unprocessable Entity."""
    response = client.post(
        "/api/tailor",
        json={"resume_text": "too short", "job_text": "also short"},
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_api_tailor_success_flow():
    """Verify happy path POST /api/tailor using a mocked Gemini service."""
    mocked_response = TailorResponse(
        bullets=[
            TailoredBullet(
                original_bullet="Built backend APIs using Python.",
                tailored_bullet="Architected high-throughput REST APIs using Python and FastAPI, reducing response latency by 40% across 50k+ daily queries.",
                matched_keywords=["FastAPI", "Python", "REST APIs", "Latency"],
                impact_metric_type="Performance",
            ),
            TailoredBullet(
                original_bullet="Made database queries faster in PostgreSQL.",
                tailored_bullet="Optimized PostgreSQL indexes and complex relational queries, improving throughput by 3.5x under peak concurrency.",
                matched_keywords=["PostgreSQL", "Database Optimization", "Concurrency"],
                impact_metric_type="Efficiency",
            ),
        ],
        summary_insight="Aligned backend development experience directly with required FastAPI and PostgreSQL scalability skills.",
    )

    with patch("main.tailor_bullets", return_value=mocked_response):
        payload = {
            "resume_text": "Built backend APIs using Python and worked on PostgreSQL database performance.",
            "job_text": "Looking for Senior Backend Engineer with FastAPI, PostgreSQL, and high-concurrency experience.",
        }
        response = client.post("/api/tailor", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "bullets" in data
        assert len(data["bullets"]) == 2
        assert data["bullets"][0]["matched_keywords"] == ["FastAPI", "Python", "REST APIs", "Latency"]
        assert data["summary_insight"] == "Aligned backend development experience directly with required FastAPI and PostgreSQL scalability skills."
