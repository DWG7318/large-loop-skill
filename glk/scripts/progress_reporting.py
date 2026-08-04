from dataclasses import dataclass
import hashlib
import json
from typing import Optional, Tuple


PROGRESS_CONTRACT_VERSION = "3.1.0"
PROGRESS_STATES = (
    "DELIVERED",
    "D1_ACCEPTED",
    "GO_CANDIDATE_READY",
    "D2_VERIFIED",
    "RUN_VERIFIED",
    "OWNER_ACCEPTED",
)


class ProgressContractError(ValueError):
    pass


def _required_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ProgressContractError(f"PROGRESS_SOURCE_INVALID: {name}")


@dataclass(frozen=True)
class WorkerDeliveryProgress:
    run_id: str
    go_id: str
    cell_id: str
    round_id: str
    cell_ordinal: int
    required_cell_count: int
    manifest_version: int
    state: str

    def __post_init__(self) -> None:
        for name in ("run_id", "go_id", "cell_id", "round_id"):
            _required_text(name, getattr(self, name))
        if self.state != "DELIVERED":
            raise ProgressContractError("PROGRESS_STAGE_OVERCLAIMED: Worker may only report DELIVERED")
        if not 1 <= self.cell_ordinal <= self.required_cell_count or self.manifest_version < 1:
            raise ProgressContractError("PROGRESS_SOURCE_INVALID: CELL position/version")

    @property
    def message(self) -> str:
        return f"GO {self.go_id} CELL {self.cell_ordinal}/{self.required_cell_count} 已交付，请检查"

    @property
    def accepted_cell_count_delta(self) -> int:
        return 0


@dataclass(frozen=True)
class RequiredCellSet:
    go_id: str
    manifest_id: str
    manifest_version: int
    plan_id: str
    plan_version: int
    required_cell_ids: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("go_id", "manifest_id", "plan_id"):
            _required_text(name, getattr(self, name))
        if self.manifest_version < 1 or self.plan_version < 1:
            raise ProgressContractError("PROGRESS_SOURCE_INVALID: required-set version")
        if not self.required_cell_ids or len(set(self.required_cell_ids)) != len(self.required_cell_ids):
            raise ProgressContractError("PROGRESS_SOURCE_INVALID: Required CELL set")
        if any(not isinstance(value, str) or not value for value in self.required_cell_ids):
            raise ProgressContractError("PROGRESS_SOURCE_INVALID: Required CELL identity")


@dataclass(frozen=True)
class D1ProgressFact:
    go_id: str
    cell_id: str
    manifest_id: str
    manifest_version: int
    verdict: str
    receipt_digest: str
    current_valid: bool
    admitted: bool
    round_id: str


@dataclass(frozen=True)
class CheckerProgressProjection:
    go_id: str
    current_cell_id: str
    accepted_cell_ids: Tuple[str, ...]
    accepted_cell_count: int
    required_cell_count: int
    manifest_version: int
    plan_version: int
    state: str
    message: str
    projection_kind: str = "DERIVED_NON_AUTHORITATIVE"


@dataclass(frozen=True)
class GoBoundaryMilestone:
    go_id: str
    go_ordinal: int
    required_go_count: int
    accepted_cell_count: int
    required_cell_count: int
    manifest_version: int
    plan_version: int
    state: str
    d2_verified: bool
    identity: str
    message: str
    projection_kind: str = "DERIVED_NON_AUTHORITATIVE"


@dataclass(frozen=True)
class SupervisorProgressProjection:
    run_id: str
    required_go_count: int
    d2_verified_required_go_count: int
    required_cell_count: int
    d1_accepted_required_cell_count: int
    active_go_ids: Tuple[str, ...]
    waiting_go_reasons: Tuple[Tuple[str, Tuple[str, ...]], ...]
    holds: Tuple[str, ...]
    graph_version: int
    cell_manifest_versions: Tuple[Tuple[str, str, int], ...]
    cell_plan_versions: Tuple[Tuple[str, str, int], ...]
    capacity_profile_version: int
    cumulative_load_version: int
    run_state: str
    message: str
    projection_kind: str = "DERIVED_NON_AUTHORITATIVE"


