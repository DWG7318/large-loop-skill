#!/usr/bin/env python3
import dataclasses
import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from method_lock import SUPPLY_CHAIN_CONFLICT, verify_method_lock
from provenance import (
    ADAPTER_CONTRACT_VERSION,
    AuthorityScope,
    BindingResult,
    CheckLivenessRequest,
    IsolationBindingSnapshot,
    IsolationResult,
    LivenessResult,
    ProvenanceError,
    ProvenanceEvaluator,
    ResolveBindingRequest,
    VerifyIsolationRequest,
    request_digest_for,
)
from run_package import FORMAL_ROOTS
from run_model import (
    RoleCapabilityProfile,
    RunBindingError,
    enforce_supervisor_capability_exclusion,
)
from run_patrol import (
    PATROL_CHECK_IDS,
    PatrolContractError,
    RunPatrolBinding,
    validate_method_role_capabilities,
    validate_patrol_capabilities,
    validate_patrol_inventory,
)
from worker_wake import REQUIRED_WORKER_WAKE_CAPABILITIES


REQUIRED_ROLE_TYPES = (
    "RUN_SUPERVISOR",
    "WORKER",
    "CHECKER",
    "GO_VERIFIER",
    "RUN_VERIFIER",
    "OWNER",
)
REQUIRED_OPERATIONAL_ISSUANCE = {
    "RUN_SUPERVISOR": frozenset(
        {
            "MONITOR_CONTROL", "WORKER_CHECKER_WAKE_BINDING",
            "DEVICE_CAPACITY_PROFILE", "CUMULATIVE_ENGINEERING_LOAD",
            "CELL_WORK_ESTIMATE", "CELL_CAPACITY_GATE", "CELL_PLAN_AMENDMENT",
            "SUPERVISOR_PROGRESS_EVENT",
        }
    ),
    "WORKER": frozenset({"WAKE_ATTEMPT", "PENDING_WAKE", "CELL_SCOPE_EXCEEDED"}),
    "CHECKER": frozenset({"WAKE_ACK", "CHECKER_PROGRESS_EVENT"}),
}
REQUIRED_ADAPTER_OPERATIONS = (
    "resolve_binding",
    "verify_issuance",
    "verify_isolation",
    "check_liveness",
)
REQUIRED_CAPABILITIES = {
    "RUN_SUPERVISOR": frozenset(
        {"GRAPH_EVENT", "SUPERVISOR_ADMISSION", "PREFLIGHT_ADMISSION"}
    ),
    "WORKER": frozenset({"D0_RECEIPT", "GO_CANDIDATE_CLOSURE"}),
    "CHECKER": frozenset({"D1_RECEIPT"}),
    "GO_VERIFIER": frozenset({"D2_RECEIPT"}),
    "RUN_VERIFIER": frozenset({"D3_RECEIPT"}),
    "OWNER": frozenset({"OWNER_ACCEPTANCE"}),
}
METHOD_LOCK_FIELDS = (
    "canonical_repository",
    "invocation",
    "commit_sha",
    "release_tag",
    "method_version",
    "schema_bundle_sha256",
    "skill_package_sha256",
    "validator_version",
    "validator_sha256",
    "adapter_profile_id",
    "adapter_contract_version",
)
LEGAL_ARCHITECTURE_RECOVERY = frozenset(
    {"FROZEN_AMENDMENT_REVALIDATION", "SEAL_AND_START_NEW_RUN"}
)
READINESS_ISOLATION_DIMENSIONS = (
    "conversation",
    "context",
    "workspace",
    "runtime_state",
    "evidence_root",
    "decision_input",
)


@dataclass(frozen=True)
class SimulationStep:
    kind: str
    subject_type: str
    subject_ref: str
    evidence_ref: str


@dataclass(frozen=True)
class SimulationReport:
    status: str
    failure_codes: Tuple[str, ...]
    marker: str
    projection_kind: str
    current_evidence_eligible: bool
    steps: Tuple[SimulationStep, ...]
    fork_active_go_ids: Tuple[str, ...]
    liveness_status: str
    health_inferred: bool
    architecture_hold_observed: bool
    recovery_decision: str | None
    formal_hold_cleared: bool
    formal_ledger_unchanged: bool
    package_index_sha256: str
    report_digest: str


