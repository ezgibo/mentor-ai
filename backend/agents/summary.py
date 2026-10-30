"""Summary Agent — the only agent that talks to the user.

It reads the resume, confirms what the user wants, explains what the other agents found,
builds the study plan, writes the mock interview, and presents the review.
Runs in the foreground: the user waits for its reply.
"""

import config
import gemini
from context import (
    describe_conversation,
    describe_job,
    describe_jobs,
    describe_preferences,
    describe_research,
)
from models import (
    InterviewPlan,
    InterviewReview,
    JobPresentation,
    ReviewPresentation,
    StudyPlan,
    TopicList,
    UnderstandingReply,
)

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ STEP 1 — Paste the Summary Agent prompt between the triple quotes.    ║
# ║ Copy it from agents/summary_agent.md → "The prompt".                  ║
# ╚════════════════════════════════════════════════════════════════════════╝
SYSTEM_PROMPT = """
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
"""


async def understand_request(profile: dict, conversation: list[dict]) -> UnderstandingReply:
    """Flow 1: read the resume + chat so far, restate what jobs the user wants, ask to confirm."""
    task = f"""TASK: UNDERSTAND THE JOB SEARCH REQUEST
The user's resume is attached. The conversation so far is below.

Update your understanding of the jobs the user wants. In `reply`:
- Restate the understanding as a short bulleted list: role, level, location, work mode, must-haves.
- Name 2-3 resume strengths you will match jobs against.
- End with "Did I get this right?" — or, if role, level, or location is still unknown, ask for it instead.
Set ready_to_confirm to true only when role, level, and location are all known.

CONVERSATION:
{describe_conversation(conversation)}"""
    return await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.resume_part(profile), gemini.text_part(task)],
        schema=UnderstandingReply,
    )


async def present_jobs(profile: dict, preferences: dict, jobs: list[dict], search_note: str = "") -> JobPresentation:
    """Flow 1: explain the Web Search Agent's results (best fit first) and why each fits the resume."""
    task = f"""TASK: PRESENT THE JOB POSTS THE WEB SEARCH AGENT FOUND
The user's resume is attached. Their confirmed request:
{describe_preferences(preferences)}

The Web Search Agent found these {len(jobs)} posts, ranked best fit first:
{describe_jobs(jobs)}

Search note from the Web Search Agent (mention it briefly if not empty): {search_note or "none"}

For EVERY job (use its number as `index`), write a one-to-two sentence summary and why it is
relevant to this user, citing specific resume experience. Be honest about gaps.
In `message`, introduce the results in 1-2 sentences and invite the user to save the ones they
like or tell you what to change."""
    return await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.resume_part(profile), gemini.text_part(task)],
        schema=JobPresentation,
    )


async def list_topics(profile: dict, job: dict) -> TopicList:
    """Flow 2: what this job expects the user to know for the interview."""
    task = f"""TASK: LIST WHAT THE USER MUST KNOW FOR THIS INTERVIEW
The user's resume is attached. The job:
{describe_job(job)}

List 4 to 8 topics the interview for this job will test (technical concepts, tools, and
behavioral themes). For each, say which part of the job description requires it and what in
the resume shows experience with it (or "None found").
In `message`, briefly explain the list and ask the user to rate how well they know each topic
from 1 (never used it) to 5 (could teach it)."""
    return await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.resume_part(profile), gemini.text_part(task)],
        schema=TopicList,
    )


async def make_study_plan(profile: dict, job: dict, topics: list[dict]) -> StudyPlan:
    """Flow 2: turn the user's self-ratings into what to study first vs. review later."""
    rated = "\n".join(
        f"{i}. {t['name']} — self-rating {t.get('self_rating') or 'not rated'}/5 "
        f"(resume evidence: {t.get('resume_evidence') or 'none'})"
        for i, t in enumerate(topics, start=1)
    )
    task = f"""TASK: BUILD A STUDY PLAN
The user's resume is attached. The job:
{describe_job(job, include_description=False)}

Topics with the user's self-ratings (1 = never used it, 5 = could teach it):
{rated}

For EVERY topic (use its number as `topic_number`): set priority to "study_first" for weak or
critical topics and "review_later" for strong ones, and give 2-3 concrete study actions.
In `message`, explain the order in 2-3 sentences and remind the user to press
"I'm done studying" when they are ready for the mock interview."""
    return await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.resume_part(profile), gemini.text_part(task)],
        schema=StudyPlan,
    )


async def compose_interview(profile: dict, job: dict, research: dict) -> InterviewPlan:
    """Flow 2: write the mock interview from reported questions, JD concepts, and the resume."""
    count = config.QUESTION_COUNT
    task = f"""TASK: WRITE THE MOCK INTERVIEW
The user's resume is attached. The job:
{describe_job(job)}

What the Web Search Agent found about this company's real interviews:
{describe_research(research)}

Write exactly {count} questions, in the order they should be asked, mixing three sources:
- "reported": questions candidates reported for this company/role (copy source_url). Use the
  relevant ones first; skip any that do not fit this role.
- "jd_concept": core concepts the job description requires.
- "resume_deep_dive": deep-dive questions on specific projects or experience in the resume.
Start with one warm-up resume question. Include at least one behavioral question.
Each question must be answerable out loud in about 2-3 minutes.
In `message`, tell the user what the interview will cover in 2 sentences."""
    return await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.resume_part(profile), gemini.text_part(task)],
        schema=InterviewPlan,
    )


async def present_review(job: dict, review: InterviewReview, scores: list[int]) -> ReviewPresentation:
    """Flow 2: present the Review Agent's grading and tell the user what to prepare next."""
    per_question = "\n".join(
        f"Q{r.question_number}: score {score}/10 — strengths: {r.strengths} — improve: {r.improvements}"
        for r, score in zip(review.reviews, scores)
    )
    task = f"""TASK: PRESENT THE INTERVIEW REVIEW
The job:
{describe_job(job, include_description=False)}

The Review Agent's results:
Overall: {review.overall_summary}
Top strengths: {', '.join(review.top_strengths)}
Focus areas: {', '.join(review.focus_areas)}
{per_question}

In `message`, summarize how the interview went in 3-4 encouraging but honest sentences.
In `prepare_next`, list 3-5 concrete things to prepare next, most important first."""
    return await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.text_part(task)],
        schema=ReviewPresentation,
    )
