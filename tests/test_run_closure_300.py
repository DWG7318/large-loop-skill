import copy
import dataclasses
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

import test_admission_graph_300 as ag
import test_run_validation_300 as rv
from glk300_fixtures import read_index, sha256_file, write_index, write_json


ROOT = Path(__file__).resolve().parents[1]
RUN_STATE_PATH = ROOT / "glk" / "scripts" / "run_state.py"


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


@dataclass(frozen=True)
class ClosureCase:
    fixture: object
    head_path: Path
    bounded_index_sha256: str

    @property
    def root(self):
        return self.fixture.root


class ClosureAdapter(rv.TrustedAdapterFixture):
    def __init__(self, provenance, run_model, *, run_isolation_result="VERIFIED"):
        super().__init__(provenance, run_model)
        self.run_isolation_result = run_isolation_result

    def resolve_binding(self, request):
        self.calls.append(("resolve_binding", request))
        role_type = self.role_overrides.get(request.binding_ref, rv.ROLE_BINDINGS.get(request.binding_ref, request.expected_role))
        profile_role = role_type if role_type in rv.ISSUABLE_BY_ROLE else "WORKER"
        issuable = tuple(rv.ISSUABLE_BY_ROLE[profile_role])
        if profile_role == "RUN_SUPERVISOR" and "SECURITY_HANDOFF" not in issuable:
            issuable += ("SECURITY_HANDOFF",)
        profile = self.rm.RoleCapabilityProfile(
            profile_id=f"CAPABILITY-{profile_role}",
            role_type=profile_role,
            issuable_artifact_types=issuable,
            held_issuance_artifact_types=(),
            invocable_issuance_artifact_types=(),
        )
        return self.p.BindingResult(
            **self._common(request),
            role_type=role_type,
            instance_id=f"INSTANCE-{request.binding_ref}",
            context_id=f"CONTEXT-{request.binding_ref}",
            workspace_id=f"WORKSPACE-{request.binding_ref}",
            evidence_root=f"evidence/roles/{request.binding_ref}",
            capability_profile=profile,
        )

    def verify_isolation(self, request):
        result = super().verify_isolation(request)
        if len(request.required_dimensions) != 6:
            return result
        if self.run_isolation_result == "MISSING_DIMENSION":
            return dataclasses.replace(
                result,
                verified_dimensions=tuple(
                    dimension
                    for dimension in result.verified_dimensions
                    if dimension != "runtime_state"
                ),
            )
        if self.run_isolation_result == "COLLISION":
            snapshots = list(result.binding_snapshots)
            snapshots[-1] = dataclasses.replace(
                snapshots[-1],
                workspace_ref=snapshots[0].workspace_ref,
            )
            return dataclasses.replace(result, binding_snapshots=tuple(snapshots))
        if self.run_isolation_result == "UNVERIFIED":
            return dataclasses.replace(result, status="UNVERIFIED")
        if self.run_isolation_result == "MISSING_BINDING":
            return dataclasses.replace(
                result,
                binding_snapshots=result.binding_snapshots[:-1],
            )
        return result


