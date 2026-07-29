import hashlib
import json
from pathlib import Path


EXCLUDED_PARTS = {
    ".git",
    ".codex",
    ".pytest_cache",
    "__pycache__",
    ".worktrees",
    ".venv",
}


def is_excluded(path: Path) -> bool:
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return True
    return path.suffix == ".pyc"


def release_files(root: Path, output: Path | None = None):
    for path in sorted(root.rglob("*")):
        if output and path.resolve() == output.resolve():
            continue
        if path.is_file() and not is_excluded(path.relative_to(root)):
            yield path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_hash_manifest(root: Path, output: Path | None = None):
    files = {}
    for path in release_files(root, output):
        relative = path.relative_to(root).as_posix()
        if relative == "FILE_HASHES.json":
            continue
        files[relative] = sha256(path)
    return {"algorithm": "sha256", "version": "2.3.1", "files": files}


def write_hash_manifest(root: Path, output: Path | None = None):
    manifest = build_hash_manifest(root, output)
    destination = root / "FILE_HASHES.json"
    destination.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination
