import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import test_admission_graph_300 as ag
import test_cell_closure_300 as cc
import test_run_closure_300 as rc
import test_run_validation_300 as rv
from glk300_fixtures import sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]
VALIDATE_RUN = ROOT / "glk" / "scripts" / "validate_run.py"


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def _record(root, artifact_type, *, go_id=None, cell_id=None):
    matches = []
    for path in rv._all_formal_paths(root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("artifact_type") != artifact_type:
            continue
        if go_id is not None and value.get("go_id") != go_id:
            continue
        if cell_id is not None and value.get("cell_id") != cell_id:
            continue
        matches.append((path, value))
    if len(matches) != 1:
        pytest.fail(f"expected one {artifact_type}/{go_id}/{cell_id}, got {len(matches)}")
    return matches[0]


def _expand_go_one_to_three_cells(case):
    root = case.root
    manifest_path, manifest = _record(root, "CELL_MANIFEST", go_id="GO-001")
    first = manifest["required_cells"][0]
    manifest["required_cells"] = [
        first,
        {
            "cell_id": "GO-001-CELL-002",
            "cell_contract_sha256": cc._contract_sha("GO-001-CELL-002"),
            "required": True,
        },
        {
            "cell_id": "GO-001-CELL-003",
            "cell_contract_sha256": cc._contract_sha("GO-001-CELL-003"),
            "required": True,
        },
    ]
    manifest["closure_sha256"] = cc._manifest_closure_sha256(manifest)
    write_json(manifest_path, manifest)

    d0_path, d0 = _record(root, "D0_RECEIPT", go_id="GO-001")
    d0["manifest_closure_sha256"] = manifest["closure_sha256"]
    d0["cell_contract_sha256"] = first["cell_contract_sha256"]
    write_json(d0_path, d0)
    d1_path, d1 = _record(root, "D1_RECEIPT", go_id="GO-001")
    d1["manifest_closure_sha256"] = manifest["closure_sha256"]
    d1["cell_contract_sha256"] = first["cell_contract_sha256"]
    d1["d0_artifact_sha256"] = sha256_file(d0_path)
    write_json(d1_path, d1)
    rv._sync_supervisor_admission(root, d0_path)
    rv._sync_supervisor_admission(root, d1_path)
    cc._add_cell_receipts(case.fixture, manifest, 2)
    cc._add_cell_receipts(case.fixture, manifest, 3)

    cell_ids = {"GO-001-CELL-001", "GO-001-CELL-002", "GO-001-CELL-003"}
    selected = cc._latest_selected_cells(case.fixture, cell_ids=cell_ids)
    closure_path, closure = _record(root, "GO_CANDIDATE_CLOSURE", go_id="GO-001")
    closure["manifest_closure_sha256"] = manifest["closure_sha256"]
    closure["selected_cells"] = selected
    closure["candidate_sha256"] = cc._go_candidate_sha256(manifest, selected)
    write_json(closure_path, closure)
    rv._sync_supervisor_admission(root, closure_path)

    d2_path, d2 = _record(root, "D2_RECEIPT", go_id="GO-001")
    d2.update(
        {
            "candidate_id": closure["candidate_id"],
            "candidate_sha256": closure["candidate_sha256"],
            "go_candidate_closure_sha256": sha256_file(closure_path),
            "manifest_closure_sha256": manifest["closure_sha256"],
            "required_cell_tuples": selected,
        }
    )
    write_json(d2_path, d2)
    rv._sync_supervisor_admission(root, d2_path)


def _make_graph_independent(case):
    root = case.root
    d2_one_path, d2_one = _record(root, "D2_RECEIPT", go_id="GO-001")
    d2_two_path, d2_two = _record(root, "D2_RECEIPT", go_id="GO-002")
    nodes = [
        ag._node(
            "GO-001",
            go_claim_sha256=d2_one["go_claim_sha256"],
            acceptance_contract_sha256=d2_one["acceptance_contract_sha256"],
        ),
        ag._node(
            "GO-002",
            go_claim_sha256=d2_two["go_claim_sha256"],
            acceptance_contract_sha256=d2_two["acceptance_contract_sha256"],
        ),
    ]
    _, baseline = ag._set_topology(
        case.fixture,
        nodes,
        [],
        ("GO-001", "GO-002"),
        ("GO-001", "GO-002"),
    )
    event_one_path, event_one = rc._artifact_by_id(root, "GRAPH-EVENT-RUN-001-V1")
    event_one.update(
        {
            "candidate_id": baseline["candidate_id"],
            "candidate_sha256": baseline["graph_hash"],
            "trigger_artifact_ref": d2_one_path.relative_to(root).as_posix(),
            "trigger_artifact_sha256": sha256_file(d2_one_path),
            "prior_event_sha256": None,
            "waiting_go_ids": [],
            "active_go_ids": ["GO-002"],
        }
    )
    write_json(event_one_path, event_one)
    event_two_path, event_two = rc._artifact_by_id(root, "GRAPH-EVENT-RUN-001-V2")
    event_two.update(
        {
            "candidate_id": baseline["candidate_id"],
            "candidate_sha256": baseline["graph_hash"],
            "trigger_artifact_ref": d2_two_path.relative_to(root).as_posix(),
            "trigger_artifact_sha256": sha256_file(d2_two_path),
            "prior_event_sha256": sha256_file(event_one_path),
            "waiting_go_ids": [],
            "active_go_ids": [],
        }
    )
    write_json(event_two_path, event_two)

    d3_path, d3 = _record(root, "D3_RECEIPT")
    seam_ref = rv._add_evidence(root, "evidence/graph/seams-empty.json", "GRAPH-SEAMS-EMPTY")
    d3.update(
        {
            "required_go_ids": ["GO-001", "GO-002"],
            "admitted_d2_artifact_sha256s": [sha256_file(d2_one_path), sha256_file(d2_two_path)],
            "graph_sha256": baseline["graph_hash"],
            "graph_seam_claims": ["GRAPH-SEAMS-EMPTY"],
            "graph_seam_evidence_refs": [seam_ref],
        }
    )
    write_json(d3_path, d3)
    rv._sync_supervisor_admission(root, d3_path)


def rebuild_conformance_indexes(case):
    root = case.root
    owner_path = next((path for path in rv._all_formal_paths(root) if yaml.safe_load(path.read_text(encoding="utf-8")).get("artifact_type") == "OWNER_ACCEPTANCE"), None)
    security_path = next((path for path in rv._all_formal_paths(root) if yaml.safe_load(path.read_text(encoding="utf-8")).get("artifact_type") == "SECURITY_HANDOFF"), None)
    owner = yaml.safe_load(owner_path.read_text(encoding="utf-8")) if owner_path else copy.deepcopy(rv._template("OWNER_ACCEPTANCE"))
    security = yaml.safe_load(security_path.read_text(encoding="utf-8")) if security_path else copy.deepcopy(rv._template("SECURITY_HANDOFF"))
    if owner_path:
        owner_path.unlink()
    if security_path:
        security_path.unlink()
    if case.head_path.exists():
        case.head_path.unlink()

    for artifact_type in ("D0_RECEIPT", "D1_RECEIPT", "GO_CANDIDATE_CLOSURE", "D2_RECEIPT", "D3_RECEIPT"):
        for target_path, _ in cc._paths_by_type(root, artifact_type):
            rv._sync_supervisor_admission(root, target_path)
    rv._materialize_referenced_evidence(root)
    rv._reindex(case.fixture)
    bounded_index_sha256 = sha256_file(case.fixture.index_path)
    d3_path, d3 = _record(root, "D3_RECEIPT")
    owner.update(
        {
            "candidate_id": d3["candidate_id"],
            "candidate_sha256": d3["candidate_sha256"],
            "admitted_d3_artifact_sha256": sha256_file(d3_path),
            "package_index_sha256": bounded_index_sha256,
            "issued_at": "2026-08-03T05:00:00Z",
        }
    )
    owner["evidence_refs"] = [rv._add_evidence(root, "evidence/RUN-001/owner-acceptance-v1.json", owner["artifact_id"])]
    owner_path = root / "acceptance" / "OWNER-ACCEPTANCE-RUN-001-V1.json"
    write_json(owner_path, owner)
    security.update(
        {
            "candidate_id": d3["candidate_id"],
            "candidate_sha256": d3["candidate_sha256"],
            "owner_acceptance_sha256": sha256_file(owner_path),
            "issued_at": "2026-08-03T05:05:00Z",
        }
    )
    security["evidence_refs"] = [rv._add_evidence(root, "evidence/RUN-001/security-handoff-v1.json", security["artifact_id"])]
    write_json(root / "handoffs" / "SECURITY-HANDOFF-RUN-001-V1.json", security)
    rebuilt = rc.ClosureCase(
        fixture=case.fixture,
        head_path=case.head_path,
        bounded_index_sha256=bounded_index_sha256,
    )
    rc._write_current_head(rebuilt)
    return rebuilt


def build_conformance_case(tmp_path):
    case = rc._build_two_go_run(tmp_path, with_owner=False, with_security=False)
    _expand_go_one_to_three_cells(case)
    _make_graph_independent(case)
    return rebuild_conformance_indexes(case)


def write_adapter_fixture(case, path, *, trusted=True, role_overrides=None):
    package_module, _, _ = rv.load_prerequisites()
    loaded = package_module.load_run_package(case.root)
    roles = dict(rv.ROLE_BINDINGS)
    expected_role_by_type = {
        artifact_type: role_type
        for role_type, artifact_types in rv.ISSUABLE_BY_ROLE.items()
        for artifact_type in artifact_types
    }
    expected_role_by_type["SECURITY_HANDOFF"] = "RUN_SUPERVISOR"
    for value in loaded.artifacts_by_digest.values():
        binding_ref = value.get("issuer_binding_ref")
        role_type = expected_role_by_type.get(value.get("artifact_type"))
        if binding_ref and role_type:
            roles.setdefault(binding_ref, role_type)
    roles.update(role_overrides or {})
    issuable = {role: list(types) for role, types in rv.ISSUABLE_BY_ROLE.items()}
    if "SECURITY_HANDOFF" not in issuable["RUN_SUPERVISOR"]:
        issuable["RUN_SUPERVISOR"].append("SECURITY_HANDOFF")
    issued = {binding_ref: [] for binding_ref in roles}
    for digest, value in loaded.artifacts_by_digest.items():
        binding_ref = value.get("issuer_binding_ref")
        if binding_ref in issued:
            issued[binding_ref].append(digest)
    snapshots = {
        binding_ref: {
            "conversation_ref": f"conversation/{ordinal}",
            "context_ref": f"context/{ordinal}",
            "workspace_ref": f"workspace/{ordinal}",
            "runtime_state_ref": f"runtime-state/{ordinal}",
            "evidence_root": f"evidence-root/{ordinal}",
            "decision_input_ref": f"decision-input/{ordinal}",
        }
        for ordinal, binding_ref in enumerate(sorted(roles), start=1)
    }
    value = {
        "fixture_kind": "GLK_PROVENANCE_CONFORMANCE_FIXTURE",
        "trusted_conformance_environment": trusted,
        "profile_id": "GLK-LOCAL-CONFORMANCE-300",
        "adapter_contract_version": "1.0",
        "verified_dimensions": [
            "conversation",
            "context",
            "workspace",
            "runtime_state",
            "evidence_root",
            "decision_input",
        ],
        "bindings": {
            binding_ref: {
                "role_type": role_type,
                "issuable_artifact_types": issuable[role_type],
                "issued_artifact_sha256s": sorted(issued.get(binding_ref, ())),
                **snapshots[binding_ref],
            }
            for binding_ref, role_type in sorted(roles.items())
        },
    }
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_cli(case, adapter_path):
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATE_RUN),
            str(case.root),
            "--adapter-fixture",
            str(adapter_path),
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_positive_two_GO_four_CELL_end_to_end_conformance(tmp_path):
    case = build_conformance_case(tmp_path)
    adapter_path = write_adapter_fixture(case, tmp_path / "trusted-adapter.json")
    completed = run_cli(case, adapter_path)
    require_equal(completed.returncode, 0, f"CLI stderr: {completed.stderr}")
    output = json.loads(completed.stdout)
    require_equal(output["status"], "PASS", "conformance status")
    require_equal([layer["status"] for layer in output["layers"]], ["PASS"] * 10, "ten layers")
    require_equal(output["formal_state"]["projection_kind"], "DERIVED_NON_AUTHORITATIVE", "report authority")
    require_equal(output["formal_state"]["security_status"], "PENDING_LCCODING_AUDIT", "security boundary")

    package_module, _, _ = rv.load_prerequisites()
    loaded = package_module.load_run_package(case.root)
    manifests = loaded.artifacts_by_type["CELL_MANIFEST"]
    require_equal(sum(len(manifest["required_cells"]) for manifest in manifests), 4, "required CELL count")
    require_equal(len(loaded.artifacts_by_type["D0_RECEIPT"]), 4, "D0 count")
    require_equal(len(loaded.artifacts_by_type["D1_RECEIPT"]), 4, "D1 count")
    admitted = {
        value["admitted_artifact_sha256"]
        for value in loaded.artifacts_by_type["SUPERVISOR_ADMISSION"]
        if value["decision"] == "ADMITTED"
    }
    for artifact_type in ("D0_RECEIPT", "D1_RECEIPT", "GO_CANDIDATE_CLOSURE", "D2_RECEIPT", "D3_RECEIPT"):
        for digest, value in loaded.artifacts_by_digest.items():
            if value.get("artifact_type") == artifact_type:
                require(digest in admitted, f"{artifact_type} lacks exact Supervisor admission")
    require_equal(len(loaded.artifacts_by_type["GRAPH_EVENT"]), 2, "graph event count")
    require_equal(len(loaded.artifacts_by_type["OWNER_ACCEPTANCE"]), 1, "Owner Acceptance count")

    state = rv.load_module(
        ROOT / "glk" / "scripts" / "graph_kernel.py",
        "glk_conformance_kernel",
        "graph/closure kernel missing",
    )
    baseline = loaded.artifacts_by_type["GRAPH_BASELINE"][0]
    topology = state.recompute_graph_topology(baseline)
    initial = state.project_graph_state(topology, (), ())
    require_equal(initial.active_go_ids, ("GO-001", "GO-002"), "maximal-safe initial ACTIVE set")
    require(not hasattr(initial, "ready_go_ids"), "READY was introduced")
