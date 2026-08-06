import copy
import hashlib
import json
from pathlib import Path

import pytest

import test_run_validation_300 as rv
from glk300_fixtures import sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]
GRAPH_MODEL_PATH = ROOT / "tests" / "support" / "legacy_graph_model.py"


def require(condition, message):
    if not condition:
        pytest.fail(message)


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def _canonical_sha256(value):
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _edge(source, target):
    return {
        "source": source,
        "target": target,
        "justification": f"{target} consumes {source} D2 output",
        "source_claim_or_output_refs": [f"{source}.output"],
        "target_input_or_assumption_refs": [f"{target}.input"],
        "consumption_evidence_refs": [f"evidence/edges/{source}-{target}.json"],
    }


def _node(
    go_id,
    predecessors=(),
    conflict_keys=(),
    constraints=(),
    required=True,
    go_claim_sha256="1" * 64,
    acceptance_contract_sha256="2" * 64,
):
    return {
        "go_id": go_id,
        "predecessors": list(predecessors),
        "required": required,
        "conflict_keys": list(conflict_keys),
        "constraints": list(constraints),
        "go_claim_sha256": go_claim_sha256,
        "acceptance_contract_sha256": acceptance_contract_sha256,
    }


def _topology_payload(baseline):
    nodes = sorted(
        (
            {
                "go_id": node["go_id"],
                "predecessors": sorted(node["predecessors"]),
                "required": node["required"],
                "conflict_keys": sorted(node["conflict_keys"]),
                "constraints": sorted(node["constraints"], key=lambda item: (item["type"], tuple(item["references"]))),
                "go_claim_sha256": node["go_claim_sha256"],
                "acceptance_contract_sha256": node["acceptance_contract_sha256"],
            }
            for node in baseline["nodes"]
        ),
        key=lambda node: node["go_id"],
    )
    edges = sorted(
        (
            {
                "source": edge["source"],
                "target": edge["target"],
                "justification": edge["justification"],
                "source_claim_or_output_refs": sorted(edge["source_claim_or_output_refs"]),
                "target_input_or_assumption_refs": sorted(edge["target_input_or_assumption_refs"]),
                "consumption_evidence_refs": sorted(edge["consumption_evidence_refs"]),
            }
            for edge in baseline["edges"]
        ),
        key=lambda edge: (edge["source"], edge["target"]),
    )
    return {
        "graph_id": baseline["graph_id"],
        "graph_version": baseline["graph_version"],
        "nodes": nodes,
        "edges": edges,
        "entry_go_ids": sorted(baseline["entry_go_ids"]),
        "terminal_go_ids": sorted(baseline["terminal_go_ids"]),
        "required_go_ids": sorted(baseline["required_go_ids"]),
        "run_feature_coverage": sorted(baseline["run_feature_coverage"]),
    }


def _set_topology(fixture, nodes, edges, entry_go_ids, terminal_go_ids):
    path, baseline = rv._artifact(fixture.root, "GRAPH_BASELINE")
    baseline.update(
        {
            "nodes": nodes,
            "edges": edges,
            "entry_go_ids": list(entry_go_ids),
            "terminal_go_ids": list(terminal_go_ids),
            "required_go_ids": sorted(node["go_id"] for node in nodes if node["required"]),
            "run_feature_coverage": ["RUN-CLAIM-001"],
            "acyclic": True,
            "waiting_go_ids": sorted(node["go_id"] for node in nodes if node["predecessors"]),
            "active_go_ids": sorted(node["go_id"] for node in nodes if not node["predecessors"]),
        }
    )
    baseline["graph_hash"] = _canonical_sha256(_topology_payload(baseline))
    baseline["candidate_sha256"] = baseline["graph_hash"]
    write_json(path, baseline)
    for edge in edges:
        for reference in edge["consumption_evidence_refs"]:
            rv._add_evidence(fixture.root, reference, f"{edge['source']}->{edge['target']}")
    return path, baseline


def _configure_event(fixture, baseline, waiting_go_ids, active_go_ids):
    d2_path, _ = rv._artifact(fixture.root, "D2_RECEIPT")
    event_path, event = rv._artifact(fixture.root, "GRAPH_EVENT")
    event.update(
        {
            "candidate_id": baseline["candidate_id"],
            "candidate_sha256": baseline["graph_hash"],
            "event_type": "SUCCESSOR_RELEASE",
            "trigger_artifact_ref": d2_path.relative_to(fixture.root).as_posix(),
            "trigger_artifact_sha256": sha256_file(d2_path),
            "prior_event_sha256": None,
            "waiting_go_ids": list(waiting_go_ids),
            "active_go_ids": list(active_go_ids),
        }
    )
    write_json(event_path, event)
    return event_path


