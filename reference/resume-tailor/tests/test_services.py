"""Unit tests for tailor_service.py parsing logic."""

import pytest
from pydantic import ValidationError
from tailor_service import parse_gemini_json_response
from models import TailorResponse


def test_parse_gemini_json_response_clean(sample_gemini_json):
    """Verify that raw clean JSON parses into a valid TailorResponse object."""
    response = parse_gemini_json_response(sample_gemini_json)

    assert isinstance(response, TailorResponse)
    assert len(response.bullets) == 2

    first_bullet = response.bullets[0]
    assert "FastAPI" in first_bullet.tailored_bullet
    assert "FastAPI" in first_bullet.matched_keywords
    assert first_bullet.impact_metric_type == "Performance"


def test_parse_gemini_json_response_with_code_fences(sample_gemini_fenced_json):
    """Verify that markdown code fences (```json ... ```) are cleanly stripped."""
    response = parse_gemini_json_response(sample_gemini_fenced_json)

    assert isinstance(response, TailorResponse)
    assert len(response.bullets) == 2
    assert "FastAPI" in response.bullets[0].tailored_bullet


def test_parse_gemini_json_response_invalid_json():
    """Verify that malformed JSON raises JSONDecodeError."""
    import json
    with pytest.raises(json.JSONDecodeError):
        parse_gemini_json_response("This is not JSON at all.")


def test_parse_gemini_json_response_missing_fields():
    """Verify that JSON missing required fields raises a ValidationError."""
    incomplete_json = '{"summary_insight": "No bullets here"}'
    with pytest.raises(ValidationError):
        parse_gemini_json_response(incomplete_json)
