import importlib.util
import copy
import json
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "glk" / "schemas" / "glk.schema.json"
TEMPLATES = ROOT / "glk" / "templates"
MODEL = ROOT / "glk" / "scripts" / "artifact_model.py"
PACKAGE = ROOT / "glk" / "scripts" / "run_package.py"

NEW_AUTHORITIES = {
    "WORKER_CHECKER_WAKE_BINDING": "RUN_SUPERVISOR",
    "WAKE_ATTEMPT": "WORKER",
    "WAKE_ACK": "CHECKER",
    "PENDING_WAKE": "WORKER",
    "DEVICE_CAPACITY_PROFILE": "RUN_SUPERVISOR",
    "CUMULATIVE_ENGINEERING_LOAD": "RUN_SUPERVISOR",
    "CELL_WORK_ESTIMATE": "RUN_SUPERVISOR",
    "CELL_CAPACITY_GATE": "RUN_SUPERVISOR",
    "CELL_PLAN_AMENDMENT": "RUN_SUPERVISOR",
    "CELL_SCOPE_EXCEEDED": "WORKER",
    "CHECKER_PROGRESS_EVENT": "CHECKER",
    "SUPERVISOR_PROGRESS_EVENT": "RUN_SUPERVISOR",
}
NEW_DEFINITIONS = {
    "WORKER_CHECKER_WAKE_BINDING": "worker_checker_wake_binding",
    "WAKE_ATTEMPT": "wake_attempt",
    "WAKE_ACK": "wake_ack",
    "PENDING_WAKE": "pending_wake",
    "DEVICE_CAPACITY_PROFILE": "device_capacity_profile",
    "CUMULATIVE_ENGINEERING_LOAD": "cumulative_engineering_load",
    "CELL_WORK_ESTIMATE": "cell_work_estimate",
    "CELL_CAPACITY_GATE": "cell_capacity_gate",
    "CELL_PLAN_AMENDMENT": "cell_plan_amendment",
    "CELL_SCOPE_EXCEEDED": "cell_scope_exceeded",
    "CHECKER_PROGRESS_EVENT": "checker_progress_event",
    "SUPERVISOR_PROGRESS_EVENT": "supervisor_progress_event",
}


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


def _schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _validate(definition, value):
    schema = _schema()
    wrapper = {
        "$schema": schema["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": schema["$defs"],
    }
    Draft202012Validator(wrapper).validate(value)


def test_new_control_artifacts_have_one_exact_authority_and_root():
    model = _module(MODEL, "artifact_model_310_contract_test")
    package = _module(PACKAGE, "run_package_310_contract_test")
    for artifact_type, authority in NEW_AUTHORITIES.items():
        assert model.FORMAL_TYPES[artifact_type].sole_issuer == authority
        assert package.FORMAL_ROOT_BY_TYPE[artifact_type] == "controls"
    assert set(model.ROLE_TYPES) == {
        "RUN_SUPERVISOR", "WORKER", "CHECKER", "GO_VERIFIER", "RUN_VERIFIER", "OWNER"
    }
    assert "RUN_PATROL" not in model.ROLE_TYPES


def test_new_templates_exist_and_validate_against_closed_schema():
    for artifact_type, definition in NEW_DEFINITIONS.items():
        path = TEMPLATES / f"{artifact_type}.yaml"
        assert path.is_file(), path
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert value["artifact_type"] == artifact_type
        _validate(definition, value)


@pytest.mark.parametrize(
    "artifact_type,field,bad",
    [
        ("WAKE_ATTEMPT", "timeout_seconds", 121),
        ("WAKE_ATTEMPT", "level", 4),
        ("WAKE_ACK", "ack_status", "PASS"),
        ("PENDING_WAKE", "state", "TECHNICALLY_ACCEPTED"),
        ("CELL_CAPACITY_GATE", "result", "READY"),
        ("CELL_SCOPE_EXCEEDED", "actor_role", "RUN_SUPERVISOR"),
    ],
)
def test_closed_operational_fields_fail_schema(artifact_type, field, bad):
    value = yaml.safe_load((TEMPLATES / f"{artifact_type}.yaml").read_text(encoding="utf-8"))
    value[field] = bad
    with pytest.raises(ValidationError):
        _validate(NEW_DEFINITIONS[artifact_type], value)


def test_monitor_control_is_patrol_bound_not_supervisor_wait_bound():
    value = yaml.safe_load((TEMPLATES / "MONITOR_CONTROL.yaml").read_text(encoding="utf-8"))
    _validate("monitor_control", value)
    assert value["patrol_model"] == "gpt-5.6-luna"
    assert value["patrol_reasoning_effort"] == "xhigh"
    assert value["patrol_interval_minutes"] in {10, 15, 30}
    assert "supervisor_task_ref" not in value
    assert "created_task_ref" not in value


@pytest.mark.parametrize("difficulty,interval", [("LOW", 10), ("MEDIUM", 15), ("HIGH", 30)])
def test_monitor_schema_binds_owner_difficulty_to_exact_interval(difficulty, interval):
    value = yaml.safe_load((TEMPLATES / "MONITOR_CONTROL.yaml").read_text(encoding="utf-8"))
    value.update(project_difficulty=difficulty, patrol_interval_minutes=interval)
    _validate("monitor_control", value)
    value["patrol_interval_minutes"] = {10: 30, 15: 10, 30: 10}[interval]
    with pytest.raises(ValidationError):
        _validate("monitor_control", value)


def test_monitor_schema_requires_exact_closed_patrol_checklist():
    value = yaml.safe_load((TEMPLATES / "MONITOR_CONTROL.yaml").read_text(encoding="utf-8"))
    value["patrol_checklist"] = value["patrol_checklist"][:-1]
    with pytest.raises(ValidationError):
        _validate("monitor_control", value)
    value = yaml.safe_load((TEMPLATES / "MONITOR_CONTROL.yaml").read_text(encoding="utf-8"))
    value["patrol_checklist"][0]["finding"] = "EVERYTHING_FINE"
    with pytest.raises(ValidationError):
        _validate("monitor_control", value)


def test_method_lock_schema_distinguishes_historical_300_and_current_310():
    current = yaml.safe_load((TEMPLATES / "GLK_METHOD_LOCK.yaml").read_text(encoding="utf-8"))
    _validate("glk_method_lock", current)
    historical = copy.deepcopy(current)
    historical.update(
        schema_version="3.0.0",
        candidate_id="METHOD-GLK-3.0.0",
        release_tag="v3.0.0",
        method_version="3.0.0",
        validator_version="3.0.0",
    )
    _validate("glk_method_lock", historical)


@pytest.mark.parametrize(
    "artifact_type",
    ["PATROL_OBSERVATION", "PROGRESS_PROJECTION", "PREFLIGHT_REPORT", "SIMULATION_REPORT"],
)
def test_derived_reports_remain_nonformal(artifact_type):
    model = _module(MODEL, f"artifact_model_nonformal_{artifact_type}")
    assert artifact_type not in model.FORMAL_TYPES
