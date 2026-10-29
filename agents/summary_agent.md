# 🧭 Step 1 — Summary Agent

> **Your task:** copy the prompt below and paste it between the triple quotes of `SYSTEM_PROMPT` in
> `backend/agents/summary.py`. Save. The server reloads and the agent turns on.

## What it does

The Summary Agent is **Mentor**, the only agent that talks to you. It reads your resume (the PDF itself — Gemini
reads documents natively), figures out what you want, and explains everything the other agents produce.

It has six jobs, one per task function in `backend/agents/summary.py`:

| Task function | When | What it returns |
|---|---|---|
| `understand_request` | Every message you send in **Find Jobs** | Your search request restated as bullets + "Did I get this right?" |
| `present_jobs` | After the Web Search Agent finds posts | A summary of each post + why it fits your resume |
| `list_topics` | You open a saved job and press **What do I need to know?** | 4–8 topics the interview will test |
| `make_study_plan` | You rate each topic 1–5 | Study first vs. review later, with concrete actions |
| `compose_interview` | After the Web Search Agent researches real interview questions | 7 interview questions (reported + job description + resume deep-dive) |
| `present_review` | After the Review Agent grades your answers | How it went + what to prepare next |

## When it runs

**In the foreground.** You wait for its reply (2–6 seconds). The other agents run in the background while you keep
using the app.

## How it talks to the other agents

```
You ⇄ Summary Agent ──confirmed request──▶ Web Search Agent ──5 job posts──▶ Summary Agent ⇄ You
You ⇄ Summary Agent ──(study done)──▶ Web Search Agent ──reported questions──▶ Summary Agent
      Summary Agent ──7 questions──▶ Mock Interview Agent ──transcripts──▶ Review Agent ──scores──▶ Summary Agent ⇄ You
```

The agents never call each other directly. `backend/orchestrator.py` passes each agent's output to the next one
when a status changes (for example, when you press **Yes, search**).

## Inputs and outputs

| | |
|---|---|
| **Input** | Your resume (PDF / image / text, attached as a file part), the conversation, and whatever the task needs (job posts, topics + ratings, research, review) |
| **Output** | Structured JSON — schemas in `backend/models.py`: `UnderstandingReply`, `JobPresentation`, `TopicList`, `StudyPlan`, `InterviewPlan`, `ReviewPresentation` |
| **Model** | `gemini-2.5-flash` (`GEMINI_MODEL` in `.env`) |

## The prompt

The prompt is the agent's **personality and rules**. The step-by-step instructions for each task (and the JSON shape)
are already written in the task functions — read one to see how they combine.

> 📋 **Copy only the text inside the box below** — not the headings or this note. If you paste the
> whole page, the agent stays locked and its chip says *Fix the paste*.

<!-- PROMPT:START (copy only the lines between the ``` fences) -->
```text
You are Mentor, the Summary Agent of Mentor AI: a career mentor who helps one job seeker find jobs and prepare for interviews. You are the only agent who talks to the user. Three agents work behind you: the Web Search Agent searches the live web, the Mock Interview Agent interviews the user by voice, and the Review Agent grades interview answers. You read the user's resume, make sure you understand what they want, and explain the other agents' results.

How you work:
1. Ground everything in the resume and the job information you are given. Cite specific resume experience (projects, internships, skills) instead of generic praise.
2. Never invent facts about the user, a company, or a job. If something is unknown, say so or ask.
3. Confirm before acting. When you restate what the user wants, ask them to confirm, and ask one clear question when something important is missing.
4. Be honest about gaps. If a job needs a skill the resume does not show, say so kindly and say how to close the gap.
5. Prioritize. Order every list by what matters most for this user.

Style:
- Warm, direct, and encouraging, like a senior mentor who wants the user to get hired.
- Keep messages to the user short: 2 to 6 sentences or a short bulleted list. Use plain words.
- Address the user as "you".

Always follow the TASK instructions in each request and return valid JSON in the requested format.
```
<!-- PROMPT:END -->

## Where to paste it

```python
# backend/agents/summary.py
SYSTEM_PROMPT = """
← paste here
"""
```

## Check that it works

1. The 🧭 chip in the top bar turns green (the app checks `/api/health` every few seconds).
2. **Find Jobs** → **Use sample resume** → type *"Entry-level software engineer in New York, hybrid is fine"* → Send.
3. Mentor replies with your request as bullets and *"Did I get this right?"*.

Stuck? `uv run python scripts/catch_up.py summary` pastes it for you.

## Slide outline

1. **Meet Mentor** — the one agent you talk to; everyone else works behind it.
2. **Multimodal input** — the resume PDF goes straight to Gemini as a file part. No PDF parsing library.
3. **The confirmation loop** — restate → "Did I get this right?" → you correct → repeat. Code (the **Yes, search** button), not the model, decides when to move on.
4. **Prompt = personality, task = instructions** — one system prompt, six task functions, JSON schemas from `models.py`.
5. **Paste it** — `backend/agents/summary.py`, watch the chip turn green.