def _fork_fixture(tmp_path, *, with_d2_admission=True, with_event=True):
    fixture = rv._prepare_validation_fixture(tmp_path)
    _, d2 = rv._artifact(fixture.root, "D2_RECEIPT")
    nodes = [
        _node(
            "GO-001",
            go_claim_sha256=d2["go_claim_sha256"],
            acceptance_contract_sha256=d2["acceptance_contract_sha256"],
        ),
        _node("GO-002", ("GO-001",), ("database",)),
        _node("GO-003", ("GO-001",)),
        _node("GO-004", ("GO-001",), ("database",)),
        _node(
            "GO-005",
            ("GO-001",),
            constraints=({"type": "RESOURCE", "references": ["gpu"]},),
        ),
    ]
    successors = ("GO-002", "GO-003", "GO-004", "GO-005")
    edges = [_edge("GO-001", target) for target in successors]
    _, baseline = _set_topology(fixture, nodes, edges, ("GO-001",), successors)
    event_path = _configure_event(fixture, baseline, ("GO-004", "GO-005"), ("GO-002", "GO-003"))
    d2_path, _ = rv._artifact(fixture.root, "D2_RECEIPT")
    d2_admission = rv._admission_for_target(fixture.root, d2_path)
    if d2_admission is None:
        pytest.fail("fixture D2 admission is missing")
    if not with_d2_admission:
        d2_admission[0].unlink()
    if not with_event:
        event_path.unlink()
    rv._reindex(fixture)
    return fixture


def _validate(fixture):
    package_module, provenance, run_model = rv.load_prerequisites()
    loaded = package_module.load_run_package(fixture.root)
    validation = rv.load_validation()
    report = validation.validate_loaded_run(loaded, rv.TrustedAdapterFixture(provenance, run_model))
    return validation, report


def _codes(report, layer):
    return {issue.code for issue in report.issues if issue.layer == layer}


def _require_layers_one_to_six_pass(report):
    issues = tuple((issue.code, issue.layer, issue.artifact_ref) for issue in report.issues if issue.layer <= 6)
    require_equal(issues, (), "layers 1-6")


def _graph_state(report):
    require(hasattr(report, "graph_state"), "derived graph state is missing")
    require(report.graph_state is not None, "derived graph state is absent")
    return report.graph_state


def test_R08_recomputes_cycle_instead_of_trusting_acyclic_true(tmp_path):
    fixture = rv._prepare_validation_fixture(tmp_path)
    nodes = [_node("GO-001", ("GO-002",)), _node("GO-002", ("GO-001",))]
    edges = [_edge("GO-001", "GO-002"), _edge("GO-002", "GO-001")]
    _set_topology(fixture, nodes, edges, (), ())
    rv._artifact_path(fixture.root, "GRAPH_EVENT").unlink()
    rv._reindex(fixture)
    _, report = _validate(fixture)
    _require_layers_one_to_six_pass(report)
    require("R08_GRAPH_CYCLE" in _codes(report, 7), "acyclic self-report overrode the real cycle")


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("DUPLICATE_NODE", "GRAPH_NODE_DUPLICATE"),
        ("UNKNOWN_ENDPOINT", "GRAPH_EDGE_ENDPOINT_INVALID"),
        ("PREDECESSOR_MISMATCH", "GRAPH_PREDECESSOR_MISMATCH"),
        ("ENTRY_MISMATCH", "GRAPH_ENTRY_SET_INVALID"),
        ("TERMINAL_MISMATCH", "GRAPH_TERMINAL_SET_INVALID"),
        ("REQUIRED_COVERAGE", "GRAPH_REQUIRED_GO_COVERAGE_INVALID"),
        ("GRAPH_DIGEST", "GRAPH_DIGEST_MISMATCH"),
    ],
)
def test_layer7_recomputes_every_graph_topology_invariant(tmp_path, mutation, expected_code):
    fixture = rv._prepare_validation_fixture(tmp_path)
    nodes = [_node("GO-001"), _node("GO-002", ("GO-001",))]
    edges = [_edge("GO-001", "GO-002")]
    if mutation == "DUPLICATE_NODE":
        nodes.append(copy.deepcopy(nodes[-1]))
    elif mutation == "UNKNOWN_ENDPOINT":
        edges.append(_edge("GO-001", "GO-UNKNOWN"))
    elif mutation == "PREDECESSOR_MISMATCH":
        nodes[-1]["predecessors"] = []
    baseline_path, baseline = _set_topology(fixture, nodes, edges, ("GO-001",), ("GO-002",))
    if mutation == "ENTRY_MISMATCH":
        baseline["entry_go_ids"] = ["GO-002"]
    elif mutation == "TERMINAL_MISMATCH":
        baseline["terminal_go_ids"] = ["GO-001"]
    elif mutation == "REQUIRED_COVERAGE":
        baseline["required_go_ids"] = ["GO-001"]
    if mutation in {"ENTRY_MISMATCH", "TERMINAL_MISMATCH", "REQUIRED_COVERAGE"}:
        baseline["graph_hash"] = _canonical_sha256(_topology_payload(baseline))
        baseline["candidate_sha256"] = baseline["graph_hash"]
    elif mutation == "GRAPH_DIGEST":
        baseline["graph_hash"] = "0" * 64
        baseline["candidate_sha256"] = baseline["graph_hash"]
    write_json(baseline_path, baseline)
    rv._artifact_path(fixture.root, "GRAPH_EVENT").unlink()
    rv._reindex(fixture)
    _, report = _validate(fixture)
    _require_layers_one_to_six_pass(report)
    require(expected_code in _codes(report, 7), f"{mutation} was trusted")