@dataclass(frozen=True)
class PreflightReport:
    status: str
    failure_codes: Tuple[str, ...]
    projection_kind: str
    can_advance_run: bool
    package_index_sha256: str
    required_role_types: Tuple[str, ...]
    readiness_receipt_count: int
    readiness_observation_digest: str
    method_lock_report_digest: str | None
    current_holds: Tuple[str, ...]
    simulation_report_digest: str | None
    operational_report_digest: str | None
    report_digest: str


@dataclass(frozen=True)
class OperationalSimulationReport:
    status: str
    failure_codes: Tuple[str, ...]
    observed_wake_levels: Tuple[int, ...]
    progress_stages: Tuple[str, ...]
    capacity_results: Tuple[str, ...]
    severe_split_counts: Tuple[int, ...]
    formal_ledger_unchanged: bool
    patrol_check_ids: Tuple[str, ...]
    wait_all_rejected: bool
    all_role_subagent_capabilities_rejected: bool
    marker: str = "SIMULATION_ONLY"
    projection_kind: str = "DERIVED_NON_AUTHORITATIVE"
    current_evidence_eligible: bool = False


@dataclass(frozen=True)
class SupervisorControlOperation:
    operation: str
    timeout_ms: int
    looped: bool
    wait_all: bool

    def __post_init__(self):
        if self.operation != "wait_threads" or self.timeout_ms < 0:
            raise ValueError("SUPERVISOR_CONTROL_OPERATION_INVALID")


@dataclass(frozen=True)
class OperationalPreflightInput:
    run_id: str
    role_capability_profiles: Tuple[RoleCapabilityProfile, ...]
    worker_wake_binding_count: int
    worker_wake_bindings_valid: bool
    patrol_bindings: Tuple[RunPatrolBinding, ...]
    patrol_heartbeat_refs: Tuple[str, ...]
    patrol_capabilities: Tuple[str, ...]
    supervisor_control_operations: Tuple[SupervisorControlOperation, ...]
    dispatch_gate_results: Tuple[str, ...]
    capacity_profile_current: bool
    cumulative_load_current: bool
    progress_denominator_versions_current: bool
    simulation_report: OperationalSimulationReport


@dataclass(frozen=True)
class OperationalPreflightReport:
    status: str
    failure_codes: Tuple[str, ...]
    run_id: str
    can_dispatch: bool
    simulation_status: str
    report_digest: str
    projection_kind: str = "DERIVED_NON_AUTHORITATIVE"


def _canonical_digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def validate_operational_simulation(
    *,
    observed_wake_levels,
    early_stop_cleanup,
    pending_wake_patrol_consumed,
    legal_pause_suppressed,
    subtask_not_subagent,
    actual_subagent_rejected,
    owner_pin_accepted,
    agent_pin_rejected,
    unknown_pin_reported_without_unpin,
    pin_then_unpin_violation_retained,
    patrol_check_ids,
    wait_all_rejected,
    all_role_subagent_capabilities_rejected,
    progress_stages,
    capacity_results,
    severe_split_counts,
    resource_safe_activation,
    formal_ledger_before_sha256,
    formal_ledger_after_sha256,
):
    failures = []
    if tuple(observed_wake_levels) != (1, 2, 3, 4):
        failures.append("SIMULATION_WAKE_LEVELS_INCOMPLETE")
    required_flags = (
        early_stop_cleanup,
        pending_wake_patrol_consumed,
        legal_pause_suppressed,
        subtask_not_subagent,
        actual_subagent_rejected,
        owner_pin_accepted,
        agent_pin_rejected,
        unknown_pin_reported_without_unpin,
        pin_then_unpin_violation_retained,
        wait_all_rejected,
        all_role_subagent_capabilities_rejected,
        resource_safe_activation,
    )
    if not all(value is True for value in required_flags):
        failures.append("SIMULATION_OPERATIONAL_GUARD_INCOMPLETE")
    expected_stages = (
        "DELIVERED",
        "D1_ACCEPTED",
        "GO_CANDIDATE_READY",
        "D2_VERIFIED",
        "RUN_VERIFIED",
        "OWNER_ACCEPTED",
    )
    if tuple(progress_stages) != expected_stages:
        failures.append("SIMULATION_PROGRESS_STAGES_INCOMPLETE")
    if tuple(capacity_results) != ("PASS", "SPLIT_REQUIRED", "CAPACITY_BLOCKED"):
        failures.append("SIMULATION_CAPACITY_RESULTS_INCOMPLETE")
    if tuple(severe_split_counts) != (3, 6, 7, 8):
        failures.append("SIMULATION_SEVERE_SPLITS_INCOMPLETE")
    if tuple(patrol_check_ids) != PATROL_CHECK_IDS:
        failures.append("SIMULATION_PATROL_CHECKLIST_INCOMPLETE")
    ledger_unchanged = (
        isinstance(formal_ledger_before_sha256, str)
        and len(formal_ledger_before_sha256) == 64
        and formal_ledger_before_sha256 == formal_ledger_after_sha256
    )
    if not ledger_unchanged:
        failures.append("SIMULATION_FORMAL_LEDGER_MUTATED")
    return OperationalSimulationReport(
        status="SIMULATION_FAIL" if failures else "SIMULATION_PASS",
        failure_codes=tuple(sorted(set(failures))),
        observed_wake_levels=tuple(observed_wake_levels),
        progress_stages=tuple(progress_stages),
        capacity_results=tuple(capacity_results),
        severe_split_counts=tuple(severe_split_counts),
        formal_ledger_unchanged=ledger_unchanged,
        patrol_check_ids=tuple(patrol_check_ids),
        wait_all_rejected=wait_all_rejected is True,
        all_role_subagent_capabilities_rejected=(
            all_role_subagent_capabilities_rejected is True
        ),
    )