def _artifact_by_id(root, artifact_id):
    for path in rv._all_formal_paths(root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("artifact_id") == artifact_id:
            return path, value
    pytest.fail(f"missing fixture artifact {artifact_id}")


def _clone_go_two_lineage(fixture):
    manifest_path, source_manifest = rv._artifact(fixture.root, "CELL_MANIFEST")
    manifest = copy.deepcopy(source_manifest)
    manifest.update(
        {
            "artifact_id": "CELL-MANIFEST-GO-002-V1",
            "candidate_id": "CELL-MANIFEST-GO-002-V1",
            "candidate_sha256": rv._candidate_hash("CELL-MANIFEST-GO-002-V1"),
            "go_id": "GO-002",
            "manifest_id": "CELL-MANIFEST-GO-002",
            "go_contract_sha256": "8" * 64,
            "required_cells": [
                {
                    "cell_id": "GO-002-CELL-001",
                    "cell_contract_sha256": "7" * 64,
                    "required": True,
                }
            ],
            "provenance_ref": "attestations/CELL-MANIFEST-GO-002-V1.json",
            "issued_at": "2026-08-03T03:10:00Z",
        }
    )
    manifest["evidence_refs"] = [
        rv._add_evidence(fixture.root, "evidence/GO-002/cell-manifest-v1.json", manifest["artifact_id"])
    ]
    manifest["closure_sha256"] = rv._manifest_closure_sha256_300(manifest)
    manifest_path = fixture.root / "manifests" / f"{manifest['artifact_id']}.json"
    write_json(manifest_path, manifest)

    candidate_id = "CANDIDATE-GO-002-CELL-001-V1"
    candidate_sha256 = rv._candidate_hash(candidate_id)
    _, source_d0 = rv._artifact(fixture.root, "D0_RECEIPT")
    d0 = copy.deepcopy(source_d0)
    d0.update(
        {
            "artifact_id": "D0-GO-002-CELL-001-V1",
            "candidate_id": candidate_id,
            "candidate_sha256": candidate_sha256,
            "go_id": "GO-002",
            "cell_id": "GO-002-CELL-001",
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "cell_contract_sha256": manifest["required_cells"][0]["cell_contract_sha256"],
            "provenance_ref": "attestations/D0-GO-002-CELL-001-V1.json",
            "issued_at": "2026-08-03T03:11:00Z",
        }
    )
    d0["evidence_refs"] = [rv._add_evidence(fixture.root, "evidence/GO-002/d0-v1.json", d0["artifact_id"])]
    d0_path = fixture.root / "receipts" / f"{d0['artifact_id']}.json"
    write_json(d0_path, d0)

    _, source_d1 = rv._artifact(fixture.root, "D1_RECEIPT")
    d1 = copy.deepcopy(source_d1)
    d1.update(
        {
            "artifact_id": "D1-GO-002-CELL-001-V1",
            "candidate_id": candidate_id,
            "candidate_sha256": candidate_sha256,
            "go_id": "GO-002",
            "cell_id": "GO-002-CELL-001",
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "cell_contract_sha256": manifest["required_cells"][0]["cell_contract_sha256"],
            "d0_artifact_sha256": sha256_file(d0_path),
            "provenance_ref": "attestations/D1-GO-002-CELL-001-V1.json",
            "issued_at": "2026-08-03T03:12:00Z",
        }
    )
    d1["evidence_refs"] = [rv._add_evidence(fixture.root, "evidence/GO-002/d1-v1.json", d1["artifact_id"])]
    d1_path = fixture.root / "receipts" / f"{d1['artifact_id']}.json"
    write_json(d1_path, d1)

    selected = {
        "cell_id": d0["cell_id"],
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "d0_artifact_sha256": sha256_file(d0_path),
        "d1_artifact_sha256": sha256_file(d1_path),
    }
    _, source_closure = rv._artifact(fixture.root, "GO_CANDIDATE_CLOSURE")
    closure = copy.deepcopy(source_closure)
    closure.update(
        {
            "artifact_id": "GO-CANDIDATE-CLOSURE-GO-002-V1",
            "candidate_id": "CANDIDATE-GO-002-V1",
            "go_id": "GO-002",
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "selected_cells": [selected],
            "provenance_ref": "attestations/GO-CANDIDATE-CLOSURE-GO-002-V1.json",
            "issued_at": "2026-08-03T03:13:00Z",
        }
    )
    closure["candidate_sha256"] = rv._go_candidate_sha256_300(manifest, closure["selected_cells"])
    closure["evidence_refs"] = [
        rv._add_evidence(fixture.root, "evidence/GO-002/closure-v1.json", closure["artifact_id"])
    ]
    closure_path = fixture.root / "closures" / f"{closure['artifact_id']}.json"
    write_json(closure_path, closure)

    _, source_d2 = rv._artifact(fixture.root, "D2_RECEIPT")
    d2 = copy.deepcopy(source_d2)
    d2.update(
        {
            "artifact_id": "D2-GO-002-V1",
            "candidate_id": closure["candidate_id"],
            "candidate_sha256": closure["candidate_sha256"],
            "go_id": "GO-002",
            "go_candidate_closure_sha256": sha256_file(closure_path),
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "required_cell_tuples": [selected],
            "provenance_ref": "attestations/D2-GO-002-V1.json",
            "issued_at": "2026-08-03T03:14:00Z",
        }
    )
    d2["evidence_refs"] = [rv._add_evidence(fixture.root, "evidence/GO-002/d2-v1.json", d2["artifact_id"])]
    d2_path = fixture.root / "receipts" / f"{d2['artifact_id']}.json"
    write_json(d2_path, d2)

    for ordinal, target_path in enumerate((d0_path, d1_path, closure_path, d2_path), start=1):
        rv._ensure_supervisor_admission(
            fixture.root,
            target_path,
            suffix=target_path.stem,
            issued_at=f"2026-08-03T03:{20 + ordinal:02d}:00Z",
        )
    return d2_path, d2


def _write_current_head(case):
    root = case.root
    rv._materialize_referenced_evidence(root)
    head = read_index(case.head_path) if case.head_path.exists() else read_index(case.fixture.index_path)
    evidence_ref = "evidence/package/RUN-PACKAGE-INDEX-RUN-001-v2.json"
    rv._add_evidence(root, evidence_ref, "RUN-PACKAGE-INDEX-RUN-001-v2")
    referenced = {evidence_ref}
    for path in rv._all_formal_paths(root):
        referenced.update(rv._evidence_references(yaml.safe_load(path.read_text(encoding="utf-8"))))
    for index_path in sorted((root / "indexes").glob("*")):
        if index_path == case.head_path or not index_path.is_file():
            continue
        referenced.update(rv._evidence_references(yaml.safe_load(index_path.read_text(encoding="utf-8"))))
    for path in tuple(sorted((root / "evidence").rglob("*"))):
        if path.is_file() and path.relative_to(root).as_posix() not in referenced:
            path.unlink()

    formal_entries = []
    ledger_heads = {}
    for path in rv._all_formal_paths(root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        digest = sha256_file(path)
        formal_entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": digest,
                "artifact_type": value["artifact_type"],
            }
        )
        ledger_heads[value["artifact_id"]] = digest
    evidence_paths = tuple(sorted(path for path in (root / "evidence").rglob("*") if path.is_file()))
    head.update(
        {
            "artifact_id": "RUN-PACKAGE-INDEX-RUN-001-v2",
            "candidate_id": "RUN-PACKAGE-RUN-001-v2",
            "candidate_sha256": rv._candidate_hash("RUN-PACKAGE-RUN-001-v2"),
            "evidence_refs": [evidence_ref],
            "provenance_ref": "attestations/RUN-PACKAGE-INDEX-RUN-001-v2.json",
            "issued_at": "2026-08-03T05:10:00Z",
            "index_version": 2,
            "prior_index_sha256": case.bounded_index_sha256,
            "formal_artifacts": formal_entries,
            "evidence_objects": [
                {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}
                for path in evidence_paths
            ],
            "ledger_heads": ledger_heads,
        }
    )
    write_index(case.head_path, head)


