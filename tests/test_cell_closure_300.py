import copy
import dataclasses
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

import test_run_validation_300 as rv
from glk300_fixtures import sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"
RUN_STATE_PATH = SCRIPTS / "run_state.py"
GRAPH_MODEL_PATH = SCRIPTS / "graph_model.py"


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def _canonical_sha256(value):
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _manifest_payload(manifest):
    return {
        "run_id": manifest["run_id"],
        "graph_id": manifest["graph_id"],
        "graph_version": manifest["graph_version"],
        "go_id": manifest["go_id"],
        "manifest_id": manifest["manifest_id"],
        "manifest_version": manifest["manifest_version"],
        "go_contract_sha256": manifest["go_contract_sha256"],
        "required_cells": sorted(
            (
                {
                    "cell_id": cell["cell_id"],
                    "cell_contract_sha256": cell["cell_contract_sha256"],
                    "required": cell["required"],
                }
                for cell in manifest["required_cells"]
            ),
            key=lambda cell: cell["cell_id"],
        ),
        "prior_manifest_sha256": manifest["prior_manifest_sha256"],
    }


def _manifest_closure_sha256(manifest):
    return _canonical_sha256(_manifest_payload(manifest))


def _go_candidate_sha256(manifest, selected_cells):
    return _canonical_sha256(
        {
            "go_id": manifest["go_id"],
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "selected_cells": sorted(selected_cells, key=lambda item: item["cell_id"]),
        }
    )


def load_state():
    return rv.load_module(
        RUN_STATE_PATH,
        "glk_run_state_300_tests",
        "GLK 3.0 versioned CELL manifest/closure state engine is missing",
    )


def load_graph_model():
    return rv.load_module(GRAPH_MODEL_PATH, "glk_graph_model_task5", "graph model is missing")


def _paths_by_type(root, artifact_type):
    matches = []
    for path in rv._all_formal_paths(root):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("artifact_type") == artifact_type:
            matches.append((path, value))
    return matches


def _contract_sha(cell_id):
    return _canonical_sha256({"cell_id": cell_id, "contract": "frozen"})


def _candidate(cell_id, version=1):
    candidate_id = f"CANDIDATE-{cell_id}-V{version}"
    return candidate_id, rv._candidate_hash(candidate_id)


def _add_cell_receipts(fixture, manifest, cell_number, *, version=1, issued_hour=3):
    cell_id = f"GO-001-CELL-{cell_number:03d}"
    candidate_id, candidate_sha256 = _candidate(cell_id, version)
    suffix = f"V{version}"
    d0_id = f"D0-{cell_id}-{suffix}"
    d0_evidence = rv._add_evidence(fixture.root, f"evidence/{d0_id}.json", d0_id)
    d0 = copy.deepcopy(rv._template("D0_RECEIPT"))
    d0.update(
        {
            "artifact_id": d0_id,
            "candidate_id": candidate_id,
            "candidate_sha256": candidate_sha256,
            "issuer_binding_ref": "ROLE-WORKER-GO-001",
            "execution_context_ref": "CONTEXT-WORKER-GO-001",
            "evidence_refs": [d0_evidence],
            "provenance_ref": f"attestations/{d0_id}.json",
            "issued_at": f"2026-08-03T{issued_hour:02d}:{cell_number:02d}:00Z",
            "go_id": "GO-001",
            "cell_id": cell_id,
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "cell_contract_sha256": _contract_sha(cell_id),
            "dispatch_admission_refs": ["SUPERVISOR-ADMISSION-D2-V1"],
        }
    )
    d0_path = fixture.root / "receipts" / f"{d0_id}.json"
    write_json(d0_path, d0)

    d1_id = f"D1-{cell_id}-{suffix}"
    d1_evidence = rv._add_evidence(fixture.root, f"evidence/{d1_id}.json", d1_id)
    d1 = copy.deepcopy(rv._template("D1_RECEIPT"))
    d1.update(
        {
            "artifact_id": d1_id,
            "candidate_id": candidate_id,
            "candidate_sha256": candidate_sha256,
            "issuer_binding_ref": "ROLE-CHECKER-GO-001",
            "execution_context_ref": "CONTEXT-CHECKER-GO-001",
            "evidence_refs": [d1_evidence],
            "provenance_ref": f"attestations/{d1_id}.json",
            "issued_at": f"2026-08-03T{issued_hour:02d}:{cell_number + 10:02d}:00Z",
            "go_id": "GO-001",
            "cell_id": cell_id,
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "cell_contract_sha256": _contract_sha(cell_id),
            "d0_artifact_sha256": sha256_file(d0_path),
        }
    )
    d1_path = fixture.root / "receipts" / f"{d1_id}.json"
    write_json(d1_path, d1)
    rv._ensure_supervisor_admission(
        fixture.root,
        d0_path,
        suffix=d0_id,
        issued_at=f"2026-08-03T{issued_hour:02d}:{cell_number + 20:02d}:00Z",
    )
    rv._ensure_supervisor_admission(
        fixture.root,
        d1_path,
        suffix=d1_id,
        issued_at=f"2026-08-03T{issued_hour:02d}:{cell_number + 30:02d}:00Z",
    )
    return d0_path, d1_path


def _latest_selected_cells(fixture, cell_ids=None):
    d0_by_digest = {sha256_file(path): (path, value) for path, value in _paths_by_type(fixture.root, "D0_RECEIPT")}
    latest_d1 = {}
    for path, value in _paths_by_type(fixture.root, "D1_RECEIPT"):
        if cell_ids is not None and value["cell_id"] not in cell_ids:
            continue
        current = latest_d1.get(value["cell_id"])
        if current is None or (value["issued_at"], value["artifact_id"]) > (current[1]["issued_at"], current[1]["artifact_id"]):
            latest_d1[value["cell_id"]] = (path, value)
    selected = []
    for cell_id, (d1_path, d1) in sorted(latest_d1.items()):
        d0_path, d0 = d0_by_digest[d1["d0_artifact_sha256"]]
        selected.append(
            {
                "cell_id": cell_id,
                "candidate_id": d0["candidate_id"],
                "candidate_sha256": d0["candidate_sha256"],
                "d0_artifact_sha256": sha256_file(d0_path),
                "d1_artifact_sha256": sha256_file(d1_path),
            }
        )
    return selected


def _rewrite_downstream(fixture, selected_cells, *, closure_path=None, d2_closure_path=None, generation=1):
    manifest_path, manifest = rv._artifact(fixture.root, "CELL_MANIFEST")
    if closure_path is None:
        closure_path, closure = rv._artifact(fixture.root, "GO_CANDIDATE_CLOSURE")
    else:
        closure = yaml.safe_load(closure_path.read_text(encoding="utf-8"))
    candidate_sha256 = _go_candidate_sha256(manifest, selected_cells)
    closure.update(
        {
            "candidate_id": f"CANDIDATE-GO-001-G{generation}",
            "candidate_sha256": candidate_sha256,
            "manifest_id": manifest["manifest_id"],
            "manifest_version": manifest["manifest_version"],
            "manifest_closure_sha256": manifest["closure_sha256"],
            "selected_cells": selected_cells,
            "go_candidate_generation": generation,
        }
    )
    write_json(closure_path, closure)
    for artifact_type in ("D0_RECEIPT", "D1_RECEIPT"):
        for receipt_path, _ in _paths_by_type(fixture.root, artifact_type):
            rv._sync_supervisor_admission(fixture.root, receipt_path)
    rv._sync_supervisor_admission(fixture.root, closure_path)
    chosen_closure_path = d2_closure_path or closure_path
    chosen_closure = yaml.safe_load(chosen_closure_path.read_text(encoding="utf-8"))
    d2_path, d2 = rv._artifact(fixture.root, "D2_RECEIPT")
    d2.update(
        {
            "candidate_id": chosen_closure["candidate_id"],
            "candidate_sha256": chosen_closure["candidate_sha256"],
            "go_candidate_closure_sha256": sha256_file(chosen_closure_path),
            "manifest_id": chosen_closure["manifest_id"],
            "manifest_version": chosen_closure["manifest_version"],
            "manifest_closure_sha256": chosen_closure["manifest_closure_sha256"],
            "required_cell_tuples": chosen_closure["selected_cells"],
        }
    )
    write_json(d2_path, d2)
    d2_digest = sha256_file(d2_path)
    rv._sync_supervisor_admission(fixture.root, d2_path)
    event_path, event = rv._artifact(fixture.root, "GRAPH_EVENT")
    event["trigger_artifact_sha256"] = d2_digest
    write_json(event_path, event)
    d3_path, d3 = rv._artifact(fixture.root, "D3_RECEIPT")
    d3["admitted_d2_artifact_sha256s"] = [d2_digest]
    write_json(d3_path, d3)
    owner_path, owner = rv._artifact(fixture.root, "OWNER_ACCEPTANCE")
    owner["admitted_d3_artifact_sha256"] = sha256_file(d3_path)
    write_json(owner_path, owner)
    rv._materialize_referenced_evidence(fixture.root)
    rv._reindex(fixture)


def _build_six_cell_package(tmp_path):
    fixture = rv._prepare_validation_fixture(tmp_path)
    manifest_path, manifest = rv._artifact(fixture.root, "CELL_MANIFEST")
    manifest["required_cells"] = [
        {
            "cell_id": f"GO-001-CELL-{number:03d}",
            "cell_contract_sha256": _contract_sha(f"GO-001-CELL-{number:03d}"),
            "required": True,
        }
        for number in range(1, 7)
    ]
    manifest["closure_sha256"] = _manifest_closure_sha256(manifest)
    write_json(manifest_path, manifest)

    d0_path, d0 = rv._artifact(fixture.root, "D0_RECEIPT")
    d0["manifest_closure_sha256"] = manifest["closure_sha256"]
    d0["cell_contract_sha256"] = manifest["required_cells"][0]["cell_contract_sha256"]
    write_json(d0_path, d0)
    d1_path, d1 = rv._artifact(fixture.root, "D1_RECEIPT")
    d1["manifest_closure_sha256"] = manifest["closure_sha256"]
    d1["cell_contract_sha256"] = manifest["required_cells"][0]["cell_contract_sha256"]
    d1["d0_artifact_sha256"] = sha256_file(d0_path)
    write_json(d1_path, d1)
    for number in range(2, 7):
        _add_cell_receipts(fixture, manifest, number)
    _rewrite_downstream(fixture, _latest_selected_cells(fixture))
    return fixture


def _validate_package(fixture):
    package_module, provenance, run_model = rv.load_prerequisites()
    loaded = package_module.load_run_package(fixture.root)
    validation = rv.load_validation()
    report = validation.validate_loaded_run(loaded, rv.TrustedAdapterFixture(provenance, run_model))
    for layer in report.layers:
        if layer.layer <= 5:
            require_equal(layer.status, "PASS", f"pre-Task5 validation layer {layer.layer}")
    return loaded, report


def _layer6_codes(report):
    return {issue.code for issue in report.issues if issue.layer == 6}


def _remove_admission_for_target(fixture, target_path):
    admission = rv._admission_for_target(fixture.root, target_path)
    if admission is None:
        pytest.fail(f"fixture admission is missing for {target_path.name}")
    admission[0].unlink()
    rv._reindex(fixture)


def _assert_exact_admissions(fixture):
    targets = []
    for artifact_type in ("D0_RECEIPT", "D1_RECEIPT", "GO_CANDIDATE_CLOSURE"):
        targets.extend(path for path, _ in _paths_by_type(fixture.root, artifact_type))
    for target_path in targets:
        admission = rv._admission_for_target(fixture.root, target_path)
        require(admission is not None, f"missing exact admission for {target_path.name}")
        _, value = admission
        require_equal(value["decision"], "ADMITTED", f"{target_path.name} admission decision")
        require_equal(value["admitted_artifact_sha256"], sha256_file(target_path), f"{target_path.name} admission digest")


@pytest.mark.parametrize("cell_count", [1, 6])
def test_single_and_six_cell_baselines_have_exact_d0_d1_and_closure_admissions(tmp_path, cell_count):
    fixture = rv._prepare_validation_fixture(tmp_path) if cell_count == 1 else _build_six_cell_package(tmp_path)
    _assert_exact_admissions(fixture)
    _, report = _validate_package(fixture)
    require_equal(_layer6_codes(report), set(), f"{cell_count}-CELL admission baseline")


@pytest.mark.parametrize("cell_count", [1, 6])
def test_layer6_requires_exact_current_d1_admission(tmp_path, cell_count):
    fixture = rv._prepare_validation_fixture(tmp_path) if cell_count == 1 else _build_six_cell_package(tmp_path)
    d1_path = _paths_by_type(fixture.root, "D1_RECEIPT")[-1][0]
    _remove_admission_for_target(fixture, d1_path)
    _, report = _validate_package(fixture)
    require("R13_D1_ADMISSION_REQUIRED" in _layer6_codes(report), "missing D1 admission authorized D2")


def test_layer6_rejected_or_wrong_target_d1_admission_is_not_current(tmp_path):
    for mutation in ("REJECTED", "WRONG_TARGET"):
        fixture = _build_six_cell_package(tmp_path / mutation.lower())
        d1_path, _ = _paths_by_type(fixture.root, "D1_RECEIPT")[-1]
        admission_path, admission = rv._admission_for_target(fixture.root, d1_path)
        if mutation == "REJECTED":
            admission["decision"] = "REJECTED"
            admission["failure_codes"] = ["D1_NOT_ADMITTED"]
        else:
            d0_path, _ = _paths_by_type(fixture.root, "D0_RECEIPT")[0]
            admission["admitted_artifact_sha256"] = sha256_file(d0_path)
        write_json(admission_path, admission)
        rv._reindex(fixture)
        _, report = _validate_package(fixture)
        require("R13_D1_ADMISSION_REQUIRED" in _layer6_codes(report), f"{mutation} D1 admission authorized D2")


