"""Shared Gemini helpers: client setup, resume attachment, and structured (JSON) calls.

Same patterns as reference/resume-tailor/backend/tailor_service.py.
"""

import json
import os
from pathlib import Path
from typing import Optional, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

import config

T = TypeVar("T", bound=BaseModel)

_client: Optional[genai.Client] = None


class UserFacingError(RuntimeError):
    """An error whose message is already written for the user; shown as-is."""


def get_client() -> genai.Client:
    """Create (once) a Gemini client from environment variables: API key first, then Vertex AI."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            _client = genai.Client(api_key=api_key)
        elif os.getenv("GOOGLE_CLOUD_PROJECT"):
            _client = genai.Client(
                vertexai=True,
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )
        else:
            _client = genai.Client()
    return _client


def resume_part(profile: Optional[dict]) -> types.Part:
    """The uploaded resume as a multimodal part (PDF / image / text) — Gemini reads it directly."""
    if not profile or not profile.get("resume_path"):
        raise ValueError("Upload your resume first (or click 'Use sample resume').")
    path = Path(profile["resume_path"])
    if not path.exists():
        raise ValueError("Your resume file is missing. Please upload it again.")
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=profile["resume_mime"])


def text_part(text: str) -> types.Part:
    return types.Part(text=text)


def parse_json(raw_text: str, schema: type[T]) -> T:
    """Parse model text into a schema, tolerating ```json fences."""
    cleaned = (raw_text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    return schema.model_validate(json.loads(cleaned))


async def generate_json(
    *,
    system_prompt: str,
    contents: list,
    schema: type[T],
    temperature: float = 0.4,
    model: Optional[str] = None,
    thinking_budget: Optional[int] = None,
) -> T:
    """One structured Gemini call: returns an instance of `schema`.

    thinking_budget=0 turns thinking off — much faster for pure extraction/formatting calls.
    """
    response = await get_client().aio.models.generate_content(
        model=model or config.TEXT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=_thinking(thinking_budget),
        ),
    )
    if isinstance(response.parsed, schema):
        return response.parsed
    try:
        return parse_json(response.text, schema)
    except (ValueError, ValidationError) as error:  # bad model output is a 502, not a user error
        raise RuntimeError(f"The model returned malformed JSON ({error.__class__.__name__}). Try again.") from error


async def generate_text(
    *,
    system_prompt: str,
    contents: list,
    tools: Optional[list[types.Tool]] = None,
    temperature: float = 0.4,
    model: Optional[str] = None,
    thinking_budget: Optional[int] = None,
) -> types.GenerateContentResponse:
    """One free-text Gemini call (optionally with tools such as Google Search)."""
    return await get_client().aio.models.generate_content(
        model=model or config.TEXT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            tools=tools,
            thinking_config=_thinking(thinking_budget),
        ),
    )


def _thinking(budget: Optional[int]) -> Optional[types.ThinkingConfig]:
    return None if budget is None else types.ThinkingConfig(thinking_budget=budget)


def friendly_error(error: Exception) -> str:
    """Turn SDK errors into a message a workshop participant can act on."""
    message = str(error)
    if isinstance(error, UserFacingError):
        return message
    upper = message.upper()
    if "API_KEY" in upper or "API KEY" in upper or "PERMISSION_DENIED" in upper or "UNAUTHENTICATED" in upper:
        return "Gemini API key is missing or invalid. Set GEMINI_API_KEY in .env and restart."
    if "402" in message or "CREDITS" in upper or "BILLING" in upper:
        return "Your Gemini API project has no credits left. Check billing at https://ai.studio/projects."
    if "429" in message or "RESOURCE_EXHAUSTED" in upper:
        return "Gemini rate limit reached. Wait a minute and try again."
    if isinstance(error, ValueError):
        return message
    return f"Gemini call failed: {message[:300]}"
