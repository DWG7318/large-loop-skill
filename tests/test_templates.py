import json
import os
import subprocess
import sys
from pathlib import Path

import yaml
import pytest
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "glk" / "schemas" / "glk.schema.json"
TEMPLATE_DIR = ROOT / "glk" / "templates"

TEMPLATES = {
    "RUN_CONTRACT.yaml": "run_contract",
    "ROLE_BINDING.yaml": "role_binding",
    "GO.yaml": "go",
    "GRAPH_BASELINE.yaml": "graph_baseline",
    "CELL_RECEIPT.yaml": "cell_receipt",
    "GO_RECEIPT.yaml": "go_receipt",
    "RUN_RECEIPT.yaml": "run_receipt",
    "GO_CAUSAL_TRACE.yaml": "go_causal_trace",
    "GRAPH_AMENDMENT.yaml": "graph_amendment",
    "FORMAL_RESOLUTION.yaml": "formal_resolution",
    "OWNER_ACCEPTANCE.yaml": "owner_acceptance",
    "SECURITY_HANDOFF.yaml": "security_handoff",
}


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_definition(schema, definition, instance):
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/$defs/{definition}",
        "$defs": schema["$defs"],
    }
    Draft202012Validator(wrapper).validate(instance)


def test_all_templates_exist_and_validate_against_executable_schema():
    schema = load_schema()
    for filename, definition in TEMPLATES.items():
        path = TEMPLATE_DIR / filename
        assert path.exists(), path
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        validate_definition(schema, definition, data)


def test_run_contract_binds_a_fresh_run_supervisor_instance():
    run = yaml.safe_load((TEMPLATE_DIR / "RUN_CONTRACT.yaml").read_text(encoding="utf-8"))
    binding = run["run_supervisor_binding"]
    assert binding["role_type"] == "RUN_SUPERVISOR"
    assert binding["run_id"] == run["run_id"]
    assert all(
        binding[key]
        for key in ["instance_id", "context_id", "workspace_id", "evidence_root"]
    )
    assert run["supervisor_reuse_forbidden"] is True


def test_run_contract_schema_rejects_a_non_supervisor_binding():
    schema = load_schema()
    run = yaml.safe_load((TEMPLATE_DIR / "RUN_CONTRACT.yaml").read_text(encoding="utf-8"))
    run["run_supervisor_binding"]["role_type"] = "WORKER"
    with pytest.raises(ValidationError):
        validate_definition(schema, "run_contract", run)


def test_go_template_has_waiting_reasons_and_no_ready_state():
    go = yaml.safe_load((TEMPLATE_DIR / "GO.yaml").read_text(encoding="utf-8"))
    assert go["graph_state"] in {"WAITING_GO", "ACTIVE_GO"}
    assert "waiting_reasons" in go
    assert "READY" not in json.dumps(go)


def test_go_and_graph_baseline_templates_are_cross_artifact_consistent():
    go = yaml.safe_load((TEMPLATE_DIR / "GO.yaml").read_text(encoding="utf-8"))
    graph = yaml.safe_load(
        (TEMPLATE_DIR / "GRAPH_BASELINE.yaml").read_text(encoding="utf-8")
    )
    assert go["go_id"] in graph["nodes"]
    assert set(go["predecessors"]) <= set(graph["nodes"])
    if go["graph_state"] == "ACTIVE_GO":
        assert go["go_id"] in graph["active_go_ids"]
    if go["graph_state"] == "WAITING_GO":
        assert go["go_id"] in graph["waiting_go_ids"]


def test_waiting_reason_requires_at_least_one_reference():
    schema = load_schema()
    go = yaml.safe_load((TEMPLATE_DIR / "GO.yaml").read_text(encoding="utf-8"))
    go["waiting_reasons"] = [
        {
            "type": "DEPENDENCY_UNMET",
            "references": [],
            "evidence_ref": "evidence/GO-001/waiting.json",
        }
    ]
    with pytest.raises(ValidationError):
        validate_definition(schema, "go", go)


def test_dependency_edges_bind_actual_consumption_evidence():
    schema = load_schema()
    graph = yaml.safe_load(
        (TEMPLATE_DIR / "GRAPH_BASELINE.yaml").read_text(encoding="utf-8")
    )
    edge = graph["edges"][0]
    assert edge["source_claim_or_output_refs"]
    assert edge["target_input_or_assumption_refs"]
    assert edge["consumption_evidence_refs"]

    edge["consumption_evidence_refs"] = []
    with pytest.raises(ValidationError):
        validate_definition(schema, "graph_baseline", graph)


def test_causal_trace_uses_incident_annotations_not_go_types_or_states():
    schema = load_schema()
    trace = yaml.safe_load(
        (TEMPLATE_DIR / "GO_CAUSAL_TRACE.yaml").read_text(encoding="utf-8")
    )
    assert trace["source_go"] not in trace["symptom_go_ids"]
    assert trace["observed_at_go"] in trace["symptom_go_ids"]
    assert trace["confirmation_status"] == "CONFIRMED"
    assert trace["causal_path"]
    assert all(step["incident_evidence_refs"] for step in trace["causal_path"])
    assert all(step["confirmation_status"] == "CONFIRMED" for step in trace["causal_path"])
    assert trace["excluded_edges"]
    assert trace["stopping_reason"]
    validate_definition(schema, "go_causal_trace", trace)