def test_layer6_requires_exact_current_d0_admission(tmp_path):
    fixture = _build_six_cell_package(tmp_path)
    d0_path = _paths_by_type(fixture.root, "D0_RECEIPT")[-1][0]
    _remove_admission_for_target(fixture, d0_path)
    _, report = _validate_package(fixture)
    require("R13_D0_ADMISSION_REQUIRED" in _layer6_codes(report), "missing D0 admission authorized D2")


@pytest.mark.parametrize("cell_count", [1, 6])
def test_layer6_requires_exact_current_closure_admission(tmp_path, cell_count):
    fixture = rv._prepare_validation_fixture(tmp_path) if cell_count == 1 else _build_six_cell_package(tmp_path)
    closure_path = _paths_by_type(fixture.root, "GO_CANDIDATE_CLOSURE")[-1][0]
    _remove_admission_for_target(fixture, closure_path)
    _, report = _validate_package(fixture)
    require("R13_CLOSURE_ADMISSION_REQUIRED" in _layer6_codes(report), "missing closure admission authorized D2")


def test_layer6_rejects_same_manifest_identity_version_with_different_digest(tmp_path):
    fixture = _build_six_cell_package(tmp_path)
    _, original = rv._artifact(fixture.root, "CELL_MANIFEST")
    fork = copy.deepcopy(original)
    fork["artifact_id"] = "CELL-MANIFEST-GO-001-FORK-V1"
    fork["candidate_id"] = "CELL-MANIFEST-GO-001-FORK-V1"
    fork["candidate_sha256"] = rv._candidate_hash(fork["candidate_id"])
    fork["go_contract_sha256"] = "9" * 64
    fork["closure_sha256"] = _manifest_closure_sha256(fork)
    fork["issued_at"] = "2026-08-03T02:00:00Z"
    fork["provenance_ref"] = "attestations/CELL-MANIFEST-GO-001-FORK-V1.json"
    evidence_ref = rv._add_evidence(fixture.root, "evidence/GO-001/cell-manifest-fork-v1.json", fork["artifact_id"])
    fork["evidence_refs"] = [evidence_ref]
    write_json(fixture.root / "manifests" / "CELL-MANIFEST-GO-001-FORK-V1.json", fork)
    rv._reindex(fixture)
    _, report = _validate_package(fixture)
    require("CELL_MANIFEST_FORK" in _layer6_codes(report), "manifest fork was silently selected")


def test_single_cell_current_manifest_closure_and_d2_pass_layer6(tmp_path):
    fixture = rv._prepare_validation_fixture(tmp_path)
    _, report = _validate_package(fixture)
    load_state()
    require_equal(_layer6_codes(report), set(), "single-CELL layer 6 issues")


def test_single_cell_forged_manifest_closure_hash_fails_layer6(tmp_path):
    fixture = rv._prepare_validation_fixture(tmp_path)
    manifest_path, manifest = rv._artifact(fixture.root, "CELL_MANIFEST")
    manifest["closure_sha256"] = "f" * 64
    write_json(manifest_path, manifest)
    for artifact_type in ("D0_RECEIPT", "D1_RECEIPT"):
        path, value = rv._artifact(fixture.root, artifact_type)
        value["manifest_closure_sha256"] = manifest["closure_sha256"]
        write_json(path, value)
    rv._refresh_lineage(fixture)
    _, report = _validate_package(fixture)
    load_state()
    require("R16_MANIFEST_CLOSURE_HASH_INVALID" in _layer6_codes(report), "single-CELL forged closure bypassed layer 6")


def test_R13_one_of_six_d1_cannot_form_closure_or_authorize_d2(tmp_path):
    fixture = _build_six_cell_package(tmp_path)
    for path, value in _paths_by_type(fixture.root, "D1_RECEIPT"):
        if value["cell_id"] != "GO-001-CELL-001":
            admission = rv._admission_for_target(fixture.root, path)
            if admission is None:
                pytest.fail(f"fixture D1 admission missing: {value['cell_id']}")
            admission[0].unlink()
            path.unlink()
    selected = _latest_selected_cells(fixture, {"GO-001-CELL-001"})
    _rewrite_downstream(fixture, selected)
    _, report = _validate_package(fixture)
    load_state()
    require("R13_PREMATURE_D2_INCOMPLETE_D1_SET" in _layer6_codes(report), "one D1 authorized D2")


def test_R14_duplicate_cell_tuple_cannot_substitute_for_sixth_cell(tmp_path):
    fixture = _build_six_cell_package(tmp_path)
    selected = _latest_selected_cells(fixture)
    selected[-1] = copy.deepcopy(selected[-2])
    _rewrite_downstream(fixture, selected)
    _, report = _validate_package(fixture)
    load_state()
    require("R14_CELL_TUPLE_SET_MISMATCH" in _layer6_codes(report), "duplicate CELL tuple was accepted")


