import importlib
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "glk" / "scripts"


def require(condition, message):
    if not condition:
        pytest.fail(message)


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
        interval_minutes=30,
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


def _complete_cycle(m, **overrides):
    specs = {
        "UNEXPLAINED_STALL": ("NORMAL_RUNNING", "CLEAR", None),
        "PENDING_WAKE": ("NO_PENDING_WAKE", "CLEAR", None),
        "SUBAGENT_EVIDENCE": ("NO_SUBAGENT_EVIDENCE", "CLEAR", None),
        "SUPERVISOR_WAIT": ("NO_SUPERVISOR_WAIT", "CLEAR", None),
        "PATROL_UNIQUENESS": ("UNIQUE_PATROL_HEARTBEAT", "CLEAR", None),
        "THREAD_PIN": ("NO_PIN", "CLEAR", None),
        "TERMINAL_CLOSURE": ("LOOP_NON_TERMINAL", "CLEAR", None),
    }
    specs.update(overrides)
    return tuple(
        _event(
            m,
            finding,
            patrol_cycle_id="PATROL-CYCLE-001",
            check_id=check_id,
            result=result,
            alert_code=alert_code,
            observation_ref=f"observations/{check_id.lower()}.json",
        )
        for check_id, (finding, result, alert_code) in specs.items()
    )


def _cycle_with(m, check_id, finding, result="CLEAR", alert_code=None, **changes):
    events = _complete_cycle(m, **{check_id: (finding, result, alert_code)})
    return tuple(
        replace(event, **changes) if event.check_id == check_id else event
        for event in events
    )


def test_REDO_owner_difficulty_mapping_is_low_10_medium_15_high_30(patrol):
    for difficulty, interval in (("LOW", 10), ("MEDIUM", 15), ("HIGH", 30)):
        binding = _binding(
            patrol, project_difficulty=difficulty, interval_minutes=interval
        )
        require(
            patrol.validate_patrol_inventory(
                (binding,), (binding.heartbeat_id,)
            ).status == "PATROL_ACTIVE",
            f"{difficulty} must map to {interval} minutes",
        )


def test_REDO_empty_or_free_form_patrol_cycle_fails_closed(patrol):
    with pytest.raises(patrol.PatrolContractError, match="PATROL_CHECKLIST_INCOMPLETE"):
        patrol.derive_patrol_observation(_binding(patrol), ())
    free_form = _event(patrol, "EVERYTHING_FINE")
    with pytest.raises(patrol.PatrolContractError, match="PATROL_CHECKLIST"):
        patrol.derive_patrol_observation(_binding(patrol), (free_form,))


def test_REDO_patrol_cycle_has_exact_complete_unique_closed_checklist(patrol):
    require(patrol.PATROL_CHECK_IDS == (
        "UNEXPLAINED_STALL",
        "PENDING_WAKE",
        "SUBAGENT_EVIDENCE",
        "SUPERVISOR_WAIT",
        "PATROL_UNIQUENESS",
        "THREAD_PIN",
        "TERMINAL_CLOSURE",
    ), "patrol checklist must be exact and closed")
    complete = _complete_cycle(patrol)
    observation = patrol.derive_patrol_observation(_binding(patrol), complete)
    require(observation.status == "PATROL_ACTIVE", "complete quiet cycle must be active")
    require(len(observation.evidence_refs) == len(patrol.PATROL_CHECK_IDS), "every check needs evidence")

    duplicate = complete[:-1] + (replace(complete[0], evidence_ref="evidence/duplicate.json"),)
    with pytest.raises(patrol.PatrolContractError, match="PATROL_CHECKLIST"):
        patrol.derive_patrol_observation(_binding(patrol), duplicate)