def checker_wake_messages(delivery: WorkerDeliveryProgress) -> Tuple[str, str]:
    return (
        f"WAKE_ACK RUN={delivery.run_id} GO={delivery.go_id} "
        f"CELL={delivery.cell_id} ROUND={delivery.round_id}",
        f"收到{delivery.go_id} CELL {delivery.cell_ordinal}/{delivery.required_cell_count}，开始检查",
    )


def _accepted_cells(required: RequiredCellSet, facts: Tuple[D1ProgressFact, ...]) -> Tuple[str, ...]:
    required_ids = set(required.required_cell_ids)
    accepted = {
        fact.cell_id
        for fact in facts
        if fact.go_id == required.go_id
        and fact.cell_id in required_ids
        and fact.manifest_id == required.manifest_id
        and fact.manifest_version == required.manifest_version
        and fact.verdict == "D1_PASS"
        and fact.current_valid is True
        and fact.admitted is True
        and isinstance(fact.receipt_digest, str)
        and len(fact.receipt_digest) == 64
    }
    return tuple(sorted(accepted))


def derive_checker_progress(
    required: RequiredCellSet,
    facts: Tuple[D1ProgressFact, ...],
    *,
    current_cell_id: str,
    rework_round: Optional[str] = None,
    blocker_ref: Optional[str] = None,
) -> CheckerProgressProjection:
    if current_cell_id not in required.required_cell_ids:
        raise ProgressContractError("PROGRESS_SOURCE_INVALID: current CELL is not Required")
    accepted = _accepted_cells(required, facts)
    count = len(accepted)
    current = tuple(
        fact
        for fact in facts
        if fact.go_id == required.go_id
        and fact.cell_id == current_cell_id
        and fact.manifest_id == required.manifest_id
        and fact.manifest_version == required.manifest_version
        and fact.current_valid
        and fact.admitted
    )
    verdicts = {fact.verdict for fact in current}
    if "D1_BLOCKED" in verdicts or blocker_ref:
        message = (
            f"{required.go_id} CELL验收仍为 {count}/{len(required.required_cell_ids)}，"
            f"{current_cell_id}阻断={blocker_ref or 'D1_BLOCKED'}"
        )
        state = "DELIVERED"
    elif "D1_REWORK" in verdicts or "D1_FAIL" in verdicts or rework_round:
        message = (
            f"{required.go_id} CELL验收仍为 {count}/{len(required.required_cell_ids)}，"
            f"{current_cell_id}进入{rework_round or 'REWORK'}返工"
        )
        state = "DELIVERED"
    elif count == len(required.required_cell_ids):
        message = f"{required.go_id} CELL验收 {count}/{len(required.required_cell_ids)}，GO候选待形成"
        state = "D1_ACCEPTED"
    else:
        message = f"{required.go_id} CELL验收 {count}/{len(required.required_cell_ids)}，下一CELL待交付"
        state = "D1_ACCEPTED" if current_cell_id in accepted else "DELIVERED"
    return CheckerProgressProjection(
        go_id=required.go_id,
        current_cell_id=current_cell_id,
        accepted_cell_ids=accepted,
        accepted_cell_count=count,
        required_cell_count=len(required.required_cell_ids),
        manifest_version=required.manifest_version,
        plan_version=required.plan_version,
        state=state,
        message=message,
    )


def _identity(parts: object) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_go_boundary_milestone(
    required: RequiredCellSet,
    facts: Tuple[D1ProgressFact, ...],
    *,
    closure_current: bool,
    go_ordinal: int,
    required_go_count: int,
    d2_current_pass: bool = False,
    previously_emitted_identity: Optional[str] = None,
) -> Optional[GoBoundaryMilestone]:
    accepted = _accepted_cells(required, facts)
    if len(accepted) != len(required.required_cell_ids) or not closure_current:
        return None
    if not 1 <= go_ordinal <= required_go_count:
        raise ProgressContractError("PROGRESS_SOURCE_INVALID: GO position")
    state = "D2_VERIFIED" if d2_current_pass else "GO_CANDIDATE_READY"
    identity = _identity(
        (
            required.go_id,
            required.manifest_id,
            required.manifest_version,
            required.plan_id,
            required.plan_version,
            accepted,
            state,
        )
    )
    if identity == previously_emitted_identity:
        return None
    message = (
        f"GO {go_ordinal}/{required_go_count}；本GO CELL "
        f"{len(accepted)}/{len(required.required_cell_ids)}已验收；当前状态={state}"
    )
    return GoBoundaryMilestone(
        go_id=required.go_id,
        go_ordinal=go_ordinal,
        required_go_count=required_go_count,
        accepted_cell_count=len(accepted),
        required_cell_count=len(required.required_cell_ids),
        manifest_version=required.manifest_version,
        plan_version=required.plan_version,
        state=state,
        d2_verified=d2_current_pass,
        identity=identity,
        message=message,
    )


