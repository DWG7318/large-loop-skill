import importlib
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "glk" / "scripts"


@pytest.fixture
def patrol():
    sys.path.insert(0, str(SCRIPTS))
    sys.modules.pop("run_patrol", None)
    try:
        yield importlib.import_module("run_patrol")
    finally:
        sys.path.remove(str(SCRIPTS))


def _binding(m, **changes):
    values = dict(
        contract_version="3.1.0",
        run_id="RUN-310",
        patrol_id="PATROL-RUN-310",
        conversation_thread_id="THREAD-PATROL-310",
        conversation_host_id="HOST-A",
        heartbeat_id="HEARTBEAT-PATROL-310",
        callback_ref="callbacks/patrol-run-310.json",
        model="gpt-5.6-luna",
        reasoning_effort="xhigh",
        project_difficulty="HIGH",
        interval_minutes=10,
        monitor_version=1,
        prior_monitor_sha256=None,
    )
    values.update(changes)
    return m.RunPatrolBinding(**values)


def _event(m, kind, **changes):
    values = dict(
        kind=kind,
        actor_type="RUN_PATROL",
        operation=None,
        task_ref="THREAD-PATROL-310",
        evidence_ref=f"evidence/{kind.lower()}.json",
        timeout_ms=None,
        looped=False,
        task_visible=True,
        pin_provenance=None,
        occurred_at="2026-08-04T00:00:00Z",
    )
    values.update(changes)
    return m.PatrolEvent(**values)


@pytest.mark.parametrize("difficulty,interval", [("HIGH", 10), ("MEDIUM", 15), ("LOW", 30)])
def test_one_patrol_uses_fixed_model_effort_and_difficulty_interval(patrol, difficulty, interval):
    binding = _binding(patrol, project_difficulty=difficulty, interval_minutes=interval)
    projection = patrol.validate_patrol_inventory((binding,), (binding.heartbeat_id,))

    assert projection.status == "PATROL_ACTIVE"
    assert projection.patrol_conversation_ref == binding.conversation_thread_id
    assert projection.heartbeat_ref == binding.heartbeat_id
    assert projection.model == "gpt-5.6-luna"
    assert projection.reasoning_effort == "xhigh"
    assert projection.interval_minutes == interval


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("DUPLICATE_CONVERSATION", "PATROL_DUPLICATE"),
        ("DUPLICATE_HEARTBEAT", "PATROL_HEARTBEAT_DUPLICATE"),
        ("WRONG_MODEL", "PATROL_BINDING_INVALID"),
        ("WRONG_EFFORT", "PATROL_BINDING_INVALID"),
        ("WRONG_INTERVAL", "PATROL_BINDING_INVALID"),
    ],
)
def test_patrol_inventory_fails_closed(patrol, mutation, code):
    first = _binding(patrol)
    bindings = (first,)
    heartbeats = (first.heartbeat_id,)
    if mutation == "DUPLICATE_CONVERSATION":
        bindings = (first, replace(first, patrol_id="PATROL-OTHER", heartbeat_id="HEARTBEAT-OTHER"))
        heartbeats = (first.heartbeat_id, "HEARTBEAT-OTHER")
    elif mutation == "DUPLICATE_HEARTBEAT":
        heartbeats = (first.heartbeat_id, first.heartbeat_id)
    elif mutation == "WRONG_MODEL":
        bindings = (replace(first, model="gpt-5.6-sol"),)
    elif mutation == "WRONG_EFFORT":
        bindings = (replace(first, reasoning_effort="high"),)
    elif mutation == "WRONG_INTERVAL":
        bindings = (replace(first, interval_minutes=30),)

    projection = patrol.validate_patrol_inventory(bindings, heartbeats)

    assert projection.status == "PATROL_HELD"
    assert code in projection.alert_codes


def test_patrol_contract_is_immutable(patrol):
    binding = _binding(patrol)
    with pytest.raises(FrozenInstanceError):
        binding.model = "changed"


@pytest.mark.parametrize(
    "operation",
    ["create_thread", "fork_thread", "spawn_agent", "delegate_task", "set_thread_pinned"],
)
def test_patrol_capabilities_reject_creation_subagents_and_pin(patrol, operation):
    with pytest.raises(patrol.PatrolContractError, match="PATROL_FORBIDDEN_CAPABILITY"):
        patrol.validate_patrol_capabilities(("read_thread", operation))


@pytest.mark.parametrize(
    "actor_type",
    ["RUN_SUPERVISOR", "WORKER", "CHECKER", "GO_VERIFIER", "RUN_VERIFIER", "OWNER", "RUN_PATROL"],
)
def test_every_method_actor_is_forbidden_from_pin_capability(patrol, actor_type):
    with pytest.raises(patrol.PatrolContractError, match="PIN_CAPABILITY_FORBIDDEN"):
        patrol.validate_method_role_capabilities(actor_type, ("set_thread_pinned",))


def test_six_formal_role_profiles_reject_pin_capability(patrol):
    run_model = importlib.import_module("run_model")
    for role_type in run_model.ROLE_TYPES:
        with pytest.raises(run_model.RunBindingError, match="PIN_CAPABILITY_FORBIDDEN"):
            run_model.RoleCapabilityProfile(
                profile_id=f"CAP-{role_type}",
                role_type=role_type,
                issuable_artifact_types=(),
                held_issuance_artifact_types=(),
                invocable_issuance_artifact_types=(),
                operational_capabilities=("set_thread_pinned",),
            )


