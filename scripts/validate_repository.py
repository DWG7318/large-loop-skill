from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
VERSION = "3.2.0"
COLLECTION_NAME = "Graph Loop Skill Collection"
EXPECTED_SKILLS = (
    "graph-loop-skill",
    "glk-design-graph",
    "glk-run-graph",
    "glk-close-run",
)
REQUIRED_ASSETS = (
    "skills/glk-design-graph/assets/GLK-GRAPH.template.md",
    "skills/glk-design-graph/assets/GLK-ROSTER.template.md",
    "skills/glk-design-graph/assets/GLK-RUN.template.md",
)
RETIRED_FILES = ("SKILL.md", "SPEC.md", "FILE_HASHES.json")
RETIRED_PREFIXES = ("agents/", "glk/", "tools/")
EXCLUDED_DIRS = {".git", ".codex", ".worktrees", "__pycache__", ".pytest_cache"}
EXCLUDED_FILES = {"MANIFEST.json"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_files(root: Path) -> list[Path]:
    values: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative.as_posix() in EXCLUDED_FILES or path.suffix == ".pyc":
            continue
        values.append(relative)
    return sorted(values, key=lambda item: item.as_posix())


def manifest_payload(root: Path) -> dict:
    return {
        "name": COLLECTION_NAME,
        "version": VERSION,
        "skill_count": len(EXPECTED_SKILLS),
        "excludes": sorted(EXCLUDED_FILES),
        "files": [
            {"path": relative.as_posix(), "sha256": sha256(root / relative)}
            for relative in release_files(root)
        ],
    }


def write_manifest(root: Path) -> None:
    text = json.dumps(manifest_payload(root), ensure_ascii=False, indent=2) + "\n"
    (root / "MANIFEST.json").write_bytes(text.encode("utf-8"))


def check(condition: bool, code: str, detail: str, errors: list[str]) -> None:
    if not condition:
        errors.append(f"{code}: {detail}")


def utf8_lf_text(path: Path, errors: list[str]) -> str:
    try:
        data = path.read_bytes()
        if b"\r\n" in data:
            errors.append(f"GLK_REPO_LF: {path.relative_to(ROOT).as_posix()}")
        return data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"GLK_REPO_UTF8: {path}: {exc}")
        return ""


def frontmatter_name(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    match = re.search(r"^name:\s*([a-z0-9-]+)\s*$", text, re.MULTILINE)
    return match.group(1) if match else None


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    required = (
        "VERSION",
        "README.md",
        "README.zh-CN.md",
        "MIGRATION.md",
        "CHANGELOG.md",
        "MANIFEST.json",
        "VALIDATION-REPORT.md",
        ".github/workflows/validate.yml",
        *REQUIRED_ASSETS,
    )
    for relative in required:
        check((root / relative).is_file(), "GLK_REPO_REQUIRED_FILE", relative, errors)
    for relative in RETIRED_FILES:
        check(not (root / relative).exists(), "GLK_REPO_RETIRED_PATH", relative, errors)
    released = {path.as_posix() for path in release_files(root)}
    for prefix in RETIRED_PREFIXES:
        check(not any(path.startswith(prefix) for path in released), "GLK_REPO_RETIRED_PREFIX", prefix, errors)
    if errors:
        return errors

    version = utf8_lf_text(root / "VERSION", errors).strip()
    check(version == VERSION, "GLK_REPO_VERSION", repr(version), errors)

    actual_skills = tuple(sorted(path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()))
    check(
        actual_skills == tuple(sorted(EXPECTED_SKILLS)),
        "GLK_REPO_SKILL_SET",
        repr(actual_skills),
        errors,
    )
    for name in EXPECTED_SKILLS:
        path = SKILLS_ROOT / name / "SKILL.md"
        check(path.is_file(), "GLK_REPO_SKILL_FILE", name, errors)
        if path.is_file():
            text = utf8_lf_text(path, errors)
            check(frontmatter_name(text) == name, "GLK_REPO_SKILL_NAME", name, errors)
            check("description: Use when " in text, "GLK_REPO_SKILL_DESCRIPTION", name, errors)

    main = utf8_lf_text(SKILLS_ROOT / "graph-loop-skill" / "SKILL.md", errors)
    for name in EXPECTED_SKILLS[1:]:
        check(main.count(f"`${name}`") == 1, "GLK_REPO_ROUTE", name, errors)
    check("`$small-loop-skill`" in main, "GLK_REPO_SLK_ROUTE", "main", errors)

    for relative in ("README.md", "README.zh-CN.md", "MIGRATION.md", "CHANGELOG.md"):
        utf8_lf_text(root / relative, errors)

    try:
        manifest = json.loads(utf8_lf_text(root / "MANIFEST.json", errors))
    except json.JSONDecodeError as exc:
        errors.append(f"GLK_REPO_MANIFEST_JSON: {exc}")
        return errors

    check(manifest.get("name") == COLLECTION_NAME, "GLK_REPO_MANIFEST_NAME", repr(manifest.get("name")), errors)
    check(manifest.get("version") == VERSION, "GLK_REPO_MANIFEST_VERSION", repr(manifest.get("version")), errors)
    check(manifest.get("skill_count") == len(EXPECTED_SKILLS), "GLK_REPO_MANIFEST_SKILLS", repr(manifest.get("skill_count")), errors)
    check(manifest.get("excludes") == sorted(EXCLUDED_FILES), "GLK_REPO_MANIFEST_EXCLUDES", repr(manifest.get("excludes")), errors)
    listed = {
        item.get("path"): item.get("sha256")
        for item in manifest.get("files", [])
        if isinstance(item, dict)
    }
    actual = {path.as_posix() for path in release_files(root)}
    check(set(listed) == actual, "GLK_REPO_MANIFEST_SET", f"missing={sorted(actual-set(listed))}; extra={sorted(set(listed)-actual)}", errors)
    for relative, expected in listed.items():
        path = root / relative
        if path.is_file():
            check(sha256(path) == expected, "GLK_REPO_MANIFEST_HASH", relative, errors)
    return errors


def main(argv: Iterable[str]) -> int:
    args = list(argv)
    if args == ["--write-manifest"]:
        write_manifest(ROOT)
        print("WROTE: MANIFEST.json")
        return 0
    if args:
        print("FAIL GLK_REPO_USAGE: optional argument is --write-manifest", file=sys.stderr)
        return 2
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    print("PASS: GLK 3.2 skill collection structure, identity, and Manifest are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