@pytest.mark.parametrize("change_kind", ["ADD", "REMOVE"])
def test_R15_manifest_membership_change_requires_frozen_amendment(tmp_path, change_kind):
    fixture = _build_six_cell_package(tmp_path)
    manifest_path, manifest = rv._artifact(fixture.root, "CELL_MANIFEST")
    manifest["manifest_version"] = 2
    manifest["prior_manifest_sha256"] = "1" * 64
    if change_kind == "ADD":
        cell_id = "GO-001-CELL-007"
        manifest["required_cells"].append(
            {"cell_id": cell_id, "cell_contract_sha256": _contract_sha(cell_id), "required": True}
        )
    else:
        manifest["required_cells"] = manifest["required_cells"][:-1]
        for artifact_type in ("D0_RECEIPT", "D1_RECEIPT"):
            for path, value in _paths_by_type(fixture.root, artifact_type):
                if value["cell_id"] == "GO-001-CELL-006":
                    admission = rv._admission_for_target(fixture.root, path)
                    if admission is not None:
                        admission[0].unlink()
                    path.unlink()
    manifest["closure_sha256"] = _manifest_closure_sha256(manifest)
    write_json(manifest_path, manifest)
    if change_kind == "ADD":
        _add_cell_receipts(fixture, manifest, 7)
    for artifact_type in ("D0_RECEIPT", "D1_RECEIPT"):
        for path, value in _paths_by_type(fixture.root, artifact_type):
            value["manifest_version"] = 2
            value["manifest_closure_sha256"] = manifest["closure_sha256"]
            write_json(path, value)
    for path, value in _paths_by_type(fixture.root, "D1_RECEIPT"):
        d0 = next(
            d0_path
            for d0_path, d0_value in _paths_by_type(fixture.root, "D0_RECEIPT")
            if d0_value["cell_id"] == value["cell_id"] and d0_value["candidate_id"] == value["candidate_id"]
        )
        value["d0_artifact_sha256"] = sha256_file(d0)
        write_json(path, value)
    _rewrite_downstream(fixture, _latest_selected_cells(fixture), generation=2)
    _, report = _validate_package(fixture)
    load_state()
    require("R15_UNAMENDED_MANIFEST_CHANGE" in _layer6_codes(report), f"unamended {change_kind} was accepted")


def test_R16_forged_manifest_closure_hash_is_recomputed(tmp_path):
    fixture = _build_six_cell_package(tmp_path)
    manifest_path, manifest = rv._artifact(fixture.root, "CELL_MANIFEST")
    manifest["closure_sha256"] = "f" * 64
    write_json(manifest_path, manifest)
    for artifact_type in ("D0_RECEIPT", "D1_RECEIPT"):
        for path, value in _paths_by_type(fixture.root, artifact_type):
            value["manifest_closure_sha256"] = manifest["closure_sha256"]
            write_json(path, value)
    for path, value in _paths_by_type(fixture.root, "D1_RECEIPT"):
        d0 = next(
            d0_path
            for d0_path, d0_value in _paths_by_type(fixture.root, "D0_RECEIPT")
            if d0_value["cell_id"] == value["cell_id"]
        )
        value["d0_artifact_sha256"] = sha256_file(d0)
        write_json(path, value)
    _rewrite_downstream(fixture, _latest_selected_cells(fixture))
    _, report = _validate_package(fixture)
    load_state()
    require("R16_MANIFEST_CLOSURE_HASH_INVALID" in _layer6_codes(report), "forged manifest closure hash was accepted")


def test_R16_forged_go_candidate_closure_hash_is_recomputed(tmp_path):
    fixture = _build_six_cell_package(tmp_path)
    closure_path, closure = rv._artifact(fixture.root, "GO_CANDIDATE_CLOSURE")
    closure["candidate_sha256"] = "f" * 64
    write_json(closure_path, closure)
    d2_path, d2 = rv._artifact(fixture.root, "D2_RECEIPT")
    d2["candidate_sha256"] = closure["candidate_sha256"]
    d2["go_candidate_closure_sha256"] = sha256_file(closure_path)
    write_json(d2_path, d2)
    d2_digest = sha256_file(d2_path)
    rv._sync_supervisor_admission(fixture.root, closure_path)
    rv._sync_supervisor_admission(fixture.root, d2_path)
    event_path, event = rv._artifact(fixture.root, "GRAPH_EVENT")
    event["trigger_artifact_sha256"] = d2_digest
    write_json(event_path, event)
    d3_path, d3 = rv._artifact(fixture.root, "D3_RECEIPT")
    d3["admitted_d2_artifact_sha256s"] = [d2_digest]
    write_json(d3_path, d3)
    owner_path, owner = rv._artifact(fixture.root, "OWNER_ACCEPTANCE")
    owner["admitted_d3_artifact_sha256"] = sha256_file(d3_path)
    write_json(owner_path, owner)
    rv._reindex(fixture)
    _, report = _validate_package(fixture)
    require("R16_GO_CLOSURE_HASH_INVALID" in _layer6_codes(report), "forged GO candidate closure hash was accepted")


