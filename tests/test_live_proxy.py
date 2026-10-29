"""Live interview relay: transcripts land on the right question, tools respond correctly."""

from types import SimpleNamespace

import db
from voice.live_proxy import InterviewRecorder, LiveInterview
from tests.conftest import sample_job


def make_session():
    request_id = db.create_search_request()
    job_id = db.save_jobs(request_id, db.add_search_results(request_id, 1, [sample_job()]))[0]
    session_id = db.create_interview(job_id, "live")
    db.add_questions(session_id, [{"question": f"Question {i}", "source": "jd_concept"} for i in (1, 2, 3)])
    return session_id


def test_recorder_attaches_text_to_current_question():
    session_id = make_session()
    recorder = InterviewRecorder(db.list_questions(session_id))
    assert recorder.current == 1  # answers land on question 1 even if the model skips next_question(1)
    recorder.add_candidate_text("cue audio, ignored until the interviewer speaks")
    recorder.set_question(1)
    recorder.add_interviewer_text("Tell me about")
    recorder.add_interviewer_text(" yourself.")
    recorder.add_candidate_text(" I am a  student")
    recorder.add_candidate_text(" at college.")
    recorder.set_question(3)
    recorder.add_candidate_text("Answer three")
    recorder.save()

    questions = {q["position"]: q for q in db.list_questions(session_id)}
    assert questions[1]["transcript"] == "I am a student at college."
    assert questions[1]["asked_text"] == "Tell me about yourself."
    assert questions[2]["transcript"] is None
    assert questions[3]["transcript"] == "Answer three"


def test_recorder_rejects_unknown_question():
    recorder = InterviewRecorder(db.list_questions(make_session()))
    assert recorder.set_question(9) is None and recorder.current == 1


def test_recorder_resumes_at_first_unanswered_question():
    session_id = make_session()
    db.update_question(db.get_question(session_id, 1)["id"], transcript="first answer")
    recorder = InterviewRecorder(db.list_questions(session_id))
    assert recorder.current == 2
    recorder.listening = True
    recorder.add_candidate_text("second answer")
    recorder.save()
    questions = {q["position"]: q for q in db.list_questions(session_id)}
    assert questions[1]["transcript"] == "first answer"
    assert questions[2]["transcript"] == "second answer"


class FakeWebSocket:
    def __init__(self):
        self.events = []

    async def send_text(self, text):
        self.events.append(text)


async def test_next_question_tool_returns_question_and_notifies_browser():
    session_id = make_session()
    live = LiveInterview(FakeWebSocket(), session_id)
    live.recorder = InterviewRecorder(db.list_questions(session_id))
    response = await live._tool(SimpleNamespace(id="c1", name="next_question", args={"number": 2}))
    assert response.response["question"] == "Question 2" and response.response["remaining"] == 1
    assert "next_question" in response.response["reminder"]
    assert live.recorder.current == 2
    assert '"position": 2' in live.websocket.events[-1]


async def test_end_interview_tool_flags_the_end():
    session_id = make_session()
    live = LiveInterview(FakeWebSocket(), session_id)
    live.recorder = InterviewRecorder(db.list_questions(session_id))
    await live._tool(SimpleNamespace(id="c2", name="end_interview", args={}))
    assert live.end_requested
    assert '"ending"' in live.websocket.events[-1]


async def test_bad_question_number_returns_error_to_model():
    session_id = make_session()
    live = LiveInterview(FakeWebSocket(), session_id)
    live.recorder = InterviewRecorder(db.list_questions(session_id))
    response = await live._tool(SimpleNamespace(id="c3", name="next_question", args={"number": 7}))
    assert "error" in response.response


# ---------- spoken cue start (Gemini 2.5 + tools is unstable when a session starts with text) ----------

import asyncio
import json

from agents import mock_interview
from voice import live_proxy


class ScriptedWebSocket(FakeWebSocket):
    """Browser side: replays queued messages, then disconnects."""

    def __init__(self, messages):
        super().__init__()
        self.inbox = list(messages)

    async def receive(self):
        await asyncio.sleep(0)
        return self.inbox.pop(0) if self.inbox else {"type": "websocket.disconnect"}


class FakeLive:
    def __init__(self):
        self.audio, self.texts = [], []

    async def send_realtime_input(self, audio=None, text=None):
        (self.audio if audio is not None else self.texts).append(audio or text)


def audio_msg(byte):
    return {"type": "websocket.receive", "bytes": bytes([byte]) * 3200}


def test_cues_exist_and_are_16k_mono():
    import wave
    for name in ("ready", "back"):
        with wave.open(str(live_proxy.CUE_DIR / f"{name}.wav"), "rb") as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
        assert len(live_proxy.load_cue(name)) > 16000  # at least half a second


