"""Paste an agent's prompt for you — for catching up during the Coding Jam.

    uv run python scripts/catch_up.py summary          # one agent
    uv run python scripts/catch_up.py all              # all four
    uv run python scripts/catch_up.py all --reset      # empty them again (organizers)

Copies the prompt between <!-- PROMPT:START --> and <!-- PROMPT:END --> in agents/<name>_agent.md
into SYSTEM_PROMPT in backend/agents/<name>.py.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_NAMES = ["summary", "web_search", "mock_interview", "review"]

PROMPT_BLOCK = re.compile(r"<!-- PROMPT:START[^>]*-->\s*```text\n(.*?)\n```\s*<!-- PROMPT:END[^>]*-->", re.DOTALL)
SLOT = re.compile(r'^SYSTEM_PROMPT = """.*?"""', re.DOTALL | re.MULTILINE)


def doc_path(name: str, root: Path = ROOT) -> Path:
    return root / "agents" / f"{name}_agent.md"


def code_path(name: str, root: Path = ROOT) -> Path:
    return root / "backend" / "agents" / f"{name}.py"


def read_prompt(name: str, root: Path = ROOT) -> str:
    match = PROMPT_BLOCK.search(doc_path(name, root).read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"No prompt block found in {doc_path(name, root)}")
    prompt = match.group(1).strip()
    if '"""' in prompt or "\\" in prompt:
        raise ValueError(f"The {name} prompt cannot contain triple quotes or backslashes.")
    return prompt


def fill_slot(source: str, prompt: str) -> str:
    if not SLOT.search(source):
        raise ValueError('SYSTEM_PROMPT = """...""" not found.')
    body = f"\n{prompt}\n" if prompt else "\n"
    return SLOT.sub(lambda _: f'SYSTEM_PROMPT = """{body}"""', source, count=1)


def apply(name: str, reset: bool = False, root: Path = ROOT) -> None:
    path = code_path(name, root)
    prompt = "" if reset else read_prompt(name, root)
    path.write_text(fill_slot(path.read_text(encoding="utf-8"), prompt), encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("agent", choices=AGENT_NAMES + ["all"])
    parser.add_argument("--reset", action="store_true", help="empty the prompt instead of filling it")
    args = parser.parse_args(argv)
    for name in AGENT_NAMES if args.agent == "all" else [args.agent]:
        apply(name, reset=args.reset)
        print(f"{'Reset' if args.reset else 'Pasted'} {name} prompt → {code_path(name).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
