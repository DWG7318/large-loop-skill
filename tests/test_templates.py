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