def _build_two_go_run(tmp_path, *, with_owner=True, with_security=True):
    fixture = rv._prepare_validation_fixture(tmp_path)
    owner_path, owner = rv._artifact(fixture.root, "OWNER_ACCEPTANCE")
    owner_path.unlink()
    d2_two_path, d2_two = _clone_go_two_lineage(fixture)
    d2_one_path, d2_one = rv._artifact(fixture.root, "D2_RECEIPT")

    edge = ag._edge("GO-001", "GO-002")
    nodes = [
        ag._node(
            "GO-001",
            go_claim_sha256=d2_one["go_claim_sha256"],
            acceptance_contract_sha256=d2_one["acceptance_contract_sha256"],
        ),
        ag._node(
            "GO-002",
            ("GO-001",),
            go_claim_sha256=d2_two["go_claim_sha256"],
            acceptance_contract_sha256=d2_two["acceptance_contract_sha256"],
        ),
    ]
    _, baseline = ag._set_topology(fixture, nodes, [edge], ("GO-001",), ("GO-002",))
    event_one_path = ag._configure_event(fixture, baseline, (), ("GO-002",))
    _, event_one = _artifact_by_id(fixture.root, "GRAPH-EVENT-RUN-001-V1")
    event_two = copy.deepcopy(event_one)
    event_two.update(
        {
            "artifact_id": "GRAPH-EVENT-RUN-001-V2",
            "event_id": "GRAPH-EVENT-RUN-001-V2",
            "trigger_artifact_ref": d2_two_path.relative_to(fixture.root).as_posix(),
            "trigger_artifact_sha256": sha256_file(d2_two_path),
            "prior_event_sha256": sha256_file(event_one_path),
            "waiting_go_ids": [],
            "active_go_ids": [],
            "provenance_ref": "attestations/GRAPH-EVENT-RUN-001-V2.json",
            "issued_at": "2026-08-03T03:30:00Z",
        }
    )
    event_two["evidence_refs"] = [
        rv._add_evidence(fixture.root, "evidence/graph/events/v2.json", event_two["artifact_id"])
    ]
    event_two_path = fixture.root / "events" / f"{event_two['artifact_id']}.json"
    write_json(event_two_path, event_two)

    d3_path, d3 = rv._artifact(fixture.root, "D3_RECEIPT")
    d3.update(
        {
            "required_go_ids": ["GO-001", "GO-002"],
            "admitted_d2_artifact_sha256s": [sha256_file(d2_one_path), sha256_file(d2_two_path)],
            "graph_sha256": baseline["graph_hash"],
            "graph_seam_claims": ["GO-001->GO-002"],
            "graph_seam_evidence_refs": edge["consumption_evidence_refs"],
        }
    )
    write_json(d3_path, d3)
    rv._ensure_supervisor_admission(
        fixture.root,
        d3_path,
        suffix="D3-RUN-001-V1",
        issued_at="2026-08-03T04:20:00Z",
    )

    rv._materialize_referenced_evidence(fixture.root)
    rv._reindex(fixture)
    bounded_index_sha256 = sha256_file(fixture.index_path)

    owner.update(
        {
            "candidate_id": d3["candidate_id"],
            "candidate_sha256": d3["candidate_sha256"],
            "admitted_d3_artifact_sha256": sha256_file(d3_path),
            "package_index_sha256": bounded_index_sha256,
            "issued_at": "2026-08-03T05:00:00Z",
        }
    )
    if with_owner:
        write_json(owner_path, owner)

    if with_security:
        security = copy.deepcopy(rv._template("SECURITY_HANDOFF"))
        security.update(
            {
                "candidate_id": d3["candidate_id"],
                "candidate_sha256": d3["candidate_sha256"],
                "owner_acceptance_sha256": sha256_file(owner_path) if with_owner else "0" * 64,
                "issued_at": "2026-08-03T05:05:00Z",
            }
        )
        security["evidence_refs"] = [
            rv._add_evidence(fixture.root, "evidence/RUN-001/security-handoff-v1.json", security["artifact_id"])
        ]
        write_json(fixture.root / "handoffs" / "SECURITY-HANDOFF-RUN-001-V1.json", security)

    case = ClosureCase(
        fixture=fixture,
        head_path=fixture.root / "indexes" / "RUN_PACKAGE_INDEX-v2.yaml",
        bounded_index_sha256=bounded_index_sha256,
    )
    _write_current_head(case)
    return case


