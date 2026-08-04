import dataclasses
from dataclasses import InitVar, dataclass
from datetime import datetime, timezone
from typing import Tuple

from provenance import (
    ADAPTER_CONTRACT_VERSION,
    AuthorityScope,
    CheckLivenessRequest,
    LivenessResult,
    ProvenanceEvaluator,
    request_digest_for,
)


RUN_AUTHORITY_HOLD = "RUN_AUTHORITY_HOLD"
RUN_ARCHITECTURE_HOLD = "RUN_ARCHITECTURE_HOLD"
RUN_MONITOR_HOLD = "RUN_MONITOR_HOLD"
LEGAL_ARCHITECTURE_RECOVERY = frozenset(
    {"FROZEN_AMENDMENT_REVALIDATION", "SEAL_AND_START_NEW_RUN"}
)
PROGRESS_FIELDS = (
    "required_go_count",
    "d2_verified_required_go_count",
    "required_cell_count",
    "d1_accepted_required_cell_count",
    "active_go_ids",
    "waiting_go_reasons",
    "blocked_or_unreachable_role_bindings",
    "current_holds",
    "graph_version",
    "cell_manifest_versions",
    "cell_plan_versions",
    "capacity_profile_version",
    "cumulative_load_version",
)
FORBIDDEN_MONITOR_FIELDS = frozenset(
    {
        "created_task_ref",
        "created_task_id",
        "cron",
        "cron_expression",
        "cron_job",
        "schedule",
        "scheduler_ref",
    }
)


class RunControlError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True, order=True)
class LivenessIssue:
    code: str
    binding_ref: str
    detail: str


@dataclass(frozen=True)
class LivenessProjection:
    overall_state: str
    role_states: Tuple[Tuple[str, str], ...]
    blocked_or_unreachable_role_bindings: Tuple[str, ...]
    issues: Tuple[LivenessIssue, ...]
    observation_deadline: str
    as_of: str
    projection_kind: str = "DERIVED_NON_AUTHORITATIVE"


@dataclass(frozen=True, order=True)
class MonitorIssue:
    code: str
    artifact_ref: str
    detail: str


@dataclass(frozen=True)
class MonitorControlProjection:
    status: str
    monitor_key: str | None
    head_sha256: str | None
    patrol_conversation_ref: str | None
    patrol_heartbeat_ref: str | None
    callback_target: str | None
    observation_deadline: str | None
    issues: Tuple[MonitorIssue, ...]
    holds: Tuple[str, ...]
    projection_kind: str = "DERIVED_NON_AUTHORITATIVE"


@dataclass(frozen=True, order=True)
class ArchitectureFinding:
    path: str
    severity: str
    sequence: int
    evidence_ref: str

    def __post_init__(self):
        if not self.path or not self.evidence_ref or self.sequence < 1:
            raise RunControlError("ARCHITECTURE_FINDING_INVALID", self.path)


@dataclass(frozen=True)
class ArchitectureRecovery:
    decision: str
    external_recovery_ref: str
    callback_target: str


@dataclass(frozen=True)
class ControlHoldProjection:
    current_holds: Tuple[str, ...]
    architecture_path: str | None
    recovery_decision: str | None
    external_recovery_ref: str | None
    callback_target: str | None
    recovery_requires_formal_revalidation: bool
    may_continue: bool
    projection_kind: str = "DERIVED_NON_AUTHORITATIVE"


@dataclass(frozen=True)
class ProgressProjection:
    required_go_count: int
    d2_verified_required_go_count: int
    required_cell_count: int
    d1_accepted_required_cell_count: int
    active_go_ids: Tuple[str, ...]
    waiting_go_reasons: Tuple[Tuple[str, Tuple[str, ...]], ...]
    blocked_or_unreachable_role_bindings: Tuple[str, ...]
    current_holds: Tuple[str, ...]
    graph_version: int
    cell_manifest_versions: Tuple[Tuple[str, str, int], ...]
    cell_plan_versions: Tuple[Tuple[str, str, int], ...]
    capacity_profile_version: int | None
    cumulative_load_version: int | None
    required_go_ids_input: InitVar[Tuple[str, ...]]
    verified_go_ids_input: InitVar[Tuple[str, ...]]
    required_cell_ids_input: InitVar[Tuple[Tuple[str, str], ...]]
    accepted_cell_ids_input: InitVar[Tuple[Tuple[str, str], ...]]

    def __post_init__(
        self,
        required_go_ids_input,
        verified_go_ids_input,
        required_cell_ids_input,
        accepted_cell_ids_input,
    ):
        object.__setattr__(self, "_required_go_ids", required_go_ids_input)
        object.__setattr__(self, "_verified_go_ids", verified_go_ids_input)
        object.__setattr__(self, "_required_cell_ids", required_cell_ids_input)
        object.__setattr__(self, "_accepted_cell_ids", accepted_cell_ids_input)

    @property
    def required_go_ids(self):
        return self._required_go_ids

    @property
    def d2_verified_required_go_ids(self):
        return self._verified_go_ids

    @property
    def required_cell_ids(self):
        return self._required_cell_ids

    @property
    def d1_accepted_required_cell_ids(self):
        return self._accepted_cell_ids

    def as_dict(self):
        return {field: getattr(self, field) for field in PROGRESS_FIELDS}


def _signed_request(request_type, **values):
    request = request_type(request_digest="0" * 64, **values)
    return dataclasses.replace(request, request_digest=request_digest_for(request))


def _artifact_digest(package, artifact):
    digest = next(
        (
            current_digest
            for current_digest, current in package.artifacts_by_digest.items()
            if current is artifact
        ),
        None,
    )
    if digest is None:
        raise RunControlError("CONTROL_ARTIFACT_UNINDEXED", artifact.get("artifact_id", ""))
    return digest


def _evidence_inventory(package):
    if not package.index_chain:
        return {}
    return {
        item.get("path"): item.get("sha256")
        for item in package.index_chain[-1].get("evidence_objects", ())
    }


def _formal_path_by_digest(package):
    if not package.index_chain:
        return {}
    return {
        item.get("sha256"): item.get("path")
        for item in package.index_chain[-1].get("formal_artifacts", ())
    }


def _utc(value):
    if not isinstance(value, str):
        raise RunControlError("CONTROL_TIMESTAMP_INVALID", repr(value))
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        raise RunControlError("CONTROL_TIMESTAMP_INVALID", value) from error


def build_liveness_request(package, binding, observation_deadline):
    return _signed_request(
        CheckLivenessRequest,
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        binding_ref=binding["role_binding_id"],
        run_id=binding["run_id"],
        scope=AuthorityScope(
            graph_id=binding["graph_id"],
            go_id=binding.get("go_id"),
            cell_id=None,
        ),
        artifact_sha256=_artifact_digest(package, binding),
        deadline=observation_deadline,
    )


def _attestation_matches(package, request, result, evidence_inventory):
    profiles = package.artifacts_by_type.get("PROVENANCE_ADAPTER_PROFILE", ())
    profile_id = profiles[0].get("profile_id") if len(profiles) == 1 else None
    matches = []
    for attestation in package.artifacts_by_type.get("LIVENESS_ATTESTATION", ()):
        if (
            attestation.get("operation") == "check_liveness"
            and attestation.get("adapter_profile_id") == profile_id
            and attestation.get("binding_ref") == request.binding_ref
            and attestation.get("run_id") == request.run_id
            and attestation.get("graph_id") == request.scope.graph_id
            and attestation.get("request_digest") == request.request_digest
            and attestation.get("subject_artifact_sha256") == request.artifact_sha256
            and attestation.get("status") == result.status
            and attestation.get("observation_deadline") == request.deadline
            and attestation.get("observed_at") == result.observed_at
            and result.evidence_ref in attestation.get("evidence_refs", ())
        ):
            matches.append(attestation)
    evidence_digest = evidence_inventory.get(result.evidence_ref)
    return (
        len(matches) == 1
        and isinstance(evidence_digest, str)
        and len(evidence_digest) == 64
        and evidence_digest in package.evidence_by_digest
    )


