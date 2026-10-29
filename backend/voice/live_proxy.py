"""Relays a mock interview between the browser and the Gemini Live API.

    browser ──(mic PCM 16 kHz)──▶ FastAPI WebSocket ──▶ Gemini Live
    browser ◀──(voice PCM 24 kHz + JSON events)── FastAPI ◀── Gemini Live

Keeping the relay on the server means the API key never reaches the browser, and transcripts
are saved straight to the database. The interviewer calls `next_question(n)` before each
question, which tells us which question the candidate's speech belongs to.

How a session starts: with a short SPOKEN cue ("Hi, I'm ready to start the interview" —
backend/voice/cues/), never with injected text. On Gemini 2.5 native audio with function tools, a
session whose first turn is started by text closes a few seconds later with error 1007 ("audio
content type is not supported"), whether or not the candidate speaks. An audio-started session is
stable, and interrupting the interviewer works normally.

Browser → server messages:  binary = PCM16 mono 16 kHz audio;  text = {"type": "end"}
Server → browser messages:  binary = PCM16 mono 24 kHz audio;  text = JSON events:
    {"type": "ready"} | {"type": "question", "position": n, "total": N}
    {"type": "transcript", "role": "interviewer"|"candidate", "text": "..."}
    {"type": "interrupted"} | {"type": "ending"} | {"type": "reconnecting", "message": "..."}
    {"type": "done", "reason": "..."} | {"type": "error", "message": "..."}
"""

import asyncio
import json
import logging
import re
import wave
from pathlib import Path
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

import config
import db
import gemini
import orchestrator
from agents import AgentLockedError, mock_interview

log = logging.getLogger("mentor.live")

