import importlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "glk" / "scripts"


@pytest.fixture
def modules():
    sys.path.insert(0, str(SCRIPTS))
    for name in ("preflight", "run_model", "worker_wake", "run_patrol", "cell_capacity"):
        sys.modules.pop(name, None)
    try:
        yield tuple(
            importlib.import_module(name)
            for name in ("preflight", "run_model", "worker_wake", "run_patrol", "cell_capacity")
        )
    finally:
        sys.path.remove(str(SCRIPTS))


def _profile(run_model, role_type, operations=()):
    issue = {
        "RUN_SUPERVISOR": ("GRAPH_EVENT", "SUPERVISOR_ADMISSION", "PREFLIGHT_ADMISSION"),
        "WORKER": ("D0_RECEIPT", "GO_CANDIDATE_CLOSURE"),
        "CHECKER": ("D1_RECEIPT",),
        "GO_VERIFIER": ("D2_RECEIPT",),
        "RUN_VERIFIER": ("D3_RECEIPT",),
        "OWNER": ("OWNER_ACCEPTANCE",),
    }[role_type]
    return run_model.RoleCapabilityProfile(
        profile_id=f"CAP-{role_type}",
        role_type=role_type,
        issuable_artifact_types=issue,
        held_issuance_artifact_types=(),
        invocable_issuance_artifact_types=(),
        operational_capabilities=tuple(operations),
    )


def _patrol_binding(run_patrol, **changes):
    values = dict(
        contract_version="3.1.0",
        run_id="RUN-310",
        patrol_id="PATROL-RUN-310",
        conversation_thread_id="THREAD-PATROL-310",
        conversation_host_id="HOST-A",
        heartbeat_id="HEARTBEAT-PATROL-310",
        callback_ref="callbacks/patrol.json",
        model="gpt-5.6-luna",
        reasoning_effort="xhigh",
        project_difficulty="MEDIUM",
        interval_minutes=15,
        monitor_version=1,
        prior_monitor_sha256=None,
    )
    values.update(changes)
    return run_patrol.RunPatrolBinding(**values)


def _simulation(preflight, **changes):
    values = dict(
        observed_wake_levels=(1, 2, 3, 4),
        early_stop_cleanup=True,
        pending_wake_patrol_consumed=True,
        legal_pause_suppressed=True,
        subtask_not_subagent=True,
        actual_subagent_rejected=True,
        owner_pin_accepted=True,
        agent_pin_rejected=True,
        unknown_pin_reported_without_unpin=True,
        pin_then_unpin_violation_retained=True,
        progress_stages=(
            "DELIVERED",
            "D1_ACCEPTED",
            "GO_CANDIDATE_READY",
            "D2_VERIFIED",
            "RUN_VERIFIED",
            "OWNER_ACCEPTED",
        ),
        capacity_results=("PASS", "SPLIT_REQUIRED", "CAPACITY_BLOCKED"),
        severe_split_counts=(3, 6, 7, 8),
        resource_safe_activation=True,
        formal_ledger_before_sha256="a" * 64,
        formal_ledger_after_sha256="a" * 64,
    )
    values.update(changes)
    return preflight.validate_operational_simulation(**values)


def _input(modules, **changes):
    preflight, run_model, worker_wake, run_patrol, _ = modules
    profiles = tuple(
        _profile(
            run_model,
            role,
            worker_wake.REQUIRED_WORKER_WAKE_CAPABILITIES if role == "WORKER" else (),
        )
        for role in run_model.ROLE_TYPES
    )
    patrol_binding = _patrol_binding(run_patrol)
    values = dict(
        run_id="RUN-310",
        role_capability_profiles=profiles,
        worker_wake_binding_count=1,
        worker_wake_bindings_valid=True,
        patrol_bindings=(patrol_binding,),
        patrol_heartbeat_refs=(patrol_binding.heartbeat_id,),
        patrol_capabilities=("read_thread", "list_threads"),
        supervisor_control_operations=(),
        dispatch_gate_results=("PASS",),
        capacity_profile_current=True,
        cumulative_load_current=True,
        progress_denominator_versions_current=True,
        simulation_report=_simulation(preflight),
    )
    values.update(changes)
    return preflight.OperationalPreflightInput(**values)


def test_complete_operational_preflight_passes(modules):
    preflight, *_ = modules
    report = preflight.derive_operational_preflight(_input(modules))
    assert report.status == "PREFLIGHT_PASS"
    assert report.can_dispatch is True
    assert report.projection_kind == "DERIVED_NON_AUTHORITATIVE"


def test_each_missing_worker_wake_capability_fails_closed(modules):
    preflight, run_model, worker_wake, *_ = modules
    base = _input(modules)
    for missing in worker_wake.REQUIRED_WORKER_WAKE_CAPABILITIES:
        operations = tuple(value for value in worker_wake.REQUIRED_WORKER_WAKE_CAPABILITIES if value != missing)
        profiles = tuple(
            _profile(run_model, item.role_type, operations if item.role_type == "WORKER" else ())
            for item in base.role_capability_profiles
        )
        report = preflight.derive_operational_preflight(
            replace(base, role_capability_profiles=profiles)
        )
        assert "WAKE_CAPABILITY_MISSING" in report.failure_codes