def test_supervisor_wait_is_alerted_but_immediate_snapshot_is_allowed(patrol):
    events = (
        _event(
            patrol,
            "THREAD_OPERATION",
            actor_type="RUN_SUPERVISOR",
            operation="wait_threads",
            timeout_ms=120000,
        ),
        _event(
            patrol,
            "THREAD_OPERATION",
            actor_type="RUN_SUPERVISOR",
            operation="wait_threads",
            timeout_ms=0,
        ),
    )

    observation = patrol.derive_patrol_observation(_binding(patrol), events)

    assert observation.alert_codes.count("SUPERVISOR_WAIT_FORBIDDEN") == 1


def test_looping_wait_is_forbidden_even_with_zero_timeout(patrol):
    event = _event(
        patrol,
        "THREAD_OPERATION",
        actor_type="RUN_SUPERVISOR",
        operation="wait_threads",
        timeout_ms=0,
        looped=True,
    )
    assert "SUPERVISOR_WAIT_FORBIDDEN" in patrol.derive_patrol_observation(
        _binding(patrol), (event,)
    ).alert_codes


def test_pending_wake_is_detected_without_taking_over(patrol):
    event = _event(patrol, "PENDING_WAKE", actor_type="WORKER", task_ref="PENDING-WAKE/abc")
    observation = patrol.derive_patrol_observation(_binding(patrol), (event,))

    assert observation.alert_codes == ("PENDING_WAKE_UNCONSUMED",)
    assert observation.actions == ("NOTIFY_FROZEN_CHECKER_CALLBACK",)
    assert observation.authority == "DERIVED_NON_AUTHORITATIVE"


@pytest.mark.parametrize("reason", ["FORMAL_PAUSE", "LEGAL_BLOCKED", "EXTERNAL_WAIT", "NORMAL_RUNNING"])
def test_legal_nonprogress_reasons_are_not_alerted(patrol, reason):
    events = (
        _event(patrol, "LOOP_STOPPED"),
        _event(patrol, reason),
    )
    assert patrol.derive_patrol_observation(_binding(patrol), events).alert_codes == ()


def test_unexplained_loop_stop_is_alerted(patrol):
    observation = patrol.derive_patrol_observation(
        _binding(patrol), (_event(patrol, "LOOP_STOPPED"),)
    )
    assert observation.alert_codes == ("LOOP_STOPPED_UNEXPECTED",)


def test_visible_task_and_subtask_word_are_not_subagents(patrol):
    events = (
        _event(patrol, "VISIBLE_TASK", task_visible=True, operation="子任务 GO-03 CELL-02"),
        _event(patrol, "THREAD_OPERATION", operation="create_thread", task_visible=True),
    )
    assert "SUBAGENT_USE_FORBIDDEN" not in patrol.derive_patrol_observation(
        _binding(patrol), events
    ).alert_codes


@pytest.mark.parametrize("operation", ["spawn_agent", "delegate_task", "hidden_agent", "background_agent"])
def test_actual_subagent_evidence_is_rejected(patrol, operation):
    event = _event(patrol, "AGENT_OPERATION", operation=operation, task_visible=False)
    assert patrol.derive_patrol_observation(_binding(patrol), (event,)).alert_codes == (
        "SUBAGENT_USE_FORBIDDEN",
    )


def test_explicit_owner_pin_is_not_reported(patrol):
    event = _event(
        patrol,
        "THREAD_PIN",
        actor_type="OWNER",
        operation="set_thread_pinned",
        pin_provenance="OWNER_EXPLICIT",
    )
    assert patrol.derive_patrol_observation(_binding(patrol), (event,)).alert_codes == ()


def test_agent_pin_is_reported_even_after_unpin(patrol):
    events = (
        _event(
            patrol,
            "THREAD_PIN",
            actor_type="RUN_SUPERVISOR",
            operation="set_thread_pinned",
            pin_provenance="METHOD_OPERATION",
        ),
        _event(
            patrol,
            "THREAD_UNPIN",
            actor_type="RUN_SUPERVISOR",
            operation="set_thread_pinned_false",
            pin_provenance="METHOD_OPERATION",
        ),
    )
    observation = patrol.derive_patrol_observation(_binding(patrol), events)
    assert observation.alert_codes == ("UNAUTHORIZED_THREAD_PIN",)
    assert observation.actions == ()


def test_unknown_pin_provenance_reports_without_unpin(patrol):
    event = _event(
        patrol,
        "THREAD_PIN",
        actor_type="UNKNOWN",
        operation="pinned_state_observed",
        pin_provenance="UNKNOWN",
    )
    observation = patrol.derive_patrol_observation(_binding(patrol), (event,))
    assert observation.alert_codes == ("PIN_PROVENANCE_UNKNOWN",)
    assert "UNPIN" not in observation.actions


def test_terminal_sequence_must_delete_close_then_archive(patrol):
    good = (
        _event(patrol, "LOOP_TERMINAL"),
        _event(patrol, "PATROL_HEARTBEAT_DELETED"),
        _event(patrol, "PATROL_CLOSED"),
        _event(patrol, "PATROL_CONVERSATION_ARCHIVED"),
    )
    bad = (
        _event(patrol, "LOOP_TERMINAL"),
        _event(patrol, "PATROL_CLOSED"),
        _event(patrol, "PATROL_CONVERSATION_ARCHIVED"),
    )
    assert patrol.derive_patrol_observation(_binding(patrol), good).status == "PATROL_CLOSED"
    assert "PATROL_NOT_CLOSED" in patrol.derive_patrol_observation(
        _binding(patrol), bad
    ).alert_codes
