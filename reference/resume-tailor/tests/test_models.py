"""Unit tests for Pydantic models in models.py."""

import pytest
from pydantic import ValidationError
from models import TailorRequest, TailoredBullet, TailorResponse


def test_tailor_request_validation_success():
    """Validates that TailorRequest succeeds with valid inputs."""
    valid_request = TailorRequest(
        resume_text="Built scalable APIs using Python and PostgreSQL.",
        job_text="Seeking Senior Backend Engineer proficient in Python.",
    )
    assert len(valid_request.resume_text) >= 10
    assert len(valid_request.job_text) >= 10


def test_tailor_request_validation_too_short():
    """Validates that TailorRequest rejects inputs shorter than 10 characters."""
    with pytest.raises(ValidationError) as exc_info:
        TailorRequest(
            resume_text="Short",
            job_text="Seeking Senior Backend Engineer.",
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("resume_text",) for err in errors)

    with pytest.raises(ValidationError) as exc_info:
        TailorRequest(
            resume_text="Valid resume bullets with enough length.",
            job_text="Tiny",
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("job_text",) for err in errors)


def test_tailor_request_validation_empty():
    """Validates that empty strings are rejected."""
    with pytest.raises(ValidationError):
        TailorRequest(resume_text="", job_text="")


def test_tailor_request_validation_too_long():
    """Validates that text exceeding 10,000 characters is rejected."""
    oversized_text = "A" * 10001
    with pytest.raises(ValidationError) as exc_info:
        TailorRequest(
            resume_text=oversized_text,
            job_text="Seeking Senior Backend Engineer.",
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("resume_text",) for err in errors)


def test_tailor_response_validation():
    """Validates that TailorResponse requires at least 1 bullet and max 5 bullets."""
    bullet = TailoredBullet(
        original_bullet="Wrote tests.",
        tailored_bullet="Engineered automated pytest suites covering 90% of business logic.",
        matched_keywords=["pytest", "Automation"],
        impact_metric_type="Quality",
    )

    response = TailorResponse(
        bullets=[bullet],
        summary_insight="Enhanced test automation narrative.",
    )
    assert len(response.bullets) == 1

    # Empty bullets list should raise ValidationError
    with pytest.raises(ValidationError):
        TailorResponse(bullets=[])
