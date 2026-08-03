import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"
PROVENANCE_PATH = SCRIPTS / "provenance.py"
RUN_MODEL_PATH = SCRIPTS / "run_model.py"


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def load_module(path: Path, name: str, missing_message: str):
    if not path.is_file():
        pytest.fail(missing_message)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


def load_provenance():
    return load_module(
        PROVENANCE_PATH,
        "glk_provenance",
        "GLK 3.0 provenance adapter boundary is missing",
    )


def load_run_model():
    return load_module(RUN_MODEL_PATH, "glk_run_model_300", "GLK Run model is missing")


class FixedResponseAdapter:
    def __init__(self, *, binding=None, issuance=None, isolation=None, liveness=None):
        self.binding = binding
        self.issuance = issuance
        self.isolation = isolation
        self.liveness = liveness
        self.calls = []

    def resolve_binding(self, request):
        self.calls.append(("resolve_binding", request))
        return self.binding

    def verify_issuance(self, request):
        self.calls.append(("verify_issuance", request))
        return self.issuance

    def verify_isolation(self, request):
        self.calls.append(("verify_isolation", request))
        return self.isolation

    def check_liveness(self, request):
        self.calls.append(("check_liveness", request))
        return self.liveness


def scope(m, go_id="GO-001", cell_id="CELL-001"):
    return m.AuthorityScope(graph_id="GRAPH-RUN-001", go_id=go_id, cell_id=cell_id)


def signed_request(m, request_type, **values):
    request = request_type(request_digest="0" * 64, **values)
    return dataclasses.replace(request, request_digest=m.request_digest_for(request))


def capability(run_model, role_type, *, issue=(), hold=(), invoke=()):
    return run_model.RoleCapabilityProfile(
        profile_id=f"CAPABILITY-{role_type}",
        role_type=role_type,
        issuable_artifact_types=tuple(issue),
        held_issuance_artifact_types=tuple(hold),
        invocable_issuance_artifact_types=tuple(invoke),
    )


def binding_request(m, role_type="WORKER", run_id="RUN-001", binding_ref="ROLE-WORKER-001"):
    return signed_request(
        m,
        m.ResolveBindingRequest,
        adapter_contract_version="1.0",
        binding_ref=binding_ref,
        run_id=run_id,
        scope=scope(m),
        artifact_sha256=None,
        expected_role=role_type,
    )


def binding_result(
    m,
    run_model,
    request,
    *,
    role_type="WORKER",
    run_id=None,
    result_scope=None,
    profile=None,
    context_id="CONTEXT-WORKER-001",
    workspace_id="WORKSPACE-WORKER-001",
):
    return m.BindingResult(
        adapter_contract_version="1.0",
        request_digest=request.request_digest,
        binding_ref=request.binding_ref,
        run_id=run_id or request.run_id,
        scope=result_scope or request.scope,
        artifact_sha256=request.artifact_sha256,
        status="VERIFIED",
        evidence_ref="attestations/binding-worker-001.json",
        observed_at="2026-08-03T04:00:00Z",
        role_type=role_type,
        instance_id="INSTANCE-WORKER-001",
        context_id=context_id,
        workspace_id=workspace_id,
        evidence_root="evidence/roles/worker-001",
        capability_profile=profile or capability(run_model, "WORKER", issue=("D0_RECEIPT",)),
    )


def issuance_request(
    m,
    *,
    artifact_type="D0_RECEIPT",
    expected_authority="WORKER",
    binding_ref="ROLE-WORKER-001",
    run_id="RUN-001",
    request_scope=None,
    artifact_sha256="a" * 64,
):
    return signed_request(
        m,
        m.VerifyIssuanceRequest,
        adapter_contract_version="1.0",
        binding_ref=binding_ref,
        run_id=run_id,
        scope=request_scope or scope(m),
        artifact_sha256=artifact_sha256,
        artifact_type=artifact_type,
        expected_authority=expected_authority,
    )


def issuance_result(m, request, *, run_id=None, result_scope=None, artifact_sha256=None):
    return m.IssuanceResult(
        adapter_contract_version="1.0",
        request_digest=request.request_digest,
        binding_ref=request.binding_ref,
        run_id=run_id or request.run_id,
        scope=result_scope or request.scope,
        artifact_sha256=artifact_sha256 or request.artifact_sha256,
        status="VERIFIED",
        evidence_ref="attestations/issuance-d0.json",
        observed_at="2026-08-03T04:01:00Z",
    )


