from dataclasses import dataclass
from typing import Optional, Tuple


PATROL_CONTRACT_VERSION = "3.1.0"
PATROL_MODEL = "gpt-5.6-luna"
PATROL_REASONING_EFFORT = "xhigh"
PATROL_INTERVALS = {"LOW": 10, "MEDIUM": 15, "HIGH": 30}
LEGAL_STOP_REASONS = frozenset(
    {"FORMAL_PAUSE", "LEGAL_BLOCKED", "EXTERNAL_WAIT", "NORMAL_RUNNING"}
)
PATROL_CHECK_IDS = (
    "UNEXPLAINED_STALL",
    "PENDING_WAKE",
    "SUBAGENT_EVIDENCE",
    "SUPERVISOR_WAIT",
    "PATROL_UNIQUENESS",
    "THREAD_PIN",
    "TERMINAL_CLOSURE",
)
PATROL_RESULTS = frozenset({"CLEAR", "LEGAL_SUPPRESSION", "ALERT", "CLOSED"})
PATROL_FINDINGS_BY_CHECK = {
    "UNEXPLAINED_STALL": frozenset(LEGAL_STOP_REASONS | {"LOOP_STOPPED"}),
    "PENDING_WAKE": frozenset({"NO_PENDING_WAKE", "PENDING_WAKE"}),
    "SUBAGENT_EVIDENCE": frozenset(
        {"NO_SUBAGENT_EVIDENCE", "VISIBLE_TASK", "AGENT_OPERATION"}
    ),
    "SUPERVISOR_WAIT": frozenset({"NO_SUPERVISOR_WAIT", "THREAD_OPERATION"}),
    "PATROL_UNIQUENESS": frozenset(
        {"UNIQUE_PATROL_HEARTBEAT", "PATROL_DUPLICATE", "PATROL_HEARTBEAT_DUPLICATE"}
    ),
    "THREAD_PIN": frozenset({"NO_PIN", "THREAD_PIN"}),
    "TERMINAL_CLOSURE": frozenset({"LOOP_NON_TERMINAL", "LOOP_TERMINAL"}),
}
METHOD_ACTOR_TYPES = frozenset(
    {
        "RUN_SUPERVISOR",
        "WORKER",
        "CHECKER",
        "GO_VERIFIER",
        "RUN_VERIFIER",
        "OWNER",
        "RUN_PATROL",
    }
)
PATROL_FORBIDDEN_CAPABILITIES = frozenset(
    {"create_thread", "fork_thread", "spawn_agent", "delegate_task", "set_thread_pinned"}
)
PIN_CAPABILITIES = frozenset({"set_thread_pinned", "pin_thread", "thread_pin"})
SUBAGENT_OPERATIONS = frozenset(
    {"spawn_agent", "delegate_task", "hidden_agent", "background_agent"}
)
OWNER_PIN_PROVENANCE = frozenset({"OWNER_MANUAL", "OWNER_EXPLICIT"})


class PatrolContractError(ValueError):
    pass