def test_suspected_trace_is_recordable_but_cannot_authorize_amendment():
    schema = load_schema()
    trace = yaml.safe_load(
        (TEMPLATE_DIR / "GO_CAUSAL_TRACE.yaml").read_text(encoding="utf-8")
    )
    trace["confirmation_status"] = "SUSPECTED"
    validate_definition(schema, "go_causal_trace", trace)

    amendment = yaml.safe_load(
        (TEMPLATE_DIR / "GRAPH_AMENDMENT.yaml").read_text(encoding="utf-8")
    )
    amendment["causal_trace_status"] = "SUSPECTED"
    with pytest.raises(ValidationError):
        validate_definition(schema, "graph_amendment", amendment)


def test_amendment_declares_minimal_impact_and_reactivation_projection():
    amendment = yaml.safe_load(
        (TEMPLATE_DIR / "GRAPH_AMENDMENT.yaml").read_text(encoding="utf-8")
    )
    assert amendment["causal_trace_status"] == "CONFIRMED"
    assert amendment["impact_seeds"]
    assert {seed["kind"] for seed in amendment["impact_seeds"]} <= {
        "CANDIDATE",
        "EVIDENCE",
        "CLAIM_OR_OUTPUT",
    }
    assert {item["disposition"] for item in amendment["impact_slice"]} <= {
        "UNAFFECTED",
        "REVERIFY",
        "REWORK",
        "QUARANTINE",
    }
    projection = amendment["reactivation_projection"]
    assert set(projection) == {
        "waiting_go_ids",
        "active_go_ids",
        "unchanged_go_ids",
    }
    assert set(projection["waiting_go_ids"]).isdisjoint(projection["active_go_ids"])


def test_schema_rejects_untyped_impact_seed_and_unconfirmed_path_step():
    schema = load_schema()
    amendment = yaml.safe_load(
        (TEMPLATE_DIR / "GRAPH_AMENDMENT.yaml").read_text(encoding="utf-8")
    )
    amendment["impact_seeds"] = [{"kind": "UNKNOWN", "ref": "GO-002.output"}]
    with pytest.raises(ValidationError):
        validate_definition(schema, "graph_amendment", amendment)

    trace = yaml.safe_load(
        (TEMPLATE_DIR / "GO_CAUSAL_TRACE.yaml").read_text(encoding="utf-8")
    )
    trace["causal_path"][0]["confirmation_status"] = "SUSPECTED"
    with pytest.raises(ValidationError):
        validate_definition(schema, "go_causal_trace", trace)


def test_amendment_schema_enforces_seed_to_source_disposition_invariant():
    schema = load_schema()
    amendment = yaml.safe_load(
        (TEMPLATE_DIR / "GRAPH_AMENDMENT.yaml").read_text(encoding="utf-8")
    )
    source_item = next(
        item for item in amendment["impact_slice"] if item["go_id"] == amendment["source_go"]
    )
    assert amendment["source_disposition"] == source_item["disposition"]

    amendment["impact_seeds"] = [
        {"kind": "CANDIDATE", "ref": "candidates/GO-002/v1"}
    ]
    amendment["source_disposition"] = "REVERIFY"
    with pytest.raises(ValidationError):
        validate_definition(schema, "graph_amendment", amendment)

    amendment["impact_seeds"] = [
        {"kind": "EVIDENCE", "ref": "evidence/GO-002/v1.json"}
    ]
    source_item["disposition"] = "REVERIFY"
    source_item["invalidated_candidate_refs"] = []
    source_item["invalidated_receipt_refs"] = ["receipts/D2-GO-002-v1.json"]
    validate_definition(schema, "graph_amendment", amendment)

    amendment["impact_seeds"] = [
        {"kind": "EVIDENCE", "ref": "evidence/GO-002/v1.json"},
        {"kind": "CANDIDATE", "ref": "candidates/GO-002/v1"},
    ]
    with pytest.raises(ValidationError):
        validate_definition(schema, "graph_amendment", amendment)

    amendment["impact_seeds"] = [
        {"kind": "CLAIM_OR_OUTPUT", "ref": "GO-002.output"}
    ]
    with pytest.raises(ValidationError):
        validate_definition(schema, "graph_amendment", amendment)


def test_bootstrap_creates_and_validates_complete_run_workspace(tmp_path):
    target = tmp_path / "run"
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, "glk/scripts/bootstrap_run.py", str(target)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
    for filename in TEMPLATES:
        assert (target / "contracts" / filename).exists()
    for dirname in ["candidates", "evidence", "receipts", "amendments"]:
        assert (target / dirname).is_dir()
