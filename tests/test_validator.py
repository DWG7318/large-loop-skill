import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def copy_repo(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(
            ".git", ".codex", ".pytest_cache", "__pycache__", "*.pyc"
        ),
    )
    return target


def run_validator(root: Path):
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "glk/scripts/validate_glk.py", "."],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_repository_validator_passes_current_tree():
    result = run_validator(ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: GLK 2.3.1" in result.stdout


def test_repository_pins_lf_for_cross_platform_hashes():
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in attributes.splitlines()


def test_validator_rejects_version_drift(tmp_path):
    root = copy_repo(tmp_path)
    (root / "VERSION").write_text("2.3.0\n", encoding="utf-8")
    result = run_validator(root)
    assert result.returncode != 0
    assert "version" in result.stdout.lower() + result.stderr.lower()


def test_validator_rejects_missing_ci_contract(tmp_path):
    root = copy_repo(tmp_path)
    (root / ".github/workflows/validate.yml").unlink()
    result = run_validator(root)
    assert result.returncode != 0
    assert "missing required files" in (result.stdout + result.stderr).lower()


def test_validator_rejects_obsolete_queue_and_legacy_control_role(tmp_path):
    root = copy_repo(tmp_path)
    with (root / "SPEC.md").open("a", encoding="utf-8") as handle:
        handle.write("\nREADY queue controlled by Grapher\n")
    result = run_validator(root)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "forbidden" in output.lower()


def test_validator_scans_all_normative_guidance(tmp_path):
    root = copy_repo(tmp_path)
    with (root / "README.zh-CN.md").open("a", encoding="utf-8") as handle:
        handle.write("\nREADY queue\n")
    result = run_validator(root)
    assert result.returncode != 0
    assert "forbidden" in (result.stdout + result.stderr).lower()


def test_validator_rejects_schema_invalid_template(tmp_path):
    root = copy_repo(tmp_path)
    path = root / "glk" / "templates" / "RUN_CONTRACT.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["run_supervisor_binding"]
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    result = run_validator(root)
    assert result.returncode != 0
    assert "schema" in (result.stdout + result.stderr).lower()


def test_validator_rejects_cache_artifacts(tmp_path):
    root = copy_repo(tmp_path)
    cache = root / "glk" / "scripts" / "__pycache__"
    cache.mkdir()
    (cache / "bad.pyc").write_bytes(b"cache")
    result = run_validator(root)
    assert result.returncode != 0
    assert "cache" in (result.stdout + result.stderr).lower()


def test_release_builder_emits_clean_integrity_checked_zip(tmp_path):
    output = tmp_path / "GLK-2.3.1.zip"
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, "glk/scripts/build_release.py", str(output)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
    assert any(name.endswith("FILE_HASHES.json") for name in names)
    assert not any(
        forbidden in name
        for name in names
        for forbidden in [".git/", ".codex/", "__pycache__/", ".pytest_cache/"]
    )


def test_release_builder_writes_hash_manifest_with_lf(tmp_path):
    root = copy_repo(tmp_path)
    output = tmp_path / "GLK-2.3.1.zip"
    result = subprocess.run(
        [sys.executable, str(root / "glk/scripts/build_release.py"), str(output)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert b"\r\n" not in (root / "FILE_HASHES.json").read_bytes()


def test_release_builder_never_archives_its_own_output_from_another_cwd(tmp_path):
    root = copy_repo(tmp_path)
    output = root / "dist" / "GLK-2.3.1.zip"
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(root / "glk/scripts/build_release.py"), str(output)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
    assert not any(name.endswith("GLK-2.3.1.zip") for name in names)
