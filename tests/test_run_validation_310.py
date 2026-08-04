import copy
import importlib
import json
import sys
from pathlib import Path

import pytest
import yaml

import glk300_fixtures as fixtures


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"
TEMPLATES = ROOT / "glk" / "templates"
NEW_TYPES = (
    "WORKER_CHECKER_WAKE_BINDING",
    "DEVICE_CAPACITY_PROFILE",
    "CUMULATIVE_ENGINEERING_LOAD",
    "CELL_WORK_ESTIMATE",
    "CELL_CAPACITY_GATE",
)


@pytest.fixture
def modules():
    sys.path.insert(0, str(SCRIPTS))
    for name in ("run_package", "run_validation"):
        sys.modules.pop(name, None)
    try:
        yield importlib.import_module("run_package"), importlib.import_module("run_validation")
    finally:
        sys.path.remove(str(SCRIPTS))


def _template(name):
    return yaml.safe_load((TEMPLATES / f"{name}.yaml").read_text(encoding="utf-8"))


def _write_artifact(root, value):
    path = root / "controls" / f"{value['artifact_id']}.json"
    fixtures.write_json(path, value)
    evidence_refs = set(value.get("evidence_refs", ()))
    for field_value in value.values():
        if isinstance(field_value, (list, tuple)):
            evidence_refs.update(
                item for item in field_value if isinstance(item, str) and item.startswith("evidence/")
            )
    for evidence_ref in evidence_refs:
        fixtures.write_json(root / evidence_ref, {"artifact_id": value["artifact_id"], "observed": True})
    return path


def _all_formal(root):
    return tuple(
        sorted(
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".json", ".yaml", ".yml"}
            and path.relative_to(root).parts[0] not in {"indexes", "evidence", "simulation"}
        )
    )


def _reindex(case):
    formal = _all_formal(case.root)
    document = fixtures._index_document(
        case.root,
        formal,
        tuple(sorted(path for path in (case.root / "evidence").rglob("*") if path.is_file())),
        version=1,
        prior_index_sha256=None,
        suffix="v1",
    )
    fixtures.write_index(case.index_path, document)


def _operational_case(tmp_path):
    case = fixtures.write_valid_run(tmp_path, cells_per_go=1, go_count=1)
    root = case.root

    old_monitor = next(
        path
        for path in _all_formal(root)
        if yaml.safe_load(path.read_text(encoding="utf-8")).get("artifact_type") == "MONITOR_CONTROL"
    )
    old_monitor_value = yaml.safe_load(old_monitor.read_text(encoding="utf-8"))
    for evidence_ref in old_monitor_value.get("evidence_refs", ()):
        (root / evidence_ref).unlink()
    monitor = _template("MONITOR_CONTROL")
    fixtures.write_json(old_monitor, monitor)
    for evidence_ref in monitor["evidence_refs"]:
        fixtures.write_json(root / evidence_ref, {"artifact_id": monitor["artifact_id"], "observed": True})

    values = {name: _template(name) for name in NEW_TYPES}
    paths = {name: _write_artifact(root, value) for name, value in values.items()}
    gate_digest = fixtures.sha256_file(paths["CELL_CAPACITY_GATE"])
    binding = values["WORKER_CHECKER_WAKE_BINDING"]
    binding["capacity_gate_sha256"] = gate_digest
    fixtures.write_json(paths["WORKER_CHECKER_WAKE_BINDING"], binding)

    attempts = []
    for level in (1, 2, 3):
        attempt = _template("WAKE_ATTEMPT")
        attempt["artifact_id"] = f"WAKE-ATTEMPT-GO-001-CELL-001-R1-L{level}"
        attempt["candidate_id"] = attempt["artifact_id"]
        attempt["level"] = level
        attempt["outcome"] = "FAILED"
        attempt["error_codes"] = ["WAKE_ACK_TIMEOUT"]
        attempt["evidence_refs"] = [f"evidence/wake/attempt-l{level}.json"]
        attempts.append(_write_artifact(root, attempt))
    pending = _template("PENDING_WAKE")
    pending["attempt_refs"] = [path.relative_to(root).as_posix() for path in attempts]
    _write_artifact(root, pending)

    _reindex(case)
    return case


def _artifact_path(root, artifact_type, occurrence=0):
    matches = []
    for path in _all_formal(root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("artifact_type") == artifact_type:
            matches.append(path)
    return matches[occurrence]


def _mutate(case, artifact_type, mutate, occurrence=0):
    path = _artifact_path(case.root, artifact_type, occurrence)
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(value)
    fixtures.write_json(path, value)
    _reindex(case)


def _codes(report):
    return {issue.code for issue in report.issues}


def test_real_indexed_operational_package_passes(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    package = package_module.load_run_package(case.root)
    report = validation.validate_operational_controls(package)
    assert report.status == "PASS"
    assert report.issues == ()
    assert report.projection_kind == "DERIVED_NON_AUTHORITATIVE"


def test_nonpass_gate_can_never_have_dispatch_or_wake_binding(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _mutate(
        case,
        "CELL_CAPACITY_GATE",
        lambda value: value.update(result="SPLIT_REQUIRED", dispatch_authorized=False),
    )
    package = package_module.load_run_package(case.root)
    assert "CELL_CAPACITY_NOT_PASS" in _codes(validation.validate_operational_controls(package))


def test_duplicate_patrol_conversation_or_heartbeat_fails(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    first_path = _artifact_path(case.root, "MONITOR_CONTROL")
    duplicate = yaml.safe_load(first_path.read_text(encoding="utf-8"))
    duplicate["artifact_id"] = "MONITOR-CONTROL-RUN-001-DUPLICATE"
    duplicate["candidate_id"] = duplicate["artifact_id"]
    _write_artifact(case.root, duplicate)
    _reindex(case)
    package = package_module.load_run_package(case.root)
    assert "PATROL_DUPLICATE" in _codes(validation.validate_operational_controls(package))


def test_pending_wake_requires_exact_three_levels_and_same_message(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    _mutate(case, "WAKE_ATTEMPT", lambda value: value.update(message_sha256="e" * 64), occurrence=1)
    package = package_module.load_run_package(case.root)
    assert "PENDING_WAKE_ATTEMPTS_INVALID" in _codes(
        validation.validate_operational_controls(package)
    )


@pytest.mark.parametrize("successor_count", [3, 6, 7, 8])
def test_post_dispatch_three_plus_requires_severe_and_remaining_recheck(
    modules, tmp_path, successor_count
):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    amendment = _template("CELL_PLAN_AMENDMENT")
    amendment["dispatch_timing"] = "POST_DISPATCH"
    amendment["successor_cell_ids"] = [f"CELL-001-{index}" for index in range(successor_count)]
    amendment["defect_codes"] = ["POST_DISPATCH_CELL_SPLIT"]
    amendment["reevaluate_undispatched_cell_ids"] = []
    _write_artifact(case.root, amendment)
    _reindex(case)
    package = package_module.load_run_package(case.root)
    assert "CELL_OVERSIZE_SEVERE_MISSING" in _codes(
        validation.validate_operational_controls(package)
    )


def test_scope_exceeded_is_not_a_product_failure_or_self_split(modules, tmp_path):
    package_module, validation = modules
    case = _operational_case(tmp_path)
    scope = _template("CELL_SCOPE_EXCEEDED")
    _write_artifact(case.root, scope)
    _reindex(case)
    package = package_module.load_run_package(case.root)
    report = validation.validate_operational_controls(package)
    assert "CELL_SELF_SPLIT_FORBIDDEN" not in _codes(report)
    assert report.status == "PASS"