def test_REDO_wait_all_is_forbidden_even_for_zero_timeout(patrol):
    events = _complete_cycle(
        patrol,
        SUPERVISOR_WAIT=("THREAD_OPERATION", "ALERT", "SUPERVISOR_WAIT_FORBIDDEN"),
    )
    wait_event = next(event for event in events if event.check_id == "SUPERVISOR_WAIT")
    wait_event = replace(
        wait_event,
        actor_type="RUN_SUPERVISOR",
        operation="wait_threads",
        timeout_ms=0,
        looped=False,
        wait_all=True,
    )
    events = tuple(
        wait_event if event.check_id == "SUPERVISOR_WAIT" else event
        for event in events
    )
    require(
        patrol.derive_patrol_observation(
            _binding(patrol), events
        ).alert_codes == ("SUPERVISOR_WAIT_FORBIDDEN",),
        "wait-all must alert even with timeout zero",
    )


@pytest.mark.parametrize("difficulty,interval", [("LOW", 10), ("MEDIUM", 15), ("HIGH", 30)])
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
        bindings = (replace(first, interval_minutes=10),)

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
    forbidden = _cycle_with(
        patrol,
        "SUPERVISOR_WAIT",
        "THREAD_OPERATION",
        "ALERT",
        "SUPERVISOR_WAIT_FORBIDDEN",
        actor_type="RUN_SUPERVISOR",
        operation="wait_threads",
        timeout_ms=120000,
    )
    allowed = _cycle_with(
        patrol,
        "SUPERVISOR_WAIT",
        "THREAD_OPERATION",
        actor_type="RUN_SUPERVISOR",
        operation="wait_threads",
        timeout_ms=0,
    )
    assert patrol.derive_patrol_observation(
        _binding(patrol), forbidden
    ).alert_codes == ("SUPERVISOR_WAIT_FORBIDDEN",)
    assert patrol.derive_patrol_observation(_binding(patrol), allowed).alert_codes == ()


def test_looping_wait_is_forbidden_even_with_zero_timeout(patrol):
    events = _cycle_with(
        patrol,
        "SUPERVISOR_WAIT",
        "THREAD_OPERATION",
        "ALERT",
        "SUPERVISOR_WAIT_FORBIDDEN",
        actor_type="RUN_SUPERVISOR",
        operation="wait_threads",
        timeout_ms=0,
        looped=True,
    )
    assert "SUPERVISOR_WAIT_FORBIDDEN" in patrol.derive_patrol_observation(
        _binding(patrol), events
    ).alert_codes


def test_pending_wake_is_detected_without_taking_over(patrol):
    events = _cycle_with(
        patrol,
        "PENDING_WAKE",
        "PENDING_WAKE",
        "ALERT",
        "PENDING_WAKE_UNCONSUMED",
        actor_type="WORKER",
        task_ref="PENDING-WAKE/abc",
    )
    observation = patrol.derive_patrol_observation(_binding(patrol), events)

    assert observation.alert_codes == ("PENDING_WAKE_UNCONSUMED",)
    assert observation.actions == ("NOTIFY_FROZEN_CHECKER_CALLBACK",)
    assert observation.authority == "DERIVED_NON_AUTHORITATIVE"


@pytest.mark.parametrize("reason", ["FORMAL_PAUSE", "LEGAL_BLOCKED", "EXTERNAL_WAIT", "NORMAL_RUNNING"])
def test_legal_nonprogress_reasons_are_not_alerted(patrol, reason):
    events = _cycle_with(
        patrol,
        "UNEXPLAINED_STALL",
        reason,
        "CLEAR" if reason == "NORMAL_RUNNING" else "LEGAL_SUPPRESSION",
    )
    assert patrol.derive_patrol_observation(_binding(patrol), events).alert_codes == ()


def test_unexplained_loop_stop_is_alerted(patrol):
    observation = patrol.derive_patrol_observation(
        _binding(patrol),
        _cycle_with(
            patrol,
            "UNEXPLAINED_STALL",
            "LOOP_STOPPED",
            "ALERT",
            "LOOP_STOPPED_UNEXPECTED",
        ),
    )
    assert observation.alert_codes == ("LOOP_STOPPED_UNEXPECTED",)


