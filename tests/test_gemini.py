"""Gemini helpers that run without the network."""

import pytest

import gemini
from models import ReviewPresentation


def test_parse_json_accepts_fenced_output():
    raw = '```json\n{"message": "Nice work", "prepare_next": ["STAR stories"]}\n```'
    parsed = gemini.parse_json(raw, ReviewPresentation)
    assert parsed.prepare_next == ["STAR stories"]


def test_resume_part_requires_upload():
    with pytest.raises(ValueError, match="Upload your resume"):
        gemini.resume_part(None)


def test_resume_part_reads_file(resume):
    part = gemini.resume_part({"resume_path": str(resume), "resume_mime": "application/pdf"})
    assert part.inline_data.mime_type == "application/pdf"
    assert part.inline_data.data.startswith(b"%PDF")


@pytest.mark.parametrize("message, expected", [
    ("400 API_KEY_INVALID", "GEMINI_API_KEY"),
    ("402 RESOURCE_EXHAUSTED prepayment credits are depleted", "no credits"),
    ("429 RESOURCE_EXHAUSTED", "rate limit"),
    ("500 boom", "Gemini call failed"),
])
def test_friendly_error(message, expected):
    assert expected in gemini.friendly_error(RuntimeError(message))
