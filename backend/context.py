"""Turns database rows into plain-text context blocks that the agents' task prompts embed."""

import json
from datetime import date, timedelta
from typing import Optional

import config


def today() -> date:
    return date.today()


def lookback_cutoff() -> date:
    return today() - timedelta(days=config.JOB_LOOKBACK_DAYS)


def describe_preferences(preferences: dict) -> str:
    return json.dumps(preferences, indent=2, ensure_ascii=False)


def describe_job(job: dict, include_description: bool = True) -> str:
    lines = [
        f"Title: {job.get('title')}",
        f"Company: {job.get('company')}",
        f"Location: {job.get('location') or 'unknown'}",
        f"Level: {job.get('level') or 'unknown'}",
        f"Posted: {job.get('posted_date') or 'unknown'}",
        f"URL: {job.get('url') or 'none'}",
    ]
    if job.get("fit_score") is not None:
        lines.append(f"Fit score: {job['fit_score']}/100")
    if include_description:
        lines.append(f"Job description:\n\"\"\"\n{(job.get('job_description') or '').strip()}\n\"\"\"")
    return "\n".join(lines)


def describe_jobs(jobs: list[dict]) -> str:
    return "\n\n".join(f"### Job {i}\n{describe_job(job)}" for i, job in enumerate(jobs, start=1))


def describe_conversation(messages: list[dict]) -> str:
    speaker = {"user": "USER", "feedback": "USER (feedback on results)", "summary": "YOU"}
    return "\n".join(f"{speaker.get(m['role'], m['role'].upper())}: {m['content']}" for m in messages)


def describe_research(research: Optional[dict]) -> str:
    if not research or not research.get("questions"):
        return "No reported interview questions were found online."
    lines = [f"Process notes: {research.get('process_notes') or 'none'}"]
    for i, q in enumerate(research["questions"], start=1):
        lines.append(f"{i}. {q['question']} (source: {q.get('source_url') or 'unknown'}; {q.get('context') or ''})")
    return "\n".join(lines)