MAX_RECONNECTS = 3
CUE_DIR = Path(__file__).resolve().parent / "cues"
CHUNK_BYTES = 3200                   # 100 ms of 16 kHz 16-bit mono audio
CUE_TRAILING_SILENCE = 8             # chunks of silence after the cue, so voice detection ends the turn
SILENCE = b"\x00\x00" * (CHUNK_BYTES // 2)
AUDIO_MIME = "audio/pcm;rate=16000"


# Gemini 2.5 native audio sometimes writes a tool call into its speech transcript instead of making it,
# e.g. "忱call:next_question{number:3}<ctrl46>". We strip it from captions and treat it as the real call.
LEAKED_CALL = re.compile(r"[^\x00-\x7F]?\s*call:\s*(\w+)\s*\{([^}]*)\}\s*(?:<ctrl\d+>)?")
CONTROL_TOKEN = re.compile(r"<ctrl\d+>")
# The unfinished start of a leaked call or control token at the end of a fragment (held until it completes).
INCOMPLETE_LEAK = re.compile(r"([^\x00-\x7F]?\s*c(a(l(l(:[^}]*)?)?)?)?|<(c(t(r(l\d*)?)?)?)?|[^\x00-\x7F])$")


def clean_transcript(text: str) -> str:
    """Remove leaked tool-call syntax and control tokens from transcript text."""
    return CONTROL_TOKEN.sub("", LEAKED_CALL.sub(" ", text))


def parse_args(raw_args: str) -> dict:
    return {key: int(value) if value.isdigit() else value
            for key, value in re.findall(r"(\w+)\s*:\s*([\w.-]+)", raw_args)}


def leaked_calls(text: str) -> list[tuple[str, dict]]:
    """Find complete leaked tool calls: [("next_question", {"number": 3}), ...]."""
    return [(name, parse_args(raw_args)) for name, raw_args in LEAKED_CALL.findall(text)]


class TranscriptCleaner:
    """Streams interviewer transcript fragments into clean text segments and leaked tool calls.

    feed("I see. 忱call:next_q") -> [("text", "I see.")]          (the unfinished call is held back)
    feed("uestion{number:2}<ctrl46>Describe") -> [("call", ("next_question", {"number": 2})), ("text", "Describe")]
    """

    def __init__(self):
        self.pending = ""

    def feed(self, fragment: str) -> list[tuple[str, object]]:
        buffer = self.pending + fragment
        held = INCOMPLETE_LEAK.search(buffer)
        cut = held.start() if held and held.group(0) else len(buffer)
        # never hold back ordinary words that merely end in "c", "ca", "cal", or "call"
        if held and held.group(0) and re.fullmatch(r"\s*c(a(l(l)?)?)?", held.group(0)) and cut > 0 and buffer[cut - 1].isalpha():
            cut = len(buffer)
        buffer, self.pending = buffer[:cut], buffer[cut:]
        events: list[tuple[str, object]] = []
        pieces = LEAKED_CALL.split(buffer)  # [text, name, args, text, name, args, ..., text]
        for i in range(0, len(pieces), 3):
            text = CONTROL_TOKEN.sub("", pieces[i])
            if text:
                events.append(("text", text))
            if i + 2 < len(pieces):
                events.append(("call", (pieces[i + 1], parse_args(pieces[i + 2]))))
        return events

    def flush(self) -> str:
        """End of a turn: release held-back text (an unfinished 'call:' that never completed is dropped)."""
        held, self.pending = self.pending, ""
        return "" if "call:" in held else CONTROL_TOKEN.sub("", held)


def load_cue(name: str) -> bytes:
    """A 16 kHz mono PCM cue from backend/voice/cues/ (built by scripts/make_voice_cues.py)."""
    with wave.open(str(CUE_DIR / f"{name}.wav"), "rb") as wav:
        return wav.readframes(wav.getnframes())


class InterviewRecorder:
    """Attaches transcript fragments to whichever question is currently being asked."""

    def __init__(self, questions: list[dict]):
        self.questions = {q["position"]: q for q in questions}
        # Start on the first unanswered question: if the interviewer forgets to call next_question,
        # the first answer still lands on the right question (and Resume continues where you left off).
        unanswered = [p for p, q in sorted(self.questions.items()) if not (q.get("transcript") or "").strip()]
        self.current = unanswered[0] if unanswered else (1 if self.questions else 0)
        self.answers: dict[int, list[str]] = {p: [] for p in self.questions}
        self.asked: dict[int, list[str]] = {p: [] for p in self.questions}
        # Off while our spoken cue plays (its transcript is not an answer); on once the interviewer speaks.
        self.listening = False

    @property
    def total(self) -> int:
        return len(self.questions)

    def set_question(self, position: int) -> Optional[dict]:
        if position in self.questions:
            self.current = position
            return self.questions[position]
        return None

    def add_candidate_text(self, text: str) -> None:
        if self.current and self.listening:
            self.answers[self.current].append(text)

    def add_interviewer_text(self, text: str) -> None:
        self.listening = True
        if self.current:
            self.asked[self.current].append(text)

    @staticmethod
    def _join(fragments: list[str]) -> str:
        return re.sub(r"\s+", " ", clean_transcript("".join(fragments))).strip()

    def transcript(self, position: int) -> str:
        return self._join(self.answers[position])

    def save(self) -> None:
        for position, question in self.questions.items():
            transcript = self.transcript(position)
            asked = self._join(self.asked[position])
            if transcript or asked:
                db.update_question(question["id"], transcript=transcript, asked_text=asked)


class LiveInterview:
    def __init__(self, websocket: WebSocket, session_id: int):
        self.websocket = websocket
        self.session_id = session_id
        self.resume_handle: Optional[str] = None
        self.end_requested = False
        self.recorder: Optional[InterviewRecorder] = None
        self.last_error = ""
        self.cue_playing = False  # browser audio is held back while our cue streams
        self.cleaner = TranscriptCleaner()  # handles tool calls leaked into the interviewer transcript

    async def send_event(self, event: dict) -> None:
        await self.websocket.send_text(json.dumps(event))

    async def run(self) -> None:
        await self.websocket.accept()
        try:
            session = orchestrator.begin_interview(self.session_id)
        except (AgentLockedError, orchestrator.StateError, LookupError) as error:
            await self.send_event({"type": "error", "message": str(error)})
            await self.websocket.close()
            return

        job = db.get_job(session["job_id"])
        questions = db.list_questions(self.session_id)
        self.recorder = InterviewRecorder(questions)
        reason = "error"
        try:
            reason = await self._connect_loop(job, questions)
        except WebSocketDisconnect:
            reason = "browser_closed"
        except Exception as error:
            log.exception("Live interview failed")
            await self._safe_send({"type": "error", "message": gemini.friendly_error(error)})
        finally:
            self.recorder.save()
            if reason == "too_many_reconnects":
                await self._safe_send({"type": "error", "message": (
                    f"The connection to the interviewer kept dropping ({self.last_error[:160]}). "
                    "Your answers so far are saved — press Resume interview, or switch to Turn by turn."
                )})
            await self._safe_send({"type": "done", "reason": reason})
            try:
                await self.websocket.close()
            except RuntimeError:
                pass

    async def _connect_loop(self, job: dict, questions: list[dict]) -> str:
        client = gemini.get_client()
        connections = 0
        while True:
            connections += 1
            start_at = max(1, self.recorder.current)
            live_config = mock_interview.live_config(job, questions, self.resume_handle, start_at)
            async with client.aio.live.connect(model=config.LIVE_MODEL, config=live_config) as live:
                if connections == 1:
                    await self.send_event({"type": "ready", "total": self.recorder.total})
                if self.resume_handle is None:
                    # Fresh session: the "candidate" speaks first (see module docstring).
                    cue = "ready" if connections == 1 and start_at == 1 else "back"
                    reason = await self._pump(live, cue)
                else:
                    reason = await self._pump(live, None)  # resumed session keeps its context
            if reason not in ("go_away", "disconnected"):
                return reason
            if connections > MAX_RECONNECTS:
                return "too_many_reconnects"
            log.info("Live connection ended (%s: %s); reconnecting", reason, self.last_error)
            await self.send_event({"type": "reconnecting", "message": "Connection dropped, reconnecting…"})

    async def _pump(self, live, cue: Optional[str]) -> str:
        upstream = asyncio.create_task(self._browser_to_gemini(live, cue))
        downstream = asyncio.create_task(self._gemini_to_browser(live))
        done, pending = await asyncio.wait({upstream, downstream}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        finished = done.pop()
        if finished.exception():
            raise finished.exception()
        return finished.result()

    async def _play_cue(self, live, name: str) -> None:
        """Stream a spoken cue (real time) + a little silence, as if the candidate said it."""
        self.cue_playing = True
        self.recorder.listening = False
        try:
            pcm = load_cue(name)
            chunks = [pcm[i:i + CHUNK_BYTES] for i in range(0, len(pcm), CHUNK_BYTES)]
            for chunk in chunks + [SILENCE] * CUE_TRAILING_SILENCE:
                await live.send_realtime_input(audio=types.Blob(data=chunk, mime_type=AUDIO_MIME))
                await asyncio.sleep(0.1)
        finally:
            self.cue_playing = False

    async def _browser_to_gemini(self, live, cue: Optional[str] = None) -> str:
        cue_task = asyncio.create_task(self._play_cue(live, cue)) if cue else None
        try:
            while True:
                message = await self.websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return "browser_closed"
                if message.get("bytes"):
                    if self.cue_playing:
                        continue  # don't mix the candidate's mic into the cue
                    try:
                        await live.send_realtime_input(audio=types.Blob(data=message["bytes"], mime_type=AUDIO_MIME))
                    except Exception as error:  # Gemini closed the connection; the receive side reports why
                        self.last_error = self.last_error or str(error)
                        return "disconnected"
                elif message.get("text"):
                    event = json.loads(message["text"])
                    if event.get("type") == "end":
                        return "user_ended"
        finally:
            if cue_task and not cue_task.done():
                cue_task.cancel()

    async def _gemini_to_browser(self, live) -> str:
        while True:
            received_any = False
            try:
                async for message in live.receive():
                    received_any = True
                    outcome = await self._handle(live, message)
                    if outcome:
                        return outcome
            except Exception as error:  # connection closed by the server
                self.last_error = str(error)
                log.info("Live receive ended: %s", error)
                return "disconnected"
            if not received_any:
                return "disconnected"

    async def _handle(self, live, message: types.LiveServerMessage) -> Optional[str]:
        update = message.session_resumption_update
        if update and update.resumable and update.new_handle:
            self.resume_handle = update.new_handle
        if message.go_away:
            return "go_away"

        if message.tool_call:
            responses = []
            for call in message.tool_call.function_calls or []:
                responses.append(await self._tool(call))
            await live.send_tool_response(function_responses=responses)

        content = message.server_content
        if content:
            if content.model_turn:
                for part in content.model_turn.parts or []:
                    if part.inline_data and part.inline_data.data:
                        await self.websocket.send_bytes(part.inline_data.data)
            if content.input_transcription and content.input_transcription.text:
                if self.recorder.listening:
                    self.recorder.add_candidate_text(content.input_transcription.text)
                    await self.send_event({"type": "transcript", "role": "candidate",
                                           "text": content.input_transcription.text})
            if content.output_transcription and content.output_transcription.text:
                for kind, value in self.cleaner.feed(content.output_transcription.text):
                    if kind == "call":
                        name, args = value
                        log.info("Interviewer leaked a tool call into its transcript: %s %s", name, args)
                        await self._tool(types.FunctionCall(name=name, args=args))
                    else:
                        self.recorder.add_interviewer_text(value)
                        await self.send_event({"type": "transcript", "role": "interviewer", "text": value})
            if content.interrupted:
                await self.send_event({"type": "interrupted"})
            if content.turn_complete or content.interrupted:
                leftover = self.cleaner.flush()
                if leftover:
                    self.recorder.add_interviewer_text(leftover)
                    await self.send_event({"type": "transcript", "role": "interviewer", "text": leftover})
            if content.turn_complete and self.end_requested:
                return "completed"
        return None

    async def _tool(self, call: types.FunctionCall) -> types.FunctionResponse:
        if call.name == "next_question":
            position = int((call.args or {}).get("number", 0))
            question = self.recorder.set_question(position)
            if question is None:
                result = {"error": f"There is no question {position}. Ask questions 1 to {self.recorder.total}."}
            else:
                await self.send_event({"type": "question", "position": position, "total": self.recorder.total})
                result = {
                    "question": question["question"],
                    "remaining": self.recorder.total - position,
                    "reminder": "Call next_question again right before the next question.",
                }
        elif call.name == "end_interview":
            self.end_requested = True
            # The browser lets the goodbye finish playing, then sends {"type": "end"}.
            await self.send_event({"type": "ending"})
            result = {"ok": True}
        else:
            result = {"error": f"Unknown tool {call.name}"}
        # SILENT: the interviewer already knows the question; it should not talk about the tool result.
        return types.FunctionResponse(id=call.id, name=call.name, response=result,
                                      scheduling=types.FunctionResponseScheduling.SILENT)

    async def _safe_send(self, event: dict) -> None:
        try:
            await self.send_event(event)
        except (RuntimeError, WebSocketDisconnect):
            pass
