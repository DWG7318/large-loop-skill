import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from jsonschema import Draft202012Validator, FormatChecker

from artifact_model import FORMAL_TYPES
from provenance import (
    ADAPTER_CONTRACT_VERSION,
    AuthorityScope,
    ProvenanceError,
    ProvenanceEvaluator,
    ResolveBindingRequest,
    VerifyIsolationRequest,
    VerifyIssuanceRequest,
    request_digest_for,
)
from run_control import RUN_AUTHORITY_HOLD
from run_state import (
    CurrentD2Fact,
    D3Eligibility,
    FrozenGraphTopology,
    GraphStateProjection,
    RunClosureProjection,
    RunStateError,
    derive_d3_eligibility,
    go_candidate_sha256_from_mapping,
    manifest_closure_sha256_from_mapping,
    project_graph_state,
    recompute_graph_topology,
)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "glk.schema.json"
TECHNICAL_TYPES = ("D0_RECEIPT", "D1_RECEIPT", "D2_RECEIPT", "D3_RECEIPT")
REQUIRES_EVIDENCE = TECHNICAL_TYPES + (
    "SUPERVISOR_ADMISSION",
    "PREFLIGHT_ADMISSION",
    "WORKER_CHECKER_WAKE_BINDING",
    "WAKE_ATTEMPT",
    "WAKE_ACK",
    "PENDING_WAKE",
    "DEVICE_CAPACITY_PROFILE",
    "CUMULATIVE_ENGINEERING_LOAD",
    "CELL_WORK_ESTIMATE",
    "CELL_CAPACITY_GATE",
    "CELL_PLAN_AMENDMENT",
    "CELL_SCOPE_EXCEEDED",
)
ROLE_AUTHORITIES = frozenset(
    {"RUN_SUPERVISOR", "WORKER", "CHECKER", "GO_VERIFIER", "RUN_VERIFIER", "OWNER"}
)
PROVEN_AUTHORITY_ERROR_CODES = frozenset(
    {
        "SUPERVISOR_TECHNICAL_CAPABILITY_FORBIDDEN",
        "ROLE_TYPE_MISMATCH",
        "AUTHORITY_ROLE_MISMATCH",
        "ISSUANCE_CAPABILITY_MISSING",
        "CAPABILITY_ROLE_MISMATCH",
    }
)
SCHEMA_DEF_BY_TYPE = {
    "GLK_METHOD_LOCK": "glk_method_lock",
    "PROVENANCE_ADAPTER_PROFILE": "provenance_adapter_profile",
    "ROLE_BINDING": "role_binding_300",
    "CELL_MANIFEST": "cell_manifest",
    "CELL_MANIFEST_AMENDMENT": "cell_manifest_amendment",
    "GO_CANDIDATE_CLOSURE": "go_candidate_closure",
    "D0_RECEIPT": "d0_receipt",
    "D1_RECEIPT": "d1_receipt",
    "SUPERVISOR_ADMISSION": "supervisor_admission",
    "PREFLIGHT_ADMISSION": "preflight_admission",
    "RUN_PACKAGE_INDEX": "run_package_index",
    "D2_RECEIPT": "d2_receipt",
    "GRAPH_EVENT": "graph_event",
    "MONITOR_CONTROL": "monitor_control",
    "WORKER_CHECKER_WAKE_BINDING": "worker_checker_wake_binding",
    "WAKE_ATTEMPT": "wake_attempt",
    "WAKE_ACK": "wake_ack",
    "PENDING_WAKE": "pending_wake",
    "DEVICE_CAPACITY_PROFILE": "device_capacity_profile",
    "CUMULATIVE_ENGINEERING_LOAD": "cumulative_engineering_load",
    "CELL_WORK_ESTIMATE": "cell_work_estimate",
    "CELL_CAPACITY_GATE": "cell_capacity_gate",
    "CELL_PLAN_AMENDMENT": "cell_plan_amendment",
    "CELL_SCOPE_EXCEEDED": "cell_scope_exceeded",
    "D3_RECEIPT": "d3_receipt",
    "OWNER_ACCEPTANCE": "owner_acceptance_300",
    "SECURITY_HANDOFF": "security_handoff_300",
}
VERDICT_FIELDS = {
    "D0_RECEIPT": ("outcome", frozenset({"D0_PASS", "D0_FAIL", "D0_BLOCKED"})),
    "D1_RECEIPT": ("verdict", frozenset({"D1_PASS", "D1_FAIL", "D1_BLOCKED"})),
    "SUPERVISOR_ADMISSION": ("decision", frozenset({"ADMITTED", "REJECTED"})),
    "PREFLIGHT_ADMISSION": (
        "decision",
        frozenset({"PREFLIGHT_ADMITTED", "PREFLIGHT_REJECTED"}),
    ),
    "D2_RECEIPT": ("verdict", frozenset({"D2_PASS", "D2_FAIL", "D2_BLOCKED"})),
    "D3_RECEIPT": ("verdict", frozenset({"D3_PASS", "D3_FAIL", "D3_BLOCKED"})),
    "OWNER_ACCEPTANCE": (
        "owner_verdict",
        frozenset(
            {
                "LOOP_OWNER_ACCEPTED",
                "LOOP_PRODUCT_REWORK",
                "PRODUCT_DEFINITION_CHANGE",
                "NEW_FEATURE_REQUEST",
            }
        ),
    ),
}
UTC_TIMESTAMP = re.compile(
    r"^(?!1970-01-01T00:00:00Z$)[0-9]{4}-(0[1-9]|1[0-2])-"
    r"(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
RUN_VALIDATOR_VERSION = "3.1.0"
REPOSITORY_VALIDATION_SCOPE = "REPOSITORY_DISTRIBUTION"
RUN_VALIDATION_SCOPE = "RUN_PACKAGE"
_VALIDATOR_CONTRACT = {
    "scope": RUN_VALIDATION_SCOPE,
    "version": RUN_VALIDATOR_VERSION,
    "layers": tuple(range(1, 12)),
    "authority": "DERIVED_NON_AUTHORITATIVE",
}
RUN_VALIDATOR_DIGEST = hashlib.sha256(
    json.dumps(
        _VALIDATOR_CONTRACT,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    layer: int
    artifact_ref: str
    detail: str


@dataclass(frozen=True)
class ValidationLayer:
    layer: int
    status: str
    issue_count: int


@dataclass(frozen=True)
class ValidationReport:
    status: str
    issues: Tuple[ValidationIssue, ...]
    holds: Tuple[str, ...]
    layers: Tuple[ValidationLayer, ...]
    index_head_sha256: str
    graph_state: GraphStateProjection | None = None
    d3_eligibility: D3Eligibility | None = None
    run_closure: RunClosureProjection | None = None
    graph_topology: FrozenGraphTopology | None = None


@dataclass(frozen=True, order=True)
class OperationalControlIssue:
    code: str
    artifact_ref: str
    detail: str


@dataclass(frozen=True)
class OperationalControlReport:
    status: str
    issues: Tuple[OperationalControlIssue, ...]
    applicable: bool
    projection_kind: str = "DERIVED_NON_AUTHORITATIVE"


@dataclass(frozen=True)
class _ArtifactRecord:
    digest: str
    value: Mapping
    relative_path: str | None = None

    @property
    def artifact_ref(self):
        raw = self.value.get("artifact_id")
        return raw if isinstance(raw, str) and raw else f"digest:{self.digest}"


def _output_digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def add_report_digest(value):
    payload = dict(value)
    payload.pop("report_digest", None)
    payload["report_digest"] = _output_digest(payload)
    return payload


def _derived_formal_state(report):
    graph_state = report.graph_state
    closure = report.run_closure
    return {
        "projection_kind": "DERIVED_NON_AUTHORITATIVE",
        "technical_status": report.status,
        "graph": None
        if graph_state is None
        else {
            "graph_sha256": graph_state.graph_sha256,
            "verified_go_ids": list(graph_state.verified_go_ids),
            "waiting_go_ids": list(graph_state.waiting_go_ids),
            "active_go_ids": list(graph_state.active_go_ids),
            "applied_event_ids": list(graph_state.applied_event_ids),
        },
        "d3_eligible": bool(report.d3_eligibility and report.d3_eligibility.eligible),
        "d3_admitted": bool(closure and closure.d3_admitted),
        "owner_accepted": bool(closure and closure.owner_verdict == "LOOP_OWNER_ACCEPTED"),
        "security_handoff_present": bool(closure and closure.security_handoff_sha256),
        "security_status": closure.security_status if closure is not None else None,
        "lccoding_security_accepted": False,
    }


def build_run_validation_output(
    package,
    report,
    *,
    trusted_conformance_environment,
    adapter_profile_id,
):
    contracts = package.artifacts_by_type.get("RUN_CONTRACT", ())
    contract = contracts[0] if contracts else {}
    trusted = trusted_conformance_environment is True
    conformance_status = (
        "TRUSTED_CONFORMANCE_ENVIRONMENT"
        if trusted
        else "UNTRUSTED_CONFORMANCE_ENVIRONMENT"
    )
    status = "PASS" if report.status == "PASS" and trusted else "FAIL"
    payload = {
        "scope": RUN_VALIDATION_SCOPE,
        "scope_boundaries": {
            "validate_glk": REPOSITORY_VALIDATION_SCOPE,
            "validate_run": RUN_VALIDATION_SCOPE,
        },
        "status": status,
        "technical_validation_status": report.status,
        "report_authority": "DERIVED_NON_AUTHORITATIVE",
        "requested_transition": "VALIDATE_CURRENT_RUN_PACKAGE",
        "validator": {
            "version": RUN_VALIDATOR_VERSION,
            "digest": RUN_VALIDATOR_DIGEST,
        },
        "package": {
            "root": package.root.as_posix(),
            "run_id": contract.get("run_id"),
            "graph_id": contract.get("graph_id"),
            "index_head_sha256": package.index_head_sha256,
        },
        "conformance_environment": {
            "profile_id": adapter_profile_id,
            "trusted": trusted,
            "status": conformance_status,
        },
        "layers": [dataclasses.asdict(layer) for layer in report.layers],
        "issues": [dataclasses.asdict(issue) for issue in report.issues],
        "holds": list(report.holds),
        "formal_state": _derived_formal_state(report),
    }
    return add_report_digest(payload)


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


def _signed_request(request_type, **values):
    request = request_type(request_digest="0" * 64, **values)
    return dataclasses.replace(request, request_digest=request_digest_for(request))


def _records(package):
    if isinstance(package, Mapping) or type(package).__name__ != "LoadedRunPackage":
        raise TypeError("validate_loaded_run requires a LoadedRunPackage")
    required = (
        "artifacts_by_digest",
        "evidence_by_digest",
        "artifacts_by_type",
        "index_chain",
        "index_head_sha256",
    )
    if any(not hasattr(package, field) for field in required):
        raise TypeError("incomplete LoadedRunPackage")
    head = package.index_chain[-1]
    path_by_digest = {
        entry.get("sha256"): entry.get("path")
        for entry in head.get("formal_artifacts", ())
        if isinstance(entry, Mapping)
    }
    records = []
    for digest, value in package.artifacts_by_digest.items():
        if not isinstance(digest, str) or len(digest) != 64 or not isinstance(value, Mapping):
            raise TypeError("invalid immutable package subject")
        records.append(_ArtifactRecord(digest=digest, value=value, relative_path=path_by_digest.get(digest)))
    return tuple(sorted(records, key=lambda record: (record.artifact_ref, record.digest)))


def _schema_bundle():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator(schema, artifact_type):
    definition = SCHEMA_DEF_BY_TYPE.get(artifact_type, "artifact_envelope_300")
    wrapper = {
        "$schema": schema["$schema"],
        "$ref": f"#/$defs/{definition}",
        "$defs": schema["$defs"],
    }
    return Draft202012Validator(wrapper, format_checker=FormatChecker())


def _schema_issue(record, schema):
    value = record.value
    artifact_type = value.get("artifact_type")
    if artifact_type in REQUIRES_EVIDENCE:
        evidence_refs = value.get("evidence_refs")
        if not isinstance(evidence_refs, (list, tuple)) or not evidence_refs:
            return ValidationIssue("R04_EMPTY_EVIDENCE", 1, record.artifact_ref, "evidence_refs must be non-empty")
    verdict = VERDICT_FIELDS.get(artifact_type)
    if verdict is not None:
        field, allowed = verdict
        if value.get(field) not in allowed:
            return ValidationIssue("R06_VERDICT_INVALID", 1, record.artifact_ref, field)
    issued_at = value.get("issued_at")
    if not isinstance(issued_at, str) or UTC_TIMESTAMP.fullmatch(issued_at) is None:
        return ValidationIssue("R06_TIMESTAMP_INVALID", 1, record.artifact_ref, "issued_at")
    errors = sorted(
        _validator(schema, artifact_type).iter_errors(_thaw(value)),
        key=lambda error: (tuple(str(item) for item in error.absolute_path), error.message),
    )
    if errors:
        first = errors[0]
        path = "/".join(str(item) for item in first.absolute_path) or "$"
        return ValidationIssue("SCHEMA_INVALID", 1, record.artifact_ref, f"{path}: {first.message}")
    return None


def validate_operational_controls(package):
    """Validate 3.1 operational-control lineage without issuing a technical verdict."""
    new_types = {
        "WORKER_CHECKER_WAKE_BINDING",
        "WAKE_ATTEMPT",
        "WAKE_ACK",
        "PENDING_WAKE",
        "DEVICE_CAPACITY_PROFILE",
        "CUMULATIVE_ENGINEERING_LOAD",
        "CELL_WORK_ESTIMATE",
        "CELL_CAPACITY_GATE",
        "CELL_PLAN_AMENDMENT",
        "CELL_SCOPE_EXCEEDED",
    }
    applicable = any(package.artifacts_by_type.get(name, ()) for name in new_types)
    if not applicable:
        return OperationalControlReport("NOT_APPLICABLE", (), False)

    issues = []

    def add(code, value, detail):
        issues.append(
            OperationalControlIssue(
                code,
                value.get("artifact_id", "OPERATIONAL-CONTROL"),
                str(detail),
            )
        )

    digest_by_identity = {
        id(value): digest for digest, value in package.artifacts_by_digest.items()
    }
    head = package.index_chain[-1] if package.index_chain else {}
    value_by_path = {}
    for entry in head.get("formal_artifacts", ()):
        digest = entry.get("sha256")
        value = package.artifacts_by_digest.get(digest)
        if value is not None:
            value_by_path[entry.get("path")] = value

    monitors = tuple(
        value
        for value in package.artifacts_by_type.get("MONITOR_CONTROL", ())
        if value.get("patrol_conversation_ref") is not None
    )
    if len(monitors) != 1:
        add("PATROL_DUPLICATE", monitors[0] if monitors else {}, "exactly one patrol control required")
    else:
        monitor = monitors[0]
        expected_interval = {"HIGH": 10, "MEDIUM": 15, "LOW": 30}.get(
            monitor.get("project_difficulty")
        )
        if (
            monitor.get("patrol_model") != "gpt-5.6-luna"
            or monitor.get("patrol_reasoning_effort") != "xhigh"
            or monitor.get("patrol_interval_minutes") != expected_interval
            or not monitor.get("patrol_conversation_ref")
            or not monitor.get("patrol_heartbeat_ref")
        ):
            add("PATROL_BINDING_INVALID", monitor, "model, effort, interval, or identity")

    profiles = tuple(package.artifacts_by_type.get("DEVICE_CAPACITY_PROFILE", ()))
    loads = tuple(package.artifacts_by_type.get("CUMULATIVE_ENGINEERING_LOAD", ()))
    if len(profiles) != 1:
        add("DEVICE_CAPACITY_CURRENT_HEAD_INVALID", profiles[0] if profiles else {}, len(profiles))
    if len(loads) != 1:
        add("CUMULATIVE_LOAD_CURRENT_HEAD_INVALID", loads[0] if loads else {}, len(loads))
    current_profile = profiles[0] if len(profiles) == 1 else None
    current_load = loads[0] if len(loads) == 1 else None
    if current_profile is not None and current_load is not None and (
        current_load.get("profile_id") != current_profile.get("profile_id")
        or current_load.get("profile_version") != current_profile.get("profile_version")
    ):
        add("CUMULATIVE_LOAD_PROFILE_MISMATCH", current_load, "profile lineage")

    estimates = {
        value.get("estimate_id"): value
        for value in package.artifacts_by_type.get("CELL_WORK_ESTIMATE", ())
    }
    gates = tuple(package.artifacts_by_type.get("CELL_CAPACITY_GATE", ()))
    gate_by_digest = {
        digest_by_identity.get(id(value)): value for value in gates
    }
    for gate in gates:
        estimate = estimates.get(gate.get("estimate_id"))
        if estimate is None or gate.get("plan_version") != estimate.get("plan_version"):
            add("CELL_CAPACITY_LINEAGE_INVALID", gate, "estimate or plan version")
        if current_profile is not None and (
            gate.get("profile_id") != current_profile.get("profile_id")
            or gate.get("profile_version") != current_profile.get("profile_version")
        ):
            add("CELL_CAPACITY_LINEAGE_INVALID", gate, "profile version")
        if current_load is not None and (
            gate.get("load_id") != current_load.get("load_id")
            or gate.get("load_version") != current_load.get("load_version")
        ):
            add("CELL_CAPACITY_LINEAGE_INVALID", gate, "load version")
        if (gate.get("result") == "PASS") != (gate.get("dispatch_authorized") is True):
            add("CELL_CAPACITY_DECISION_INVALID", gate, "dispatch_authorized contradicts result")

    wake_bindings = tuple(package.artifacts_by_type.get("WORKER_CHECKER_WAKE_BINDING", ()))
    wake_by_id = {value.get("wake_binding_id"): value for value in wake_bindings}
    if len(wake_by_id) != len(wake_bindings):
        add("WAKE_BINDING_DUPLICATE", wake_bindings[0] if wake_bindings else {}, "identity")
    for binding in wake_bindings:
        gate = gate_by_digest.get(binding.get("capacity_gate_sha256"))
        if gate is None or gate.get("result") != "PASS" or gate.get("dispatch_authorized") is not True:
            add("CELL_CAPACITY_NOT_PASS", binding, "wake/dispatch lacks exact PASS gate")

    attempts = tuple(package.artifacts_by_type.get("WAKE_ATTEMPT", ()))
    attempts_by_path = {
        path: value for path, value in value_by_path.items() if value.get("artifact_type") == "WAKE_ATTEMPT"
    }
    for attempt in attempts:
        if attempt.get("wake_binding_id") not in wake_by_id:
            add("WAKE_BINDING_MISMATCH", attempt, "unknown wake binding")
    for ack in package.artifacts_by_type.get("WAKE_ACK", ()):
        binding = wake_by_id.get(ack.get("wake_binding_id"))
        if binding is None or any(
            ack.get(field) != binding.get(field)
            for field in ("go_id", "cell_id", "round_id")
        ) or ack.get("checker_binding_ref") != binding.get("checker_binding_ref"):
            add("WAKE_ACK_SCOPE_MISMATCH", ack, "ACK does not bind frozen scope")
    for pending in package.artifacts_by_type.get("PENDING_WAKE", ()):
        selected = tuple(attempts_by_path.get(path) for path in pending.get("attempt_refs", ()))
        binding = wake_by_id.get(pending.get("wake_binding_id"))
        valid = (
            binding is not None
            and len(selected) == 3
            and all(value is not None for value in selected)
            and {value.get("level") for value in selected} == {1, 2, 3}
            and all(value.get("wake_binding_id") == pending.get("wake_binding_id") for value in selected)
            and all(value.get("message_sha256") == pending.get("message_sha256") for value in selected)
        )
        if not valid:
            add("PENDING_WAKE_ATTEMPTS_INVALID", pending, "requires exact Levels 1-3 and message")

    for amendment in package.artifacts_by_type.get("CELL_PLAN_AMENDMENT", ()):
        successors = tuple(amendment.get("successor_cell_ids", ()))
        codes = set(amendment.get("defect_codes", ()))
        if amendment.get("dispatch_timing") == "POST_DISPATCH":
            if "POST_DISPATCH_CELL_SPLIT" not in codes:
                add("POST_DISPATCH_CELL_SPLIT_MISSING", amendment, "post-dispatch split")
            if len(successors) >= 3 and (
                "CELL_OVERSIZE_SEVERE" not in codes
                or not amendment.get("reevaluate_undispatched_cell_ids")
            ):
                add("CELL_OVERSIZE_SEVERE_MISSING", amendment, len(successors))

    ordered = tuple(sorted(set(issues)))
    return OperationalControlReport("FAIL" if ordered else "PASS", ordered, True)


def _layer_three(records, blocked, add_issue):
    canonical_run = None
    canonical_graph = None
    contracts = [record for record in records if record.value.get("artifact_type") == "RUN_CONTRACT"]
    if contracts:
        canonical_run = contracts[0].value.get("run_id")
        canonical_graph = contracts[0].value.get("graph_id")
    elif records:
        canonical_run = records[0].value.get("run_id")
        canonical_graph = records[0].value.get("graph_id")

    seen_ids = {}
    for record in records:
        if record.artifact_ref in blocked:
            continue
        artifact_id = record.value.get("artifact_id")
        if artifact_id in seen_ids and seen_ids[artifact_id] != record.digest:
            add_issue("IDENTITY_DUPLICATE_ARTIFACT", 3, record, str(artifact_id), block=True)
            continue
        seen_ids[artifact_id] = record.digest
        if record.value.get("run_id") != canonical_run or record.value.get("graph_id") != canonical_graph:
            add_issue("IDENTITY_SCOPE_MISMATCH", 3, record, "Run/Graph identity", block=True)
            continue
        if record.value.get("artifact_type") == "RUN_CONTRACT":
            supervisor = record.value.get("run_supervisor_binding")
            if not isinstance(supervisor, Mapping) or supervisor.get("run_id") != record.value.get("run_id"):
                add_issue(
                    "R07_RUN_BINDING_SCOPE_MISMATCH",
                    3,
                    record,
                    "embedded Supervisor Run differs from Run contract",
                    block=True,
                )


def _scope(record):
    return AuthorityScope(
        graph_id=record.value.get("graph_id", ""),
        go_id=record.value.get("go_id"),
        cell_id=record.value.get("cell_id"),
    )


def _authority_code(artifact_type):
    if artifact_type == "D0_RECEIPT":
        return "R01_SUPERVISOR_D0_AUTHORITY"
    if artifact_type == "D1_RECEIPT":
        return "R02_SUPERVISOR_D1_AUTHORITY"
    return "R03_SUPERVISOR_D2_D3_AUTHORITY"


def _layer_four(records, blocked, adapter, add_issue, holds):
    evaluator = ProvenanceEvaluator(adapter)
    technical_records = []
    for record in records:
        if record.artifact_ref in blocked:
            continue
        artifact_type = record.value.get("artifact_type")
        authority = FORMAL_TYPES.get(artifact_type)
        expected = authority.sole_issuer if authority is not None else None
        if expected not in ROLE_AUTHORITIES:
            continue
        binding_ref = record.value.get("issuer_binding_ref", "")
        binding_request = _signed_request(
            ResolveBindingRequest,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            binding_ref=binding_ref,
            run_id=record.value.get("run_id", ""),
            scope=_scope(record),
            artifact_sha256=None,
            expected_role=expected,
        )
        issuance_request = _signed_request(
            VerifyIssuanceRequest,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            binding_ref=binding_ref,
            run_id=record.value.get("run_id", ""),
            scope=_scope(record),
            artifact_sha256=record.digest,
            artifact_type=artifact_type,
            expected_authority=expected,
        )
        try:
            evaluator.evaluate_issuance(binding_request, issuance_request)
        except ProvenanceError as error:
            if error.code == "ROLE_TYPE_INVALID":
                add_issue("R09_UNTRUSTED_ROLE_STRING", 4, record, error.detail, block=True)
            elif artifact_type in TECHNICAL_TYPES and error.code in PROVEN_AUTHORITY_ERROR_CODES:
                add_issue(_authority_code(artifact_type), 4, record, error.detail, block=True)
                holds.add(RUN_AUTHORITY_HOLD)
            else:
                add_issue("AUTHORITY_PROVENANCE_INVALID", 4, record, error.detail, block=True)
            continue
        if artifact_type in TECHNICAL_TYPES:
            technical_records.append(record)

    d0_records = [record for record in technical_records if record.value.get("artifact_type") == "D0_RECEIPT"]
    d1_records = [record for record in technical_records if record.value.get("artifact_type") == "D1_RECEIPT"]
    for d1 in d1_records:
        peers = [
            d0
            for d0 in d0_records
            if d0.value.get("go_id") == d1.value.get("go_id")
            and d0.value.get("cell_id") == d1.value.get("cell_id")
        ]
        if not peers:
            continue
        d0 = peers[0]
        request = _signed_request(
            VerifyIsolationRequest,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            binding_ref=d1.value.get("issuer_binding_ref", ""),
            run_id=d1.value.get("run_id", ""),
            scope=_scope(d1),
            artifact_sha256=d1.digest,
            binding_refs=(d0.value.get("issuer_binding_ref", ""), d1.value.get("issuer_binding_ref", "")),
            required_dimensions=("conversation", "context", "workspace"),
        )
        try:
            evaluator.evaluate_isolation(request)
        except ProvenanceError as error:
            add_issue("R10_ISOLATION_NOT_PROVEN", 4, d1, error.detail, block=True)


def _same_cell_candidate(left, right):
    return all(
        left.get(field) == right.get(field)
        for field in ("run_id", "graph_id", "go_id", "cell_id", "candidate_id", "candidate_sha256")
    )


def _layer_five(records, blocked, add_issue):
    by_digest = {record.digest: record for record in records}
    by_type = {}
    for record in records:
        by_type.setdefault(record.value.get("artifact_type"), []).append(record)

    def unresolved(owner, digest, label):
        target = by_digest.get(digest)
        if target is None:
            add_issue("R05_UNRESOLVED_RECEIPT_LINEAGE", 5, owner, label, block=True)
            return None
        if target.artifact_ref in blocked:
            return None
        return target

    for d1 in by_type.get("D1_RECEIPT", ()):
        if d1.artifact_ref in blocked:
            continue
        d0 = unresolved(d1, d1.value.get("d0_artifact_sha256"), "D1.d0_artifact_sha256")
        if d0 is not None and (
            d0.value.get("artifact_type") != "D0_RECEIPT"
            or not _same_cell_candidate(d0.value, d1.value)
        ):
            add_issue("RECEIPT_LINEAGE_MISMATCH", 5, d1, "D0/D1 candidate tuple", block=True)

    for closure in by_type.get("GO_CANDIDATE_CLOSURE", ()):
        if closure.artifact_ref in blocked:
            continue
        for selected in closure.value.get("selected_cells", ()):
            d0 = unresolved(closure, selected.get("d0_artifact_sha256"), "closure D0")
            d1 = unresolved(closure, selected.get("d1_artifact_sha256"), "closure D1")
            if d0 is None or d1 is None:
                continue
            expected = {
                "cell_id": d0.value.get("cell_id"),
                "candidate_id": d0.value.get("candidate_id"),
                "candidate_sha256": d0.value.get("candidate_sha256"),
            }
            if any(selected.get(field) != value for field, value in expected.items()):
                add_issue("RECEIPT_LINEAGE_MISMATCH", 5, closure, "closure selected CELL tuple", block=True)
                break

    for d2 in by_type.get("D2_RECEIPT", ()):
        if d2.artifact_ref in blocked:
            continue
        closure = unresolved(d2, d2.value.get("go_candidate_closure_sha256"), "D2 closure")
        if closure is None:
            continue
        if closure.value.get("artifact_type") != "GO_CANDIDATE_CLOSURE":
            add_issue("RECEIPT_LINEAGE_MISMATCH", 5, d2, "D2 closure type", block=True)
            continue
        if _thaw(d2.value.get("required_cell_tuples")) != _thaw(closure.value.get("selected_cells")):
            add_issue("RECEIPT_LINEAGE_MISMATCH", 5, d2, "D2 exact CELL tuple set", block=True)

    for admission in by_type.get("SUPERVISOR_ADMISSION", ()):
        if admission.artifact_ref in blocked:
            continue
        unresolved(admission, admission.value.get("admitted_artifact_sha256"), "admission target")

    for d3 in by_type.get("D3_RECEIPT", ()):
        if d3.artifact_ref in blocked:
            continue
        for digest in d3.value.get("admitted_d2_artifact_sha256s", ()):
            target = unresolved(d3, digest, "D3 admitted D2")
            if target is not None and target.value.get("artifact_type") != "D2_RECEIPT":
                add_issue("RECEIPT_LINEAGE_MISMATCH", 5, d3, "D3 target type", block=True)
                break


def _admitted_target_records(records, blocked):
    by_digest = {record.digest: record for record in records}
    by_type = {}
    for record in records:
        by_type.setdefault(record.value.get("artifact_type"), []).append(record)
    admitted = {}
    for admission in by_type.get("SUPERVISOR_ADMISSION", ()):
        value = admission.value
        target = by_digest.get(value.get("admitted_artifact_sha256"))
        target_ref = value.get("admitted_artifact_ref")
        if (
            admission.artifact_ref in blocked
            or value.get("decision") != "ADMITTED"
            or target is None
            or target.artifact_ref in blocked
            or not isinstance(target_ref, str)
            or target_ref != target.relative_path
            or value.get("run_id") != target.value.get("run_id")
            or value.get("graph_id") != target.value.get("graph_id")
            or value.get("graph_version") != target.value.get("graph_version")
            or value.get("candidate_id") != target.value.get("candidate_id")
            or value.get("candidate_sha256") != target.value.get("candidate_sha256")
        ):
            continue
        admitted.setdefault(target.digest, []).append(admission)
    return {digest: tuple(items) for digest, items in admitted.items()}


def _admitted_target_digests(records, blocked):
    return frozenset(_admitted_target_records(records, blocked))


def _layer_six(records, blocked, add_issue):
    by_digest = {record.digest: record for record in records}
    by_type = {}
    for record in records:
        by_type.setdefault(record.value.get("artifact_type"), []).append(record)
    admitted_digests = _admitted_target_digests(records, blocked)

    manifests_by_go = {}
    for record in by_type.get("CELL_MANIFEST", ()):
        if record.artifact_ref not in blocked:
            manifests_by_go.setdefault(record.value.get("go_id"), []).append(record)

    for go_id, manifest_records in sorted(manifests_by_go.items(), key=lambda item: str(item[0])):
        manifest_identities = {}
        for record in manifest_records:
            identity = (record.value.get("manifest_id"), record.value.get("manifest_version"))
            manifest_identities.setdefault(identity, []).append(record)
        forked = [
            candidates
            for candidates in manifest_identities.values()
            if len({candidate.digest for candidate in candidates}) > 1
        ]
        if forked:
            for candidates in sorted(
                forked,
                key=lambda items: (
                    str(items[0].value.get("manifest_id")),
                    str(items[0].value.get("manifest_version")),
                ),
            ):
                representative = min(candidates, key=lambda record: (record.artifact_ref, record.digest))
                add_issue(
                    "CELL_MANIFEST_FORK",
                    6,
                    representative,
                    "multiple manifest digests claim the same manifest identity and version",
                    block=True,
                )
            continue
        current = max(
            manifest_records,
            key=lambda record: (record.value.get("manifest_version", 0), record.value.get("issued_at", ""), record.artifact_ref),
        )
        manifest = current.value
        version = manifest.get("manifest_version")
        expected_manifest_hash = manifest_closure_sha256_from_mapping(manifest)
        if manifest.get("closure_sha256") != expected_manifest_hash:
            add_issue(
                "R16_MANIFEST_CLOSURE_HASH_INVALID",
                6,
                current,
                "CELL manifest closure_sha256 does not match canonical fields",
                block=True,
            )
            continue

        if version == 1:
            if manifest.get("prior_manifest_sha256") is not None:
                add_issue("R15_UNAMENDED_MANIFEST_CHANGE", 6, current, "version 1 has prior manifest", block=True)
                continue
        elif isinstance(version, int) and version > 1:
            prior_digest = manifest.get("prior_manifest_sha256")
            prior = by_digest.get(prior_digest)
            amendments = [
                record
                for record in by_type.get("CELL_MANIFEST_AMENDMENT", ())
                if record.artifact_ref not in blocked
                and record.value.get("manifest_id") == manifest.get("manifest_id")
                and record.value.get("manifest_version") == version
                and record.value.get("prior_manifest_sha256") == prior_digest
            ]
            if (
                prior is None
                or prior.value.get("artifact_type") != "CELL_MANIFEST"
                or prior.value.get("go_id") != go_id
                or prior.value.get("manifest_version") != version - 1
                or not amendments
            ):
                add_issue(
                    "R15_UNAMENDED_MANIFEST_CHANGE",
                    6,
                    current,
                    "manifest version lacks exact prior manifest and frozen amendment",
                    block=True,
                )
                continue

        required_entries = [entry for entry in manifest.get("required_cells", ()) if entry.get("required")]
        required_ids = tuple(sorted(entry.get("cell_id") for entry in required_entries))
        if not required_ids or len(set(required_ids)) != len(required_ids):
            add_issue("R14_CELL_TUPLE_SET_MISMATCH", 6, current, "required CELL registry is empty or duplicated", block=True)
            continue
        contracts = {entry.get("cell_id"): entry.get("cell_contract_sha256") for entry in required_entries}

        scoped_d1 = [
            record
            for record in by_type.get("D1_RECEIPT", ())
            if record.artifact_ref not in blocked
            and record.value.get("go_id") == go_id
            and record.value.get("manifest_id") == manifest.get("manifest_id")
            and record.value.get("manifest_version") == version
        ]
        wrong_manifest_d1 = [
            record for record in scoped_d1 if record.value.get("manifest_closure_sha256") != manifest.get("closure_sha256")
        ]
        if wrong_manifest_d1:
            for record in wrong_manifest_d1:
                add_issue(
                    "R16_D1_FUTURE_CLOSURE_BINDING",
                    6,
                    record,
                    "D1 must bind the current manifest, never a later GO closure",
                    block=True,
                )
            continue

        latest_d1 = {}
        for record in scoped_d1:
            cell_id = record.value.get("cell_id")
            existing = latest_d1.get(cell_id)
            if existing is None or (
                record.value.get("issued_at", ""),
                record.artifact_ref,
                record.digest,
            ) > (
                existing.value.get("issued_at", ""),
                existing.artifact_ref,
                existing.digest,
            ):
                latest_d1[cell_id] = record

        expected_tuples = {}
        missing_d1_admission = set()
        missing_d0_admission = set()
        for cell_id, d1_record in latest_d1.items():
            d1 = d1_record.value
            if d1_record.digest not in admitted_digests:
                missing_d1_admission.add(cell_id)
                continue
            d0_record = by_digest.get(d1.get("d0_artifact_sha256"))
            if d0_record is None or d0_record.artifact_ref in blocked or d0_record.value.get("artifact_type") != "D0_RECEIPT":
                continue
            if d0_record.digest not in admitted_digests:
                missing_d0_admission.add(cell_id)
                continue
            d0 = d0_record.value
            if (
                cell_id not in contracts
                or d0.get("cell_id") != cell_id
                or d0.get("manifest_id") != manifest.get("manifest_id")
                or d0.get("manifest_version") != version
                or d0.get("manifest_closure_sha256") != manifest.get("closure_sha256")
                or d0.get("cell_contract_sha256") != contracts[cell_id]
                or d1.get("cell_contract_sha256") != contracts[cell_id]
                or d0.get("candidate_id") != d1.get("candidate_id")
                or d0.get("candidate_sha256") != d1.get("candidate_sha256")
                or d0.get("outcome") != "D0_PASS"
                or d1.get("verdict") != "D1_PASS"
            ):
                continue
            expected_tuples[cell_id] = {
                "cell_id": cell_id,
                "candidate_id": d0.get("candidate_id"),
                "candidate_sha256": d0.get("candidate_sha256"),
                "d0_artifact_sha256": d0_record.digest,
                "d1_artifact_sha256": d1_record.digest,
            }

        d2_records = [
            record
            for record in by_type.get("D2_RECEIPT", ())
            if record.artifact_ref not in blocked and record.value.get("go_id") == go_id
        ]
        for d2_record in d2_records:
            if missing_d1_admission:
                add_issue(
                    "R13_D1_ADMISSION_REQUIRED",
                    6,
                    d2_record,
                    "D2 requires an exact ADMITTED Supervisor admission for every current D1",
                    block=True,
                )
                continue
            if missing_d0_admission:
                add_issue(
                    "R13_D0_ADMISSION_REQUIRED",
                    6,
                    d2_record,
                    "D2 requires an exact ADMITTED Supervisor admission for every current D0",
                    block=True,
                )
                continue
            if set(expected_tuples) != set(required_ids):
                add_issue(
                    "R13_PREMATURE_D2_INCOMPLETE_D1_SET",
                    6,
                    d2_record,
                    "D2 requires one current D1 PASS for every required CELL",
                    block=True,
                )
                continue
            closure_record = by_digest.get(d2_record.value.get("go_candidate_closure_sha256"))
            if closure_record is None or closure_record.value.get("artifact_type") != "GO_CANDIDATE_CLOSURE":
                add_issue("R14_CELL_TUPLE_SET_MISMATCH", 6, d2_record, "D2 closure is unresolved", block=True)
                continue
            if closure_record.digest not in admitted_digests:
                add_issue(
                    "R13_CLOSURE_ADMISSION_REQUIRED",
                    6,
                    d2_record,
                    "D2 requires an exact ADMITTED Supervisor admission for the GO closure",
                    block=True,
                )
                continue
            closure = closure_record.value
            if (
                closure.get("manifest_id") != manifest.get("manifest_id")
                or closure.get("manifest_version") != version
                or closure.get("manifest_closure_sha256") != manifest.get("closure_sha256")
            ):
                add_issue(
                    "R16_GO_CLOSURE_MANIFEST_BINDING_INVALID",
                    6,
                    closure_record,
                    "GO closure does not bind the current manifest",
                    block=True,
                )
                continue
            selected = tuple(closure.get("selected_cells", ()))
            selected_ids = tuple(item.get("cell_id") for item in selected)
            if len(selected_ids) != len(required_ids) or len(set(selected_ids)) != len(selected_ids) or set(selected_ids) != set(required_ids):
                add_issue(
                    "R14_CELL_TUPLE_SET_MISMATCH",
                    6,
                    closure_record,
                    "GO closure CELL registry differs from the manifest",
                    block=True,
                )
                continue
            if closure.get("candidate_sha256") != go_candidate_sha256_from_mapping(manifest, selected):
                add_issue(
                    "R16_GO_CLOSURE_HASH_INVALID",
                    6,
                    closure_record,
                    "GO candidate hash does not match the selected tuple set",
                    block=True,
                )
                continue
            actual_tuples = {item.get("cell_id"): _thaw(item) for item in selected}
            if actual_tuples != expected_tuples:
                has_superseded_generation = any(
                    sum(1 for record in scoped_d1 if record.value.get("cell_id") == cell_id) > 1
                    for cell_id in required_ids
                )
                code = "R28_SUPERSEDED_CLOSURE_FOR_D2" if has_superseded_generation else "R14_CELL_TUPLE_SET_MISMATCH"
                add_issue(code, 6, d2_record, "D2 does not consume the exact current D1 tuple set", block=True)


def _layer_seven(records, blocked, add_issue):
    baselines = [
        record
        for record in records
        if record.value.get("artifact_type") == "GRAPH_BASELINE" and record.artifact_ref not in blocked
    ]
    if not baselines:
        return None, None
    if len(baselines) != 1:
        current = min(baselines, key=lambda record: (record.artifact_ref, record.digest))
        add_issue("GRAPH_BASELINE_CARDINALITY_INVALID", 7, current, "exactly one current graph baseline is required", block=True)
        return None, current
    current = baselines[0]
    fallback_go_ids = tuple(
        sorted(
            {
                record.value.get("go_id")
                for record in records
                if record.value.get("artifact_type") == "CELL_MANIFEST" and record.value.get("go_id")
            }
        )
    )
    try:
        topology = recompute_graph_topology(current.value, fallback_go_ids=fallback_go_ids)
    except RunStateError as error:
        add_issue(error.code, 7, current, error.detail, block=True)
        return None, current

    node_ids = {node.go_id for node in topology.nodes}
    artifact_go_ids = {
        record.value.get("go_id")
        for record in records
        if record.value.get("artifact_type") in {"CELL_MANIFEST", "GO_CANDIDATE_CLOSURE", "D2_RECEIPT"}
        and record.value.get("go_id")
        and record.artifact_ref not in blocked
    }
    if not artifact_go_ids.issubset(node_ids):
        add_issue(
            "GRAPH_GO_ARTIFACT_COVERAGE_INVALID",
            7,
            current,
            "a GO-scoped artifact is outside the current graph",
            block=True,
        )
        return None, current
    if topology.explicit and current.value.get("candidate_sha256") != topology.graph_sha256:
        add_issue("GRAPH_DIGEST_MISMATCH", 7, current, "baseline candidate does not bind the recomputed graph", block=True)
        return None, current

    initial = project_graph_state(topology)
    if topology.explicit and (
        tuple(current.value.get("waiting_go_ids", ())) != initial.waiting_go_ids
        or tuple(current.value.get("active_go_ids", ())) != initial.active_go_ids
    ):
        add_issue(
            "GRAPH_BASELINE_STATE_MISMATCH",
            7,
            current,
            "self-reported WAITING/ACTIVE sets differ from recomputation",
            block=True,
        )
        return None, current
    return topology, current


def _ordered_graph_events(events, add_issue):
    if not events:
        return ()
    event_digests = {record.digest for record in events}
    roots = []
    children = {}
    for record in events:
        prior = record.value.get("prior_event_sha256")
        if prior is None:
            roots.append(record)
            continue
        if prior not in event_digests:
            add_issue("GRAPH_EVENT_CHAIN_INVALID", 8, record, "prior graph event is unresolved", block=True)
            return None
        children.setdefault(prior, []).append(record)
    if len(roots) != 1 or any(len(items) != 1 for items in children.values()):
        representative = min(events, key=lambda record: (record.artifact_ref, record.digest))
        add_issue("GRAPH_EVENT_CHAIN_INVALID", 8, representative, "graph event ledger has multiple roots or a fork", block=True)
        return None
    ordered = []
    current = roots[0]
    visited = set()
    while current is not None:
        if current.digest in visited:
            add_issue("GRAPH_EVENT_CHAIN_INVALID", 8, current, "graph event ledger contains a cycle", block=True)
            return None
        visited.add(current.digest)
        ordered.append(current)
        descendants = children.get(current.digest, ())
        current = descendants[0] if descendants else None
    if visited != event_digests:
        representative = min(events, key=lambda record: (record.artifact_ref, record.digest))
        add_issue("GRAPH_EVENT_CHAIN_INVALID", 8, representative, "graph event ledger is disconnected", block=True)
        return None
    return tuple(ordered)


def _layer_eight(records, blocked, holds, topology, add_issue):
    if topology is None:
        return None
    state = project_graph_state(topology)
    if not topology.explicit:
        return state

    by_digest = {record.digest: record for record in records}
    events = [
        record
        for record in records
        if record.value.get("artifact_type") == "GRAPH_EVENT" and record.artifact_ref not in blocked
    ]
    ordered_events = _ordered_graph_events(events, add_issue)
    if ordered_events is None:
        return state
    if holds and ordered_events:
        add_issue("GRAPH_EVENT_HOLD_ACTIVE", 8, ordered_events[0], ",".join(sorted(holds)), block=True)
        return state

    d2_records = [
        record
        for record in records
        if record.value.get("artifact_type") == "D2_RECEIPT"
        and record.artifact_ref not in blocked
        and record.value.get("graph_id") == topology.graph_id
        and record.value.get("graph_version") == topology.graph_version
    ]
    current_d2_by_go = {}
    for record in d2_records:
        go_id = record.value.get("go_id")
        existing = current_d2_by_go.get(go_id)
        if existing is None or (
            record.value.get("issued_at", ""),
            record.artifact_ref,
            record.digest,
        ) > (
            existing.value.get("issued_at", ""),
            existing.artifact_ref,
            existing.digest,
        ):
            current_d2_by_go[go_id] = record
    admitted_digests = _admitted_target_digests(records, blocked)
    node_by_id = {node.go_id: node for node in topology.nodes}
    verified = set()
    applied_event_ids = []

    for event_record in ordered_events:
        event = event_record.value
        if (
            event.get("run_id") != topology.run_id
            or event.get("graph_id") != topology.graph_id
            or event.get("graph_version") != topology.graph_version
            or event.get("candidate_id") != topology.baseline_candidate_id
            or event.get("candidate_sha256") != topology.graph_sha256
        ):
            add_issue(
                "GRAPH_EVENT_GRAPH_BINDING_INVALID",
                8,
                event_record,
                "graph event does not bind the current graph identity, version, and digest",
                block=True,
            )
            continue
        trigger = by_digest.get(event.get("trigger_artifact_sha256"))
        if (
            trigger is None
            or trigger.artifact_ref in blocked
            or trigger.value.get("artifact_type") != "D2_RECEIPT"
            or event.get("trigger_artifact_ref") != trigger.relative_path
            or event.get("event_type") != "SUCCESSOR_RELEASE"
            or trigger.value.get("verdict") != "D2_PASS"
        ):
            add_issue(
                "GRAPH_EVENT_TRIGGER_INVALID",
                8,
                event_record,
                "successor release requires one exact D2 PASS trigger",
                block=True,
            )
            continue
        go_id = trigger.value.get("go_id")
        if current_d2_by_go.get(go_id) is not trigger:
            add_issue(
                "GRAPH_EVENT_STALE_GENERATION",
                8,
                event_record,
                "graph event targets a superseded D2 generation",
                block=True,
            )
            continue
        if trigger.digest not in admitted_digests:
            add_issue(
                "GRAPH_EVENT_D2_ADMISSION_REQUIRED",
                8,
                event_record,
                "successor release requires an exact ADMITTED D2",
                block=True,
            )
            continue
        if go_id not in node_by_id or go_id in verified or go_id not in state.active_go_ids:
            add_issue(
                "GRAPH_EVENT_RELEASE_INVALID",
                8,
                event_record,
                "graph event targets an unknown, waiting, or already released GO",
                block=True,
            )
            continue
        node = node_by_id[go_id]
        if (
            trigger.value.get("go_claim_sha256") != node.go_claim_sha256
            or trigger.value.get("acceptance_contract_sha256") != node.acceptance_contract_sha256
        ):
            add_issue(
                "D2_GO_CONTRACT_MISMATCH",
                8,
                trigger,
                "D2 claim or acceptance digest differs from the current GO contract",
                block=True,
            )
            continue
        selected_d1 = [
            by_digest.get(item.get("d1_artifact_sha256"))
            for item in trigger.value.get("required_cell_tuples", ())
        ]
        if any(
            record is None
            or record.value.get("artifact_type") != "D1_RECEIPT"
            or record.value.get("execution_context_ref") == trigger.value.get("execution_context_ref")
            for record in selected_d1
        ):
            add_issue(
                "D2_VERIFIER_ISOLATION_INVALID",
                8,
                trigger,
                "GO Verifier context is not isolated from every consumed Checker D1",
                block=True,
            )
            continue

        candidate_verified = verified | {go_id}
        candidate_event_ids = tuple(applied_event_ids + [event.get("event_id")])
        candidate_state = project_graph_state(topology, candidate_verified, candidate_event_ids)
        if (
            tuple(event.get("waiting_go_ids", ())) != candidate_state.waiting_go_ids
            or tuple(event.get("active_go_ids", ())) != candidate_state.active_go_ids
        ):
            add_issue(
                "GRAPH_EVENT_PROJECTION_MISMATCH",
                8,
                event_record,
                "event WAITING/ACTIVE claims differ from maximal-safe recomputation",
                block=True,
            )
            continue
        verified = candidate_verified
        applied_event_ids.append(event.get("event_id"))
        state = candidate_state
    return state


def _latest_record(records):
    return max(
        records,
        key=lambda record: (
            record.value.get("issued_at", ""),
            record.artifact_ref,
            record.digest,
        ),
    ) if records else None


def _same_exact_members(actual, expected):
    return (
        isinstance(actual, (list, tuple))
        and len(actual) == len(expected)
        and set(actual) == set(expected)
    )


def _layer_nine(records, blocked, holds, package, topology, graph_state, adapter, add_issue):
    if topology is None or graph_state is None or not topology.explicit:
        return None, None
    by_digest = {record.digest: record for record in records}
    d2_by_go = {}
    for go_id in topology.required_go_ids:
        candidates = [
            record
            for record in records
            if record.value.get("artifact_type") == "D2_RECEIPT"
            and record.artifact_ref not in blocked
            and record.value.get("go_id") == go_id
            and record.value.get("graph_id") == topology.graph_id
            and record.value.get("graph_version") == topology.graph_version
        ]
        current = _latest_record(candidates)
        if current is not None:
            d2_by_go[go_id] = current
    d2_facts = {
        go_id: CurrentD2Fact(
            go_id=go_id,
            artifact_sha256=record.digest,
            candidate_id=record.value.get("candidate_id", ""),
            candidate_sha256=record.value.get("candidate_sha256", ""),
            verifier_binding_ref=record.value.get("issuer_binding_ref", ""),
            execution_context_ref=record.value.get("execution_context_ref", ""),
            verdict=record.value.get("verdict", ""),
        )
        for go_id, record in d2_by_go.items()
    }
    contracts = [
        record
        for record in records
        if record.value.get("artifact_type") == "RUN_CONTRACT" and record.artifact_ref not in blocked
    ]
    run_contract = _latest_record(contracts)
    final_candidate = run_contract.value if run_contract is not None else {}
    expected_seam_claims = tuple(sorted(f"{edge.source}->{edge.target}" for edge in topology.edges))
    expected_seam_evidence = tuple(
        sorted({reference for edge in topology.edges for reference in edge.consumption_evidence_refs})
    )
    if not expected_seam_claims:
        expected_seam_claims = ("GRAPH-SEAMS-EMPTY",)
    if not expected_seam_evidence:
        expected_seam_evidence = ("evidence/graph/seams-empty.json",)
    eligibility = derive_d3_eligibility(
        topology=topology,
        graph_state=graph_state,
        current_d2_by_go=d2_facts,
        admitted_d2_digests=_admitted_target_digests(records, blocked),
        final_candidate=final_candidate,
        graph_seam_claims=expected_seam_claims,
        graph_seam_evidence_refs=expected_seam_evidence,
    )

    d3_candidates = [
        record
        for record in records
        if record.value.get("artifact_type") == "D3_RECEIPT" and record.artifact_ref not in blocked
    ]
    current_d3 = _latest_record(d3_candidates)
    if current_d3 is None:
        return eligibility, None
    d3 = current_d3.value
    if holds:
        add_issue("R17_D3_ACTIVE_HOLD", 9, current_d3, ",".join(sorted(holds)), block=True)
    if not _same_exact_members(d3.get("required_go_ids"), eligibility.required_go_ids):
        add_issue(
            "R17_D3_REQUIRED_GO_SET_MISMATCH",
            9,
            current_d3,
            "D3 required GO set differs from the current graph",
            block=True,
        )
    if not _same_exact_members(
        d3.get("admitted_d2_artifact_sha256s"),
        eligibility.admitted_d2_artifact_sha256s,
    ):
        add_issue(
            "R17_D3_D2_SET_MISMATCH",
            9,
            current_d3,
            "D3 does not consume the exact current admitted D2 set",
            block=True,
        )
    if (
        d3.get("graph_id") != eligibility.graph_id
        or d3.get("graph_version") != eligibility.graph_version
        or d3.get("graph_sha256") != eligibility.graph_sha256
    ):
        add_issue(
            "R17_D3_GRAPH_DIGEST_MISMATCH",
            9,
            current_d3,
            "D3 graph identity, version, or digest is stale or forged",
            block=True,
        )
    indexed_evidence = {
        entry.get("path")
        for entry in package.index_chain[-1].get("evidence_objects", ())
        if isinstance(entry, Mapping)
    }
    if (
        not _same_exact_members(d3.get("graph_seam_claims"), eligibility.graph_seam_claims)
        or not _same_exact_members(d3.get("graph_seam_evidence_refs"), eligibility.graph_seam_evidence_refs)
        or not set(eligibility.graph_seam_evidence_refs).issubset(indexed_evidence)
    ):
        add_issue(
            "R17_D3_GRAPH_SEAM_EVIDENCE_MISSING",
            9,
            current_d3,
            "D3 graph-seam claims and indexed evidence are incomplete",
            block=True,
        )
    if (
        d3.get("candidate_id") != eligibility.final_candidate_id
        or d3.get("candidate_sha256") != eligibility.final_candidate_sha256
    ):
        add_issue(
            "R17_D3_FINAL_CANDIDATE_MISMATCH",
            9,
            current_d3,
            "D3 final Run candidate differs from the Run contract",
            block=True,
        )
    verifier_bindings = {
        record.value.get("role_binding_id")
        for record in records
        if record.value.get("artifact_type") == "ROLE_BINDING"
        and record.artifact_ref not in blocked
        and record.value.get("role_type") == "RUN_VERIFIER"
    }
    if d3.get("issuer_binding_ref") not in verifier_bindings:
        add_issue(
            "R18_RUN_VERIFIER_BINDING_INVALID",
            9,
            current_d3,
            "D3 issuer is not the current Run Verifier binding",
            block=True,
        )
    consumed_contexts = {record.value.get("execution_context_ref") for record in d2_by_go.values()}
    consumed_bindings = {record.value.get("issuer_binding_ref") for record in d2_by_go.values()}
    for d2_record in d2_by_go.values():
        for selected in d2_record.value.get("required_cell_tuples", ()):
            d1_record = by_digest.get(selected.get("d1_artifact_sha256"))
            if d1_record is not None:
                consumed_contexts.add(d1_record.value.get("execution_context_ref"))
                consumed_bindings.add(d1_record.value.get("issuer_binding_ref"))
    run_verifier_binding = d3.get("issuer_binding_ref")
    free_string_collision = (
        d3.get("execution_context_ref") in consumed_contexts
        or run_verifier_binding in consumed_bindings
    )
    if free_string_collision:
        add_issue(
            "R18_RUN_VERIFIER_ISOLATION_INVALID",
            9,
            current_d3,
            "Run Verifier context collides with consumed GO Verifier or Checker context",
            block=True,
        )
    else:
        request = _signed_request(
            VerifyIsolationRequest,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            binding_ref=run_verifier_binding,
            run_id=d3.get("run_id", ""),
            scope=_scope(current_d3),
            artifact_sha256=current_d3.digest,
            binding_refs=(run_verifier_binding, *tuple(sorted(consumed_bindings))),
            required_dimensions=(
                "conversation",
                "context",
                "workspace",
                "runtime_state",
                "evidence_root",
                "decision_input",
            ),
        )
        try:
            ProvenanceEvaluator(adapter).evaluate_isolation(request)
        except ProvenanceError as error:
            add_issue(
                "R18_RUN_VERIFIER_ISOLATION_INVALID",
                9,
                current_d3,
                error.detail,
                block=True,
            )
    return eligibility, current_d3


def _layer_ten(records, blocked, eligibility, current_d3, add_issue):
    if eligibility is None:
        return None
    admitted = _admitted_target_records(records, blocked)
    d3_admitted = current_d3 is not None and current_d3.digest in admitted
    owners = [
        record
        for record in records
        if record.value.get("artifact_type") == "OWNER_ACCEPTANCE" and record.artifact_ref not in blocked
    ]
    owner = _latest_record(owners)
    owner_valid = False
    bounded_index_sha256 = None
    if owner is not None:
        bounded_index_sha256 = owner.value.get("package_index_sha256")
        if not eligibility.eligible or (current_d3 is not None and current_d3.artifact_ref in blocked):
            add_issue(
                "R18_D3_NOT_ELIGIBLE",
                10,
                owner,
                "Owner Acceptance requires a mechanically eligible D3 input closure",
                block=True,
            )
        elif current_d3 is None or owner.value.get("admitted_d3_artifact_sha256") != current_d3.digest:
            add_issue(
                "R18_OWNER_D3_REFERENCE_INVALID",
                10,
                owner,
                "Owner Acceptance does not consume the exact current D3",
                block=True,
            )
        elif current_d3.value.get("verdict") != "D3_PASS":
            add_issue("R18_D3_NOT_PASS", 10, owner, "Owner cannot accept D3 FAIL or BLOCKED", block=True)
        elif not d3_admitted:
            add_issue(
                "R18_D3_ADMISSION_REQUIRED",
                10,
                owner,
                "Owner Acceptance requires an exact ADMITTED current D3",
                block=True,
            )
        elif (
            owner.value.get("candidate_id") != current_d3.value.get("candidate_id")
            or owner.value.get("candidate_sha256") != current_d3.value.get("candidate_sha256")
        ):
            add_issue(
                "R18_OWNER_D3_REFERENCE_INVALID",
                10,
                owner,
                "Owner candidate differs from current D3",
                block=True,
            )
        else:
            index_record = next(
                (
                    record
                    for record in records
                    if record.digest == bounded_index_sha256
                    and record.value.get("artifact_type") == "RUN_PACKAGE_INDEX"
                ),
                None,
            )
            bounded_digests = {
                entry.get("sha256")
                for entry in index_record.value.get("formal_artifacts", ())
                if isinstance(entry, Mapping)
            } if index_record is not None else set()
            admission_digests = {record.digest for record in admitted.get(current_d3.digest, ())}
            if (
                index_record is None
                or current_d3.digest not in bounded_digests
                or not admission_digests
                or not admission_digests.issubset(bounded_digests)
            ):
                add_issue(
                    "R18_OWNER_PACKAGE_BOUNDARY_INVALID",
                    10,
                    owner,
                    "Owner Acceptance package boundary does not contain current D3 and admission",
                    block=True,
                )
            else:
                owner_valid = True

    security_records = [
        record
        for record in records
        if record.value.get("artifact_type") == "SECURITY_HANDOFF" and record.artifact_ref not in blocked
    ]
    security = _latest_record(security_records)
    if security is not None:
        if (
            not owner_valid
            or owner.value.get("owner_verdict") != "LOOP_OWNER_ACCEPTED"
            or security.value.get("owner_acceptance_sha256") != owner.digest
        ):
            add_issue(
                "R19_SECURITY_HANDOFF_PREMATURE",
                10,
                security,
                "security handoff requires exact accepted Owner Acceptance",
                block=True,
            )
        if security.value.get("status") != "PENDING_LCCODING_AUDIT":
            add_issue(
                "R19_SECURITY_STATUS_FORBIDDEN",
                10,
                security,
                "GLK cannot assert that the LCCoding security audit passed",
                block=True,
            )
    return RunClosureProjection(
        d3_eligible=eligibility.eligible,
        current_d3_sha256=current_d3.digest if current_d3 is not None else None,
        d3_admitted=d3_admitted,
        owner_acceptance_sha256=owner.digest if owner is not None else None,
        owner_verdict=owner.value.get("owner_verdict") if owner is not None else None,
        bounded_index_sha256=bounded_index_sha256,
        security_handoff_sha256=security.digest if security is not None else None,
        security_status=security.value.get("status") if security is not None else None,
        lccoding_security_accepted=False,
    )

def validate_loaded_run(package, adapter):
    """Derive ten technical layers plus the applicable 3.1 operational-control gate."""
    records = _records(package)
    issues = []
    blocked = set()
    holds = set()

    def add_issue(code, layer, record, detail, *, block=False):
        issues.append(ValidationIssue(code, layer, record.artifact_ref, str(detail)))
        if block:
            blocked.add(record.artifact_ref)

    schema = _schema_bundle()
    for record in records:
        issue = _schema_issue(record, schema)
        if issue is not None:
            issues.append(issue)
            blocked.add(record.artifact_ref)

    # Layer 2 facts are deliberately consumed from Task 2's immutable loader output.
    if not package.index_chain or package.index_head_sha256 not in package.artifacts_by_digest:
        synthetic = _ArtifactRecord(package.index_head_sha256 or "0" * 64, {"artifact_id": "RUN_PACKAGE"})
        add_issue("PACKAGE_INTEGRITY_FACTS_INVALID", 2, synthetic, "verified index head missing", block=True)

    _layer_three(records, blocked, add_issue)
    _layer_four(records, blocked, adapter, add_issue, holds)
    _layer_five(records, blocked, add_issue)
    _layer_six(records, blocked, add_issue)
    topology, _ = _layer_seven(records, blocked, add_issue)
    graph_state = _layer_eight(records, blocked, holds, topology, add_issue)
    d3_eligibility, current_d3 = _layer_nine(
        records,
        blocked,
        holds,
        package,
        topology,
        graph_state,
        adapter,
        add_issue,
    )
    run_closure = _layer_ten(
        records,
        blocked,
        d3_eligibility,
        current_d3,
        add_issue,
    )
    operational_controls = validate_operational_controls(package)
    if operational_controls.applicable:
        issues.extend(
            ValidationIssue(issue.code, 11, issue.artifact_ref, issue.detail)
            for issue in operational_controls.issues
        )

    ordered = tuple(sorted(issues, key=lambda issue: (issue.layer, issue.artifact_ref, issue.code)))
    layer_numbers = range(1, 12) if operational_controls.applicable else range(1, 11)
    layers = tuple(
        ValidationLayer(
            layer=layer,
            status="FAIL" if any(issue.layer == layer for issue in ordered) else "PASS",
            issue_count=sum(1 for issue in ordered if issue.layer == layer),
        )
        for layer in layer_numbers
    )
    return ValidationReport(
        status="FAIL" if ordered else "PASS",
        issues=ordered,
        holds=tuple(sorted(holds)),
        layers=layers,
        index_head_sha256=package.index_head_sha256,
        graph_state=graph_state,
        d3_eligibility=d3_eligibility,
        run_closure=run_closure,
        graph_topology=topology,
    )
