"""Turn-by-turn voice fallback: one HTTP request per question and one per answer.

    GET  question n → the interviewer's line (text + TTS audio)
    POST answer n   → browser-recorded WAV → transcript saved on the question
"""

import base64
import logging

import db
import orchestrator
from agents import mock_interview
from gemini import friendly_error

log = logging.getLogger("mentor.turn")


def _question(session_id: int, position: int) -> dict:
    question = db.get_question(session_id, position)
    if question is None:
        raise LookupError(f"Question {position} not found.")
    return question


async def question_turn(session_id: int, position: int) -> dict:
    session = orchestrator.begin_interview(session_id)
    job = db.get_job(session["job_id"])
    questions = db.list_questions(session_id)
    question = _question(session_id, position)
    previous = db.get_question(session_id, position - 1) if position > 1 else None

    text = await mock_interview.spoken_line(job, questions, position, previous and previous.get("transcript"))
    db.update_question(question["id"], asked_text=text)

    audio_b64, rate, audio_error = None, 24000, None
    try:
        pcm, rate = await mock_interview.synthesize(text)
        audio_b64 = base64.b64encode(pcm).decode()
    except Exception as error:  # the text still works without audio
        log.warning("TTS failed: %s", error)
        audio_error = friendly_error(error)

    return {
        "position": position,
        "total": len(questions),
        "question": question["question"],
        "source": question["source"],
        "spoken_text": text,
        "audio_b64": audio_b64,
        "sample_rate": rate,
        "audio_error": audio_error,
    }


async def answer_turn(session_id: int, position: int, audio: bytes, mime_type: str) -> dict:
    orchestrator.begin_interview(session_id)
    question = _question(session_id, position)
    if not audio:
        raise ValueError("The recording was empty. Check your microphone and try again.")
    transcript = await mock_interview.transcribe(audio, mime_type or "audio/wav")
    db.update_question(question["id"], transcript=transcript)
    return {"position": position, "transcript": transcript}