def test_protocol_has_exactly_four_operations_and_immutable_contracts():
    m = load_provenance()
    operations = {
        name
        for name, value in m.ProvenanceAdapter.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    require_equal(
        operations,
        {"resolve_binding", "verify_issuance", "verify_isolation", "check_liveness"},
        "Protocol operations",
    )
    request = binding_request(m)
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.run_id = "RUN-FORGED"
    require_equal(len(request.request_digest), 64, "request digest length")


def test_run_model_closes_role_types_and_defines_capability_profiles():
    run_model = load_run_model()
    require_equal(
        set(run_model.ROLE_TYPES),
        {"RUN_SUPERVISOR", "WORKER", "CHECKER", "GO_VERIFIER", "RUN_VERIFIER", "OWNER"},
        "closed role types",
    )
    values = {
        "role_binding_id": "ROLE-UNKNOWN",
        "role_type": "SUPERVISORISH",
        "run_id": "RUN-001",
        "instance_id": "INSTANCE-UNKNOWN",
        "context_id": "CONTEXT-UNKNOWN",
        "workspace_id": "WORKSPACE-UNKNOWN",
        "evidence_root": "evidence/unknown",
        "capability_profile_id": "CAPABILITY-UNKNOWN",
    }
    with pytest.raises(run_model.RunBindingError, match="role_type"):
        run_model.RoleBinding(**values)
    profile = capability(run_model, "WORKER", issue=("D0_RECEIPT",))
    require_equal(profile.issuable_artifact_types, ("D0_RECEIPT",), "issuable types")


@pytest.mark.parametrize(
    "artifact_type,expected_authority,capability_kind",
    [
        ("D0_RECEIPT", "WORKER", "issue"),
        ("D1_RECEIPT", "CHECKER", "hold"),
        ("D2_RECEIPT", "GO_VERIFIER", "invoke"),
        ("D3_RECEIPT", "RUN_VERIFIER", "issue"),
    ],
)
def test_r01_r03_supervisor_technical_capability_fails_before_issuance_call(
    artifact_type, expected_authority, capability_kind
):
    m = load_provenance()
    run_model = load_run_model()
    binding = binding_request(
        m, role_type="RUN_SUPERVISOR", binding_ref="ROLE-SUPERVISOR-001"
    )
    capability_values = {"issue": (), "hold": (), "invoke": ()}
    capability_values[capability_kind] = (artifact_type,)
    profile = capability(run_model, "RUN_SUPERVISOR", **capability_values)
    resolved = binding_result(
        m,
        run_model,
        binding,
        role_type="RUN_SUPERVISOR",
        profile=profile,
        context_id="CONTEXT-SUPERVISOR-001",
        workspace_id="WORKSPACE-SUPERVISOR-001",
    )
    issuance = issuance_request(
        m,
        artifact_type=artifact_type,
        expected_authority=expected_authority,
        binding_ref=binding.binding_ref,
    )
    adapter = FixedResponseAdapter(
        binding=resolved,
        issuance=issuance_result(m, issuance),
    )
    evaluator = m.ProvenanceEvaluator(adapter)
    with pytest.raises(m.ProvenanceError) as captured:
        evaluator.evaluate_issuance(binding, issuance)
    require_equal(
        captured.value.code,
        "SUPERVISOR_TECHNICAL_CAPABILITY_FORBIDDEN",
        artifact_type,
    )
    require_equal(
        tuple(name for name, unused in adapter.calls),
        ("resolve_binding",),
        "adapter call order",
    )


def test_worker_issuance_uses_resolve_then_exact_digest_verification():
    m = load_provenance()
    run_model = load_run_model()
    binding = binding_request(m)
    issuance = issuance_request(m)
    adapter = FixedResponseAdapter(
        binding=binding_result(m, run_model, binding),
        issuance=issuance_result(m, issuance),
    )
    result = m.ProvenanceEvaluator(adapter).evaluate_issuance(binding, issuance)
    require_equal(result.status, "VERIFIED", "issuance status")
    require_equal(
        tuple(name for name, unused in adapter.calls),
        ("resolve_binding", "verify_issuance"),
        "adapter call order",
    )


def test_r09_free_role_string_cannot_resolve_a_binding():
    m = load_provenance()
    run_model = load_run_model()
    request = binding_request(m)
    adapter = FixedResponseAdapter(
        binding=binding_result(m, run_model, request, role_type="SUPERVISORISH")
    )
    with pytest.raises(m.ProvenanceError) as captured:
        m.ProvenanceEvaluator(adapter).evaluate_binding(request)
    require_equal(captured.value.code, "ROLE_TYPE_INVALID", "free role string")


@pytest.mark.parametrize(
    "mismatch,expected_code",
    [
        ("run", "RUN_SCOPE_MISMATCH"),
        ("scope", "SCOPE_MISMATCH"),
        ("digest", "ARTIFACT_DIGEST_MISMATCH"),
    ],
)
def test_run_scope_and_artifact_digest_mismatches_fail_closed(
    tmp_path, mismatch, expected_code
):
    del tmp_path
    m = load_provenance()
    run_model = load_run_model()
    binding = binding_request(m)
    issuance = issuance_request(m)
    resolved = binding_result(
        m,
        run_model,
        binding,
        run_id="RUN-OTHER" if mismatch == "run" else None,
    )
    issued = issuance_result(
        m,
        issuance,
        result_scope=scope(m, go_id="GO-OTHER") if mismatch == "scope" else None,
        artifact_sha256="b" * 64 if mismatch == "digest" else None,
    )
    adapter = FixedResponseAdapter(binding=resolved, issuance=issued)
    with pytest.raises(m.ProvenanceError) as captured:
        m.ProvenanceEvaluator(adapter).evaluate_issuance(binding, issuance)
    require_equal(captured.value.code, expected_code, mismatch)


def isolation_request(m):
    return signed_request(
        m,
        m.VerifyIsolationRequest,
        adapter_contract_version="1.0",
        binding_ref="ROLE-WORKER-001",
        run_id="RUN-001",
        scope=scope(m),
        artifact_sha256=None,
        binding_refs=("ROLE-WORKER-001", "ROLE-CHECKER-001"),
        required_dimensions=("context", "workspace"),
    )


def isolation_result(m, request, *, same_context=False, same_workspace=False, dimensions=None):
    worker = m.IsolationBindingSnapshot(
        binding_ref="ROLE-WORKER-001",
        conversation_ref="CONVERSATION-WORKER-001",
        context_ref="CONTEXT-SHARED" if same_context else "CONTEXT-WORKER-001",
        workspace_ref="WORKSPACE-SHARED" if same_workspace else "WORKSPACE-WORKER-001",
        runtime_state_ref="RUNTIME-WORKER-001",
        evidence_root="evidence/roles/worker-001",
        decision_input_ref="DECISION-WORKER-001",
    )
    checker = m.IsolationBindingSnapshot(
        binding_ref="ROLE-CHECKER-001",
        conversation_ref="CONVERSATION-CHECKER-001",
        context_ref="CONTEXT-SHARED" if same_context else "CONTEXT-CHECKER-001",
        workspace_ref="WORKSPACE-SHARED" if same_workspace else "WORKSPACE-CHECKER-001",
        runtime_state_ref="RUNTIME-CHECKER-001",
        evidence_root="evidence/roles/checker-001",
        decision_input_ref="DECISION-CHECKER-001",
    )
    return m.IsolationResult(
        adapter_contract_version="1.0",
        request_digest=request.request_digest,
        binding_ref=request.binding_ref,
        run_id=request.run_id,
        scope=request.scope,
        artifact_sha256=request.artifact_sha256,
        status="VERIFIED",
        evidence_ref="attestations/isolation-worker-checker.json",
        observed_at="2026-08-03T04:02:00Z",
        verified_dimensions=dimensions or ("context", "workspace"),
        binding_snapshots=(worker, checker),
    )


@pytest.mark.parametrize("collision", ["context", "workspace"])
def test_r10_same_context_or_workspace_cannot_masquerade_as_isolated(collision):
    m = load_provenance()
    request = isolation_request(m)
    result = isolation_result(
        m,
        request,
        same_context=collision == "context",
        same_workspace=collision == "workspace",
    )
    adapter = FixedResponseAdapter(isolation=result)
    with pytest.raises(m.ProvenanceError) as captured:
        m.ProvenanceEvaluator(adapter).evaluate_isolation(request)
    require_equal(captured.value.code, "ISOLATION_COLLISION", collision)


def test_isolation_requires_every_requested_dimension_and_accepts_distinct_bindings():
    m = load_provenance()
    request = isolation_request(m)
    incomplete_adapter = FixedResponseAdapter(
        isolation=isolation_result(m, request, dimensions=("context",))
    )
    with pytest.raises(m.ProvenanceError) as captured:
        m.ProvenanceEvaluator(incomplete_adapter).evaluate_isolation(request)
    require_equal(captured.value.code, "ISOLATION_INSUFFICIENT", "missing workspace")

    complete_adapter = FixedResponseAdapter(isolation=isolation_result(m, request))
    result = m.ProvenanceEvaluator(complete_adapter).evaluate_isolation(request)
    require_equal(result.status, "VERIFIED", "isolation status")


def test_liveness_operation_has_closed_status_and_evidence_contract():
    m = load_provenance()
    request = signed_request(
        m,
        m.CheckLivenessRequest,
        adapter_contract_version="1.0",
        binding_ref="ROLE-WORKER-001",
        run_id="RUN-001",
        scope=scope(m),
        artifact_sha256=None,
        deadline="2026-08-03T05:00:00Z",
    )
    result = m.LivenessResult(
        adapter_contract_version="1.0",
        request_digest=request.request_digest,
        binding_ref=request.binding_ref,
        run_id=request.run_id,
        scope=request.scope,
        artifact_sha256=None,
        status="LIVE",
        evidence_ref="attestations/liveness-worker-001.json",
        observed_at="2026-08-03T04:03:00Z",
        deadline=request.deadline,
    )
    adapter = FixedResponseAdapter(liveness=result)
    evaluated = m.ProvenanceEvaluator(adapter).evaluate_liveness(request)
    require_equal(evaluated.status, "LIVE", "liveness status")
    with pytest.raises(dataclasses.FrozenInstanceError):
        evaluated.status = "UNKNOWN"
