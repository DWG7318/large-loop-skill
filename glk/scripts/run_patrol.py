from dataclasses import dataclass
from typing import Optional, Tuple


PATROL_CONTRACT_VERSION = "3.1.0"
PATROL_MODEL = "gpt-5.6-luna"
PATROL_REASONING_EFFORT = "xhigh"
PATROL_INTERVALS = {"HIGH": 10, "MEDIUM": 15, "LOW": 30}
METHOD_ACTOR_TYPES = frozenset(
    {
        "RUN_SUPERVISOR",
        "WORKER",
        "CHECKER",
        "GO_VERIFIER",
        "RUN_VERIFIER",
        "OWNER",
        "RUN_PATROL",
        "ROUTER",
        "GRAPHER",
    }
)
PATROL_FORBIDDEN_CAPABILITIES = frozenset(
    {"create_thread", "fork_thread", "spawn_agent", "delegate_task", "set_thread_pinned"}
)
PIN_CAPABILITIES = frozenset({"set_thread_pinned", "pin_thread", "thread_pin"})
SUBAGENT_OPERATIONS = frozenset(
    {"spawn_agent", "delegate_task", "hidden_agent", "background_agent"}
)
LEGAL_STOP_REASONS = frozenset(
    {"FORMAL_PAUSE", "LEGAL_BLOCKED", "EXTERNAL_WAIT", "NORMAL_RUNNING"}
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

    def __post_init__(self) -> None:
        if not self.kind or not self.actor_type or not self.task_ref or not self.evidence_ref:
            raise PatrolContractError("PATROL_EVENT_INVALID: required identity is missing")
        if self.timeout_ms is not None and self.timeout_ms < 0:
            raise PatrolContractError("PATROL_EVENT_INVALID: timeout cannot be negative")


@dataclass(frozen=True)
class PatrolObservation:
    run_id: str
    patrol_id: str
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


def _terminal_status(events: Tuple[PatrolEvent, ...], alerts: list[str]) -> str:
    kinds = tuple(event.kind for event in events)
    if "LOOP_TERMINAL" not in kinds:
        return "PATROL_ACTIVE"
    required = (
        "LOOP_TERMINAL",
        "PATROL_HEARTBEAT_DELETED",
        "PATROL_CLOSED",
        "PATROL_CONVERSATION_ARCHIVED",
    )
    try:
        positions = tuple(kinds.index(kind) for kind in required)
    except ValueError:
        alerts.append("PATROL_NOT_CLOSED")
        return "PATROL_HELD"
    if positions != tuple(sorted(positions)) or len(set(positions)) != len(positions):
        alerts.append("PATROL_NOT_CLOSED")
        return "PATROL_HELD"
    return "PATROL_CLOSED"


def derive_patrol_observation(
    binding: RunPatrolBinding, events: Tuple[PatrolEvent, ...]
) -> PatrolObservation:
    alerts = []
    actions = []
    kinds = {event.kind for event in events}

    if "LOOP_STOPPED" in kinds and not (kinds & LEGAL_STOP_REASONS):
        alerts.append("LOOP_STOPPED_UNEXPECTED")
    if "PENDING_WAKE" in kinds:
        alerts.append("PENDING_WAKE_UNCONSUMED")
        actions.append("NOTIFY_FROZEN_CHECKER_CALLBACK")

    for event in events:
        if (
            event.kind == "THREAD_OPERATION"
            and event.actor_type == "RUN_SUPERVISOR"
            and event.operation == "wait_threads"
            and ((event.timeout_ms or 0) > 0 or event.looped)
        ):
            alerts.append("SUPERVISOR_WAIT_FORBIDDEN")
        if event.kind == "AGENT_OPERATION" and event.operation in SUBAGENT_OPERATIONS:
            alerts.append("SUBAGENT_USE_FORBIDDEN")
        if event.kind == "THREAD_PIN":
            if (
                event.actor_type == "OWNER"
                and event.pin_provenance in OWNER_PIN_PROVENANCE
            ):
                continue
            if event.pin_provenance in {"METHOD_OPERATION", "AGENT_OPERATION"}:
                alerts.append("UNAUTHORIZED_THREAD_PIN")
            else:
                alerts.append("PIN_PROVENANCE_UNKNOWN")

    status = _terminal_status(events, alerts)
    ordered_alerts = tuple(sorted(set(alerts)))
    if ordered_alerts and status == "PATROL_ACTIVE":
        status = "PATROL_ALERT"
    return PatrolObservation(
        run_id=binding.run_id,
        patrol_id=binding.patrol_id,
        status=status,
        evidence_refs=tuple(sorted({event.evidence_ref for event in events})),
        alert_codes=ordered_alerts,
        actions=tuple(sorted(set(actions))),
    )