@dataclass(frozen=True)
class RunPatrolBinding:
    contract_version: str
    run_id: str
    patrol_id: str
    conversation_thread_id: str
    conversation_host_id: str
    heartbeat_id: str
    callback_ref: str
    model: str
    reasoning_effort: str
    project_difficulty: str
    interval_minutes: int
    monitor_version: int
    prior_monitor_sha256: Optional[str]

    def __post_init__(self) -> None:
        for name in (
            "contract_version",
            "run_id",
            "patrol_id",
            "conversation_thread_id",
            "conversation_host_id",
            "heartbeat_id",
            "callback_ref",
            "model",
            "reasoning_effort",
            "project_difficulty",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise PatrolContractError(f"PATROL_BINDING_INVALID: {name}")
        if self.monitor_version < 1 or self.interval_minutes < 1:
            raise PatrolContractError("PATROL_BINDING_INVALID: version and interval must be positive")


@dataclass(frozen=True)
class PatrolInventoryProjection:
    status: str
    patrol_conversation_ref: Optional[str]
    heartbeat_ref: Optional[str]
    model: Optional[str]
    reasoning_effort: Optional[str]
    interval_minutes: Optional[int]
    alert_codes: Tuple[str, ...]
    authority: str = "DERIVED_NON_AUTHORITATIVE"


@dataclass(frozen=True)
class PatrolEvent:
    kind: str
    actor_type: str
    operation: Optional[str]
    task_ref: str
    evidence_ref: str
    timeout_ms: Optional[int]
    looped: bool
    task_visible: bool
    pin_provenance: Optional[str]
    occurred_at: str
    patrol_cycle_id: str = ""
    check_id: str = ""
    result: str = ""
    alert_code: Optional[str] = None
    observation_ref: str = ""
    wait_all: bool = False
    terminal_sequence: Tuple[str, ...] = ()
    operation_history: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.kind or not self.actor_type or not self.task_ref or not self.evidence_ref:
            raise PatrolContractError("PATROL_EVENT_INVALID: required identity is missing")
        if self.timeout_ms is not None and self.timeout_ms < 0:
            raise PatrolContractError("PATROL_EVENT_INVALID: timeout cannot be negative")


@dataclass(frozen=True)
class PatrolObservation:
    run_id: str
    patrol_id: str
    patrol_cycle_id: str
    status: str
    evidence_refs: Tuple[str, ...]
    alert_codes: Tuple[str, ...]
    actions: Tuple[str, ...]
    authority: str = "DERIVED_NON_AUTHORITATIVE"


def patrol_monitor_key(run_id: str) -> str:
    if not isinstance(run_id, str) or not run_id:
        raise PatrolContractError("PATROL_BINDING_INVALID: run_id")
    return f"{run_id}-RUN-PATROL"


def validate_patrol_inventory(
    bindings: Tuple[RunPatrolBinding, ...], heartbeat_refs: Tuple[str, ...]
) -> PatrolInventoryProjection:
    alerts = []
    if len(bindings) != 1 or len({item.conversation_thread_id for item in bindings}) != len(bindings):
        alerts.append("PATROL_DUPLICATE")
    if len(heartbeat_refs) != 1 or len(set(heartbeat_refs)) != len(heartbeat_refs):
        alerts.append("PATROL_HEARTBEAT_DUPLICATE")
    current = bindings[0] if len(bindings) == 1 else None
    if current is not None:
        if (
            current.contract_version != PATROL_CONTRACT_VERSION
            or current.model != PATROL_MODEL
            or current.reasoning_effort != PATROL_REASONING_EFFORT
            or current.project_difficulty not in PATROL_INTERVALS
            or current.interval_minutes != PATROL_INTERVALS.get(current.project_difficulty)
            or tuple(heartbeat_refs) != (current.heartbeat_id,)
        ):
            alerts.append("PATROL_BINDING_INVALID")
    ordered = tuple(sorted(set(alerts)))
    return PatrolInventoryProjection(
        status="PATROL_HELD" if ordered else "PATROL_ACTIVE",
        patrol_conversation_ref=current.conversation_thread_id if current else None,
        heartbeat_ref=current.heartbeat_id if current else None,
        model=current.model if current else None,
        reasoning_effort=current.reasoning_effort if current else None,
        interval_minutes=current.interval_minutes if current else None,
        alert_codes=ordered,
    )


def validate_patrol_capabilities(capabilities: Tuple[str, ...]) -> None:
    forbidden = tuple(sorted(set(capabilities) & PATROL_FORBIDDEN_CAPABILITIES))
    if forbidden:
        raise PatrolContractError("PATROL_FORBIDDEN_CAPABILITY: " + ", ".join(forbidden))


def validate_method_role_capabilities(actor_type: str, capabilities: Tuple[str, ...]) -> None:
    if actor_type not in METHOD_ACTOR_TYPES:
        raise PatrolContractError(f"PATROL_BINDING_INVALID: unknown actor {actor_type}")
    forbidden = tuple(sorted(set(capabilities) & PIN_CAPABILITIES))
    if forbidden:
        raise PatrolContractError("PIN_CAPABILITY_FORBIDDEN: " + ", ".join(forbidden))
    forbidden_subagents = tuple(sorted(set(capabilities) & SUBAGENT_OPERATIONS))
    if forbidden_subagents:
        raise PatrolContractError(
            "SUBAGENT_CAPABILITY_FORBIDDEN: " + ", ".join(forbidden_subagents)
        )


def _validated_cycle(events: Tuple[PatrolEvent, ...]):
    if not events:
        raise PatrolContractError("PATROL_CHECKLIST_INCOMPLETE: no patrol checks")
    cycle_ids = {event.patrol_cycle_id for event in events}
    check_ids = tuple(event.check_id for event in events)
    if (
        len(cycle_ids) != 1
        or "" in cycle_ids
        or len(check_ids) != len(PATROL_CHECK_IDS)
        or set(check_ids) != set(PATROL_CHECK_IDS)
        or len(check_ids) != len(set(check_ids))
    ):
        raise PatrolContractError("PATROL_CHECKLIST_INCOMPLETE: exact unique check set required")
    indexed = {event.check_id: event for event in events}
    for check_id, event in indexed.items():
        if (
            event.kind not in PATROL_FINDINGS_BY_CHECK[check_id]
            or event.result not in PATROL_RESULTS
            or not event.observation_ref
            or not event.evidence_ref
        ):
            raise PatrolContractError("PATROL_CHECKLIST_INVALID: closed finding/result/evidence")
    return next(iter(cycle_ids)), indexed


def _expected_check(event: PatrolEvent):
    alert = None
    action = None
    result = "CLEAR"
    if event.check_id == "UNEXPLAINED_STALL":
        if event.kind == "LOOP_STOPPED":
            alert = "LOOP_STOPPED_UNEXPECTED"
        elif event.kind != "NORMAL_RUNNING":
            result = "LEGAL_SUPPRESSION"
    elif event.check_id == "PENDING_WAKE" and event.kind == "PENDING_WAKE":
        alert = "PENDING_WAKE_UNCONSUMED"
        action = "NOTIFY_FROZEN_CHECKER_CALLBACK"
    elif event.check_id == "SUBAGENT_EVIDENCE":
        if event.kind == "AGENT_OPERATION" and event.operation in SUBAGENT_OPERATIONS:
            alert = "SUBAGENT_USE_FORBIDDEN"
        elif event.kind == "AGENT_OPERATION":
            raise PatrolContractError("PATROL_CHECKLIST_INVALID: unknown Agent operation")
    elif event.check_id == "SUPERVISOR_WAIT":
        if event.kind == "THREAD_OPERATION":
            if event.actor_type != "RUN_SUPERVISOR" or event.operation != "wait_threads":
                raise PatrolContractError("PATROL_CHECKLIST_INVALID: Supervisor wait envelope")
            if (event.timeout_ms or 0) > 0 or event.looped or event.wait_all:
                alert = "SUPERVISOR_WAIT_FORBIDDEN"
    elif event.check_id == "PATROL_UNIQUENESS":
        if event.kind in {"PATROL_DUPLICATE", "PATROL_HEARTBEAT_DUPLICATE"}:
            alert = event.kind
    elif event.check_id == "THREAD_PIN" and event.kind == "THREAD_PIN":
        if event.actor_type == "OWNER" and event.pin_provenance in OWNER_PIN_PROVENANCE:
            pass
        elif event.pin_provenance in {"METHOD_OPERATION", "AGENT_OPERATION"}:
            alert = "UNAUTHORIZED_THREAD_PIN"
        else:
            alert = "PIN_PROVENANCE_UNKNOWN"
    elif event.check_id == "TERMINAL_CLOSURE" and event.kind == "LOOP_TERMINAL":
        required = (
            "LOOP_TERMINAL",
            "PATROL_HEARTBEAT_DELETED",
            "PATROL_CLOSED",
            "PATROL_CONVERSATION_ARCHIVED",
        )
        if event.terminal_sequence == required:
            result = "CLOSED"
        else:
            alert = "PATROL_NOT_CLOSED"
    if alert is not None:
        result = "ALERT"
    if event.result != result or event.alert_code != alert:
        raise PatrolContractError("PATROL_CHECKLIST_RESULT_MISMATCH: finding/result/alert")
    return alert, action, result


def derive_patrol_observation(
    binding: RunPatrolBinding, events: Tuple[PatrolEvent, ...]
) -> PatrolObservation:
    cycle_id, indexed = _validated_cycle(events)
    alerts = []
    actions = []
    results = []
    for check_id in PATROL_CHECK_IDS:
        alert, action, result = _expected_check(indexed[check_id])
        if alert:
            alerts.append(alert)
        if action:
            actions.append(action)
        results.append(result)
    status = "PATROL_CLOSED" if "CLOSED" in results else "PATROL_ACTIVE"
    ordered_alerts = tuple(sorted(set(alerts)))
    if ordered_alerts:
        status = "PATROL_ALERT"
    return PatrolObservation(
        run_id=binding.run_id,
        patrol_id=binding.patrol_id,
        patrol_cycle_id=cycle_id,
        status=status,
        evidence_refs=tuple(sorted({event.evidence_ref for event in events})),
        alert_codes=ordered_alerts,
        actions=tuple(sorted(set(actions))),
    )