def derive_operational_preflight(values: OperationalPreflightInput) -> OperationalPreflightReport:
    failures = []
    role_types = tuple(profile.role_type for profile in values.role_capability_profiles)
    if len(role_types) != len(REQUIRED_ROLE_TYPES) or set(role_types) != set(REQUIRED_ROLE_TYPES):
        failures.append("ROLE_BINDING_INCOMPLETE")
    workers = tuple(
        profile for profile in values.role_capability_profiles if profile.role_type == "WORKER"
    )
    for profile in values.role_capability_profiles:
        try:
            validate_method_role_capabilities(profile.role_type, profile.operational_capabilities)
        except PatrolContractError as error:
            failures.append(
                "SUBAGENT_CAPABILITY_FORBIDDEN"
                if "SUBAGENT" in str(error)
                else "PIN_CAPABILITY_FORBIDDEN"
            )
        required_issuance = REQUIRED_OPERATIONAL_ISSUANCE.get(profile.role_type, frozenset())
        if not required_issuance.issubset(profile.issuable_artifact_types):
            failures.append("OPERATIONAL_ISSUANCE_CAPABILITY_MISSING")
    for worker in workers:
        if not set(REQUIRED_WORKER_WAKE_CAPABILITIES).issubset(worker.operational_capabilities):
            failures.append("WAKE_CAPABILITY_MISSING")
    if (
        values.worker_wake_binding_count != len(workers)
        or not values.worker_wake_bindings_valid
    ):
        failures.append("WAKE_BINDING_MISMATCH")

    inventory = validate_patrol_inventory(values.patrol_bindings, values.patrol_heartbeat_refs)
    failures.extend(inventory.alert_codes)
    try:
        validate_patrol_capabilities(values.patrol_capabilities)
    except PatrolContractError:
        failures.append("PATROL_FORBIDDEN_CAPABILITY")
    for operation in values.supervisor_control_operations:
        if not isinstance(operation, SupervisorControlOperation):
            failures.append("SUPERVISOR_CONTROL_OPERATION_INVALID")
            continue
        if operation.timeout_ms > 0 or operation.looped or operation.wait_all:
            failures.append("SUPERVISOR_WAIT_FORBIDDEN")

    if not values.capacity_profile_current:
        failures.append("DEVICE_CAPACITY_STALE")
    if not values.cumulative_load_current:
        failures.append("CUMULATIVE_LOAD_STALE")
    if not values.dispatch_gate_results or any(
        result != "PASS" for result in values.dispatch_gate_results
    ):
        failures.append("CELL_CAPACITY_NOT_PASS")
    if not values.progress_denominator_versions_current:
        failures.append("PROGRESS_DENOMINATOR_STALE")
    if values.simulation_report.status != "SIMULATION_PASS":
        failures.append("OPERATIONAL_SIMULATION_REQUIRED")

    failure_codes = tuple(sorted(set(failures)))
    payload = {
        "run_id": values.run_id,
        "failure_codes": failure_codes,
        "simulation_status": values.simulation_report.status,
    }
    return OperationalPreflightReport(
        status="PREFLIGHT_FAIL" if failure_codes else "PREFLIGHT_PASS",
        failure_codes=failure_codes,
        run_id=values.run_id,
        can_dispatch=not failure_codes,
        simulation_status=values.simulation_report.status,
        report_digest=_canonical_digest(payload),
    )