def test_R12_legacy_d2_with_successor_release_is_not_a_formal_d2(tmp_path):
    fixture = _fork_fixture(tmp_path)
    d2_path, d2 = rv._artifact(fixture.root, "D2_RECEIPT")
    d2["successor_release"] = {"active_go_ids": ["GO-002", "GO-003"]}
    write_json(d2_path, d2)
    rv._refresh_lineage(fixture)
    rv._reindex(fixture)
    _, report = _validate(fixture)
    require(("SCHEMA_INVALID", 1) in {(issue.code, issue.layer) for issue in report.issues}, "mixed D2 was formal")


@pytest.mark.parametrize(
    ("with_d2_admission", "with_event"),
    [(False, False), (True, False)],
)
def test_D2_or_D2_admission_without_graph_event_cannot_release_successors(
    tmp_path, with_d2_admission, with_event
):
    fixture = _fork_fixture(tmp_path, with_d2_admission=with_d2_admission, with_event=with_event)
    _, report = _validate(fixture)
    _require_layers_one_to_six_pass(report)
    state = _graph_state(report)
    require_equal(state.verified_go_ids, (), "verified GO without graph event")
    require_equal(state.active_go_ids, ("GO-001",), "active successors without graph event")
    require_equal(
        state.waiting_go_ids,
        ("GO-002", "GO-003", "GO-004", "GO-005"),
        "waiting successors",
    )


def test_exact_admitted_D2_and_graph_event_activate_maximal_safe_successors(tmp_path):
    fixture = _fork_fixture(tmp_path)
    _, report = _validate(fixture)
    _require_layers_one_to_six_pass(report)
    require_equal(_codes(report, 7), set(), "graph integrity")
    require_equal(_codes(report, 8), set(), "graph event fold")
    state = _graph_state(report)
    require_equal(state.verified_go_ids, ("GO-001",), "verified GO")
    require_equal(state.active_go_ids, ("GO-002", "GO-003"), "maximal safe ACTIVE set")
    require_equal(state.waiting_go_ids, ("GO-004", "GO-005"), "conflict/resource waiting set")
    require_equal(state.applied_event_ids, ("GRAPH-EVENT-RUN-001-V1",), "applied graph events")
    require(not hasattr(state, "ready_go_ids"), "READY was introduced")


def test_graph_model_formal_D2_admission_event_seam_releases_only_at_event():
    model = _load_graph_model()
    graph = model.GoGraph(
        [model.Go("A"), model.Go("B", predecessors={"A"})],
        edges=[_model_edge(model)],
    )
    graph.start_checking("A", "candidate-A-v1", "d0-A")
    graph.d1_pass("A", "candidate-A-v1", "d1-A", "checker-A")
    d2_digest = "d" * 64
    graph.record_d2_verdict("A", "candidate-A-v1", "d2-A", d2_digest, "verifier-A")
    require_equal(graph.state("A"), model.ACTIVE_GO, "state after D2")
    require_equal(graph.waiting(), ["B"], "waiting after D2")
    graph.admit_d2("A", d2_digest, "ADMISSION-D2-A")
    require_equal(graph.state("A"), model.ACTIVE_GO, "state after admission")
    require_equal(graph.waiting(), ["B"], "waiting after admission")
    graph.apply_d2_graph_event("A", d2_digest, "ADMISSION-D2-A", "GRAPH-EVENT-A")
    require_equal(graph.state("A"), model.GO_VERIFIED, "state after graph event")
    require_equal(graph.active(), ["B"], "successor after graph event")


