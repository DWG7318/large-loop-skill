from dataclasses import dataclass
from typing import Optional, Protocol, Tuple

from run_model import RoleCapabilityProfile


WAKE_CONTRACT_VERSION = "3.1.0"
WAKE_WAIT_LIMIT_SECONDS = 120
WAKE_DISPOSITIONS = ("DELIVERED", "BLOCKED", "EXECUTION_FAILURE")
REQUIRED_WORKER_WAKE_CAPABILITIES = (
    "send_message_to_thread",
    "read_thread",
    "list_threads",
    "unarchive_thread",
    "bounded_wait_for_wake_ack",
    "upsert_temporary_heartbeat",
    "delete_temporary_heartbeat",
    "write_pending_wake",
)


class WakeContractError(ValueError):
    pass


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise WakeContractError(f"WAKE_BINDING_MISMATCH: {name} is required")


@dataclass(frozen=True)
class FrozenWakeBinding:
    contract_version: str
    run_id: str
    go_id: str
    cell_id: str
    round_id: str
    cell_ordinal: int
    required_cell_count: int
    cell_manifest_id: str
    cell_manifest_version: int
    worker_binding_id: str
    worker_thread_id: str
    worker_host_id: str
    checker_binding_id: str
    checker_thread_id: str
    checker_host_id: str
    capability_profile_digest: str
    frozen_at: str

    def __post_init__(self) -> None:
        if self.contract_version != WAKE_CONTRACT_VERSION:
            raise WakeContractError("WAKE_BINDING_MISMATCH: unsupported contract version")
        for name in (
            "run_id",
            "go_id",
            "cell_id",
            "round_id",
            "cell_manifest_id",
            "worker_binding_id",
            "worker_thread_id",
            "worker_host_id",
            "checker_binding_id",
            "checker_thread_id",
            "checker_host_id",
            "capability_profile_digest",
            "frozen_at",
        ):
            _require_text(name, getattr(self, name))
        if self.cell_ordinal < 1 or self.required_cell_count < 1:
            raise WakeContractError("WAKE_BINDING_MISMATCH: CELL counts must be positive")
        if self.cell_ordinal > self.required_cell_count:
            raise WakeContractError("WAKE_BINDING_MISMATCH: CELL ordinal exceeds required count")
        if self.cell_manifest_version < 1:
            raise WakeContractError("WAKE_BINDING_MISMATCH: manifest version must be positive")
        if len(self.capability_profile_digest) != 64:
            raise WakeContractError("WAKE_BINDING_MISMATCH: capability profile digest is invalid")

    @property
    def wake_identity(self) -> Tuple[str, ...]:
        return (
            self.run_id,
            self.go_id,
            self.cell_id,
            self.round_id,
            self.worker_binding_id,
            self.checker_binding_id,
        )


@dataclass(frozen=True)
class WakeAck:
    run_id: str
    go_id: str
    cell_id: str
    round_id: str
    checker_binding_id: str
    checker_thread_id: str
    checker_host_id: str
    acknowledged_at: str


@dataclass(frozen=True)
class CheckerProcessingEvidence:
    run_id: str
    go_id: str
    cell_id: str
    round_id: str
    checker_binding_id: str
    checker_thread_id: str
    checker_host_id: str
    observed_at: str


@dataclass(frozen=True)
class ThreadSnapshot:
    thread_id: str
    host_id: str
    role_binding_id: str
    archived: bool
    running: bool
    observed_at: str


@dataclass(frozen=True)
class WakeAttempt:
    level: int
    started_at: str
    message: str
    outcome: str
    error_code: Optional[str] = None


@dataclass(frozen=True)
class WakeResult:
    status: str
    success_level: Optional[int]
    wake_identity: Tuple[str, ...]
    message: str
    attempts: Tuple[WakeAttempt, ...]
    error_codes: Tuple[str, ...]


class WakeClock(Protocol):
    def monotonic(self) -> float: ...

    def utc_now(self) -> str: ...


class WorkerWakeGateway(Protocol):
    def send_message(self, *, thread_id: str, host_id: str, message: str) -> None: ...

    def wait_for_ack(
        self,
        *,
        wake_identity: Tuple[str, ...],
        checker_binding_id: str,
        timeout_seconds: int,
    ) -> Optional[object]: ...

    def read_thread(self, *, thread_id: str, host_id: str) -> Optional[ThreadSnapshot]: ...

    def list_threads(self, *, host_id: str) -> Tuple[ThreadSnapshot, ...]: ...

    def unarchive_thread(self, *, thread_id: str, host_id: str) -> None: ...


def format_worker_message(binding: FrozenWakeBinding, disposition: str = "DELIVERED") -> str:
    if disposition not in WAKE_DISPOSITIONS:
        raise WakeContractError(f"WAKE_BINDING_MISMATCH: unknown disposition {disposition}")
    position = f"GO {binding.go_id} CELL {binding.cell_ordinal}/{binding.required_cell_count}"
    if disposition == "DELIVERED":
        return f"{position} 已交付，请检查"
    return f"{position} {disposition}，请检查"


def format_wake_ack(ack: WakeAck) -> str:
    return (
        f"WAKE_ACK RUN={ack.run_id} GO={ack.go_id} "
        f"CELL={ack.cell_id} ROUND={ack.round_id}"
    )