def _sync_d3_downstream(case):
    d3_path, d3 = rv._artifact(case.root, "D3_RECEIPT")
    rv._sync_supervisor_admission(case.root, d3_path)
    owner_matches = [item for item in rv._all_formal_paths(case.root) if yaml.safe_load(item.read_text(encoding="utf-8")).get("artifact_type") == "OWNER_ACCEPTANCE"]
    if owner_matches:
        owner_path = owner_matches[0]
        owner = yaml.safe_load(owner_path.read_text(encoding="utf-8"))
        owner["candidate_id"] = d3["candidate_id"]
        owner["candidate_sha256"] = d3["candidate_sha256"]
        owner["admitted_d3_artifact_sha256"] = sha256_file(d3_path)
        write_json(owner_path, owner)
        security_matches = [item for item in rv._all_formal_paths(case.root) if yaml.safe_load(item.read_text(encoding="utf-8")).get("artifact_type") == "SECURITY_HANDOFF"]
        if security_matches:
            security_path = security_matches[0]
            security = yaml.safe_load(security_path.read_text(encoding="utf-8"))
            security["owner_acceptance_sha256"] = sha256_file(owner_path)
            write_json(security_path, security)
    _write_current_head(case)


def _validate(case):
    validation, report, loaded, _ = _validate_with_adapter(case)
    return validation, report, loaded