def evaluate_liveness(package, adapter, *, observation_deadline, as_of):
    deadline = _utc(observation_deadline)
    observed_now = _utc(as_of)
    evaluator = ProvenanceEvaluator(adapter)
    evidence_inventory = _evidence_inventory(package)
    issues = []
    role_states = []
    bindings = tuple(
        sorted(
            package.artifacts_by_type.get("ROLE_BINDING", ()),
            key=lambda item: item.get("role_binding_id", ""),
        )
    )
    for binding in bindings:
        binding_ref = binding["role_binding_id"]
        request = build_liveness_request(package, binding, observation_deadline)
        result = None
        try:
            result = evaluator.evaluate_liveness(request)
        except Exception as error:
            issues.append(LivenessIssue("LIVENESS_READ_FAILED", binding_ref, str(error)))
        if result is not None and not _attestation_matches(
            package, request, result, evidence_inventory
        ):
            issues.append(
                LivenessIssue(
                    "LIVENESS_ATTESTATION_UNINDEXED_OR_UNBOUND",
                    binding_ref,
                    result.evidence_ref,
                )
            )
            result = None
        if result is not None:
            try:
                result_time = _utc(result.observed_at)
            except RunControlError as error:
                issues.append(
                    LivenessIssue(
                        "LIVENESS_ATTESTATION_TIME_INVALID",
                        binding_ref,
                        error.detail,
                    )
                )
                result = None
            else:
                if result_time > deadline or result_time > observed_now:
                    issues.append(
                        LivenessIssue(
                            "LIVENESS_ATTESTATION_TIME_INVALID",
                            binding_ref,
                            result.observed_at,
                        )
                    )
                    result = None
        if observed_now > deadline:
            state = "ROLE_UNREACHABLE"
        elif result is None or result.status == "UNKNOWN":
            state = "UNKNOWN"
        elif result.status == "UNREACHABLE":
            state = "ROLE_UNREACHABLE"
        else:
            state = result.status
        role_states.append((binding_ref, state))
    frozen_states = tuple(role_states)
    blocked = tuple(ref for ref, state in frozen_states if state != "LIVE")
    if frozen_states and all(state == "LIVE" for _, state in frozen_states):
        overall = "ALL_LIVE"
    elif any(state == "ROLE_UNREACHABLE" for _, state in frozen_states):
        overall = "ROLE_UNREACHABLE"
    else:
        overall = "UNKNOWN"
    return LivenessProjection(
        overall_state=overall,
        role_states=frozen_states,
        blocked_or_unreachable_role_bindings=blocked,
        issues=tuple(sorted(set(issues))),
        observation_deadline=observation_deadline,
        as_of=as_of,
    )


def _monitor_key(run_id):
    return f"{run_id}-ROLE-LIVENESS"