def derive_supervisor_progress(
    *,
    run_id: str,
    graph_version: int,
    required_go_ids: Tuple[str, ...],
    d2_verified_go_ids: Tuple[str, ...],
    required_cell_sets: Tuple[RequiredCellSet, ...],
    d1_facts: Tuple[D1ProgressFact, ...],
    active_go_ids: Tuple[str, ...],
    waiting_go_reasons: Tuple[Tuple[str, Tuple[str, ...]], ...],
    holds: Tuple[str, ...],
    capacity_profile_version: int,
    cumulative_load_version: int,
    run_verified: bool,
    owner_accepted: bool,
    previous: Optional[SupervisorProgressProjection] = None,
) -> Optional[SupervisorProgressProjection]:
    required_go = tuple(dict.fromkeys(required_go_ids))
    if not required_go or len(required_go) != len(required_go_ids):
        raise ProgressContractError("PROGRESS_SOURCE_INVALID: Required GO set")
    verified = tuple(sorted(set(required_go) & set(d2_verified_go_ids)))
    required_cells = tuple(
        sorted((item.go_id, cell_id) for item in required_cell_sets for cell_id in item.required_cell_ids)
    )
    accepted_cells = tuple(
        sorted(
            (item.go_id, cell_id)
            for item in required_cell_sets
            for cell_id in _accepted_cells(item, d1_facts)
        )
    )
    manifests = tuple(
        sorted((item.go_id, item.manifest_id, item.manifest_version) for item in required_cell_sets)
    )
    plans = tuple(sorted((item.go_id, item.plan_id, item.plan_version) for item in required_cell_sets))
    if owner_accepted and not run_verified:
        raise ProgressContractError("PROGRESS_STAGE_OVERCLAIMED: Owner Acceptance requires Run verification")
    if owner_accepted:
        run_state = "OWNER_ACCEPTED"
    elif run_verified:
        run_state = "RUN_VERIFIED"
    elif verified:
        run_state = "D2_VERIFIED"
    else:
        run_state = "DELIVERED"
    message = (
        f"Run={run_id} CELL(D1)={len(accepted_cells)}/{len(required_cells)} "
        f"GO(D2)={len(verified)}/{len(required_go)} ACTIVE={','.join(active_go_ids) or '-'} "
        f"WAITING={len(waiting_go_reasons)} HOLDS={','.join(sorted(set(holds))) or '-'} "
        f"Graph=v{graph_version} Capacity=v{capacity_profile_version} Load=v{cumulative_load_version} "
        f"状态={run_state}"
    )
    current = SupervisorProgressProjection(
        run_id=run_id,
        required_go_count=len(required_go),
        d2_verified_required_go_count=len(verified),
        required_cell_count=len(required_cells),
        d1_accepted_required_cell_count=len(accepted_cells),
        active_go_ids=tuple(active_go_ids),
        waiting_go_reasons=tuple(waiting_go_reasons),
        holds=tuple(sorted(set(holds))),
        graph_version=graph_version,
        cell_manifest_versions=manifests,
        cell_plan_versions=plans,
        capacity_profile_version=capacity_profile_version,
        cumulative_load_version=cumulative_load_version,
        run_state=run_state,
        message=message,
    )
    if current == previous:
        return None
    return current


def validate_progress_emitter(emitter: str, event_kind: str) -> None:
    if event_kind == "CONTINUOUS_PROGRESS" and emitter not in {"CHECKER", "RUN_SUPERVISOR"}:
        raise ProgressContractError(
            f"PROGRESS_EMITTER_FORBIDDEN: {emitter} cannot emit continuous progress"
        )