def test_R16_d1_cannot_bind_a_later_go_closure(tmp_path):
    fixture = _build_six_cell_package(tmp_path)
    future_closure = "e" * 64
    for path, value in _paths_by_type(fixture.root, "D1_RECEIPT"):
        value["manifest_closure_sha256"] = future_closure
        write_json(path, value)
    _rewrite_downstream(fixture, _latest_selected_cells(fixture))
    _, report = _validate_package(fixture)
    load_state()
    require("R16_D1_FUTURE_CLOSURE_BINDING" in _layer6_codes(report), "D1 bound a later GO closure")


def test_R28_old_closure_cannot_authorize_d2_after_only_cell6_changes(tmp_path):
    fixture = _build_six_cell_package(tmp_path)
    old_closure_path, old_closure = rv._artifact(fixture.root, "GO_CANDIDATE_CLOSURE")
    old_closure_digest = sha256_file(old_closure_path)
    manifest = rv._artifact(fixture.root, "CELL_MANIFEST")[1]
    _add_cell_receipts(fixture, manifest, 6, version=2, issued_hour=4)
    selected = _latest_selected_cells(fixture)
    new_closure = copy.deepcopy(old_closure)
    new_closure["artifact_id"] = "GO-CANDIDATE-CLOSURE-GO-001-V2"
    new_closure["provenance_ref"] = "attestations/GO-CANDIDATE-CLOSURE-GO-001-V2.json"
    new_closure["issued_at"] = "2026-08-03T04:20:00Z"
    new_closure_path = fixture.root / "closures" / "GO-CANDIDATE-CLOSURE-GO-001-V2.json"
    write_json(new_closure_path, new_closure)
    _rewrite_downstream(
        fixture,
        selected,
        closure_path=new_closure_path,
        d2_closure_path=old_closure_path,
        generation=2,
    )
    require_equal(sha256_file(old_closure_path), old_closure_digest, "historical closure mutation")
    _, report = _validate_package(fixture)
    load_state()
    require("R28_SUPERSEDED_CLOSURE_FOR_D2" in _layer6_codes(report), "old closure authorized D2")


def _state_inputs(state, manifest, cell_id, *, version=1, observed_at="2026-08-03T05:00:00Z", expires_at="2026-08-03T06:00:00Z"):
    candidate_id, candidate_sha256 = _candidate(cell_id, version)
    contract = {"cell_id": cell_id, "cell_contract_sha256": _contract_sha(cell_id)}
    candidate = {"cell_id": cell_id, "candidate_id": candidate_id, "candidate_sha256": candidate_sha256}
    d0_digest = _canonical_sha256({"d0": cell_id, "version": version})
    d1_digest = _canonical_sha256({"d1": cell_id, "version": version})
    d0 = {
        "artifact_sha256": d0_digest,
        "cell_id": cell_id,
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "cell_contract_sha256": contract["cell_contract_sha256"],
        "manifest_id": manifest.manifest_id,
        "manifest_version": manifest.manifest_version,
        "manifest_closure_sha256": manifest.closure_sha256,
        "outcome": "D0_PASS",
        "evidence_refs": (f"evidence/{cell_id}/d0-v{version}.json",),
        "provenance_ref": f"attestations/{cell_id}/d0-v{version}.json",
        "execution_context_ref": f"context/worker/{cell_id}",
    }
    d1 = {
        "artifact_sha256": d1_digest,
        "cell_id": cell_id,
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "cell_contract_sha256": contract["cell_contract_sha256"],
        "manifest_id": manifest.manifest_id,
        "manifest_version": manifest.manifest_version,
        "manifest_closure_sha256": manifest.closure_sha256,
        "d0_artifact_sha256": d0_digest,
        "verdict": "D1_PASS",
        "evidence_refs": (f"evidence/{cell_id}/d1-v{version}.json",),
        "provenance_ref": f"attestations/{cell_id}/d1-v{version}.json",
        "execution_context_ref": f"context/checker/{cell_id}",
    }
    provenance = {
        "d0_artifact_sha256": d0_digest,
        "d1_artifact_sha256": d1_digest,
        "d0_evidence_refs": d0["evidence_refs"],
        "d1_evidence_refs": d1["evidence_refs"],
        "d0_provenance_ref": d0["provenance_ref"],
        "d1_provenance_ref": d1["provenance_ref"],
        "worker_context_ref": d0["execution_context_ref"],
        "checker_context_ref": d1["execution_context_ref"],
        "observed_at": observed_at,
        "expires_at": expires_at,
        "invalidated_refs": (),
    }
    return contract, candidate, d0, d1, provenance


