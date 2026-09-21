from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".codex", ".worktrees", "__pycache__", ".pytest_cache"}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release_paths() -> set[str]:
    values: set[str] = set()
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative.as_posix() == "MANIFEST.json" or path.suffix == ".pyc":
            continue
        values.add(relative.as_posix())
    return values


def test_repository_validator_passes_for_the_320_collection() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_repository.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: GLK 4.0 skill collection" in result.stdout


def test_manifest_exactly_covers_repository_bytes_except_itself() -> None:
    manifest = json.loads(read("MANIFEST.json"))
    assert manifest["name"] == "Graph Loop Skill Collection"
    assert manifest["version"] == "4.0.0"
    assert manifest["skill_count"] == 4
    assert manifest["excludes"] == ["MANIFEST.json"]
    listed = {item["path"]: item["sha256"] for item in manifest["files"]}
    assert set(listed) == release_paths()
    for relative, digest in listed.items():
        assert sha256(ROOT / relative) == digest, relative


def test_readmes_explain_the_current_method_without_old_runtime() -> None:
    english = read("README.md")
    chinese = read("README.zh-CN.md")
    for text in (english, chinese):
        for marker in ("4.0.0", "GLK", "DAG", "Fusion", "SLK", "Supervisor"):
            assert marker in text
        assert "GLK-GRAPH.md" in text
        assert "GLK-ROSTER.md" in text
        assert "GLK-RUN-<RUN-ID>.md" in text
    assert "multi-start" in english
    assert "four sibling Skill directories" in english
    assert "多个起点" in chinese
    assert "4个并列Skill目录" in chinese


def test_ci_runs_collection_validation_on_windows_and_ubuntu() -> None:
    workflow = read(".github/workflows/validate.yml")
    assert "ubuntu-latest" in workflow
    assert "windows-latest" in workflow
    assert "python scripts/validate_repository.py" in workflow
    assert "python scripts/quick_validate.py skills" in workflow
    assert "python -m pytest -q" in workflow


def test_required_assets_and_lf_policy_are_present() -> None:
    required = (
        "skills/glk-design-graph/assets/GLK-GRAPH.template.md",
        "skills/glk-design-graph/assets/GLK-ROSTER.template.md",
        "skills/glk-design-graph/assets/GLK-RUN.template.md",
    )
    for relative in required:
        assert (ROOT / relative).is_file(), relative
    assert "* text=auto eol=lf" in read(".gitattributes")


def test_old_active_kernel_is_absent_after_reconstruction() -> None:
    for relative in ("SKILL.md", "SPEC.md", "FILE_HASHES.json"):
        assert not (ROOT / relative).exists(), relative
    released = release_paths()
    for prefix in ("agents/", "glk/", "tools/", "tests/support/"):
        assert not any(path.startswith(prefix) for path in released), prefix
    assert {path.name for path in (ROOT / "scripts").iterdir() if path.is_file()} == {
        "quick_validate.py",
        "validate_repository.py",
    }
    assert {path.name for path in (ROOT / "tests").iterdir() if path.is_file()} == {
        "skill_testkit.py",
        "test_repository_320.py",
        "test_skill_collection_320.py",
    }
