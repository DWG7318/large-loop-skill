import json
from pathlib import Path

import pytest
import yaml

import test_admission_graph_300 as ag
import test_conformance_300 as cf
import test_run_closure_300 as rc
import test_run_validation_300 as rv
from glk300_fixtures import sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def _prepare_case(tmp_path, layer):
    case = cf.build_conformance_case(tmp_path)
    role_overrides = None
    if layer == 1:
        path, value = cf._record(
            case.root,
            "D0_RECEIPT",
            go_id="GO-001",
            cell_id="GO-001-CELL-001",
        )
        value["evidence_refs"] = []
        write_json(path, value)
        case = cf.rebuild_conformance_indexes(case)
    elif layer == 2:
        adapter_path = cf.write_adapter_fixture(
            case,
            tmp_path / "adapter-layer-2.json",
        )
        path, _ = cf._record(
            case.root,
            "D0_RECEIPT",
            go_id="GO-001",
            cell_id="GO-001-CELL-001",
        )
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        return case, adapter_path
    elif layer == 3:
        path, value = cf._record(case.root, "RUN_CONTRACT")
        value["run_supervisor_binding"]["run_id"] = "RUN-OTHER"
        write_json(path, value)
        case = cf.rebuild_conformance_indexes(case)
    elif layer == 4:
        role_overrides = {"ROLE-WORKER-GO-001": "RUN_SUPERVISOR"}
    elif layer == 5:
        path, value = cf._record(
            case.root,
            "D1_RECEIPT",
            go_id="GO-001",
            cell_id="GO-001-CELL-001",
        )
        value["d0_artifact_sha256"] = "9" * 64
        write_json(path, value)
        case = cf.rebuild_conformance_indexes(case)
    elif layer == 6:
        path, value = cf._record(case.root, "CELL_MANIFEST", go_id="GO-001")
        value["closure_sha256"] = "9" * 64
        write_json(path, value)
        case = cf.rebuild_conformance_indexes(case)
    elif layer == 7:
        _, d2_one = cf._record(case.root, "D2_RECEIPT", go_id="GO-001")
        _, d2_two = cf._record(case.root, "D2_RECEIPT", go_id="GO-002")
        nodes = [
            ag._node(
                "GO-001",
                ("GO-002",),
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
        ag._set_topology(
            case.fixture,
            nodes,
            [ag._edge("GO-001", "GO-002"), ag._edge("GO-002", "GO-001")],
            (),
            (),
        )
        case = cf.rebuild_conformance_indexes(case)
    elif layer == 8:
        event_one_path, event_one = rc._artifact_by_id(case.root, "GRAPH-EVENT-RUN-001-V1")
        event_one["active_go_ids"] = []
        write_json(event_one_path, event_one)
        event_two_path, event_two = rc._artifact_by_id(case.root, "GRAPH-EVENT-RUN-001-V2")
        event_two["prior_event_sha256"] = sha256_file(event_one_path)
        write_json(event_two_path, event_two)
        case = cf.rebuild_conformance_indexes(case)
    elif layer == 9:
        d3_path, d3 = cf._record(case.root, "D3_RECEIPT")
        d3["graph_sha256"] = "9" * 64
        write_json(d3_path, d3)
        case = cf.rebuild_conformance_indexes(case)
    elif layer == 10:
        d3_path, d3 = cf._record(case.root, "D3_RECEIPT")
        d3["verdict"] = "D3_FAIL"
        write_json(d3_path, d3)
        case = cf.rebuild_conformance_indexes(case)
    adapter_path = cf.write_adapter_fixture(
        case,
        tmp_path / f"adapter-layer-{layer}.json",
        role_overrides=role_overrides,
    )
    return case, adapter_path


def _issue_pairs(output):
    return {(issue["layer"], issue["code"]) for issue in output.get("issues", ())}


def test_validate_run_CLI_emits_deterministic_complete_RUN_PACKAGE_JSON(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    adapter_path = cf.write_adapter_fixture(case, tmp_path / "trusted-adapter.json")
    first = cf.run_cli(case, adapter_path)
    second = cf.run_cli(case, adapter_path)
    require_equal(first.returncode, 0, f"first stderr: {first.stderr}")
    require_equal(second.returncode, 0, f"second stderr: {second.stderr}")
    require_equal(first.stdout, second.stdout, "deterministic JSON stdout")
    require_equal(first.stderr, "", "PASS stderr")
    output = json.loads(first.stdout)
    require_equal(output["scope"], "RUN_PACKAGE", "validator scope")
    require_equal(output["scope_boundaries"]["validate_glk"], "REPOSITORY_DISTRIBUTION", "repository scope")
    require_equal(output["scope_boundaries"]["validate_run"], "RUN_PACKAGE", "Run scope")
    require_equal(output["package"]["root"], case.root.resolve().as_posix(), "package root")
    require_equal(output["package"]["index_head_sha256"], sha256_file(case.head_path), "index head")
    require_equal(output["validator"]["version"], "3.1.0", "validator version")
    require_equal(len(output["validator"]["digest"]), 64, "validator digest")
    require_equal(len(output["report_digest"]), 64, "report digest")
    require_equal([layer["layer"] for layer in output["layers"]], list(range(1, 11)), "layer numbers")
    require_equal(output["issues"], [], "valid issues")
    require_equal(output["holds"], [], "valid holds")
    require_equal(output["formal_state"]["projection_kind"], "DERIVED_NON_AUTHORITATIVE", "formal-state boundary")


@pytest.mark.parametrize(
    ("layer", "expected_code"),
    [
        (1, "R04_EMPTY_EVIDENCE"),
        (3, "R07_RUN_BINDING_SCOPE_MISMATCH"),
        (4, "R01_SUPERVISOR_D0_AUTHORITY"),
        (5, "R05_UNRESOLVED_RECEIPT_LINEAGE"),
        (6, "R16_MANIFEST_CLOSURE_HASH_INVALID"),
        (7, "R08_GRAPH_CYCLE"),
        (8, "GRAPH_EVENT_PROJECTION_MISMATCH"),
        (9, "R17_D3_GRAPH_DIGEST_MISMATCH"),
        (10, "R18_D3_NOT_PASS"),
    ],
)
def test_validate_run_CLI_reports_each_technical_layer_after_prior_layers_pass(
    tmp_path,
    layer,
    expected_code,
):
    case, adapter_path = _prepare_case(tmp_path, layer)
    completed = cf.run_cli(case, adapter_path)
    require_equal(completed.returncode, 1, f"layer {layer} stderr: {completed.stderr}")
    output = json.loads(completed.stdout)
    require((layer, expected_code) in _issue_pairs(output), f"missing layer {layer} code {expected_code}")
    require_equal(
        [item["status"] for item in output["layers"][: layer - 1]],
        ["PASS"] * (layer - 1),
        f"layers before {layer}",
    )


def test_validate_run_CLI_marks_loader_failure_as_package_integrity_not_verdict(tmp_path):
    case, adapter_path = _prepare_case(tmp_path, 2)
    completed = cf.run_cli(case, adapter_path)
    require_equal(completed.returncode, 2, "loader failure exit")
    output = json.loads(completed.stdout)
    require_equal(output["status"], "ERROR", "loader status")
    require_equal(output["error"]["scope"], "PACKAGE_INTEGRITY", "loader error scope")
    require_equal(output["error"]["code"], "DIGEST_MISMATCH", "loader error code")
    require_equal(output["issues"], [], "loader technical issues")
    require_equal(output["formal_state"]["projection_kind"], "UNAVAILABLE", "loader formal state")


def test_validate_run_CLI_returns_exit_two_for_invocation_fixture_error(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    completed = cf.run_cli(case, tmp_path / "missing-adapter.json")
    require_equal(completed.returncode, 2, "invocation error exit")
    output = json.loads(completed.stdout)
    require_equal(output["error"]["scope"], "INVOCATION", "invocation error scope")
    require_equal(output["error"]["code"], "ADAPTER_FIXTURE_NOT_FOUND", "invocation error code")
    require("adapter fixture error" in completed.stderr, "human-readable invocation diagnostic")


def test_untrusted_fixture_cannot_create_formal_PASS(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    adapter_path = cf.write_adapter_fixture(case, tmp_path / "untrusted-adapter.json", trusted=False)
    completed = cf.run_cli(case, adapter_path)
    require_equal(completed.returncode, 1, "untrusted fixture exit")
    output = json.loads(completed.stdout)
    require_equal([layer["status"] for layer in output["layers"]], ["PASS"] * 10, "mechanical validation")
    require_equal(output["status"], "FAIL", "formal status")
    require_equal(
        output["conformance_environment"]["status"],
        "UNTRUSTED_CONFORMANCE_ENVIRONMENT",
        "fixture trust status",
    )


def test_CLI_report_and_formal_state_cannot_act_as_formal_artifacts(tmp_path):
    case = cf.build_conformance_case(tmp_path)
    adapter_path = cf.write_adapter_fixture(case, tmp_path / "trusted-adapter.json")
    output = json.loads(cf.run_cli(case, adapter_path).stdout)
    serialized = json.dumps(output["formal_state"], sort_keys=True)
    for forbidden in ("artifact_type", "issuer_binding_ref", "verdict", "admitted_artifact_sha256", "event_type"):
        require(f'"{forbidden}"' not in serialized, f"derived report exposed formal field {forbidden}")
    source = (ROOT / "glk" / "scripts" / "validate_run.py").read_text(encoding="utf-8")
    require_equal(source.count("load_run_package("), 1, "CLI package loads")
    require_equal(source.count("validate_loaded_run("), 1, "CLI validation calls")