async def test_session_starts_with_spoken_cue_not_text(monkeypatch):
    monkeypatch.setattr(live_proxy, "load_cue", lambda name: b"\x05" * 6400)
    monkeypatch.setattr(live_proxy, "CUE_TRAILING_SILENCE", 1)
    session_id = make_session()
    live_session = LiveInterview(ScriptedWebSocket([]), session_id)
    live_session.recorder = InterviewRecorder(db.list_questions(session_id))
    gemini_live = FakeLive()
    await live_session._play_cue(gemini_live, "ready")
    assert gemini_live.texts == []  # never injected text
    assert [blob.data[0] for blob in gemini_live.audio] == [5, 5, 0]  # cue chunks, then silence
    assert live_session.cue_playing is False


async def test_browser_audio_is_held_while_cue_plays():
    session_id = make_session()
    live_session = LiveInterview(ScriptedWebSocket([audio_msg(1), audio_msg(2)]), session_id)
    live_session.recorder = InterviewRecorder(db.list_questions(session_id))
    gemini_live = FakeLive()
    live_session.cue_playing = True
    await live_session._browser_to_gemini(gemini_live)
    assert gemini_live.audio == []
    live_session.cue_playing = False
    live_session.websocket.inbox = [audio_msg(3)]
    await live_session._browser_to_gemini(gemini_live)
    assert [blob.data[0] for blob in gemini_live.audio] == [3]


def test_cue_transcript_is_not_saved_as_an_answer():
    recorder = InterviewRecorder(db.list_questions(make_session()))
    recorder.add_candidate_text("Hi, I'm here and ready to start the interview.")  # the cue, transcribed
    recorder.add_interviewer_text("Welcome! Tell me about yourself.")
    recorder.add_candidate_text("I'm a CS student.")
    assert recorder.transcript(1) == "I'm a CS student."


def test_brief_resumes_at_the_right_question():
    job = {"company": "Acme", "title": "SWE"}
    questions = [{"position": i, "question": f"Q{i}"} for i in (1, 2, 3)]
    assert "next_question with number 1" in mock_interview.interview_brief(job, questions)
    resumed = mock_interview.interview_brief(job, questions, start_at=3)
    assert "Questions 1 to 2 are already done" in resumed and "number 3" in resumed


# ---------- tool calls leaked into the interviewer's transcript ----------

LEAK = "Hi, thanks for joining us. 忱call:next_question{number:1}<ctrl43>Can you tell me about yourself?"


def test_clean_transcript_strips_leaked_calls():
    assert live_proxy.clean_transcript(LEAK) == "Hi, thanks for joining us.  Can you tell me about yourself?"
    assert live_proxy.leaked_calls(LEAK) == [("next_question", {"number": 1})]
    assert live_proxy.leaked_calls("Thanks! call:end_interview{}") == [("end_interview", {})]


def test_cleaner_holds_split_leaks_and_keeps_ordinary_words():
    cleaner = live_proxy.TranscriptCleaner()
    assert cleaner.feed("I see. 忱call:next_q") == [("text", "I see. ")]
    assert cleaner.feed("uestion{number:2}<ctrl46>Describe a bug.") == [
        ("call", ("next_question", {"number": 2})), ("text", "Describe a bug.")]
    assert cleaner.feed(" Let me recall") == [("text", " Let me recall")]  # "call" inside a word is not held
    assert cleaner.feed(" a basic") == [("text", " a basic")]
    assert cleaner.feed(" café") == [("text", " caf")] and cleaner.flush() == "é"  # held until the turn ends
    cleaner.feed("Bye. 忱call:end_inter")
    assert cleaner.flush() == ""  # a call that never completed is dropped, not shown


async def test_leaked_call_split_across_fragments_moves_the_question_once():
    session_id = make_session()
    ws = FakeWebSocket()
    live_session = LiveInterview(ws, session_id)
    live_session.recorder = InterviewRecorder(db.list_questions(session_id))
    for fragment in ["Great. 忱call:next_q", "uestion{number:2}<ctrl46>", "Describe a bug you fixed."]:
        message = SimpleNamespace(session_resumption_update=None, go_away=None, tool_call=None,
                                  server_content=SimpleNamespace(model_turn=None, input_transcription=None,
                                                                 output_transcription=SimpleNamespace(text=fragment),
                                                                 interrupted=None, turn_complete=None))
        await live_session._handle(None, message)
    assert live_session.recorder.current == 2
    assert sum('"question"' in e for e in ws.events) == 1
    captions = "".join(json.loads(e)["text"] for e in ws.events if '"transcript"' in e)
    assert captions == "Great. Describe a bug you fixed."
    live_session.recorder.save()
    assert db.get_question(session_id, 1)["asked_text"] == "Great."
    assert db.get_question(session_id, 2)["asked_text"] == "Describe a bug you fixed."