def test_invalid_or_missing_wake_binding_fails(modules):
    preflight, *_ = modules
    report = preflight.derive_operational_preflight(
        replace(_input(modules), worker_wake_binding_count=0, worker_wake_bindings_valid=False)
    )
    assert "WAKE_BINDING_MISMATCH" in report.failure_codes


@pytest.mark.parametrize("mutation", ["DUPLICATE", "WRONG_MODEL", "WRONG_INTERVAL"])
def test_patrol_inventory_must_be_unique_and_fixed(modules, mutation):
    preflight, _, _, run_patrol, _ = modules
    base = _input(modules)
    first = base.patrol_bindings[0]
    if mutation == "DUPLICATE":
        bindings = (first, replace(first, patrol_id="PATROL-2", heartbeat_id="HEARTBEAT-2"))
        heartbeats = (first.heartbeat_id, "HEARTBEAT-2")
    elif mutation == "WRONG_MODEL":
        bindings = (replace(first, model="gpt-5.6-sol"),)
        heartbeats = (first.heartbeat_id,)
    else:
        bindings = (replace(first, interval_minutes=30),)
        heartbeats = (first.heartbeat_id,)
    report = preflight.derive_operational_preflight(
        replace(base, patrol_bindings=bindings, patrol_heartbeat_refs=heartbeats)
    )
    assert any(code.startswith("PATROL_") for code in report.failure_codes)


@pytest.mark.parametrize("operation", ["create_thread", "spawn_agent", "delegate_task", "set_thread_pinned"])
def test_patrol_forbidden_capability_fails_preflight(modules, operation):
    preflight, *_ = modules
    report = preflight.derive_operational_preflight(
        replace(_input(modules), patrol_capabilities=("read_thread", operation))
    )
    assert "PATROL_FORBIDDEN_CAPABILITY" in report.failure_codes


@pytest.mark.parametrize(
    "operation",
    [("wait_threads", 120000, False), ("wait_threads", 0, True)],
)
def test_supervisor_long_or_looping_wait_fails_preflight(modules, operation):
    preflight, *_ = modules
    report = preflight.derive_operational_preflight(
        replace(_input(modules), supervisor_control_operations=(operation,))
    )
    assert "SUPERVISOR_WAIT_FORBIDDEN" in report.failure_codes


def test_supervisor_immediate_snapshot_is_allowed(modules):
    preflight, *_ = modules
    report = preflight.derive_operational_preflight(
        replace(_input(modules), supervisor_control_operations=(("wait_threads", 0, False),))
    )
    assert report.status == "PREFLIGHT_PASS"


@pytest.mark.parametrize(
    "change,code",
    [
        ({"capacity_profile_current": False}, "DEVICE_CAPACITY_STALE"),
        ({"cumulative_load_current": False}, "CUMULATIVE_LOAD_STALE"),
        ({"dispatch_gate_results": ("SPLIT_REQUIRED",)}, "CELL_CAPACITY_NOT_PASS"),
        ({"dispatch_gate_results": ("CAPACITY_BLOCKED",)}, "CELL_CAPACITY_NOT_PASS"),
        ({"progress_denominator_versions_current": False}, "PROGRESS_DENOMINATOR_STALE"),
    ],
)
def test_capacity_and_progress_versions_gate_dispatch(modules, change, code):
    preflight, *_ = modules
    report = preflight.derive_operational_preflight(replace(_input(modules), **change))
    assert code in report.failure_codes


def test_simulation_must_cover_all_wake_levels_and_preserve_formal_ledger(modules):
    preflight, *_ = modules
    incomplete = _simulation(
        preflight,
        observed_wake_levels=(1, 2, 3),
        formal_ledger_after_sha256="b" * 64,
    )
    report = preflight.derive_operational_preflight(
        replace(_input(modules), simulation_report=incomplete)
    )
    assert "OPERATIONAL_SIMULATION_REQUIRED" in report.failure_codes
    assert incomplete.formal_ledger_unchanged is False


def test_pin_provenance_and_subagent_classification_are_mandatory_simulation_cases(modules):
    preflight, *_ = modules
    incomplete = _simulation(
        preflight,
        subtask_not_subagent=False,
        unknown_pin_reported_without_unpin=False,
        pin_then_unpin_violation_retained=False,
    )
    assert incomplete.status == "SIMULATION_FAIL"


@pytest.mark.parametrize("count", [3, 6, 7, 8])
def test_severe_split_cases_are_mandatory_in_simulation(modules, count):
    preflight, *_ = modules
    incomplete = _simulation(
        preflight,
        severe_split_counts=tuple(value for value in (3, 6, 7, 8) if value != count),
    )
    assert incomplete.status == "SIMULATION_FAIL"
