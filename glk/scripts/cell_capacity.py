from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
from typing import Optional, Tuple


CAPACITY_CONTRACT_VERSION = "3.1.0"
CAPACITY_RESULTS = ("PASS", "SPLIT_REQUIRED", "CAPACITY_BLOCKED")
SAFETY_FACTOR = 0.80


class CapacityContractError(ValueError):
    pass


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise CapacityContractError("DEVICE_CAPACITY_UNKNOWN: timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise CapacityContractError("DEVICE_CAPACITY_UNKNOWN: timestamp") from error


@dataclass(frozen=True)
class CapacityVector:
    cpu_slots: int
    ram_mb: int
    gpu_count: int
    vram_mb: int
    disk_mb: int
    io_mb_s: int
    processes: int
    ports: Tuple[int, ...]
    parallel_commands: int
    duration_seconds: int
    context_tokens: int
    evidence_mb: int
    external_service_slots: int

    def __post_init__(self) -> None:
        for name in (
            "cpu_slots",
            "ram_mb",
            "gpu_count",
            "vram_mb",
            "disk_mb",
            "io_mb_s",
            "processes",
            "parallel_commands",
            "duration_seconds",
            "context_tokens",
            "evidence_mb",
            "external_service_slots",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise CapacityContractError(f"DEVICE_CAPACITY_UNKNOWN: {name}")
        if len(set(self.ports)) != len(self.ports) or any(
            not isinstance(port, int) or not 1 <= port <= 65535 for port in self.ports
        ):
            raise CapacityContractError("DEVICE_CAPACITY_UNKNOWN: ports")


@dataclass(frozen=True)
class DeviceCapacityProfile:
    profile_id: str
    profile_version: int
    observed_at: str
    fresh_until: str
    capacity: CapacityVector
    gpu_applicability: str
    network_applicability: str
    command_durations: Tuple[Tuple[str, int], ...]
    evidence_refs: Tuple[str, ...]
    units_explicit: bool
    provenance_verified: bool
    prior_profile_sha256: Optional[str]


@dataclass(frozen=True)
class CumulativeEngineeringLoad:
    load_id: str
    load_version: int
    profile_id: str
    profile_version: int
    graph_version: int
    accepted_baseline_ref: str
    regression_case_count: int
    regression_duration_seconds: int
    file_count: int
    dependency_count: int
    evidence_size_mb: int
    context_recovery_seconds: int
    active_reservations: CapacityVector
    evidence_refs: Tuple[str, ...]
    prior_load_sha256: Optional[str]
    observed_memory_peak_mb: int = 0


@dataclass(frozen=True)
class CellWorkEstimate:
    estimate_id: str
    go_id: str
    cell_id: str
    plan_id: str
    plan_version: int
    go_outcome_ref: str
    acceptance_refs: Tuple[str, ...]
    implementation_scope_refs: Tuple[str, ...]
    input_dependency_refs: Tuple[str, ...]
    expected_artifact_refs: Tuple[str, ...]
    build_test_matrix: Tuple[str, ...]
    checker_reproduction_refs: Tuple[str, ...]
    regression_refs: Tuple[str, ...]
    evidence_hash_cleanup_refs: Tuple[str, ...]
    context_refs: Tuple[str, ...]
    external_tool_refs: Tuple[str, ...]
    rollback_retry_count: int
    cumulative_coupling_score: int
    cost: CapacityVector
    includes_full_regression: bool
    dispatched: bool
    evidence_refs: Tuple[str, ...]


@dataclass(frozen=True)
class CellCapacityGate:
    profile_id: str
    profile_version: int
    load_id: str
    load_version: int
    estimate_id: str
    plan_version: int
    result: str
    reasons: Tuple[str, ...]
    evaluated_at: str


@dataclass(frozen=True)
class DispatchAuthorization:
    cell_id: str
    gate_result: str
    dispatch_authorized: bool


@dataclass(frozen=True)
class CellPlanAmendment:
    go_id: str
    parent_cell_id: str
    successor_cell_ids: Tuple[str, ...]
    go_outcome_ref: str
    acceptance_refs: Tuple[str, ...]
    plan_version: int
    manifest_version: int
    amendment_kind: str = "PRE_DISPATCH_SPLIT"


@dataclass(frozen=True)
class CellScopeExceeded:
    go_id: str
    cell_id: str
    plan_version: int
    checkpoint_refs: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    signal: str = "CELL_SCOPE_EXCEEDED"
    authorized_action: str = "RETURN_TO_ORIGINAL_CHECKER_AND_PLANNING_AUTHORITY"


@dataclass(frozen=True)
class PostDispatchSplitDefect:
    go_id: str
    cell_id: str
    successor_count: int
    codes: Tuple[str, ...]
    reevaluate_cell_ids: Tuple[str, ...]


def _profile_failures(profile: DeviceCapacityProfile, load: CumulativeEngineeringLoad, as_of: str) -> list[str]:
    failures = []
    if (
        not profile.profile_id
        or profile.profile_version < 1
        or not profile.units_explicit
        or not profile.provenance_verified
        or not profile.evidence_refs
    ):
        failures.append("DEVICE_CAPACITY_UNKNOWN")
    if profile.gpu_applicability not in {"AVAILABLE", "NOT_APPLICABLE"}:
        failures.append("DEVICE_CAPACITY_UNKNOWN")
    if profile.network_applicability not in {"AVAILABLE", "RESTRICTED", "NOT_APPLICABLE"}:
        failures.append("DEVICE_CAPACITY_UNKNOWN")
    required_positive = (
        profile.capacity.cpu_slots,
        profile.capacity.ram_mb,
        profile.capacity.disk_mb,
        profile.capacity.io_mb_s,
        profile.capacity.processes,
        profile.capacity.parallel_commands,
        profile.capacity.duration_seconds,
        profile.capacity.context_tokens,
        profile.capacity.evidence_mb,
    )
    if any(value <= 0 for value in required_positive):
        failures.append("DEVICE_CAPACITY_UNKNOWN")
    if not profile.command_durations or any(
        not name or not isinstance(seconds, int) or seconds <= 0
        for name, seconds in profile.command_durations
    ):
        failures.append("DEVICE_CAPACITY_UNKNOWN")
    try:
        if _utc(as_of) > _utc(profile.fresh_until) or _utc(profile.observed_at) > _utc(as_of):
            failures.append("DEVICE_CAPACITY_STALE")
    except CapacityContractError:
        failures.append("DEVICE_CAPACITY_UNKNOWN")
    if load.profile_id != profile.profile_id or load.profile_version != profile.profile_version:
        failures.append("DEVICE_CAPACITY_UNKNOWN")
    if load.load_version < 1 or not load.evidence_refs:
        failures.append("DEVICE_CAPACITY_UNKNOWN")
    return failures


def evaluate_cell_capacity(
    profile: DeviceCapacityProfile,
    load: CumulativeEngineeringLoad,
    estimate: CellWorkEstimate,
    *,
    as_of: str,
) -> CellCapacityGate:
    failures = _profile_failures(profile, load, as_of)
    if failures:
        return CellCapacityGate(
            profile.profile_id,
            profile.profile_version,
            load.load_id,
            load.load_version,
            estimate.estimate_id,
            estimate.plan_version,
            "CAPACITY_BLOCKED",
            tuple(sorted(set(failures))),
            as_of,
        )

    capacity = profile.capacity
    reservations = load.active_reservations
    requirements = {
        "CPU": estimate.cost.cpu_slots + reservations.cpu_slots,
        "RAM": estimate.cost.ram_mb + reservations.ram_mb + load.observed_memory_peak_mb,
        "GPU": estimate.cost.gpu_count + reservations.gpu_count,
        "VRAM": estimate.cost.vram_mb + reservations.vram_mb,
        "DISK": estimate.cost.disk_mb + reservations.disk_mb,
        "IO": estimate.cost.io_mb_s + reservations.io_mb_s,
        "PROCESSES": estimate.cost.processes + reservations.processes,
        "PARALLEL_COMMANDS": estimate.cost.parallel_commands + reservations.parallel_commands,
        "CONTEXT": estimate.cost.context_tokens + reservations.context_tokens,
        "EVIDENCE": estimate.cost.evidence_mb + reservations.evidence_mb + load.evidence_size_mb,
        "EXTERNAL_SERVICE": estimate.cost.external_service_slots + reservations.external_service_slots,
    }
    limits = {
        "CPU": capacity.cpu_slots,
        "RAM": capacity.ram_mb,
        "GPU": capacity.gpu_count,
        "VRAM": capacity.vram_mb,
        "DISK": capacity.disk_mb,
        "IO": capacity.io_mb_s,
        "PROCESSES": capacity.processes,
        "PARALLEL_COMMANDS": capacity.parallel_commands,
        "CONTEXT": capacity.context_tokens,
        "EVIDENCE": capacity.evidence_mb,
        "EXTERNAL_SERVICE": capacity.external_service_slots,
    }
    reasons = [name for name, value in requirements.items() if value > int(limits[name] * SAFETY_FACTOR)]
    required_ports = set(estimate.cost.ports) | set(reservations.ports)
    if not required_ports.issubset(set(capacity.ports)):
        reasons.append("PORT_NOT_PERMITTED")
    duration = estimate.cost.duration_seconds + load.context_recovery_seconds
    if estimate.includes_full_regression:
        duration += load.regression_duration_seconds
    if duration > int(capacity.duration_seconds * SAFETY_FACTOR):
        reasons.append("TOTAL_ENGINEERING_DURATION")
    result = "SPLIT_REQUIRED" if reasons else "PASS"
    if "PORT_NOT_PERMITTED" in reasons or (
        estimate.cost.gpu_count > 0 and profile.gpu_applicability == "NOT_APPLICABLE"
    ):
        result = "CAPACITY_BLOCKED"
    return CellCapacityGate(
        profile.profile_id,
        profile.profile_version,
        load.load_id,
        load.load_version,
        estimate.estimate_id,
        estimate.plan_version,
        result,
        tuple(sorted(set(reasons))),
        as_of,
    )


def authorize_dispatch(estimate: CellWorkEstimate, gate: CellCapacityGate) -> DispatchAuthorization:
    if gate.estimate_id != estimate.estimate_id or gate.plan_version != estimate.plan_version:
        raise CapacityContractError("CELL_CAPACITY_NOT_PASS: gate does not bind current estimate")
    if gate.result != "PASS":
        raise CapacityContractError("CELL_CAPACITY_NOT_PASS: only PASS may dispatch")
    return DispatchAuthorization(estimate.cell_id, gate.result, True)


def split_before_dispatch(
    parent: CellWorkEstimate,
    successors: Tuple[CellWorkEstimate, ...],
    *,
    new_manifest_version: int,
) -> CellPlanAmendment:
    if parent.dispatched:
        raise CapacityContractError("POST_DISPATCH_CELL_SPLIT: parent was already dispatched")
    if len(successors) < 2 or len({item.cell_id for item in successors}) != len(successors):
        raise CapacityContractError("CELL_SPLIT_INVALID: at least two unique successors required")
    if any(
        item.go_id != parent.go_id
        or item.go_outcome_ref != parent.go_outcome_ref
        or item.acceptance_refs != parent.acceptance_refs
        or item.dispatched
        or item.plan_version <= parent.plan_version
        for item in successors
    ):
        raise CapacityContractError("CELL_SPLIT_OUTCOME_CHANGED: GO outcome or acceptance changed")
    return CellPlanAmendment(
        go_id=parent.go_id,
        parent_cell_id=parent.cell_id,
        successor_cell_ids=tuple(item.cell_id for item in successors),
        go_outcome_ref=parent.go_outcome_ref,
        acceptance_refs=parent.acceptance_refs,
        plan_version=successors[0].plan_version,
        manifest_version=new_manifest_version,
    )


def record_scope_exceeded(
    *,
    actor_role: str,
    estimate: CellWorkEstimate,
    checkpoint_refs: Tuple[str, ...],
    evidence_refs: Tuple[str, ...],
    proposed_successor_cell_ids: Tuple[str, ...] = (),
) -> CellScopeExceeded:
    if actor_role != "WORKER":
        raise CapacityContractError("CELL_SCOPE_SIGNAL_ROLE_INVALID")
    if proposed_successor_cell_ids:
        raise CapacityContractError("CELL_SELF_SPLIT_FORBIDDEN: Worker cannot split its CELL")
    if not checkpoint_refs or not evidence_refs:
        raise CapacityContractError("CELL_SCOPE_EXCEEDED_EVIDENCE_MISSING")
    return CellScopeExceeded(
        estimate.go_id,
        estimate.cell_id,
        estimate.plan_version,
        checkpoint_refs,
        evidence_refs,
    )


def record_post_dispatch_split(
    estimate: CellWorkEstimate,
    *,
    successor_count: int,
    undispatched_cell_ids: Tuple[str, ...],
) -> PostDispatchSplitDefect:
    if not estimate.dispatched or successor_count < 2:
        raise CapacityContractError("POST_DISPATCH_CELL_SPLIT_INVALID")
    codes = ["POST_DISPATCH_CELL_SPLIT"]
    reevaluate = ()
    if successor_count >= 3:
        codes.append("CELL_OVERSIZE_SEVERE")
        reevaluate = tuple(undispatched_cell_ids)
    return PostDispatchSplitDefect(
        estimate.go_id, estimate.cell_id, successor_count, tuple(codes), reevaluate
    )


def _load_digest(load: CumulativeEngineeringLoad) -> str:
    return hashlib.sha256(repr(load).encode("utf-8")).hexdigest()


def update_cumulative_load(
    load: CumulativeEngineeringLoad,
    *,
    observed_regression_seconds: int,
    observed_memory_peak_mb: int,
    evidence_ref: str,
) -> CumulativeEngineeringLoad:
    if observed_regression_seconds < 0 or observed_memory_peak_mb < 0 or not evidence_ref:
        raise CapacityContractError("CUMULATIVE_LOAD_OBSERVATION_INVALID")
    return replace(
        load,
        load_version=load.load_version + 1,
        regression_duration_seconds=max(load.regression_duration_seconds, observed_regression_seconds),
        observed_memory_peak_mb=max(load.observed_memory_peak_mb, observed_memory_peak_mb),
        evidence_refs=tuple(dict.fromkeys(load.evidence_refs + (evidence_ref,))),
        prior_load_sha256=_load_digest(load),
    )