def _validate_worker_profile(profile: RoleCapabilityProfile) -> None:
    if profile.role_type != "WORKER":
        raise WakeContractError("WAKE_ROLE_FORBIDDEN: only Worker may invoke the wake ladder")
    missing = tuple(
        capability
        for capability in REQUIRED_WORKER_WAKE_CAPABILITIES
        if capability not in profile.operational_capabilities
    )
    if missing:
        raise WakeContractError("WAKE_CAPABILITY_MISSING: " + ", ".join(missing))


def _ack_matches(binding: FrozenWakeBinding, value: object) -> bool:
    if not isinstance(value, (WakeAck, CheckerProcessingEvidence)):
        return False
    return (
        value.run_id == binding.run_id
        and value.go_id == binding.go_id
        and value.cell_id == binding.cell_id
        and value.round_id == binding.round_id
        and value.checker_binding_id == binding.checker_binding_id
        and value.checker_thread_id == binding.checker_thread_id
        and value.checker_host_id == binding.checker_host_id
    )


def _snapshot_matches(binding: FrozenWakeBinding, snapshot: ThreadSnapshot) -> bool:
    return (
        snapshot.thread_id == binding.checker_thread_id
        and snapshot.host_id == binding.checker_host_id
        and snapshot.role_binding_id == binding.checker_binding_id
    )


def _wait(
    binding: FrozenWakeBinding,
    gateway: WorkerWakeGateway,
) -> Tuple[bool, Optional[str]]:
    value = gateway.wait_for_ack(
        wake_identity=binding.wake_identity,
        checker_binding_id=binding.checker_binding_id,
        timeout_seconds=WAKE_WAIT_LIMIT_SECONDS,
    )
    if value is None:
        return False, "WAKE_ACK_TIMEOUT"
    if not _ack_matches(binding, value):
        return False, "WAKE_ACK_SCOPE_MISMATCH"
    return True, None


def attempt_levels_one_two(
    *,
    binding: FrozenWakeBinding,
    worker_profile: RoleCapabilityProfile,
    gateway: WorkerWakeGateway,
    clock: WakeClock,
    disposition: str = "DELIVERED",
) -> WakeResult:
    _validate_worker_profile(worker_profile)
    message = format_worker_message(binding, disposition)
    attempts = []
    errors = []

    started_at = clock.utc_now()
    gateway.send_message(
        thread_id=binding.checker_thread_id,
        host_id=binding.checker_host_id,
        message=message,
    )
    matched, error = _wait(binding, gateway)
    attempts.append(
        WakeAttempt(1, started_at, message, "ACKNOWLEDGED" if matched else "FAILED", error)
    )
    if matched:
        return WakeResult("ACKNOWLEDGED", 1, binding.wake_identity, message, tuple(attempts), ())
    if error:
        errors.append(error)

    started_at = clock.utc_now()
    snapshot = gateway.read_thread(
        thread_id=binding.checker_thread_id,
        host_id=binding.checker_host_id,
    )
    listed = tuple(gateway.list_threads(host_id=binding.checker_host_id))
    candidates = tuple(item for item in (snapshot,) + listed if item is not None)
    exact = tuple(item for item in candidates if _snapshot_matches(binding, item))
    if not candidates:
        errors.append("WAKE_THREAD_NOT_FOUND")
        attempts.append(WakeAttempt(2, started_at, message, "FAILED", "WAKE_THREAD_NOT_FOUND"))
        return WakeResult(
            "ESCALATE_LEVEL_3", None, binding.wake_identity, message, tuple(attempts), tuple(dict.fromkeys(errors))
        )
    if not exact:
        errors.append("WAKE_BINDING_MISMATCH")
        attempts.append(WakeAttempt(2, started_at, message, "FAILED", "WAKE_BINDING_MISMATCH"))
        return WakeResult(
            "ESCALATE_LEVEL_3", None, binding.wake_identity, message, tuple(attempts), tuple(dict.fromkeys(errors))
        )
    current = exact[0]
    if current.archived:
        gateway.unarchive_thread(
            thread_id=binding.checker_thread_id,
            host_id=binding.checker_host_id,
        )
    if current.running:
        evidence = CheckerProcessingEvidence(
            run_id=binding.run_id,
            go_id=binding.go_id,
            cell_id=binding.cell_id,
            round_id=binding.round_id,
            checker_binding_id=binding.checker_binding_id,
            checker_thread_id=binding.checker_thread_id,
            checker_host_id=binding.checker_host_id,
            observed_at=current.observed_at,
        )
        if _ack_matches(binding, evidence):
            attempts.append(WakeAttempt(2, started_at, message, "PROCESSING_OBSERVED"))
            return WakeResult(
                "ACKNOWLEDGED", 2, binding.wake_identity, message, tuple(attempts), tuple(dict.fromkeys(errors))
            )

    gateway.send_message(
        thread_id=binding.checker_thread_id,
        host_id=binding.checker_host_id,
        message=message,
    )
    matched, error = _wait(binding, gateway)
    attempts.append(
        WakeAttempt(2, started_at, message, "ACKNOWLEDGED" if matched else "FAILED", error)
    )
    if matched:
        return WakeResult(
            "ACKNOWLEDGED", 2, binding.wake_identity, message, tuple(attempts), tuple(dict.fromkeys(errors))
        )
    if error:
        errors.append(error)
    return WakeResult(
        "ESCALATE_LEVEL_3", None, binding.wake_identity, message, tuple(attempts), tuple(dict.fromkeys(errors))
    )