def _report_digest(report_type, values):
    return _canonical_digest({"report_type": report_type, **values})


def _signed_request(request_type, **values):
    request = request_type(request_digest="0" * 64, **values)
    return dataclasses.replace(request, request_digest=request_digest_for(request))


def _formal_artifact_digest(package, artifact):
    return next(
        (digest for digest, current in package.artifacts_by_digest.items() if current is artifact),
        None,
    )


def _indexed_evidence(package):
    if not package.index_chain:
        return {}
    return {
        item.get("path"): item.get("sha256")
        for item in package.index_chain[-1].get("evidence_objects", ())
        if isinstance(item, dict) or hasattr(item, "get")
    }


def _evidence_is_current(package, inventory, evidence_ref):
    digest = inventory.get(evidence_ref)
    return (
        isinstance(evidence_ref, str)
        and bool(evidence_ref)
        and isinstance(digest, str)
        and len(digest) == 64
        and digest in package.evidence_by_digest
    )


def _readiness_failures(package, adapter, observation_deadline):
    failures = []
    verified_bindings = 0
    profiles = package.artifacts_by_type.get("PROVENANCE_ADAPTER_PROFILE", ())
    observation = {
        "adapter_profile_id": profiles[0].get("profile_id") if len(profiles) == 1 else None,
        "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "binding_observations": [],
        "isolation_observation": None,
    }
    if not isinstance(observation_deadline, str) or not observation_deadline:
        return (
            ["READINESS_LIVENESS_INVALID"],
            verified_bindings,
            _canonical_digest(observation),
        )
    if any(not callable(getattr(adapter, operation, None)) for operation in REQUIRED_ADAPTER_OPERATIONS):
        return (
            ["READINESS_ADAPTER_INVALID"],
            verified_bindings,
            _canonical_digest(observation),
        )

    bindings = tuple(
        sorted(
            package.artifacts_by_type.get("ROLE_BINDING", ()),
            key=lambda item: item.get("role_binding_id", ""),
        )
    )
    binding_refs = tuple(binding.get("role_binding_id") for binding in bindings)
    role_types = tuple(binding.get("role_type") for binding in bindings)
    if (
        len(bindings) != len(REQUIRED_ROLE_TYPES)
        or len(set(binding_refs)) != len(bindings)
        or len(set(role_types)) != len(bindings)
        or set(role_types) != set(REQUIRED_ROLE_TYPES)
    ):
        failures.append("ROLE_BINDING_INCOMPLETE")
        observation["binding_refs"] = binding_refs
        return failures, verified_bindings, _canonical_digest(observation)

    inventory = _indexed_evidence(package)
    evaluator = ProvenanceEvaluator(adapter)
    binding_digests = {}
    resolved = {}
    for binding in bindings:
        binding_ref = binding["role_binding_id"]
        artifact_digest = _formal_artifact_digest(package, binding)
        if artifact_digest is None:
            failures.append("READINESS_BINDING_INVALID")
            continue
        binding_digests[binding_ref] = artifact_digest
        scope = AuthorityScope(
            graph_id=binding["graph_id"],
            go_id=binding.get("go_id"),
            cell_id=None,
        )
        request = _signed_request(
            ResolveBindingRequest,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            binding_ref=binding_ref,
            run_id=binding["run_id"],
            scope=scope,
            artifact_sha256=artifact_digest,
            expected_role=binding["role_type"],
        )
        binding_observation = {
            "binding_ref": binding_ref,
            "role_type": binding["role_type"],
            "artifact_sha256": artifact_digest,
            "binding_request_digest": request.request_digest,
            "formal_evidence": tuple(
                (ref, inventory.get(ref)) for ref in binding.get("evidence_refs", ())
            ),
        }
        try:
            result = evaluator.evaluate_binding(request)
        except (ProvenanceError, RunBindingError):
            failures.append("READINESS_BINDING_INVALID")
            binding_observation["binding_status"] = "INVALID"
            observation["binding_observations"].append(binding_observation)
            continue
        binding_observation.update(
            {
                "binding_status": result.status,
                "capability_profile_id": result.capability_profile.profile_id,
                "binding_evidence": (
                    result.evidence_ref,
                    inventory.get(result.evidence_ref),
                ),
                "binding_observed_at": result.observed_at,
            }
        )
        if (
            result.instance_id != binding.get("instance_id")
            or result.context_id != binding.get("execution_context_ref")
            or result.workspace_id != binding.get("workspace_ref")
            or result.evidence_root != binding.get("evidence_root")
            or result.capability_profile.profile_id != binding.get("capability_profile_id")
        ):
            failures.append("READINESS_BINDING_INVALID")
        required = REQUIRED_CAPABILITIES[binding["role_type"]]
        if not required.issubset(set(result.capability_profile.issuable_artifact_types)):
            failures.append("READINESS_CAPABILITY_MISSING")
        if binding["role_type"] == "RUN_SUPERVISOR":
            try:
                enforce_supervisor_capability_exclusion(result.capability_profile)
            except RunBindingError:
                failures.append("SUPERVISOR_TECHNICAL_CAPABILITY_FORBIDDEN")
        evidence_refs = tuple(binding.get("evidence_refs", ())) + (result.evidence_ref,)
        if not evidence_refs or any(
            not _evidence_is_current(package, inventory, ref) for ref in evidence_refs
        ):
            failures.append("READINESS_EVIDENCE_UNINDEXED")
        resolved[binding_ref] = result
        verified_bindings += 1

        liveness_request = _signed_request(
            CheckLivenessRequest,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            binding_ref=binding_ref,
            run_id=binding["run_id"],
            scope=scope,
            artifact_sha256=artifact_digest,
            deadline=observation_deadline,
        )
        try:
            liveness = evaluator.evaluate_liveness(liveness_request)
        except ProvenanceError:
            failures.append("READINESS_LIVENESS_INVALID")
            binding_observation["liveness_status"] = "INVALID"
        else:
            binding_observation.update(
                {
                    "liveness_request_digest": liveness_request.request_digest,
                    "liveness_status": liveness.status,
                    "liveness_evidence": (
                        liveness.evidence_ref,
                        inventory.get(liveness.evidence_ref),
                    ),
                    "liveness_observed_at": liveness.observed_at,
                }
            )
            if liveness.status != "LIVE":
                failures.append("READINESS_LIVENESS_INVALID")
            if not _evidence_is_current(package, inventory, liveness.evidence_ref):
                failures.append("READINESS_EVIDENCE_UNINDEXED")
        observation["binding_observations"].append(binding_observation)

    if len(resolved) == len(bindings):
        supervisor = next(
            binding for binding in bindings if binding["role_type"] == "RUN_SUPERVISOR"
        )
        isolation_digest = _canonical_digest(
            tuple((ref, binding_digests[ref]) for ref in binding_refs)
        )
        isolation_request = _signed_request(
            VerifyIsolationRequest,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            binding_ref=supervisor["role_binding_id"],
            run_id=supervisor["run_id"],
            scope=AuthorityScope(
                graph_id=supervisor["graph_id"], go_id=None, cell_id=None
            ),
            artifact_sha256=isolation_digest,
            binding_refs=binding_refs,
            required_dimensions=READINESS_ISOLATION_DIMENSIONS,
        )
        observation["isolation_observation"] = {
            "request_digest": isolation_request.request_digest,
            "required_dimensions": isolation_request.required_dimensions,
        }
        try:
            isolation = evaluator.evaluate_isolation(isolation_request)
        except ProvenanceError as error:
            observation["isolation_observation"]["error_code"] = error.code
            if error.code == "ISOLATION_INSUFFICIENT":
                failures.append("READINESS_ISOLATION_DIMENSION_MISSING")
            elif error.code == "ISOLATION_BINDINGS_INVALID":
                failures.append("READINESS_OBSERVATION_UNBOUND")
            elif error.code == "ISOLATION_COLLISION" and error.detail == "workspace":
                failures.append("READINESS_WORKSPACE_NOT_SEPARATED")
            else:
                failures.append("READINESS_ISOLATION_INVALID")
        else:
            snapshot_refs = tuple(item.binding_ref for item in isolation.binding_snapshots)
            if (
                len(snapshot_refs) != len(binding_refs)
                or len(set(snapshot_refs)) != len(snapshot_refs)
            ):
                failures.append("READINESS_OBSERVATION_UNBOUND")
            snapshots = {item.binding_ref: item for item in isolation.binding_snapshots}
            for binding in bindings:
                snapshot = snapshots[binding["role_binding_id"]]
                if (
                    snapshot.conversation_ref != binding.get("conversation_ref")
                    or snapshot.context_ref != binding.get("execution_context_ref")
                    or snapshot.workspace_ref != binding.get("workspace_ref")
                    or snapshot.evidence_root != binding.get("evidence_root")
                ):
                    failures.append("READINESS_ISOLATION_INVALID")
            if not _evidence_is_current(package, inventory, isolation.evidence_ref):
                failures.append("READINESS_EVIDENCE_UNINDEXED")
            observation["isolation_observation"].update(
                {
                    "verified_dimensions": isolation.verified_dimensions,
                    "binding_refs": snapshot_refs,
                    "evidence": (
                        isolation.evidence_ref,
                        inventory.get(isolation.evidence_ref),
                    ),
                    "observed_at": isolation.observed_at,
                }
            )
    return failures, verified_bindings, _canonical_digest(observation)


