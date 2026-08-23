from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
EXPECTED_CHILDREN = ("glk-design-graph", "glk-run-graph", "glk-close-run")
EXPECTED_SKILLS = ("graph-loop-skill", *EXPECTED_CHILDREN)


def read_skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def assert_skill_shape(name: str) -> None:
    text = read_skill(name)
    assert text.startswith("---\n"), name
    frontmatter, body = text[4:].split("\n---\n", 1)
    assert re.search(rf"^name:\s*{re.escape(name)}\s*$", frontmatter, re.MULTILINE), name
    assert "description: Use when " in frontmatter, name
    assert body.strip(), name
    assert len(text.splitlines()) <= 100, name
