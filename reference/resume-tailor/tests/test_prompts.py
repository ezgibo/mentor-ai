"""Unit tests for prompt construction and system instruction in prompts.py."""

from prompts import SYSTEM_INSTRUCTION, build_tailor_prompt


def test_system_instruction_contains_core_rules():
    """Verify that system instruction contains X-Y-Z formula and anti-hallucination guidelines."""
    assert "X-Y-Z" in SYSTEM_INSTRUCTION
    assert "Anti-Hallucination" in SYSTEM_INSTRUCTION
    assert "Action Verbs" in SYSTEM_INSTRUCTION
    assert "JSON" in SYSTEM_INSTRUCTION


def test_build_tailor_prompt_embedding():
    """Assert that build_tailor_prompt correctly embeds resume and job text."""
    resume_sample = "Engineered microservices using Python and Docker."
    job_sample = "Looking for Senior Engineer with Python, Docker, and Kubernetes expertise."

    prompt = build_tailor_prompt(resume_sample, job_sample)

    assert resume_sample in prompt
    assert job_sample in prompt
    assert "Target Job Description & Requirements:" in prompt
    assert "Candidate's Current Resume / Experience Bullets:" in prompt


def test_build_tailor_prompt_strips_whitespace():
    """Verify that leading and trailing whitespace is stripped."""
    raw_resume = "   \n  Built data pipelines in Spark.  \n "
    raw_job = "   \n  Seeking Big Data Engineer.  \n "

    prompt = build_tailor_prompt(raw_resume, raw_job)

    assert "Built data pipelines in Spark." in prompt
    assert "Seeking Big Data Engineer." in prompt