def _formal_ledger_digest(root):
    roots = set(FORMAL_ROOTS) | {"evidence"}
    inventory = []
    for dirname in sorted(roots):
        base = root / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                inventory.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
    return _canonical_digest(inventory)


def _records_by_type(package, artifact_type):
    records = []
    for digest, value in package.artifacts_by_digest.items():
        if value.get("artifact_type") == artifact_type:
            records.append((digest, value))
    return tuple(
        sorted(
            records,
            key=lambda item: (
                item[1].get("issued_at", ""),
                item[1].get("artifact_id", ""),
                item[0],
            ),
        )
    )


def _maximal_safe_successors(fork):
    successors = tuple(sorted(set(fork.get("successor_go_ids", ()))))
    conflicts = {
        frozenset(pair)
        for pair in fork.get("conflict_pairs", ())
        if isinstance(pair, (list, tuple)) and len(pair) == 2
    }
    for size in range(len(successors), -1, -1):
        safe = [
            choice
            for choice in itertools.combinations(successors, size)
            if all(frozenset(pair) not in conflicts for pair in itertools.combinations(choice, 2))
        ]
        if safe:
            return min(safe)
    return ()


def _simulation_payload(values):
    return {
        **values,
        "steps": [dataclasses.asdict(step) for step in values["steps"]],
    }


