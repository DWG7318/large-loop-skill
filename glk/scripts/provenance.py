from dataclasses import asdict, dataclass
from typing import Protocol, Tuple

from artifact_model import canonical_sha256
from run_model import (
    ROLE_TYPES,
    TECHNICAL_RECEIPT_TYPES,
    RoleCapabilityProfile,
    RunBindingError,
    enforce_supervisor_capability_exclusion,
)


ADAPTER_CONTRACT_VERSION = "1.0"
VERIFIED_STATUS = "VERIFIED"
LIVENESS_STATUSES = frozenset({"LIVE", "STOPPED", "UNREACHABLE", "UNKNOWN"})
ISOLATION_DIMENSIONS = {
    "conversation": "conversation_ref",
    "context": "context_ref",
    "workspace": "workspace_ref",
    "runtime_state": "runtime_state_ref",
    "evidence_root": "evidence_root",
    "decision_input": "decision_input_ref",
}


class ProvenanceError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class AuthorityScope:
    graph_id: str
    go_id: str | None
    cell_id: str | None

    def __post_init__(self):
        if not self.graph_id:
            raise ProvenanceError("SCOPE_INVALID", "graph_id is required")


@dataclass(frozen=True)
class AdapterRequest:
    adapter_contract_version: str
    request_digest: str
    binding_ref: str
    run_id: str
    scope: AuthorityScope
    artifact_sha256: str | None


@dataclass(frozen=True)
class ResolveBindingRequest(AdapterRequest):
    expected_role: str


@dataclass(frozen=True)
class VerifyIssuanceRequest(AdapterRequest):
    artifact_type: str
    expected_authority: str


@dataclass(frozen=True)
class VerifyIsolationRequest(AdapterRequest):
    binding_refs: Tuple[str, ...]
    required_dimensions: Tuple[str, ...]


@dataclass(frozen=True)
class CheckLivenessRequest(AdapterRequest):
    deadline: str


@dataclass(frozen=True)
class AdapterResult:
    adapter_contract_version: str
    request_digest: str
    binding_ref: str
    run_id: str
    scope: AuthorityScope
    artifact_sha256: str | None
    status: str
    evidence_ref: str
    observed_at: str


@dataclass(frozen=True)
class BindingResult(AdapterResult):
    role_type: str
    instance_id: str
    context_id: str
    workspace_id: str
    evidence_root: str
    capability_profile: RoleCapabilityProfile


@dataclass(frozen=True)
class IssuanceResult(AdapterResult):
    pass


@dataclass(frozen=True)
class IsolationBindingSnapshot:
    binding_ref: str
    conversation_ref: str
    context_ref: str
    workspace_ref: str
    runtime_state_ref: str
    evidence_root: str
    decision_input_ref: str


@dataclass(frozen=True)
class IsolationResult(AdapterResult):
    verified_dimensions: Tuple[str, ...]
    binding_snapshots: Tuple[IsolationBindingSnapshot, ...]


@dataclass(frozen=True)
class LivenessResult(AdapterResult):
    deadline: str


class ProvenanceAdapter(Protocol):
    def resolve_binding(self, request: ResolveBindingRequest) -> BindingResult:
        raise NotImplementedError

    def verify_issuance(self, request: VerifyIssuanceRequest) -> IssuanceResult:
        raise NotImplementedError

    def verify_isolation(self, request: VerifyIsolationRequest) -> IsolationResult:
        raise NotImplementedError

    def check_liveness(self, request: CheckLivenessRequest) -> LivenessResult:
        raise NotImplementedError


def request_digest_for(request: AdapterRequest) -> str:
    payload = asdict(request)
    payload.pop("request_digest", None)
    return canonical_sha256(payload)


