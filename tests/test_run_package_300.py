import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from glk300_fixtures import (
    append_index,
    read_index,
    sha256_file,
    write_index,
    write_json,
    write_valid_run,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"
MODEL_PATH = SCRIPTS / "run_package.py"


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def load_model():
    if not MODEL_PATH.is_file():
        pytest.fail("GLK 3.0 complete Run package loader is missing")
    spec = importlib.util.spec_from_file_location("glk_run_package", MODEL_PATH)
    if spec is None or spec.loader is None:
        pytest.fail("cannot load GLK 3.0 Run package loader")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


def test_fixture_writes_real_complete_inventory_with_true_digests(tmp_path):
    fixture = write_valid_run(tmp_path, cells_per_go=2, go_count=2)
    index = read_index(fixture.index_path)
    require_equal(index["index_version"], 1, "index version")
    require_equal(index["prior_index_sha256"], None, "first prior digest")
    require_equal(len(fixture.formal_paths), 23, "formal artifact count")
    require_equal(len(fixture.evidence_paths), 23, "artifact evidence count")
    indexed_formal = {entry["path"]: entry for entry in index["formal_artifacts"]}
    for path in fixture.formal_paths:
        relative = path.relative_to(fixture.root).as_posix()
        require(relative in indexed_formal, f"formal artifact not indexed: {relative}")
        require_equal(indexed_formal[relative]["sha256"], sha256_file(path), relative)
    require(
        not any(entry["path"].startswith("indexes/") for entry in index["formal_artifacts"]),
        "RUN_PACKAGE_INDEX must not list itself",
    )
    for entry in index["evidence_objects"]:
        path = fixture.root / entry["path"]
        require(path.is_file(), f"indexed evidence missing: {entry['path']}")
        require_equal(entry["sha256"], sha256_file(path), entry["path"])


def test_valid_package_loads_from_one_index_head(tmp_path):
    model = load_model()
    fixture = write_valid_run(tmp_path)
    loaded = model.load_run_package(fixture.root)
    require_equal(loaded.root, fixture.root.resolve(), "loaded root")
    require_equal(len(loaded.index_chain), 1, "index chain length")
    require_equal(loaded.index_head_sha256, sha256_file(fixture.index_path), "head digest")
    require_equal(len(loaded.artifacts_by_digest), len(fixture.formal_paths) + 1, "loaded artifacts")


def _mutate_r20(case, fixture):
    index = read_index(fixture.index_path)
    first_entry = index["formal_artifacts"][0]
    first_path = fixture.root / first_entry["path"]
    if case == "omitted":
        first_path.unlink()
    elif case == "extra_unindexed":
        artifact = json.loads(first_path.read_text(encoding="utf-8"))
        artifact["artifact_id"] = "EXTRA-UNINDEXED-D0"
        artifact["artifact_type"] = "D0_RECEIPT"
        write_json(fixture.root / "receipts/EXTRA-UNINDEXED-D0.json", artifact)
    elif case == "wrong_digest":
        first_path.write_bytes(first_path.read_bytes() + b" ")
    elif case == "forked_index":
        prior = sha256_file(fixture.index_path)
        append_index(fixture, version=2, prior_index_sha256=prior, suffix="v2-a")
        append_index(fixture, version=2, prior_index_sha256=prior, suffix="v2-b")
    elif case == "multiple_heads":
        append_index(fixture, version=1, prior_index_sha256=None, suffix="other-v1")
    elif case == "escaping_path":
        first_entry["path"] = "../outside.json"
        write_index(fixture.index_path, index)
    elif case == "unknown_formal_root":
        rogue_path = fixture.root / "rogue" / first_path.name
        rogue_path.parent.mkdir(parents=True)
        first_path.replace(rogue_path)
        first_entry["path"] = rogue_path.relative_to(fixture.root).as_posix()
        write_index(fixture.index_path, index)
    else:
        pytest.fail(f"unknown R20 mutation: {case}")


@pytest.mark.parametrize(
    "case,expected_code",
    [
        ("omitted", "PACKAGE_OBJECT_MISSING"),
        ("extra_unindexed", "EXTRA_UNINDEXED_FORMAL_ARTIFACT"),
        ("wrong_digest", "DIGEST_MISMATCH"),
        ("forked_index", "INDEX_FORK"),
        ("multiple_heads", "MULTIPLE_INDEX_HEADS"),
        ("escaping_path", "PATH_ESCAPE"),
        ("unknown_formal_root", "UNKNOWN_FORMAL_ROOT"),
    ],
)
def test_r20_package_integrity_failures_have_stable_codes(tmp_path, case, expected_code):
    model = load_model()
    fixture = write_valid_run(tmp_path)
    _mutate_r20(case, fixture)
    with pytest.raises(model.PackageError) as captured:
        model.load_run_package(fixture.root)
    require_equal(captured.value.code, expected_code, case)


def test_symlinked_formal_artifact_is_rejected_before_read(tmp_path):
    model = load_model()
    fixture = write_valid_run(tmp_path)
    target = fixture.formal_paths[0]
    if os.name == "nt":
        external = fixture.root.parent / "outside-formal-root"
        shutil.copytree(target.parent, external)
        shutil.rmtree(target.parent)
        result = subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(target.parent), str(external)],
            text=True,
            capture_output=True,
            check=False,
        )
        require_equal(result.returncode, 0, "junction creation")
    else:
        external = fixture.root.parent / "outside-artifact.json"
        shutil.copyfile(target, external)
        target.unlink()
        target.symlink_to(external)
    with pytest.raises(model.PackageError) as captured:
        model.load_run_package(fixture.root)
    require_equal(captured.value.code, "SYMLINK_FORBIDDEN", "symlink rejection")


