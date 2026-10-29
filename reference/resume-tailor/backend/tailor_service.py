"""Service module managing Gemini AI interaction and response parsing."""

import json
import os
from typing import Optional
from google import genai
from google.genai import types

from models import TailorResponse
from prompts import SYSTEM_INSTRUCTION, build_tailor_prompt

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def create_gemini_client() -> genai.Client:
    """Create a Gemini client from environment variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    
    # Fallback to Vertex AI if configured
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if project:
        return genai.Client(
            vertexai=True,
            project=project,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
    
    # Return client with default environment lookup
    return genai.Client()


def parse_gemini_json_response(raw_text: str) -> TailorResponse:
    """Parse and validate raw Gemini output into a TailorResponse model."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    data = json.loads(cleaned)
    return TailorResponse.model_validate(data)


def tailor_bullets(
    resume_text: str,
    job_text: str,
    client: Optional[genai.Client] = None,
) -> TailorResponse:
    """Generate tailored resume bullets matching job requirements using Gemini."""
    if len(resume_text.strip()) < 10 or len(job_text.strip()) < 10:
        raise ValueError("Resume text and job description must each be at least 10 characters.")

    if client is None:
        client = create_gemini_client()

    user_prompt = build_tailor_prompt(resume_text, job_text)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.3,
        response_mime_type="application/json",
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=user_prompt,
        config=config,
    )

    response_text = getattr(response, "text", "") or ""
    return parse_gemini_json_response(response_text)