def _require_text(value, code: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ProvenanceError(code, f"{label} is required")


def _validate_request(request: AdapterRequest) -> None:
    if request.adapter_contract_version != ADAPTER_CONTRACT_VERSION:
        raise ProvenanceError("ADAPTER_CONTRACT_MISMATCH", request.binding_ref)
    _require_text(request.binding_ref, "BINDING_REF_INVALID", "binding_ref")
    _require_text(request.run_id, "RUN_SCOPE_MISMATCH", "run_id")
    if not isinstance(request.scope, AuthorityScope):
        raise ProvenanceError("SCOPE_MISMATCH", request.binding_ref)
    if request.artifact_sha256 is not None and (
        not isinstance(request.artifact_sha256, str)
        or len(request.artifact_sha256) != 64
    ):
        raise ProvenanceError("ARTIFACT_DIGEST_INVALID", request.binding_ref)
    if request.request_digest != request_digest_for(request):
        raise ProvenanceError("REQUEST_DIGEST_MISMATCH", request.binding_ref)


def _validate_common_result(
    request: AdapterRequest,
    result: AdapterResult,
    allowed_statuses,
) -> None:
    if not isinstance(result, AdapterResult):
        raise ProvenanceError("ADAPTER_RESULT_INVALID", request.binding_ref)
    if result.adapter_contract_version != request.adapter_contract_version:
        raise ProvenanceError("ADAPTER_CONTRACT_MISMATCH", request.binding_ref)
    if result.request_digest != request.request_digest:
        raise ProvenanceError("REQUEST_DIGEST_MISMATCH", request.binding_ref)
    if result.binding_ref != request.binding_ref:
        raise ProvenanceError("BINDING_REF_MISMATCH", request.binding_ref)
    if result.run_id != request.run_id:
        raise ProvenanceError("RUN_SCOPE_MISMATCH", request.binding_ref)
    if result.scope != request.scope:
        raise ProvenanceError("SCOPE_MISMATCH", request.binding_ref)
    if result.artifact_sha256 != request.artifact_sha256:
        raise ProvenanceError("ARTIFACT_DIGEST_MISMATCH", request.binding_ref)
    if result.status not in allowed_statuses:
        raise ProvenanceError("ADAPTER_STATUS_INVALID", result.status)
    _require_text(result.evidence_ref, "ADAPTER_EVIDENCE_MISSING", "evidence_ref")
    _require_text(result.observed_at, "OBSERVATION_TIME_MISSING", "observed_at")


def _profile_field(profile, name: str) -> Tuple[str, ...]:
    value = getattr(profile, name, None)
    if not isinstance(value, tuple):
        raise ProvenanceError("CAPABILITY_PROFILE_INVALID", name)
    return value


class ProvenanceEvaluator:
    def __init__(self, adapter: ProvenanceAdapter):
        self._adapter = adapter

    def evaluate_binding(self, request: ResolveBindingRequest) -> BindingResult:
        _validate_request(request)
        result = self._adapter.resolve_binding(request)
        _validate_common_result(request, result, {VERIFIED_STATUS})
        if result.role_type not in ROLE_TYPES:
            raise ProvenanceError("ROLE_TYPE_INVALID", result.role_type)
        if request.expected_role not in ROLE_TYPES:
            raise ProvenanceError("ROLE_TYPE_INVALID", request.expected_role)
        if result.role_type != request.expected_role:
            raise ProvenanceError("ROLE_TYPE_MISMATCH", request.binding_ref)
        for label in ("instance_id", "context_id", "workspace_id", "evidence_root"):
            _require_text(
                getattr(result, label, None), "BINDING_RESULT_INVALID", label
            )
        profile = result.capability_profile
        if getattr(profile, "role_type", None) != result.role_type:
            raise ProvenanceError("CAPABILITY_ROLE_MISMATCH", request.binding_ref)
        _require_text(
            getattr(profile, "profile_id", None),
            "CAPABILITY_PROFILE_INVALID",
            "profile_id",
        )
        for field in (
            "issuable_artifact_types",
            "held_issuance_artifact_types",
            "invocable_issuance_artifact_types",
        ):
            _profile_field(profile, field)
        return result

    def evaluate_issuance(
        self,
        binding_request: ResolveBindingRequest,
        issuance_request: VerifyIssuanceRequest,
    ) -> IssuanceResult:
        _validate_request(issuance_request)
        resolved = self.evaluate_binding(binding_request)
        profile = resolved.capability_profile
        try:
            enforce_supervisor_capability_exclusion(profile)
        except RunBindingError as error:
            raise ProvenanceError(
                "SUPERVISOR_TECHNICAL_CAPABILITY_FORBIDDEN", str(error)
            ) from error
        if (
            resolved.role_type == "RUN_SUPERVISOR"
            and issuance_request.artifact_type in TECHNICAL_RECEIPT_TYPES
        ):
            raise ProvenanceError(
                "SUPERVISOR_TECHNICAL_CAPABILITY_FORBIDDEN",
                issuance_request.artifact_type,
            )
        if issuance_request.binding_ref != binding_request.binding_ref:
            raise ProvenanceError("BINDING_REF_MISMATCH", issuance_request.binding_ref)
        if issuance_request.run_id != binding_request.run_id:
            raise ProvenanceError("RUN_SCOPE_MISMATCH", issuance_request.binding_ref)
        if issuance_request.scope != binding_request.scope:
            raise ProvenanceError("SCOPE_MISMATCH", issuance_request.binding_ref)
        if resolved.role_type != issuance_request.expected_authority:
            raise ProvenanceError(
                "AUTHORITY_ROLE_MISMATCH", issuance_request.artifact_type
            )
        if issuance_request.artifact_type not in _profile_field(
            profile, "issuable_artifact_types"
        ):
            raise ProvenanceError(
                "ISSUANCE_CAPABILITY_MISSING", issuance_request.artifact_type
            )
        result = self._adapter.verify_issuance(issuance_request)
        _validate_common_result(issuance_request, result, {VERIFIED_STATUS})
        return result

    def evaluate_isolation(
        self, request: VerifyIsolationRequest
    ) -> IsolationResult:
        _validate_request(request)
        if len(request.binding_refs) < 2 or len(set(request.binding_refs)) != len(
            request.binding_refs
        ):
            raise ProvenanceError("ISOLATION_BINDINGS_INVALID", request.binding_ref)
        if any(dimension not in ISOLATION_DIMENSIONS for dimension in request.required_dimensions):
            raise ProvenanceError("ISOLATION_DIMENSION_INVALID", request.binding_ref)
        result = self._adapter.verify_isolation(request)
        _validate_common_result(request, result, {VERIFIED_STATUS})
        missing_dimensions = set(request.required_dimensions) - set(
            result.verified_dimensions
        )
        if missing_dimensions:
            raise ProvenanceError(
                "ISOLATION_INSUFFICIENT", ", ".join(sorted(missing_dimensions))
            )
        snapshots = {snapshot.binding_ref: snapshot for snapshot in result.binding_snapshots}
        if set(snapshots) != set(request.binding_refs):
            raise ProvenanceError("ISOLATION_BINDINGS_INVALID", request.binding_ref)
        for dimension in request.required_dimensions:
            attribute = ISOLATION_DIMENSIONS[dimension]
            values = [getattr(snapshots[ref], attribute) for ref in request.binding_refs]
            if any(not value for value in values) or len(set(values)) != len(values):
                raise ProvenanceError("ISOLATION_COLLISION", dimension)
        return result

    def evaluate_liveness(self, request: CheckLivenessRequest) -> LivenessResult:
        _validate_request(request)
        _require_text(request.deadline, "LIVENESS_DEADLINE_INVALID", "deadline")
        result = self._adapter.check_liveness(request)
        _validate_common_result(request, result, LIVENESS_STATUSES)
        if result.deadline != request.deadline:
            raise ProvenanceError("LIVENESS_DEADLINE_MISMATCH", request.binding_ref)
        return result