def test_visible_task_and_subtask_word_are_not_subagents(patrol):
    events = _cycle_with(
        patrol,
        "SUBAGENT_EVIDENCE",
        "VISIBLE_TASK",
        task_visible=True,
        operation="子任务 GO-03 CELL-02",
    )
    assert "SUBAGENT_USE_FORBIDDEN" not in patrol.derive_patrol_observation(
        _binding(patrol), events
    ).alert_codes


@pytest.mark.parametrize("operation", ["spawn_agent", "delegate_task", "hidden_agent", "background_agent"])
def test_actual_subagent_evidence_is_rejected(patrol, operation):
    events = _cycle_with(
        patrol,
        "SUBAGENT_EVIDENCE",
        "AGENT_OPERATION",
        "ALERT",
        "SUBAGENT_USE_FORBIDDEN",
        operation=operation,
        task_visible=False,
    )
    assert patrol.derive_patrol_observation(_binding(patrol), events).alert_codes == (
        "SUBAGENT_USE_FORBIDDEN",
    )


def test_explicit_owner_pin_is_not_reported(patrol):
    events = _cycle_with(
        patrol,
        "THREAD_PIN",
        "THREAD_PIN",
        actor_type="OWNER",
        operation="set_thread_pinned",
        pin_provenance="OWNER_EXPLICIT",
    )
    assert patrol.derive_patrol_observation(_binding(patrol), events).alert_codes == ()


def test_agent_pin_is_reported_even_after_unpin(patrol):
    events = _cycle_with(
        patrol,
        "THREAD_PIN",
        "THREAD_PIN",
        "ALERT",
        "UNAUTHORIZED_THREAD_PIN",
        actor_type="RUN_SUPERVISOR",
        operation="set_thread_pinned",
        pin_provenance="METHOD_OPERATION",
        operation_history=("set_thread_pinned", "set_thread_pinned_false"),
    )
    observation = patrol.derive_patrol_observation(_binding(patrol), events)
    assert observation.alert_codes == ("UNAUTHORIZED_THREAD_PIN",)
    assert observation.actions == ()


def test_unknown_pin_provenance_reports_without_unpin(patrol):
    events = _cycle_with(
        patrol,
        "THREAD_PIN",
        "THREAD_PIN",
        "ALERT",
        "PIN_PROVENANCE_UNKNOWN",
        actor_type="UNKNOWN",
        operation="pinned_state_observed",
        pin_provenance="UNKNOWN",
    )
    observation = patrol.derive_patrol_observation(_binding(patrol), events)
    assert observation.alert_codes == ("PIN_PROVENANCE_UNKNOWN",)
    assert "UNPIN" not in observation.actions


def test_terminal_sequence_must_delete_close_then_archive(patrol):
    good = _cycle_with(
        patrol,
        "TERMINAL_CLOSURE",
        "LOOP_TERMINAL",
        "CLOSED",
        terminal_sequence=(
            "LOOP_TERMINAL",
            "PATROL_HEARTBEAT_DELETED",
            "PATROL_CLOSED",
            "PATROL_CONVERSATION_ARCHIVED",
        ),
    )
    bad = _cycle_with(
        patrol,
        "TERMINAL_CLOSURE",
        "LOOP_TERMINAL",
        "ALERT",
        "PATROL_NOT_CLOSED",
        terminal_sequence=(
            "LOOP_TERMINAL",
            "PATROL_CLOSED",
            "PATROL_CONVERSATION_ARCHIVED",
        ),
    )
    assert patrol.derive_patrol_observation(_binding(patrol), good).status == "PATROL_CLOSED"
    assert "PATROL_NOT_CLOSED" in patrol.derive_patrol_observation(
        _binding(patrol), bad
    ).alert_codes