def _reuse_proof(state, admission, *, impact_refs=(), **overrides):
    values = {
        "cell_id": admission.cell_id,
        "admitted_d1": admission,
        "current_manifest_id": admission.manifest_id,
        "current_manifest_version": admission.manifest_version,
        "current_manifest_closure_sha256": admission.manifest_closure_sha256,
        "current_cell_contract_sha256": admission.cell_contract_sha256,
        "current_candidate_id": admission.candidate_id,
        "current_candidate_sha256": admission.candidate_sha256,
        "current_d0_artifact_sha256": admission.d0_artifact_sha256,
        "current_d1_artifact_sha256": admission.d1_artifact_sha256,
        "current_d0_evidence_refs": admission.d0_evidence_refs,
        "current_d1_evidence_refs": admission.d1_evidence_refs,
        "current_d0_provenance_ref": admission.d0_provenance_ref,
        "current_d1_provenance_ref": admission.d1_provenance_ref,
        "observed_at": admission.observed_at,
        "impact_refs": tuple(impact_refs),
    }
    values.update(overrides)
    return state.D1ReuseProof(**values)


def test_R28_five_d1_are_reused_and_cell6_gets_new_d0_d1_and_closure():
    state = load_state()
    go_contract = {
        "run_id": "RUN-001",
        "graph_id": "GRAPH-RUN-001",
        "graph_version": 1,
        "go_id": "GO-001",
        "go_contract_sha256": "a" * 64,
    }
    required = tuple(
        {"cell_id": f"GO-001-CELL-{number:03d}", "cell_contract_sha256": _contract_sha(f"GO-001-CELL-{number:03d}"), "required": True}
        for number in range(1, 7)
    )
    manifest = state.freeze_cell_manifest(go_contract, required)
    admitted_v1 = {}
    for number in range(1, 7):
        cell_id = f"GO-001-CELL-{number:03d}"
        admitted_v1[cell_id] = state.admit_current_d1(manifest, *_state_inputs(state, manifest, cell_id))
    old_closure = state.derive_go_candidate_closure(manifest, admitted_v1)
    proofs = tuple(
        _reuse_proof(
            state,
            admitted_v1[f"GO-001-CELL-{number:03d}"],
            impact_refs=(state.ImpactRef(cell_id="GO-001-CELL-006", kind="CANDIDATE", ref="candidate-v2"),)
            if number == 6
            else (),
        )
        for number in range(1, 7)
    )
    reusable = state.classify_reusable_d1(manifest, manifest, proofs)
    require_equal(reusable, tuple(f"GO-001-CELL-{number:03d}" for number in range(1, 6)), "five reusable CELLs")
    admitted_v2 = dict(admitted_v1)
    admitted_v2["GO-001-CELL-006"] = state.admit_current_d1(
        manifest, *_state_inputs(state, manifest, "GO-001-CELL-006", version=2)
    )
    new_closure = state.derive_go_candidate_closure(manifest, admitted_v2)
    require_equal(
        tuple(item.d1_artifact_sha256 for item in new_closure.selected_cells[:5]),
        tuple(item.d1_artifact_sha256 for item in old_closure.selected_cells[:5]),
        "five historical D1 digests",
    )
    require(new_closure.selected_cells[5].d1_artifact_sha256 != old_closure.selected_cells[5].d1_artifact_sha256, "CELL-6 D1 was reused")
    require(new_closure.closure_sha256 != old_closure.closure_sha256, "selected tuple change kept old closure")


@pytest.mark.parametrize("kind", ["EXPIRY", "PROVENANCE", "IMPACT", "CANDIDATE", "EVIDENCE"])
def test_R28_reuse_classifier_rejects_each_current_validity_change(kind):
    state = load_state()
    go_contract = {
        "run_id": "RUN-001",
        "graph_id": "GRAPH-RUN-001",
        "graph_version": 1,
        "go_id": "GO-001",
        "go_contract_sha256": "a" * 64,
    }
    required = (
        {"cell_id": "GO-001-CELL-001", "cell_contract_sha256": _contract_sha("GO-001-CELL-001"), "required": True},
    )
    manifest = state.freeze_cell_manifest(go_contract, required)
    admission = state.admit_current_d1(
        manifest, *_state_inputs(state, manifest, "GO-001-CELL-001")
    )
    reusable = state.classify_reusable_d1(
        manifest,
        manifest,
        (
            _reuse_proof(
                state,
                admission,
                impact_refs=(state.ImpactRef(cell_id="GO-001-CELL-001", kind=kind, ref=f"changed-{kind.lower()}"),),
            ),
        ),
    )
    require_equal(reusable, (), f"{kind} invalidation")


