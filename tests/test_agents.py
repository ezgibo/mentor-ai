"""Paste slots: agents start locked, the catch-up script fills/resets prompts, prompts are paste-safe."""

import shutil

import pytest

import agents
from scripts import catch_up


def test_all_agents_start_locked_in_the_repo():
    """The starter must ship with empty prompts — pasting them is the participant's job."""
    for name in agents.AGENTS:
        assert not agents.is_active(name), f"{name} prompt should be empty in the starter repo"


def test_require_raises_with_paste_instructions():
    with pytest.raises(agents.AgentLockedError) as error:
        agents.require("web_search")
    assert "Step 2" in str(error.value) and "backend/agents/web_search.py" in str(error.value)


def test_active_agents_fixture_unlocks(active_agents):
    agents.require("summary", "web_search", "mock_interview", "review")
    assert all(a["active"] for a in agents.status())


def test_whole_page_paste_keeps_agent_locked_with_a_fix_hint(monkeypatch):
    from agents import review
    page = (catch_up.doc_path("review")).read_text()
    monkeypatch.setattr(review, "SYSTEM_PROMPT", page)
    assert not agents.is_active("review")
    assert "only the text inside the prompt box" in agents.paste_problem("review")
    with pytest.raises(agents.AgentLockedError, match="pasted more than the prompt"):
        agents.require("review")
    assert next(a for a in agents.status() if a["name"] == "review")["problem"]


def test_clean_prompt_has_no_paste_problem(monkeypatch):
    from agents import review
    monkeypatch.setattr(review, "SYSTEM_PROMPT", catch_up.read_prompt("review"))
    assert agents.is_active("review") and agents.paste_problem("review") is None


@pytest.mark.parametrize("name", catch_up.AGENT_NAMES)
def test_every_doc_has_a_paste_safe_prompt(name):
    prompt = catch_up.read_prompt(name)
    assert len(prompt) >= agents.MIN_PROMPT_LENGTH
    assert not any(marker in prompt for marker in agents.WHOLE_PAGE_MARKERS)


@pytest.mark.parametrize("name", catch_up.AGENT_NAMES)
def test_catch_up_fills_and_resets_a_copy(name, tmp_path):
    for folder in ("agents", "backend/agents"):
        shutil.copytree(catch_up.ROOT / folder, tmp_path / folder)

    catch_up.apply(name, root=tmp_path)
    filled = catch_up.code_path(name, tmp_path).read_text()
    assert catch_up.read_prompt(name) in filled
    compile(filled, name, "exec")  # still valid Python

    catch_up.apply(name, reset=True, root=tmp_path)
    assert catch_up.code_path(name, tmp_path).read_text() == catch_up.code_path(name).read_text()