def _validate_with_adapter(case, *, run_isolation_result="VERIFIED"):
    package_module, provenance, run_model = rv.load_prerequisites()
    loaded = package_module.load_run_package(case.root)
    validation = rv.load_validation()
    adapter = ClosureAdapter(
        provenance,
        run_model,
        run_isolation_result=run_isolation_result,
    )
    report = validation.validate_loaded_run(loaded, adapter)
    return validation, report, loaded, adapter


def _codes(report, layer):
    return {issue.code for issue in report.issues if issue.layer == layer}


def _require_layers_one_to_eight_pass(report):
    issues = tuple((issue.code, issue.layer, issue.artifact_ref) for issue in report.issues if issue.layer <= 8)
    require_equal(issues, (), "layers 1-8")


def test_positive_D3_owner_acceptance_and_security_handoff_closure(tmp_path):
    case = _build_two_go_run(tmp_path)
    _, report, _ = _validate(case)
    _require_layers_one_to_eight_pass(report)
    require_equal(_codes(report, 9), set(), "D3 closure")
    require_equal(_codes(report, 10), set(), "Owner closure")
    require(hasattr(report, "run_closure"), "derived Run closure is missing")
    require_equal(report.run_closure.owner_verdict, "LOOP_OWNER_ACCEPTED", "Owner verdict")
    require_equal(report.run_closure.security_status, "PENDING_LCCODING_AUDIT", "handoff status")
    require_equal(report.run_closure.lccoding_security_accepted, False, "LCCoding audit ownership")


def test_R18_Run_Verifier_isolation_requires_six_dimension_adapter_attestation(tmp_path):
    case = _build_two_go_run(tmp_path)
    _, report, loaded, adapter = _validate_with_adapter(case)
    _require_layers_one_to_eight_pass(report)
    require_equal(_codes(report, 9), set(), "adapter-attested Run Verifier isolation")
    requests = tuple(
        request
        for operation, request in adapter.calls
        if operation == "verify_isolation" and len(request.required_dimensions) == 6
    )
    require_equal(len(requests), 1, "Run Verifier isolation adapter calls")
    request = requests[0]
    require_equal(
        set(request.required_dimensions),
        {"conversation", "context", "workspace", "runtime_state", "evidence_root", "decision_input"},
        "Run Verifier isolation dimensions",
    )
    formal = tuple(loaded.artifacts_by_digest.values())
    d3 = next(value for value in formal if value.get("artifact_type") == "D3_RECEIPT")
    d2s = tuple(value for value in formal if value.get("artifact_type") == "D2_RECEIPT")
    d1_by_digest = {
        digest: value
        for digest, value in loaded.artifacts_by_digest.items()
        if value.get("artifact_type") == "D1_RECEIPT"
    }
    expected_bindings = {d3["issuer_binding_ref"]}
    expected_bindings.update(value["issuer_binding_ref"] for value in d2s)
    for d2 in d2s:
        expected_bindings.update(
            d1_by_digest[selected["d1_artifact_sha256"]]["issuer_binding_ref"]
            for selected in d2["required_cell_tuples"]
        )
    require_equal(set(request.binding_refs), expected_bindings, "Run Verifier isolation bindings")
    require_equal(request.binding_ref, d3["issuer_binding_ref"], "Run Verifier request binding")
    require_equal(request.run_id, d3["run_id"], "Run Verifier request Run")
    require_equal(request.scope.graph_id, d3["graph_id"], "Run Verifier request graph scope")
    require_equal(request.scope.go_id, d3.get("go_id"), "Run Verifier request GO scope")
    require_equal(request.scope.cell_id, d3.get("cell_id"), "Run Verifier request CELL scope")
    require_equal(
        request.request_digest,
        adapter.p.request_digest_for(request),
        "Run Verifier isolation request digest",
    )
    require_equal(request.artifact_sha256, next(
        digest for digest, value in loaded.artifacts_by_digest.items() if value is d3
    ), "Run Verifier request D3 digest")


