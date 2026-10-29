# 🎙️ Step 3 — Mock Interview Agent

> **Your task:** copy the prompt below and paste it between the triple quotes of `SYSTEM_PROMPT` in
> `backend/agents/mock_interview.py`. Save. The server reloads and the agent turns on.

## What it does

The Mock Interview Agent **interviews you out loud** as a senior team member at the company you are applying to.
It asks the 7 questions the Summary Agent wrote, listens to your spoken answers, and transcribes them.

## Two voice paths, one prompt

| | **Live (main path)** | **Turn by turn (fallback)** |
|---|---|---|
| How | Gemini Live API: real-time audio both ways over a WebSocket | Question spoken with TTS → you record your answer → it is transcribed |
| Feels like | A real video call — you can interrupt | A walkie-talkie |
| Model | `gemini-2.5-flash-native-audio-preview-12-2025` | `gemini-2.5-flash-preview-tts` + `gemini-2.5-flash` |
| Code | `backend/voice/live_proxy.py` | `backend/voice/turn_based.py` |
| Switch | `VOICE_MODE=live` in `.env` | `VOICE_MODE=turn`, or the toggle on the interview screen |

## How it knows which answer belongs to which question

The agent has two tools (function calling):

- `next_question(number)` — called right **before** asking each question. The server marks the current question,
  and every transcript fragment of your speech after that is saved to it.
- `end_interview()` — called after the goodbye. The browser lets the audio finish, then hands off to review.

```
Browser mic ─PCM 16 kHz─▶ FastAPI WebSocket ─▶ Gemini Live ─▶ voice PCM 24 kHz ─▶ Browser speaker
                                   │
                    next_question(3) → transcript of your speech saved to question 3
```

The API key stays on the server: the browser only talks to FastAPI.

## Long sessions

7 questions take about 15–20 minutes. A Live audio session normally stops at 15 minutes and a connection lasts about
10, so the config turns on **context window compression** and **session resumption**, and the relay reconnects
automatically and continues from the first unanswered question (as does **Resume interview**).

> **Model note:** the Live model is pinned to `gemini-2.5-flash-native-audio-preview-12-2025`, and every session
> starts with a short *spoken* cue ("Hi, I'm ready to start the interview" — `backend/voice/cues/`) instead of a text
> message. On Gemini 2.5 with tools, a session started by text drops with error 1007 a few seconds in.

## How it talks to the other agents

```
Summary Agent ──7 questions──▶ Mock Interview Agent ──question + transcript pairs──▶ Review Agent
```

## The prompt

`backend/agents/mock_interview.py` adds the session details after your prompt: the company, the role, and the
numbered questions (`interview_brief`).

> 📋 **Copy only the text inside the box below** — not the headings or this note. If you paste the
> whole page, the agent stays locked and its chip says *Fix the paste*.

<!-- PROMPT:START (copy only the lines between the ``` fences) -->
```text
You are the Mock Interview Agent of Mentor AI. You run a realistic spoken mock interview. You play a senior team member at the hiring company: the kind of experienced engineer or manager who sits on the interview panel for this role. The session details below give you the company, the role, and the exact questions.

How to interview:
- This is a voice conversation. Speak naturally and keep each turn short: one question at a time, in 1 to 3 sentences.
- Ask the questions in the given order, in your own natural words, without changing what they test. Do not add new main questions.
- After an answer, you may ask at most one short follow-up if the answer is vague, for example "What was your specific part in that?". Then move on.
- Do not teach, hint, grade, or give feedback during the interview. A neutral "Thanks" or "Got it" is enough. Feedback comes later from the Review Agent.
- If the candidate asks you to repeat or clarify a question, do it briefly. If they say they do not know, reassure them in one sentence and move to the next question.
- Stay in your role as the interviewer. Describe the team and role only with facts from the session details; never invent company facts, people's names, or salary information. If asked something you do not know, say the recruiter will follow up.
- Be professional and friendly: realistic pressure, never hostile.
- Keep the interview moving, about 2 to 3 minutes per question.
```
<!-- PROMPT:END -->

## Where to paste it

```python
# backend/agents/mock_interview.py
SYSTEM_PROMPT = """
← paste here
"""
```

## Check that it works

1. The 🎙️ chip turns green.
2. Open a saved job whose interview is **Ready** → **Start interview**. Allow the microphone. **Use headphones** so
   the interviewer does not hear itself.
3. The interviewer greets you and asks question 1. The question tracker moves as you go; your words appear in the
   live transcript.

No sound or the connection fails? Flip the toggle to **Turn by turn** and try again.
Stuck? `uv run python scripts/catch_up.py mock_interview`

## Slide outline

1. **Multimodal, for real** — voice in, voice out, text transcripts of both.
2. **The relay** — browser ⇄ FastAPI WebSocket ⇄ Gemini Live; why the key stays on the server.
3. **Tools during a conversation** — `next_question(n)` lines up transcripts with questions.
4. **Long sessions** — compression + resumption.
5. **Plan B** — turn-by-turn with TTS + transcription, same prompt.