def test_R28_contract_or_manifest_version_change_rejects_d1_reuse():
    state = load_state()
    go_contract = {
        "run_id": "RUN-001",
        "graph_id": "GRAPH-RUN-001",
        "graph_version": 1,
        "go_id": "GO-001",
        "go_contract_sha256": "a" * 64,
    }
    old_manifest = state.freeze_cell_manifest(
        go_contract,
        ({"cell_id": "GO-001-CELL-001", "cell_contract_sha256": _contract_sha("GO-001-CELL-001"), "required": True},),
    )
    amended_contract = dict(go_contract)
    amended_contract["amendment_ref"] = "CELL-MANIFEST-AMENDMENT-GO-001-V2"
    new_manifest = state.freeze_cell_manifest(
        amended_contract,
        ({"cell_id": "GO-001-CELL-001", "cell_contract_sha256": "c" * 64, "required": True},),
        prior_manifest=old_manifest,
    )
    admission = state.admit_current_d1(
        old_manifest,
        *_state_inputs(state, old_manifest, "GO-001-CELL-001"),
    )
    require_equal(
        state.classify_reusable_d1(old_manifest, new_manifest, (_reuse_proof(state, admission),)),
        (),
        "contract/version reuse",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("current_candidate_sha256", "9" * 64),
        ("current_cell_contract_sha256", "8" * 64),
        ("current_d0_artifact_sha256", "7" * 64),
        ("current_d1_evidence_refs", ("evidence/changed-d1.json",)),
        ("current_d1_provenance_ref", "attestations/changed-d1.json"),
        ("observed_at", "2026-08-03T04:00:00Z"),
        ("observed_at", "2026-08-03T06:00:00Z"),
    ],
)
def test_R28_reuse_requires_exact_current_candidate_contract_evidence_provenance_and_expiry(field, value):
    state = load_state()
    manifest = state.freeze_cell_manifest(
        {
            "run_id": "RUN-001",
            "graph_id": "GRAPH-RUN-001",
            "graph_version": 1,
            "go_id": "GO-001",
            "go_contract_sha256": "a" * 64,
        },
        ({"cell_id": "GO-001-CELL-001", "cell_contract_sha256": _contract_sha("GO-001-CELL-001"), "required": True},),
    )
    admission = state.admit_current_d1(
        manifest, *_state_inputs(state, manifest, "GO-001-CELL-001")
    )
    proof = _reuse_proof(state, admission, **{field: value})
    require_equal(state.classify_reusable_d1(manifest, manifest, (proof,)), (), f"changed {field} reuse")


def test_go_model_manifest_registry_requires_exact_cell_set_and_closure():
    graph_model = load_graph_model()
    graph = graph_model.GoGraph([graph_model.Go("GO-001")])
    required = tuple(f"GO-001-CELL-{number:03d}" for number in range(1, 7))
    graph.bind_cell_manifest("GO-001", "CELL-MANIFEST-GO-001", 1, "a" * 64, required)
    with pytest.raises(graph_model.GraphError, match="every required CELL D1"):
        graph.record_candidate_closure("GO-001", "a" * 64, required, "b" * 64)
    for cell_id in required:
        graph.record_cell_d1("GO-001", "a" * 64, cell_id, f"d0-{cell_id}", f"d1-{cell_id}")
    graph.record_candidate_closure("GO-001", "a" * 64, required, "b" * 64)
    require_equal(graph.gos["GO-001"].required_cell_ids, required, "GO required CELL registry")
    require_equal(tuple(sorted(graph.gos["GO-001"].d1_receipt_ids_by_cell)), required, "GO D1 CELL registry")
    with pytest.raises(graph_model.GraphError, match="exact required CELL set"):
        graph.record_candidate_closure("GO-001", "a" * 64, required[:-1], "c" * 64)


def test_state_models_are_frozen_canonical_and_hashable():
    state = load_state()
    manifest = state.freeze_cell_manifest(
        {
            "run_id": "RUN-001",
            "graph_id": "GRAPH-RUN-001",
            "graph_version": 1,
            "go_id": "GO-001",
            "go_contract_sha256": "a" * 64,
        },
        ({"cell_id": "GO-001-CELL-001", "cell_contract_sha256": "b" * 64, "required": True},),
    )
    require_equal(hash(manifest), hash(manifest), "manifest hashability")
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.manifest_version = 2