def advance_monitor_control(
    package,
    *,
    existing_patrol_conversation_ref=None,
    existing_patrol_heartbeat_ref=None,
    existing_callback_target=None,
    existing_supervisor_task_ref=None,
):
    controls = tuple(package.artifacts_by_type.get("MONITOR_CONTROL", ()))
    issues = []

    def add(code, control, detail):
        issues.append(MonitorIssue(code, control.get("artifact_id", "MONITOR"), detail))

    if not controls:
        issues.append(MonitorIssue("MONITOR_CONTROL_MISSING", "MONITOR", "no control"))
        return MonitorControlProjection(
            "MONITOR_HELD",
            None,
            None,
            None,
            None,
            None,
            None,
            tuple(issues),
            (RUN_MONITOR_HOLD,),
        )

    digests = {_artifact_digest(package, control): control for control in controls}
    run_ids = {control.get("run_id") for control in controls}
    modern_patrol = any(control.get("patrol_conversation_ref") for control in controls)
    expected_key = (
        f"{next(iter(run_ids))}-RUN-PATROL"
        if len(run_ids) == 1 and modern_patrol
        else _monitor_key(next(iter(run_ids))) if len(run_ids) == 1 else None
    )
    if expected_key is None or any(
        control.get("monitor_key") != expected_key for control in controls
    ):
        add("MONITOR_KEY_INVALID", controls[0], "monitor_key is not deterministic")
    if len({control.get("monitor_id") for control in controls}) != 1:
        add("MONITOR_DUPLICATE_KEY", controls[0], "multiple monitor identities")

    for control in controls:
        forbidden = FORBIDDEN_MONITOR_FIELDS & set(control)
        if forbidden:
            add("MONITOR_CRON_FORBIDDEN", control, ",".join(sorted(forbidden)))
        if modern_patrol:
            if control.get("patrol_conversation_ref") != existing_patrol_conversation_ref:
                add("MONITOR_SECOND_VISIBLE_TASK", control, "patrol conversation reference changed")
            if control.get("patrol_heartbeat_ref") != existing_patrol_heartbeat_ref:
                add("PATROL_HEARTBEAT_DUPLICATE", control, "patrol heartbeat reference changed")
            expected_interval = {"HIGH": 10, "MEDIUM": 15, "LOW": 30}.get(
                control.get("project_difficulty")
            )
            if (
                control.get("patrol_model") != "gpt-5.6-luna"
                or control.get("patrol_reasoning_effort") != "xhigh"
                or control.get("patrol_interval_minutes") != expected_interval
            ):
                add("PATROL_BINDING_INVALID", control, "patrol model, effort, or interval")
        elif control.get("supervisor_task_ref") != existing_supervisor_task_ref:
            add("MONITOR_SECOND_VISIBLE_TASK", control, "historical Supervisor task reference changed")
        if control.get("callback_target") != existing_callback_target:
            add("MONITOR_CALLBACK_INVALID", control, "callback target changed")

    roots = [control for control in controls if control.get("prior_monitor_sha256") is None]
    if len(roots) != 1:
        add("MONITOR_DUPLICATE_KEY", controls[0], "monitor chain has multiple roots")
    child_digests = {}
    referenced_priors = set()
    for digest, control in digests.items():
        prior = control.get("prior_monitor_sha256")
        if prior is None:
            if control.get("monitor_version") != 1:
                add("MONITOR_CHAIN_INVALID", control, "root version must be 1")
            continue
        referenced_priors.add(prior)
        child_digests.setdefault(prior, []).append(digest)
        parent = digests.get(prior)
        if parent is None or control.get("monitor_version") != parent.get("monitor_version", 0) + 1:
            add("MONITOR_CHAIN_INVALID", control, "prior digest or version is invalid")
    if any(len(children) > 1 for children in child_digests.values()):
        add("MONITOR_FORKED_HEAD", controls[0], "one monitor head has multiple successors")
    heads = tuple(sorted(set(digests) - referenced_priors))
    if len(heads) != 1:
        add("MONITOR_FORKED_HEAD", controls[0], "monitor chain does not have one head")

    formal_paths = _formal_path_by_digest(package)
    artifact_by_path = {
        formal_paths[digest]: value
        for digest, value in package.artifacts_by_digest.items()
        if digest in formal_paths
    }
    bindings = {
        binding.get("role_binding_id"): binding
        for binding in package.artifacts_by_type.get("ROLE_BINDING", ())
    }
    profiles = package.artifacts_by_type.get("PROVENANCE_ADAPTER_PROFILE", ())
    current_profile_id = profiles[0].get("profile_id") if len(profiles) == 1 else None
    for control in controls:
        refs = tuple(control.get("liveness_attestation_refs", ()))
        indexed = bool(refs) and not any(
            ref not in artifact_by_path
            or artifact_by_path[ref].get("artifact_type") != "LIVENESS_ATTESTATION"
            for ref in refs
        )
        if not indexed:
            add(
                "MONITOR_LIVENESS_ATTESTATION_UNINDEXED",
                control,
                "liveness attestation reference is not a current formal artifact",
            )
            continue
        attestations = tuple(artifact_by_path[ref] for ref in refs)
        bound_refs = tuple(item.get("binding_ref") for item in attestations)
        exact_set = (
            len(refs) == len(set(refs)) == len(bindings)
            and len(bound_refs) == len(set(bound_refs))
            and set(bound_refs) == set(bindings)
        )
        for attestation in attestations:
            binding = bindings.get(attestation.get("binding_ref"))
            if binding is None:
                exact_set = False
                continue
            expected_request = build_liveness_request(
                package, binding, control.get("observation_deadline")
            )
            if (
                attestation.get("operation") != "check_liveness"
                or attestation.get("adapter_profile_id") != current_profile_id
                or attestation.get("run_id") != control.get("run_id")
                or attestation.get("graph_id") != control.get("graph_id")
                or attestation.get("observation_deadline")
                != control.get("observation_deadline")
                or attestation.get("request_digest") != expected_request.request_digest
                or attestation.get("subject_artifact_sha256")
                != expected_request.artifact_sha256
            ):
                exact_set = False
        if not exact_set:
            add(
                "MONITOR_LIVENESS_ATTESTATION_UNBOUND",
                control,
                "liveness attestations do not bind the current Run role set",
            )

    ordered_issues = tuple(sorted(set(issues)))
    head = digests[heads[0]] if len(heads) == 1 else None
    return MonitorControlProjection(
        status="MONITOR_HELD" if ordered_issues else head.get("monitor_state", "MONITOR_HELD"),
        monitor_key=expected_key,
        head_sha256=heads[0] if len(heads) == 1 else None,
        patrol_conversation_ref=head.get("patrol_conversation_ref") if head is not None else None,
        patrol_heartbeat_ref=head.get("patrol_heartbeat_ref") if head is not None else None,
        callback_target=head.get("callback_target") if head is not None else None,
        observation_deadline=head.get("observation_deadline") if head is not None else None,
        issues=ordered_issues,
        holds=(RUN_MONITOR_HOLD,) if ordered_issues else (),
    )