@pytest.mark.parametrize(
    "run_isolation_result",
    ("MISSING_DIMENSION", "COLLISION", "UNVERIFIED", "MISSING_BINDING"),
)
def test_R18_Run_Verifier_isolation_fails_closed_on_invalid_adapter_attestation(
    tmp_path,
    run_isolation_result,
):
    case = _build_two_go_run(tmp_path)
    d3_path, d3 = rv._artifact(case.root, "D3_RECEIPT")
    consumed_contexts = {
        value.get("execution_context_ref")
        for value in (
            yaml.safe_load(path.read_text(encoding="utf-8"))
            for path in rv._all_formal_paths(case.root)
        )
        if value.get("artifact_type") in {"D1_RECEIPT", "D2_RECEIPT"}
    }
    consumed_binding_refs = {
        value.get("issuer_binding_ref")
        for value in (
            yaml.safe_load(path.read_text(encoding="utf-8"))
            for path in rv._all_formal_paths(case.root)
        )
        if value.get("artifact_type") in {"D1_RECEIPT", "D2_RECEIPT"}
    }
    require(d3["execution_context_ref"] not in consumed_contexts, "fixture free-string contexts must differ")
    require(d3["issuer_binding_ref"] not in consumed_binding_refs, "fixture free-string bindings must differ")
    _, report, _, adapter = _validate_with_adapter(
        case,
        run_isolation_result=run_isolation_result,
    )
    _require_layers_one_to_eight_pass(report)
    require_equal(
        _codes(report, 9),
        {"R18_RUN_VERIFIER_ISOLATION_INVALID"},
        f"{run_isolation_result} isolation failure",
    )
    require(
        any(operation == "verify_isolation" and len(request.required_dimensions) == 6 for operation, request in adapter.calls),
        "layer 9 did not call the provenance adapter",
    )


def test_R18_identical_free_string_context_is_rejected_before_adapter(tmp_path):
    case = _build_two_go_run(tmp_path)
    d3_path, d3 = rv._artifact(case.root, "D3_RECEIPT")
    _, d2 = _artifact_by_id(case.root, "D2-GO-001-V1")
    d3["execution_context_ref"] = d2["execution_context_ref"]
    write_json(d3_path, d3)
    _sync_d3_downstream(case)
    _, report, _, adapter = _validate_with_adapter(case)
    _require_layers_one_to_eight_pass(report)
    require_equal(
        _codes(report, 9),
        {"R18_RUN_VERIFIER_ISOLATION_INVALID"},
        "identical free-string context",
    )
    require_equal(
        tuple(
            request
            for operation, request in adapter.calls
            if operation == "verify_isolation" and len(request.required_dimensions) == 6
        ),
        (),
        "adapter must not be called after a free-string collision",
    )


