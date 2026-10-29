"""Pydantic models and schemas for Resume Tailor."""

from typing import List
from pydantic import BaseModel, Field


class TailorRequest(BaseModel):
    """Input payload containing raw resume bullets and job posting description."""
    resume_text: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Raw resume bullets or experience summary",
    )
    job_text: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Target job description and requirements",
    )


class TailoredBullet(BaseModel):
    """An optimized resume bullet with matching keyword badges."""
    original_bullet: str = Field(
        default="",
        description="The source bullet point or topic addressed",
    )
    tailored_bullet: str = Field(
        ...,
        description="Upgraded bullet using action verbs and quantified impact",
    )
    matched_keywords: List[str] = Field(
        default_factory=list,
        description="Specific skills or keywords aligned with the job posting",
    )
    impact_metric_type: str = Field(
        default="Quantified Result",
        description="Type of metric framed (e.g., Performance, Scale, Efficiency)",
    )


class TailorResponse(BaseModel):
    """Output payload containing tailored bullets and summary insight."""
    bullets: List[TailoredBullet] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="List of tailored resume bullets",
    )
    summary_insight: str = Field(
        default="",
        description="Brief note on how the bullets were aligned with the role",
    )