def test_graph_event_ledger_rejects_a_second_root_instead_of_selecting_one(tmp_path):
    fixture = _fork_fixture(tmp_path)
    _, original = rv._artifact(fixture.root, "GRAPH_EVENT")
    fork = copy.deepcopy(original)
    fork["artifact_id"] = "GRAPH-EVENT-RUN-001-FORK-V1"
    fork["event_id"] = "GRAPH-EVENT-RUN-001-FORK-V1"
    fork["issued_at"] = "2026-08-03T04:10:00Z"
    fork["provenance_ref"] = "attestations/GRAPH-EVENT-RUN-001-FORK-V1.json"
    fork["evidence_refs"] = [
        rv._add_evidence(
            fixture.root,
            "evidence/graph/events/fork-v1.json",
            fork["artifact_id"],
        )
    ]
    write_json(fixture.root / "events" / "GRAPH-EVENT-RUN-001-FORK-V1.json", fork)
    rv._reindex(fixture)
    _, report = _validate(fixture)
    _require_layers_one_to_six_pass(report)
    require("GRAPH_EVENT_CHAIN_INVALID" in _codes(report, 8), "graph event fork was selected")


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("MISSING_ADMISSION", "GRAPH_EVENT_D2_ADMISSION_REQUIRED"),
        ("WRONG_DIGEST", "GRAPH_EVENT_TRIGGER_INVALID"),
        ("WRONG_GRAPH_VERSION", "GRAPH_EVENT_GRAPH_BINDING_INVALID"),
        ("STALE_GENERATION", "GRAPH_EVENT_STALE_GENERATION"),
        ("WAITING_SOURCE", "GRAPH_EVENT_RELEASE_INVALID"),
        ("WRONG_PROJECTION", "GRAPH_EVENT_PROJECTION_MISMATCH"),
        ("GO_CLAIM_MISMATCH", "D2_GO_CONTRACT_MISMATCH"),
        ("VERIFIER_ISOLATION", "D2_VERIFIER_ISOLATION_INVALID"),
    ],
)
def test_graph_event_fails_closed_for_unbound_or_stale_D2(tmp_path, mutation, expected_code):
    fixture = _fork_fixture(tmp_path)
    event_path, event = rv._artifact(fixture.root, "GRAPH_EVENT")
    if mutation == "MISSING_ADMISSION":
        d2_path, _ = rv._artifact(fixture.root, "D2_RECEIPT")
        admission = rv._admission_for_target(fixture.root, d2_path)
        if admission is None:
            pytest.fail("fixture D2 admission is missing")
        admission[0].unlink()
    elif mutation == "WRONG_DIGEST":
        d1_path, _ = rv._artifact(fixture.root, "D1_RECEIPT")
        event["trigger_artifact_ref"] = d1_path.relative_to(fixture.root).as_posix()
        event["trigger_artifact_sha256"] = sha256_file(d1_path)
        write_json(event_path, event)
    elif mutation == "WRONG_GRAPH_VERSION":
        event["graph_version"] = 2
        write_json(event_path, event)
    elif mutation == "STALE_GENERATION":
        old_d2_path, old_d2 = rv._artifact(fixture.root, "D2_RECEIPT")
        current = copy.deepcopy(old_d2)
        current["artifact_id"] = "D2-GO-001-V2"
        current["issued_at"] = "2026-08-03T04:00:00Z"
        current["provenance_ref"] = "attestations/D2-GO-001-V2.json"
        current["evidence_refs"] = [rv._add_evidence(fixture.root, "evidence/GO-001/d2-v2.json", current["artifact_id"])]
        current_path = fixture.root / "receipts" / "D2-GO-001-V2.json"
        write_json(current_path, current)
        rv._ensure_supervisor_admission(
            fixture.root,
            current_path,
            suffix="D2-GO-001-V2",
            issued_at="2026-08-03T04:01:00Z",
        )
        require(event["trigger_artifact_sha256"] == sha256_file(old_d2_path), "event no longer targets old D2")
    elif mutation == "WAITING_SOURCE":
        d2_path, d2 = rv._artifact(fixture.root, "D2_RECEIPT")
        d2["go_id"] = "GO-002"
        write_json(d2_path, d2)
        rv._refresh_lineage(fixture)
    elif mutation == "GO_CLAIM_MISMATCH":
        d2_path, d2 = rv._artifact(fixture.root, "D2_RECEIPT")
        d2["go_claim_sha256"] = "9" * 64
        write_json(d2_path, d2)
        rv._refresh_lineage(fixture)
    elif mutation == "VERIFIER_ISOLATION":
        d2_path, d2 = rv._artifact(fixture.root, "D2_RECEIPT")
        _, d1 = rv._artifact(fixture.root, "D1_RECEIPT")
        d2["execution_context_ref"] = d1["execution_context_ref"]
        write_json(d2_path, d2)
        rv._refresh_lineage(fixture)
    else:
        event["waiting_go_ids"] = ["GO-002", "GO-003", "GO-005"]
        event["active_go_ids"] = ["GO-004"]
        write_json(event_path, event)
    rv._reindex(fixture)
    _, report = _validate(fixture)
    _require_layers_one_to_six_pass(report)
    require(expected_code in _codes(report, 8), f"{mutation} graph event was accepted")