def test_D3_exact_required_GO_and_D2_sets_are_order_independent(tmp_path):
    case = _build_two_go_run(tmp_path)
    d3_path, d3 = rv._artifact(case.root, "D3_RECEIPT")
    d3["required_go_ids"] = list(reversed(d3["required_go_ids"]))
    d3["admitted_d2_artifact_sha256s"] = list(reversed(d3["admitted_d2_artifact_sha256s"]))
    write_json(d3_path, d3)
    _sync_d3_downstream(case)
    _, report, _ = _validate(case)
    _require_layers_one_to_eight_pass(report)
    require_equal(_codes(report, 9), set(), "order-independent D3 sets")


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("MISSING_GO", "R17_D3_REQUIRED_GO_SET_MISMATCH"),
        ("EXTRA_GO", "R17_D3_REQUIRED_GO_SET_MISMATCH"),
        ("MISSING_D2", "R17_D3_D2_SET_MISMATCH"),
        ("FORGED_GRAPH", "R17_D3_GRAPH_DIGEST_MISMATCH"),
        ("STALE_GRAPH_VERSION", "R17_D3_GRAPH_DIGEST_MISMATCH"),
        ("MISSING_SEAM", "R17_D3_GRAPH_SEAM_EVIDENCE_MISSING"),
        ("STALE_D2", "R17_D3_D2_SET_MISMATCH"),
        ("STALE_RUN_VERIFIER", "R18_RUN_VERIFIER_BINDING_INVALID"),
        ("RUN_VERIFIER_COLLISION", "R18_RUN_VERIFIER_ISOLATION_INVALID"),
    ],
)
def test_R17_R18_D3_closure_fails_closed_after_layers_eight(tmp_path, mutation, expected_code):
    case = _build_two_go_run(tmp_path)
    d3_path, d3 = rv._artifact(case.root, "D3_RECEIPT")
    if mutation == "MISSING_GO":
        d3["required_go_ids"] = ["GO-001"]
    elif mutation == "EXTRA_GO":
        d3["required_go_ids"].append("GO-EXTRA")
    elif mutation == "MISSING_D2":
        d3["admitted_d2_artifact_sha256s"] = d3["admitted_d2_artifact_sha256s"][:1]
    elif mutation == "FORGED_GRAPH":
        d3["graph_sha256"] = "9" * 64
    elif mutation == "STALE_GRAPH_VERSION":
        d3["graph_version"] = 2
    elif mutation == "MISSING_SEAM":
        d3["graph_seam_evidence_refs"] = ["evidence/RUN-001/d3-v1.json"]
    elif mutation == "STALE_RUN_VERIFIER":
        d3["issuer_binding_ref"] = "ROLE-RUN-VERIFIER-RUN-001-STALE"
    elif mutation == "RUN_VERIFIER_COLLISION":
        _, d2 = _artifact_by_id(case.root, "D2-GO-001-V1")
        d3["execution_context_ref"] = d2["execution_context_ref"]
    elif mutation == "STALE_D2":
        old_d2_path, old_d2 = _artifact_by_id(case.root, "D2-GO-001-V1")
        current = copy.deepcopy(old_d2)
        current["artifact_id"] = "D2-GO-001-V2"
        current["issued_at"] = "2026-08-03T04:30:00Z"
        current["provenance_ref"] = "attestations/D2-GO-001-V2.json"
        current["evidence_refs"] = [rv._add_evidence(case.root, "evidence/GO-001/d2-v2.json", current["artifact_id"])]
        current_path = case.root / "receipts" / "D2-GO-001-V2.json"
        write_json(current_path, current)
        rv._ensure_supervisor_admission(case.root, current_path, suffix="D2-GO-001-V2", issued_at="2026-08-03T04:31:00Z")
        event_one_path, event_one = _artifact_by_id(case.root, "GRAPH-EVENT-RUN-001-V1")
        event_one["trigger_artifact_ref"] = current_path.relative_to(case.root).as_posix()
        event_one["trigger_artifact_sha256"] = sha256_file(current_path)
        write_json(event_one_path, event_one)
        event_two_path, event_two = _artifact_by_id(case.root, "GRAPH-EVENT-RUN-001-V2")
        event_two["prior_event_sha256"] = sha256_file(event_one_path)
        write_json(event_two_path, event_two)
        require(d3["admitted_d2_artifact_sha256s"][0] == sha256_file(old_d2_path), "D3 no longer targets stale D2")
    write_json(d3_path, d3)
    _sync_d3_downstream(case)
    _, report, _ = _validate(case)
    _require_layers_one_to_eight_pass(report)
    require(expected_code in _codes(report, 9), f"{mutation} D3 closure was accepted")


