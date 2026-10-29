"""FastAPI Application for Resume Tailor."""

import json
import os
import sys

# Ensure backend directory is in Python path for direct script execution
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from models import TailorRequest, TailorResponse
from tailor_service import MODEL_NAME, tailor_bullets

load_dotenv()

app = FastAPI(
    title="Resume Tailor",
    description="AI-powered resume bullet optimizer aligned with job requirements",
    version="0.1.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/api/tailor",
    response_model=TailorResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate tailored resume bullets matching job description",
)
async def tailor(request: TailorRequest):
    """Analyze input resume bullets and job posting to return tailored, high-impact bullets."""
    try:
        response = tailor_bullets(
            resume_text=request.resume_text,
            job_text=request.job_text,
        )
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse structured AI output: {str(e)}",
        )
    except Exception as e:
        # Check for missing API key or client auth failure
        error_msg = str(e)
        if "API_KEY" in error_msg.upper() or "AUTHENTICATION" in error_msg.upper():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini API Key is not configured. Please set GEMINI_API_KEY in .env",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tailoring generation failed: {error_msg}",
        )


@app.get("/api/health", summary="Health check endpoint")
async def health():
    """Health check endpoint confirming API status and model configuration."""
    return {
        "status": "ok",
        "model": MODEL_NAME,
    }


# Mount frontend static assets if available
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
