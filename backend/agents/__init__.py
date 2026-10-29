"""The four Mentor AI agents.

Each agent module has a `SYSTEM_PROMPT` that starts empty. Participants paste the prompt from
agents/<name>_agent.md into it during the Coding Jam. An agent with an empty prompt is "locked":
the app keeps running, and the features that need it explain how to unlock it.
"""

from typing import Optional

from agents import mock_interview, review, summary, web_search

AGENTS = {
    "summary": summary,
    "web_search": web_search,
    "mock_interview": mock_interview,
    "review": review,
}

INFO = {
    "summary": {"step": 1, "title": "Summary Agent", "icon": "🧭"},
    "web_search": {"step": 2, "title": "Web Search Agent", "icon": "🔎"},
    "mock_interview": {"step": 3, "title": "Mock Interview Agent", "icon": "🎙️"},
    "review": {"step": 4, "title": "Review Agent", "icon": "📝"},
}

# A pasted prompt is a few paragraphs long; anything shorter is treated as "not pasted yet".
MIN_PROMPT_LENGTH = 40

# Text that only appears in the guide page around the prompt — never inside the prompt itself.
WHOLE_PAGE_MARKERS = ("<!-- PROMPT", "## What it does", "## The prompt", "```")
WHOLE_PAGE_MESSAGE = (
    "You pasted more than the prompt (the guide page text came along). "
    "Copy only the text inside the prompt box — between the ``` lines — and paste again."
)


class AgentLockedError(Exception):
    """Raised when a feature needs an agent whose prompt has not been pasted (correctly) yet."""

    def __init__(self, name: str):
        self.name = name
        info = INFO[name]
        problem = paste_problem(name)
        if problem:
            message = f"{info['title']}: {problem} File: backend/agents/{name}.py"
        else:
            message = (
                f"{info['title']} is not active yet. Step {info['step']}: paste its prompt from "
                f"agents/{name}_agent.md into backend/agents/{name}.py."
            )
        super().__init__(message)


def paste_problem(name: str) -> Optional[str]:
    """Explain what is wrong with a pasted prompt, or None if it looks fine (or is still empty)."""
    prompt = AGENTS[name].SYSTEM_PROMPT
    if any(marker in prompt for marker in WHOLE_PAGE_MARKERS):
        return WHOLE_PAGE_MESSAGE
    return None


def is_active(name: str) -> bool:
    return len(AGENTS[name].SYSTEM_PROMPT.strip()) >= MIN_PROMPT_LENGTH and paste_problem(name) is None


def require(*names: str) -> None:
    for name in names:
        if not is_active(name):
            raise AgentLockedError(name)


def status() -> list[dict]:
    return [
        {"name": name, **INFO[name], "active": is_active(name), "problem": paste_problem(name)}
        for name in AGENTS
    ]