def derive_control_holds(validation_holds, architecture_findings, *, recovery=None):
    holds = set(validation_holds)
    held_path = None
    findings_by_path = {}
    for finding in architecture_findings:
        findings_by_path.setdefault(finding.path, []).append(finding)
    for path in sorted(findings_by_path):
        ordered = tuple(
            sorted(findings_by_path[path], key=lambda item: item.sequence)
        )
        if any(
            previous.severity == "HIGH"
            and current.severity == "HIGH"
            and current.sequence == previous.sequence + 1
            for previous, current in zip(ordered, ordered[1:])
        ):
            held_path = path
            holds.add(RUN_ARCHITECTURE_HOLD)
            break
    if recovery is not None:
        if (
            recovery.decision not in LEGAL_ARCHITECTURE_RECOVERY
            or not recovery.external_recovery_ref
            or not recovery.callback_target
        ):
            raise RunControlError("ARCHITECTURE_RECOVERY_INVALID", recovery.decision)
        if RUN_ARCHITECTURE_HOLD not in holds:
            raise RunControlError("ARCHITECTURE_RECOVERY_WITHOUT_HOLD", recovery.decision)
    return ControlHoldProjection(
        current_holds=tuple(sorted(holds)),
        architecture_path=held_path,
        recovery_decision=recovery.decision if recovery is not None else None,
        external_recovery_ref=(
            recovery.external_recovery_ref if recovery is not None else None
        ),
        callback_target=recovery.callback_target if recovery is not None else None,
        recovery_requires_formal_revalidation=recovery is not None,
        may_continue=not holds,
    )


def _current_manifests(package, required_go_ids):
    by_go = {}
    for manifest in package.artifacts_by_type.get("CELL_MANIFEST", ()):
        go_id = manifest.get("go_id")
        if go_id not in required_go_ids:
            continue
        current = by_go.get(go_id)
        if current is None or manifest.get("manifest_version", 0) > current.get(
            "manifest_version", 0
        ):
            by_go[go_id] = manifest
    if set(by_go) != set(required_go_ids):
        raise RunControlError("PROGRESS_MANIFEST_INCOMPLETE", ",".join(required_go_ids))
    return by_go