def _load_graph_model():
    return rv.load_module(GRAPH_MODEL_PATH, "glk_graph_model_task6", "graph model is missing")


def _model_edge(model, source="A", target="B"):
    return model.DependencyEdge(
        source=source,
        target=target,
        justification=f"{target} consumes {source} D2 output",
        source_claim_or_output_refs=(f"{source}.out",),
        target_input_or_assumption_refs=(f"{target}.in",),
        consumption_evidence_refs=(f"evidence/{source}-{target}.json",),
    )


def _complete_go(model, graph, go_id, candidate_id):
    graph.start_checking(go_id, candidate_id, f"d0-{go_id}")
    graph.d1_pass(go_id, candidate_id, f"d1-{go_id}", f"checker-{go_id}")
    graph.d2_pass(go_id, candidate_id, f"d2-{go_id}", f"verifier-{go_id}")


def _confirmed_two_go_incident(model):
    edge = _model_edge(model)
    graph = model.GoGraph([model.Go("A"), model.Go("B", predecessors={"A"})], edges=[edge])
    _complete_go(model, graph, "A", "candidate-A-v1")
    _complete_go(model, graph, "B", "candidate-B-v1")
    trace = graph.confirm_causal_trace(
        incident_id="INC-TASK6",
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate-A-v1",
        evidence_refs=("evidence/root.json", "evidence/A-B.json"),
        symptom_gos=("B",),
        selected_path=(
            model.CausalEdgeSelection(
                source="A",
                target="B",
                incident_evidence_refs=("evidence/A-B.json",),
                confirmation_status=model.CONFIRMED,
            ),
        ),
    )
    return graph, trace


def test_R26_reachability_without_incident_selected_edge_evidence_remains_rejected(tmp_path):
    fixture = _fork_fixture(tmp_path, with_event=False)
    _, report = _validate(fixture)
    _require_layers_one_to_six_pass(report)
    model = _load_graph_model()
    edge = _model_edge(model)
    graph = model.GoGraph([model.Go("A"), model.Go("B", predecessors={"A"})], edges=[edge])
    _complete_go(model, graph, "A", "candidate-A-v1")
    _complete_go(model, graph, "B", "candidate-B-v1")
    with pytest.raises(model.GraphError, match="selected path"):
        graph.confirm_causal_trace(
            incident_id="INC-R26",
            observed_at_go="B",
            source_go="A",
            source_candidate_ref="candidate-A-v1",
            evidence_refs=("evidence/root.json",),
            symptom_gos=("B",),
            selected_path=(),
        )


def test_R27_candidate_seed_cannot_hide_behind_source_REVERIFY(tmp_path):
    fixture = _fork_fixture(tmp_path, with_event=False)
    _, report = _validate(fixture)
    _require_layers_one_to_six_pass(report)
    model = _load_graph_model()
    graph, trace = _confirmed_two_go_incident(model)
    with pytest.raises(model.GraphError, match="CANDIDATE seed.*REWORK or QUARANTINE"):
        graph.apply_causal_amendment(
            trace,
            impact_seeds=(model.ImpactSeed(model.SEED_CANDIDATE, "candidate-A-v1"),),
            dispositions={"A": model.REVERIFY, "B": model.REVERIFY},
            impact_evidence={
                "A": ("evidence/A-impact.json",),
                "B": ("evidence/B-impact.json",),
            },
            new_graph_version=2,
        )
