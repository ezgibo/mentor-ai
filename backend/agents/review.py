"""Review Agent — grades each answer as a senior employee of the company would.

Runs in the background after the interview. Each answer gets four rubric scores (1-10); the
overall 1-10 score is the rounded average, computed in code so it is consistent run to run.
"""

import gemini
from context import describe_job
from models import InterviewReview

# ╔═══════════════════════════════════════════════════════════════════════╗
# ║ STEP 4 — Paste the Review Agent prompt between the triple quotes.    ║
# ║ Copy it from agents/review_agent.md → "The prompt".                  ║
# ╚═══════════════════════════════════════════════════════════════════════╝
SYSTEM_PROMPT = """
"""


async def review_interview(profile: dict, job: dict, questions: list[dict]) -> InterviewReview:
    """Grade every question + transcript pair. Raises ValueError if a question is left unreviewed."""
    pairs = "\n\n".join(
        f"### Question {q['position']} ({q['source']})\n"
        f"Question: {q['question']}\n"
        f"What a strong answer must show: {q.get('what_it_tests') or 'not specified'}\n"
        f"Candidate's answer (speech transcript):\n\"\"\"\n{(q.get('transcript') or '').strip() or '(no answer)'}\n\"\"\""
        for q in questions
    )
    task = f"""TASK: REVIEW THE MOCK INTERVIEW
The candidate's resume is attached. The job:
{describe_job(job)}

Review EVERY question below (use its number as `question_number`). For each, score the four
rubric criteria from 1 to 10, then write what was good, what to prepare to answer better, and
what a senior interviewer at this company listens for on this question.
Then write an overall summary, the top strengths, and the focus areas.

{pairs}"""
    review = await gemini.generate_json(
        system_prompt=SYSTEM_PROMPT,
        contents=[gemini.resume_part(profile), gemini.text_part(task)],
        schema=InterviewReview,
        temperature=0.2,
    )
    reviewed = {r.question_number for r in review.reviews}
    missing = [q["position"] for q in questions if q["position"] not in reviewed]
    if missing:
        raise ValueError(f"The Review Agent skipped question(s) {missing}. Press Retry.")
    return review
