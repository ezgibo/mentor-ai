"""Mock Interview Agent — interviews the user by voice as a senior employee of the company.

Main path: Gemini Live API (real-time audio), relayed by backend/voice/live_proxy.py.
Fallback:  turn-by-turn (backend/voice/turn_based.py) — the question is spoken with TTS,
           the answer is recorded in the browser and transcribed here.
The same SYSTEM_PROMPT drives both paths.
"""

import re
from typing import Optional

from google.genai import types

import config
import gemini

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ STEP 3 — Paste the Mock Interview Agent prompt between the triple quotes. ║
# ║ Copy it from agents/mock_interview_agent.md → "The prompt".               ║
# ╚════════════════════════════════════════════════════════════════════════════╝
SYSTEM_PROMPT = """
"""

# NON_BLOCKING: the interviewer keeps talking while we record the call. With blocking tools, Gemini 2.5
# native audio dropped the connection (error 1007) about twice as often in our stress tests.
NEXT_QUESTION = types.FunctionDeclaration(
    behavior=types.Behavior.NON_BLOCKING,
    name="next_question",
    description="Call this right BEFORE asking each interview question, with its number.",
    parameters={
        "type": "OBJECT",
        "properties": {"number": {"type": "INTEGER", "description": "1-based question number"}},
        "required": ["number"],
    },
)

END_INTERVIEW = types.FunctionDeclaration(
    behavior=types.Behavior.NON_BLOCKING,
    name="end_interview",
    description="Call this once, after the candidate answered the last question and you said goodbye.",
    parameters={"type": "OBJECT", "properties": {}},
)


def interview_brief(job: dict, questions: list[dict], start_at: int = 1) -> str:
    """The session-specific part of the instructions: who you are, and the questions in order."""
    numbered = "\n".join(f"{q['position']}. {q['question']}" for q in questions)
    if start_at <= 1:
        opening = ("The call starts when the candidate says they are ready. Greet them briefly, then call "
                   "next_question with number 1 and ask question 1.")
    else:
        opening = (f"Questions 1 to {start_at - 1} are already done: the candidate is rejoining after a break. "
                   f"When they say they are back, welcome them back in one sentence (do not greet from scratch), "
                   f"then call next_question with number {start_at} and ask question {start_at}.")
    return f"""INTERVIEW SESSION
Company: {job['company']}
Role the candidate is interviewing for: {job['title']} ({job.get('level') or 'level not stated'})
You are a senior team member at {job['company']} on the team that is hiring for this role.

Ask these {len(questions)} questions in this exact order:
{numbered}

{opening}

Tool rules:
- Right before asking question N, call next_question with number N, then ask question N from the list
  above in your own natural spoken words without changing its meaning.
- After the candidate answers the last question, thank them, say goodbye, then call end_interview."""


def live_config(
    job: dict, questions: list[dict], resume_handle: Optional[str] = None, start_at: int = 1
) -> types.LiveConnectConfig:
    """Live API session config: audio out, transcripts both ways, tools, and long-session support."""
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(
            parts=[types.Part(text=f"{SYSTEM_PROMPT.strip()}\n\n{interview_brief(job, questions, start_at)}")]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=config.INTERVIEWER_VOICE)
            )
        ),
        tools=[types.Tool(function_declarations=[NEXT_QUESTION, END_INTERVIEW])],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # A 7-question interview runs ~15-20 minutes: longer than an audio session without
        # compression (15 min) and a single connection (~10 min). Compression + resumption fix both.
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow(),
        ),
        session_resumption=types.SessionResumptionConfig(handle=resume_handle),
    )


# ---------- turn-by-turn fallback ----------

async def spoken_line(job: dict, questions: list[dict], position: int, previous_answer: Optional[str]) -> str:
    """What the interviewer says for question `position` (greeting / short acknowledgement + question)."""
    question = questions[position - 1]["question"]
    if position == 1:
        lead = "This is the start of the interview. Greet the candidate in one sentence, introduce yourself by role (no made-up name), then ask question 1."
    else:
        lead = (
            "The candidate just answered the previous question (transcript below). Acknowledge it in "
            "at most one short neutral sentence — do not evaluate it — then ask the next question."
            f"\n\nPrevious answer transcript:\n\"\"\"\n{previous_answer or '(no answer)'}\n\"\"\""
        )
    task = f"""{lead}

Question {position} to ask: {question}

Reply with ONLY the words you will say out loud. No stage directions, no markdown."""
    response = await gemini.generate_text(
        system_prompt=f"{SYSTEM_PROMPT.strip()}\n\n{interview_brief(job, questions)}",
        contents=[gemini.text_part(task)],
        temperature=0.6,
    )
    return (response.text or question).strip()


async def synthesize(text: str) -> tuple[bytes, int]:
    """Text-to-speech for the interviewer's line. Returns (16-bit PCM bytes, sample rate)."""
    response = await gemini.get_client().aio.models.generate_content(
        model=config.TTS_MODEL,
        contents=f"Say in a calm, professional interviewer voice: {text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=config.INTERVIEWER_VOICE)
                )
            ),
        ),
    )
    blob = response.candidates[0].content.parts[0].inline_data
    return blob.data, sample_rate(blob.mime_type)


async def transcribe(audio: bytes, mime_type: str = "audio/wav") -> str:
    """Speech-to-text for one recorded answer."""
    response = await gemini.get_client().aio.models.generate_content(
        model=config.TRANSCRIBE_MODEL,
        contents=[
            types.Part.from_bytes(data=audio, mime_type=mime_type),
            gemini.text_part(
                "Transcribe this interview answer word for word. Return only the transcript. "
                "If there is no speech, return an empty string."
            ),
        ],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    return (response.text or "").strip()


def sample_rate(mime_type: Optional[str], default: int = 24000) -> int:
    """Read the rate from a mime type like 'audio/L16;codec=pcm;rate=24000'."""
    match = re.search(r"rate=(\d+)", mime_type or "")
    return int(match.group(1)) if match else default
