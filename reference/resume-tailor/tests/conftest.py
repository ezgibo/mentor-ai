"""Shared pytest fixtures and test data."""

import json
import os
import sys
import pytest

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


@pytest.fixture
def sample_gemini_json():
    """Valid JSON payload simulating Gemini structured output."""
    return json.dumps({
        "bullets": [
            {
                "original_bullet": "Built backend APIs using Python.",
                "tailored_bullet": "Architected high-throughput REST APIs using Python and FastAPI, reducing response latency by 40% across 50k+ daily queries.",
                "matched_keywords": ["FastAPI", "Python", "REST APIs", "Latency"],
                "impact_metric_type": "Performance"
            },
            {
                "original_bullet": "Made database queries faster in PostgreSQL.",
                "tailored_bullet": "Optimized PostgreSQL indexes and complex relational queries, improving throughput by 3.5x under peak concurrency.",
                "matched_keywords": ["PostgreSQL", "Database Optimization", "Concurrency"],
                "impact_metric_type": "Efficiency"
            }
        ],
        "summary_insight": "Aligned backend development experience directly with required FastAPI and PostgreSQL scalability skills."
    })


@pytest.fixture
def sample_gemini_fenced_json(sample_gemini_json):
    """JSON wrapped in markdown code fences simulating LLM markdown output."""
    return f"```json\n{sample_gemini_json}\n```"