def test_R18_supervisor_cannot_issue_D3_even_before_closure_layer(tmp_path):
    case = _build_two_go_run(tmp_path)
    d3_path, d3 = rv._artifact(case.root, "D3_RECEIPT")
    d3["issuer_binding_ref"] = "ROLE-RUN-001-SUPERVISOR"
    write_json(d3_path, d3)
    _sync_d3_downstream(case)
    _, report, _ = _validate(case)
    require("R03_SUPERVISOR_D2_D3_AUTHORITY" in _codes(report, 4), "Supervisor issued D3")


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("NO_D3_ADMISSION", "R18_D3_ADMISSION_REQUIRED"),
        ("REJECTED_D3_ADMISSION", "R18_D3_ADMISSION_REQUIRED"),
        ("WRONG_D3_ADMISSION", "R18_D3_ADMISSION_REQUIRED"),
        ("D3_FAIL", "R18_D3_NOT_PASS"),
        ("D3_BLOCKED", "R18_D3_NOT_PASS"),
        ("STALE_D3", "R18_OWNER_D3_REFERENCE_INVALID"),
        ("WRONG_PACKAGE_BOUNDARY", "R18_OWNER_PACKAGE_BOUNDARY_INVALID"),
    ],
)
def test_R18_owner_requires_current_admitted_D3_PASS_and_bounded_index(tmp_path, mutation, expected_code):
    case = _build_two_go_run(tmp_path)
    d3_path, d3 = rv._artifact(case.root, "D3_RECEIPT")
    if mutation == "NO_D3_ADMISSION":
        admission = rv._admission_for_target(case.root, d3_path)
        if admission is None:
            pytest.fail("fixture D3 admission is missing")
        admission[0].unlink()
        _write_current_head(case)
    elif mutation in {"REJECTED_D3_ADMISSION", "WRONG_D3_ADMISSION"}:
        admission_path, admission = rv._admission_for_target(case.root, d3_path)
        if mutation == "REJECTED_D3_ADMISSION":
            admission["decision"] = "REJECTED"
            admission["failure_codes"] = ["D3_NOT_ADMITTED"]
        else:
            d2_path, _ = _artifact_by_id(case.root, "D2-GO-001-V1")
            admission["admitted_artifact_sha256"] = sha256_file(d2_path)
        write_json(admission_path, admission)
        _write_current_head(case)
    elif mutation in {"D3_FAIL", "D3_BLOCKED"}:
        d3["verdict"] = mutation
        write_json(d3_path, d3)
        _sync_d3_downstream(case)
    elif mutation == "STALE_D3":
        current = copy.deepcopy(d3)
        current["artifact_id"] = "D3-RUN-001-V2"
        current["issued_at"] = "2026-08-03T05:01:00Z"
        current["provenance_ref"] = "attestations/D3-RUN-001-V2.json"
        current["evidence_refs"] = [rv._add_evidence(case.root, "evidence/RUN-001/d3-v2.json", current["artifact_id"])]
        current_path = case.root / "receipts" / "D3-RUN-001-V2.json"
        write_json(current_path, current)
        rv._ensure_supervisor_admission(case.root, current_path, suffix="D3-RUN-001-V2", issued_at="2026-08-03T05:02:00Z")
        _write_current_head(case)
    else:
        owner_path, owner = rv._artifact(case.root, "OWNER_ACCEPTANCE")
        owner["package_index_sha256"] = "0" * 64
        write_json(owner_path, owner)
        security_path, security = rv._artifact(case.root, "SECURITY_HANDOFF")
        security["owner_acceptance_sha256"] = sha256_file(owner_path)
        write_json(security_path, security)
        _write_current_head(case)
    _, report, _ = _validate(case)
    _require_layers_one_to_eight_pass(report)
    require(expected_code in _codes(report, 10), f"{mutation} Owner closure was accepted")


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("OWNER_MISSING", "R19_SECURITY_HANDOFF_PREMATURE"),
        ("AUDIT_SELF_ACCEPTED", "R19_SECURITY_STATUS_FORBIDDEN"),
    ],
)
def test_R19_security_handoff_requires_owner_and_cannot_accept_LCCoding_audit(tmp_path, mutation, expected_code):
    case = _build_two_go_run(tmp_path)
    if mutation == "OWNER_MISSING":
        owner_path, _ = rv._artifact(case.root, "OWNER_ACCEPTANCE")
        owner_path.unlink()
    else:
        security_path, security = rv._artifact(case.root, "SECURITY_HANDOFF")
        security["status"] = "ACCEPTED_BY_LCCODING"
        write_json(security_path, security)
    _write_current_head(case)
    _, report, _ = _validate(case)
    _require_layers_one_to_eight_pass(report)
    require(expected_code in _codes(report, 10), f"{mutation} security handoff was accepted")


def test_D3_eligibility_is_immutable_derived_fact_not_a_formal_issuer(tmp_path):
    case = _build_two_go_run(tmp_path, with_owner=False, with_security=False)
    _, report, _ = _validate(case)
    _require_layers_one_to_eight_pass(report)
    require(hasattr(report, "d3_eligibility"), "D3 eligibility projection is missing")
    eligibility = report.d3_eligibility
    require(eligibility is not None and eligibility.eligible, "D3 eligibility was not derived")
    require(not hasattr(eligibility, "artifact_type"), "derived eligibility became a formal artifact")
    require(not hasattr(eligibility, "verdict"), "derived eligibility issued a D3 verdict")
    with pytest.raises(dataclasses.FrozenInstanceError):
        eligibility.eligible = False
