import dataclasses
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


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "glk.schema.json"
TECHNICAL_TYPES = ("D0_RECEIPT", "D1_RECEIPT", "D2_RECEIPT", "D3_RECEIPT")
REQUIRES_EVIDENCE = TECHNICAL_TYPES + ("SUPERVISOR_ADMISSION", "PREFLIGHT_ADMISSION")
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


@dataclass(frozen=True)
class _ArtifactRecord:
    digest: str
    value: Mapping

    @property
    def artifact_ref(self):
        raw = self.value.get("artifact_id")
        return raw if isinstance(raw, str) and raw else f"digest:{self.digest}"


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
    records = []
    for digest, value in package.artifacts_by_digest.items():
        if not isinstance(digest, str) or len(digest) != 64 or not isinstance(value, Mapping):
            raise TypeError("invalid immutable package subject")
        records.append(_ArtifactRecord(digest=digest, value=value))
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
                holds.add("RUN_AUTHORITY_HOLD")
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


def validate_loaded_run(package, adapter):
    """Derive a frozen five-layer report from one already integrity-checked package."""
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

    ordered = tuple(sorted(issues, key=lambda issue: (issue.layer, issue.artifact_ref, issue.code)))
    layers = tuple(
        ValidationLayer(
            layer=layer,
            status="FAIL" if any(issue.layer == layer for issue in ordered) else "PASS",
            issue_count=sum(1 for issue in ordered if issue.layer == layer),
        )
        for layer in range(1, 6)
    )
    return ValidationReport(
        status="FAIL" if ordered else "PASS",
        issues=ordered,
        holds=tuple(sorted(holds)),
        layers=layers,
        index_head_sha256=package.index_head_sha256,
    )