def derive_progress(package, validation_report, liveness, control_holds):
    topology = validation_report.graph_topology
    graph_state = validation_report.graph_state
    if topology is None or graph_state is None:
        raise RunControlError("PROGRESS_GRAPH_FACTS_MISSING", "validated topology required")
    required_go_ids = tuple(topology.required_go_ids)
    verified_go_ids = tuple(
        sorted(set(required_go_ids) & set(graph_state.verified_go_ids))
    )
    manifests = _current_manifests(package, required_go_ids)
    required_cells = tuple(
        sorted(
            (go_id, cell["cell_id"])
            for go_id, manifest in manifests.items()
            for cell in manifest.get("required_cells", ())
            if cell.get("required") is True
        )
    )
    admitted_digests = {
        admission.get("admitted_artifact_sha256")
        for admission in package.artifacts_by_type.get("SUPERVISOR_ADMISSION", ())
        if admission.get("decision") == "ADMITTED"
    }
    accepted_cells = []
    for digest, receipt in package.artifacts_by_digest.items():
        if receipt.get("artifact_type") != "D1_RECEIPT" or receipt.get("verdict") != "D1_PASS":
            continue
        go_id = receipt.get("go_id")
        cell_id = receipt.get("cell_id")
        manifest = manifests.get(go_id)
        if (
            digest in admitted_digests
            and (go_id, cell_id) in required_cells
            and receipt.get("manifest_id") == manifest.get("manifest_id")
            and receipt.get("manifest_version") == manifest.get("manifest_version")
            and receipt.get("manifest_closure_sha256") == manifest.get("closure_sha256")
        ):
            accepted_cells.append((go_id, cell_id))
    accepted_cell_ids = tuple(sorted(set(accepted_cells)))

    node_by_id = {node.go_id: node for node in topology.nodes}
    waiting_reasons = []
    for go_id in graph_state.waiting_go_ids:
        node = node_by_id[go_id]
        reasons = [
            f"DEPENDENCY_WAITING_GO:{predecessor}"
            for predecessor in node.predecessors
            if predecessor not in graph_state.verified_go_ids
        ]
        reasons.extend(
            "CONSTRAINT_WAITING_GO:"
            + constraint.kind
            + ":"
            + ",".join(constraint.references)
            for constraint in node.constraints
        )
        waiting_reasons.append((go_id, tuple(reasons)))
    manifest_versions = tuple(
        sorted(
            (
                go_id,
                manifest["manifest_id"],
                manifest["manifest_version"],
            )
            for go_id, manifest in manifests.items()
        )
    )
    plan_versions = tuple(
        sorted(
            (
                item.get("go_id"),
                item.get("plan_id"),
                item.get("plan_version"),
            )
            for item in package.artifacts_by_type.get("CELL_WORK_ESTIMATE", ())
            if item.get("go_id") in required_go_ids
        )
    )
    capacity_versions = tuple(
        item.get("profile_version")
        for item in package.artifacts_by_type.get("DEVICE_CAPACITY_PROFILE", ())
        if isinstance(item.get("profile_version"), int)
    )
    load_versions = tuple(
        item.get("load_version")
        for item in package.artifacts_by_type.get("CUMULATIVE_ENGINEERING_LOAD", ())
        if isinstance(item.get("load_version"), int)
    )
    holds = tuple(
        sorted(set(validation_report.holds) | set(control_holds.current_holds))
    )
    return ProgressProjection(
        required_go_count=len(required_go_ids),
        d2_verified_required_go_count=len(verified_go_ids),
        required_cell_count=len(required_cells),
        d1_accepted_required_cell_count=len(accepted_cell_ids),
        active_go_ids=tuple(graph_state.active_go_ids),
        waiting_go_reasons=tuple(waiting_reasons),
        blocked_or_unreachable_role_bindings=tuple(
            liveness.blocked_or_unreachable_role_bindings
        ),
        current_holds=holds,
        graph_version=topology.graph_version,
        cell_manifest_versions=manifest_versions,
        cell_plan_versions=plan_versions,
        capacity_profile_version=max(capacity_versions) if capacity_versions else None,
        cumulative_load_version=max(load_versions) if load_versions else None,
        required_go_ids_input=required_go_ids,
        verified_go_ids_input=verified_go_ids,
        required_cell_ids_input=required_cells,
        accepted_cell_ids_input=accepted_cell_ids,
    )