def test_linear_index_chain_is_ordered_and_requires_consecutive_versions(tmp_path):
    model = load_model()
    fixture = write_valid_run(tmp_path)
    prior = sha256_file(fixture.index_path)
    second = append_index(fixture, version=2, prior_index_sha256=prior, suffix="v2")
    loaded = model.load_run_package(fixture.root)
    require_equal(
        tuple(index["index_version"] for index in loaded.index_chain),
        (1, 2),
        "linear index versions",
    )
    require_equal(loaded.index_head_sha256, sha256_file(second), "second index head")

    second.unlink()
    append_index(fixture, version=3, prior_index_sha256=prior, suffix="v3")
    with pytest.raises(model.PackageError) as captured:
        model.load_run_package(fixture.root)
    require_equal(captured.value.code, "INDEX_VERSION_GAP", "version gap")


def test_unknown_prior_index_digest_is_rejected(tmp_path):
    model = load_model()
    fixture = write_valid_run(tmp_path)
    append_index(fixture, version=2, prior_index_sha256="0" * 64, suffix="v2")
    with pytest.raises(model.PackageError) as captured:
        model.load_run_package(fixture.root)
    require_equal(captured.value.code, "INDEX_PRIOR_NOT_FOUND", "unknown prior")


def test_unindexed_evidence_is_rejected_by_exact_inventory(tmp_path):
    model = load_model()
    fixture = write_valid_run(tmp_path)
    write_json(fixture.root / "evidence/extra.json", {"result": "UNINDEXED"})
    with pytest.raises(model.PackageError) as captured:
        model.load_run_package(fixture.root)
    require_equal(captured.value.code, "EXTRA_UNINDEXED_EVIDENCE", "extra evidence")


def test_run_package_index_cannot_list_itself_as_formal_inventory(tmp_path):
    model = load_model()
    fixture = write_valid_run(tmp_path)
    index = read_index(fixture.index_path)
    index["formal_artifacts"].append(
        {
            "path": fixture.index_path.relative_to(fixture.root).as_posix(),
            "sha256": "0" * 64,
            "artifact_type": "RUN_PACKAGE_INDEX",
        }
    )
    write_index(fixture.index_path, index)
    with pytest.raises(model.PackageError) as captured:
        model.load_run_package(fixture.root)
    require_equal(captured.value.code, "INDEX_SELF_LISTED", "self-listed index")


def test_loaded_subject_is_deep_frozen_against_memory_and_disk_mutation(tmp_path):
    model = load_model()
    fixture = write_valid_run(tmp_path)
    loaded = model.load_run_package(fixture.root)
    index = read_index(fixture.index_path)
    entry = index["formal_artifacts"][0]
    artifact = loaded.artifacts_by_digest[entry["sha256"]]
    artifact_id = artifact["artifact_id"]
    evidence_digest, evidence_bytes = next(iter(loaded.evidence_by_digest.items()))

    with pytest.raises(TypeError):
        artifact["artifact_id"] = "MUTATED-IN-MEMORY"
    require(isinstance(artifact["evidence_refs"], tuple), "nested list was not frozen")

    path = fixture.root / entry["path"]
    path.write_text("{}\n", encoding="utf-8", newline="\n")
    evidence_path = fixture.root / index["evidence_objects"][0]["path"]
    evidence_path.write_bytes(b"changed after load")
    require_equal(artifact["artifact_id"], artifact_id, "artifact snapshot")
    require_equal(loaded.evidence_by_digest[evidence_digest], evidence_bytes, "evidence snapshot")