def simulate_run(package, validation_report, simulation_root, scenario):
    failures = []
    steps = []
    before_digest = _formal_ledger_digest(package.root)
    simulation_path = Path(simulation_root)
    expected_root = (package.root / "simulation").resolve(strict=False)
    simulation_root_valid = simulation_path.resolve(strict=False) == expected_root
    if not simulation_root_valid:
        failures.append("SIMULATION_ROOT_INVALID")
    if validation_report.status != "PASS" or any(
        layer.status != "PASS" for layer in validation_report.layers
    ):
        failures.append("RUN_PACKAGE_VALIDATION_REQUIRED")
    if validation_report.holds:
        failures.append("SIMULATION_ACTIVE_HOLD")

    admissions = {
        value.get("admitted_artifact_sha256"): (digest, value)
        for digest, value in _records_by_type(package, "SUPERVISOR_ADMISSION")
        if value.get("decision") == "ADMITTED"
    }

    def append_with_admission(artifact_type, kind):
        for digest, value in _records_by_type(package, artifact_type):
            steps.append(
                SimulationStep(
                    kind=kind,
                    subject_type=artifact_type,
                    subject_ref=value.get("artifact_id", digest),
                    evidence_ref=(value.get("evidence_refs") or ("MISSING",))[0],
                )
            )
            admission = admissions.get(digest)
            if admission is None:
                failures.append(f"{artifact_type}_ADMISSION_MISSING")
                continue
            admission_digest, admission_value = admission
            steps.append(
                SimulationStep(
                    kind="SUPERVISOR_ADMISSION",
                    subject_type="SUPERVISOR_ADMISSION",
                    subject_ref=admission_value.get("artifact_id", admission_digest),
                    evidence_ref=(admission_value.get("evidence_refs") or ("MISSING",))[0],
                )
            )

    append_with_admission("D0_RECEIPT", "TECHNICAL_RECEIPT")
    append_with_admission("D1_RECEIPT", "TECHNICAL_RECEIPT")
    append_with_admission("GO_CANDIDATE_CLOSURE", "GO_CLOSURE")
    append_with_admission("D2_RECEIPT", "TECHNICAL_RECEIPT")
    graph_events = _records_by_type(package, "GRAPH_EVENT")
    event_triggers = {value.get("trigger_artifact_sha256") for _, value in graph_events}
    for d2_digest, _ in _records_by_type(package, "D2_RECEIPT"):
        if d2_digest not in event_triggers:
            failures.append("D2_GRAPH_EVENT_MISSING")
    for digest, value in graph_events:
        steps.append(
            SimulationStep(
                kind="GRAPH_EVENT",
                subject_type="GRAPH_EVENT",
                subject_ref=value.get("artifact_id", digest),
                evidence_ref=(value.get("evidence_refs") or ("MISSING",))[0],
            )
        )
    append_with_admission("D3_RECEIPT", "TECHNICAL_RECEIPT")
    owners = _records_by_type(package, "OWNER_ACCEPTANCE")
    for digest, value in owners:
        steps.append(
            SimulationStep(
                kind="OWNER_GATE",
                subject_type="OWNER_ACCEPTANCE",
                subject_ref=value.get("artifact_id", digest),
                evidence_ref=(value.get("evidence_refs") or ("MISSING",))[0],
            )
        )
    if not owners:
        failures.append("OWNER_GATE_MISSING")

    fork = scenario.get("fork", {})
    source_go_id = fork.get("source_go_id")
    successor_go_ids = fork.get("successor_go_ids", ())
    active_go_ids = _maximal_safe_successors(fork)
    if not source_go_id or len(set(successor_go_ids)) < 2 or not active_go_ids:
        failures.append("FORK_MAX_SAFE_ACTIVATION_INVALID")

    liveness = scenario.get("liveness", {})
    liveness_status = liveness.get("status", "UNKNOWN")
    if liveness_status not in {"UNKNOWN", "UNREACHABLE"} or not liveness.get("evidence_ref"):
        failures.append("LIVENESS_FAILURE_NOT_REHEARSED")

    architecture = scenario.get("architecture", {})
    architecture_hold = architecture.get("hold") == "RUN_ARCHITECTURE_HOLD"
    recovery_decision = architecture.get("recovery_decision")
    if not architecture_hold:
        failures.append("ARCHITECTURE_HOLD_NOT_REHEARSED")
    if recovery_decision not in LEGAL_ARCHITECTURE_RECOVERY:
        failures.append("ARCHITECTURE_RECOVERY_INVALID")
    if not architecture.get("evidence_ref"):
        failures.append("ARCHITECTURE_RECOVERY_EVIDENCE_MISSING")

    if simulation_root_valid:
        simulation_path.mkdir(parents=True, exist_ok=True)
    after_digest = _formal_ledger_digest(package.root)
    formal_unchanged = before_digest == after_digest
    if not formal_unchanged:
        failures.append("FORMAL_LEDGER_MUTATED")
    failure_codes = tuple(sorted(set(failures)))
    values = {
        "status": "SIMULATION_PASS" if not failure_codes else "SIMULATION_FAIL",
        "failure_codes": failure_codes,
        "marker": "SIMULATION_ONLY",
        "projection_kind": "DERIVED_NON_AUTHORITATIVE",
        "current_evidence_eligible": False,
        "steps": tuple(steps),
        "fork_active_go_ids": tuple(active_go_ids),
        "liveness_status": liveness_status,
        "health_inferred": False,
        "architecture_hold_observed": architecture_hold,
        "recovery_decision": recovery_decision,
        "formal_hold_cleared": False,
        "formal_ledger_unchanged": formal_unchanged,
        "package_index_sha256": package.index_head_sha256,
    }
    digest = _report_digest("SIMULATION_REPORT", _simulation_payload(values))
    report = SimulationReport(**values, report_digest=digest)
    if simulation_root_valid:
        output = dataclasses.asdict(report)
        (simulation_path / "SIMULATION_REPORT.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def derive_preflight_report(
    package,
    validation_report,
    adapter,
    expected_method_lock,
    simulation_report,
    operational_input,
    *,
    current_holds,
    observation_deadline,
    installation_descriptors=None,
):
    failures = []
    locks = package.artifacts_by_type.get("GLK_METHOD_LOCK", ())
    actual_lock = locks[0] if len(locks) == 1 else None
    if actual_lock is None:
        failures.append("METHOD_LOCK_MISSING")
    missing_lock_fields = [
        field
        for field in METHOD_LOCK_FIELDS
        if field not in expected_method_lock or not expected_method_lock.get(field)
    ]
    if missing_lock_fields:
        failures.append("METHOD_LOCK_INCOMPLETE")
    elif actual_lock is not None and any(
        actual_lock.get(field) != expected_method_lock.get(field)
        for field in METHOD_LOCK_FIELDS
    ):
        failures.append("METHOD_LOCK_MISMATCH")

    profiles = package.artifacts_by_type.get("PROVENANCE_ADAPTER_PROFILE", ())
    profile = profiles[0] if len(profiles) == 1 else None
    if profile is None:
        failures.append("ADAPTER_PROFILE_MISSING")
    elif (
        set(profile.get("allowed_operations", ())) != set(REQUIRED_ADAPTER_OPERATIONS)
        or profile.get("technical_verdicts_forbidden") is not True
        or not profile.get("trust_root_refs")
        or profile.get("adapter_contract_version") != ADAPTER_CONTRACT_VERSION
        or actual_lock is None
        or profile.get("profile_id") != actual_lock.get("adapter_profile_id")
        or profile.get("adapter_contract_version") != actual_lock.get("adapter_contract_version")
    ):
        failures.append("ADAPTER_PROFILE_INVALID")

    method_lock_report_digest = None
    declared_installations = tuple(installation_descriptors or ())
    if actual_lock is None or profile is None or not declared_installations:
        failures.append(SUPPLY_CHAIN_CONFLICT)
    else:
        method_lock_report = verify_method_lock(
            actual_lock,
            profile,
            declared_installations,
        )
        method_lock_report_digest = method_lock_report.report_digest
        if method_lock_report.status != "PASS":
            failures.append(SUPPLY_CHAIN_CONFLICT)

    bindings = package.artifacts_by_type.get("ROLE_BINDING", ())
    bound_roles = {binding.get("role_type") for binding in bindings}
    if bound_roles != set(REQUIRED_ROLE_TYPES):
        failures.append("ROLE_BINDING_INCOMPLETE")
    readiness_failures, readiness_count, readiness_observation_digest = _readiness_failures(
        package, adapter, observation_deadline
    )
    failures.extend(readiness_failures)

    if (
        validation_report.status != "PASS"
        or len(validation_report.layers) not in {10, 11}
        or any(layer.status != "PASS" for layer in validation_report.layers)
    ):
        failures.append("RUN_PACKAGE_VALIDATION_REQUIRED")
    holds = tuple(sorted(set(current_holds) | set(validation_report.holds)))
    if holds:
        failures.append("PREFLIGHT_ACTIVE_HOLD")
    if simulation_report is None or simulation_report.status != "SIMULATION_PASS":
        failures.append("SIMULATION_REQUIRED")
    elif simulation_report.current_evidence_eligible:
        failures.append("SIMULATION_EVIDENCE_BOUNDARY_INVALID")
    operational_report = derive_operational_preflight(operational_input)
    if operational_report.status != "PREFLIGHT_PASS":
        failures.extend(operational_report.failure_codes)

    failure_codes = tuple(sorted(set(failures)))
    values = {
        "status": "PREFLIGHT_PASS" if not failure_codes else "PREFLIGHT_FAIL",
        "failure_codes": failure_codes,
        "projection_kind": "DERIVED_NON_AUTHORITATIVE",
        "can_advance_run": False,
        "package_index_sha256": package.index_head_sha256,
        "required_role_types": REQUIRED_ROLE_TYPES,
        "readiness_receipt_count": readiness_count,
        "readiness_observation_digest": readiness_observation_digest,
        "method_lock_report_digest": method_lock_report_digest,
        "current_holds": holds,
        "simulation_report_digest": (
            simulation_report.report_digest if simulation_report is not None else None
        ),
        "operational_report_digest": operational_report.report_digest,
    }
    digest = _report_digest("PREFLIGHT_REPORT", values)
    return PreflightReport(**values, report_digest=digest)
