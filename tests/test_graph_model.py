import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "glk" / "scripts" / "graph_model.py"


def load_model():
    if not MODEL_PATH.exists():
        pytest.fail("GLK 2.4.0 graph model does not exist")
    spec = importlib.util.spec_from_file_location("glk_graph_model", MODEL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.path.insert(0, str(MODEL_PATH.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(MODEL_PATH.parent))
    return module


def test_independent_roots_activate_immediately_and_join_waits():
    m = load_model()
    graph = m.GoGraph(
        [m.Go("A"), m.Go("B"), m.Go("C", predecessors={"A", "B"})]
    )
    assert graph.active() == ["A", "B"]
    assert graph.waiting() == ["C"]
    assert graph.waiting_reasons("C") == [
        m.WaitingReason("DEPENDENCY_UNMET", ("A", "B"))
    ]
    assert not hasattr(graph, "ready")


def test_waiting_go_activates_directly_after_all_predecessor_d2_passes():
    m = load_model()
    graph = m.GoGraph(
        [m.Go("A"), m.Go("B"), m.Go("C", predecessors={"A", "B"})]
    )
    complete_go(m, graph, "A", "candidate-a")
    assert graph.active() == ["B"]
    complete_go(m, graph, "B", "candidate-b")
    assert graph.active() == ["C"]
    assert graph.waiting() == []


def test_non_dependency_constraint_waits_without_creating_an_edge():
    m = load_model()
    graph = m.GoGraph(
        [m.Go("A"), m.Go("B", constraints={"RESOURCE:gpu"})]
    )
    assert graph.active() == ["A"]
    assert graph.waiting_reasons("B") == [m.WaitingReason("RESOURCE", ("gpu",))]
    assert graph.predecessors("B") == set()
    graph.clear_constraint("B", "RESOURCE:gpu")
    assert graph.active() == ["A", "B"]


def test_conflicting_roots_form_a_deterministic_maximal_safe_active_set():
    m = load_model()
    graph = m.GoGraph(
        [
            m.Go("A", conflict_keys={"database"}),
            m.Go("B", conflict_keys={"database"}),
            m.Go("C"),
        ]
    )
    assert graph.active() == ["A", "C"]
    assert graph.waiting() == ["B"]
    assert graph.waiting_reasons("B") == [m.WaitingReason("CONFLICT", ("A",))]


def test_activation_maximizes_the_number_of_safe_independent_go_nodes():
    m = load_model()
    graph = m.GoGraph(
        [
            m.Go("A", conflict_keys={"x", "y"}),
            m.Go("B", conflict_keys={"x"}),
            m.Go("C", conflict_keys={"y"}),
        ]
    )
    assert graph.active() == ["B", "C"]
    assert graph.waiting() == ["A"]


def test_d2_requires_d1_same_candidate_and_independent_context():
    m = load_model()
    graph = m.GoGraph([m.Go("A")])
    graph.start_checking("A", "candidate-a", "d0-a")
    with pytest.raises(m.GraphError, match="D1 PASS"):
        graph.d2_pass("A", "candidate-a", "d2-a", "go-verifier-a")
    graph.d1_pass("A", "candidate-a", "d1-a", "checker-a")
    with pytest.raises(m.GraphError, match="independent"):
        graph.d2_pass("A", "candidate-a", "d2-a", "checker-a")
    with pytest.raises(m.GraphError, match="candidate"):
        graph.d2_pass("A", "candidate-b", "d2-a", "go-verifier-a")
    graph.d2_pass("A", "candidate-a", "d2-a", "go-verifier-a")
    assert graph.state("A") == m.GO_VERIFIED


def test_required_cancel_does_not_complete_without_formal_resolution():
    m = load_model()
    graph = m.GoGraph([m.Go("A", required=True)])
    with pytest.raises(m.GraphError, match="formal resolution"):
        graph.cancel("A")
    graph.apply_resolution(
        "A",
        m.FormalResolution(
            resolution_id="RES-1",
            kind="CANCELLED",
            amendment_id="GA-1",
            releases_successors=False,
            removes_required=True,
        ),
    )
    assert graph.complete_prerequisites()


def test_waiting_reason_rejects_subjective_or_unknown_reason_types():
    m = load_model()
    with pytest.raises(m.GraphError, match="waiting reason type"):
        m.WaitingReason("PREFERENCE", ("serialize-for-convenience",))


def test_dependency_edge_requires_d2_justification():
    m = load_model()
    with pytest.raises(m.GraphError, match="justification"):
        m.DependencyEdge(
            source="A",
            target="B",
            justification="",
            source_claim_or_output_refs=("A.out",),
            target_input_or_assumption_refs=("B.input",),
            consumption_evidence_refs=("evidence/A-B.json",),
        )


def test_causal_source_cannot_also_be_a_downstream_symptom_annotation():
    m = load_model()
    with pytest.raises(m.GraphError, match="source GO cannot be a symptom"):
        m.GoCausalTrace(
            incident_id="INC-BAD",
            graph_version=1,
            observed_at_go="B",
            source_go="A",
            source_candidate_ref="candidate/A-v1",
            evidence_refs=("evidence/INC-BAD.json",),
            symptom_gos=("A", "B"),
            causal_path=(),
            excluded_edges=(),
            stopping_reason="confirmed source reached",
            confirmation_status=m.CONFIRMED,
        )


def test_confirmed_causal_trace_distinguishes_internal_source_from_symptom():
    m = load_model()
    graph = m.GoGraph(
        [
            m.Go("R"),
            m.Go("A", predecessors={"R"}),
            m.Go("X"),
            m.Go("B", predecessors={"A", "X"}),
        ],
        edges=[
            edge(m, "R", "A", "R.out", "A.base"),
            edge(m, "A", "B", "A.out", "B.input"),
            edge(m, "X", "B", "X.out", "B.other"),
        ],
    )
    complete_go(m, graph, "R", "candidate-R-v1")
    complete_go(m, graph, "X", "candidate-X-v1")
    complete_go(m, graph, "A", "candidate/A-v1")

    trace = graph.confirm_causal_trace(
        incident_id="INC-1",
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate/A-v1",
        evidence_refs=("evidence/INC-1/root-cause.json", "evidence/INC-1/A-B.json"),
        symptom_gos=("B",),
        selected_path=(selection(m, "A", "B", "evidence/INC-1/A-B.json"),),
    )

    assert trace.confirmation_status == m.CONFIRMED
    assert trace.source_go == "A"
    assert trace.symptom_gos == ("B",)
    assert [(step.source, step.target) for step in trace.causal_path] == [("A", "B")]
    assert [(step.source, step.target) for step in trace.excluded_edges] == [
        ("R", "A"),
        ("X", "B"),
    ]
    assert trace.stopping_reason == "confirmed source reached"


def test_multi_hop_causal_carrier_is_not_automatically_a_symptom_go():
    m = load_model()
    graph = m.GoGraph(
        [
            m.Go("A"),
            m.Go("M", predecessors={"A"}),
            m.Go("X"),
            m.Go("B", predecessors={"M", "X"}),
        ],
        edges=[
            edge(m, "A", "M", "A.out", "M.input"),
            edge(m, "M", "B", "M.out", "B.input"),
            edge(m, "X", "B", "X.out", "B.other"),
        ],
    )
    complete_go(m, graph, "A", "candidate/A-v1")
    complete_go(m, graph, "M", "candidate-M-v1")

    trace = graph.confirm_causal_trace(
        incident_id="INC-MULTI",
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate/A-v1",
        evidence_refs=("evidence/INC-MULTI/root-cause.json", "evidence/INC-MULTI/path.json"),
        symptom_gos=("B",),
        selected_path=(
            selection(m, "A", "M", "evidence/INC-MULTI/path.json"),
            selection(m, "M", "B", "evidence/INC-MULTI/path.json"),
        ),
    )

    assert trace.symptom_gos == ("B",)
    assert [(step.source, step.target) for step in trace.causal_path] == [
        ("A", "M"),
        ("M", "B"),
    ]
    assert [(step.source, step.target) for step in trace.excluded_edges] == [("X", "B")]


def test_causal_trace_requires_bound_consumption_edges():
    m = load_model()
    graph = m.GoGraph([m.Go("A"), m.Go("B", predecessors={"A"})])
    complete_go(m, graph, "A", "candidate/A-v1")

    with pytest.raises(m.GraphError, match="current D2 consumption edge"):
        graph.confirm_causal_trace(
            incident_id="INC-1",
            observed_at_go="B",
            source_go="A",
            source_candidate_ref="candidate/A-v1",
            evidence_refs=("evidence/INC-1/root-cause.json", "evidence/INC-1/path.json"),
            symptom_gos=("B",),
            selected_path=(selection(m, "A", "B", "evidence/INC-1/path.json"),),
        )


def test_causal_trace_fails_closed_when_path_node_has_unbound_incoming_edge():
    m = load_model()
    graph = m.GoGraph(
        [m.Go("A"), m.Go("X"), m.Go("B", predecessors={"A", "X"})],
        edges=[edge(m, "A", "B", "A.out", "B.input")],
    )
    complete_go(m, graph, "A", "candidate/A-v1")

    with pytest.raises(m.GraphError, match="unbound incoming dependency"):
        graph.confirm_causal_trace(
            incident_id="INC-UNBOUND",
            observed_at_go="B",
            source_go="A",
            source_candidate_ref="candidate/A-v1",
            evidence_refs=("evidence/INC-UNBOUND/root-cause.json", "evidence/INC-UNBOUND/path.json"),
            symptom_gos=("B",),
            selected_path=(selection(m, "A", "B", "evidence/INC-UNBOUND/path.json"),),
        )


def test_suspected_causal_trace_cannot_invalidate_receipts():
    m = load_model()
    graph = m.GoGraph(
        [m.Go("A"), m.Go("B", predecessors={"A"})],
        edges=[edge(m, "A", "B", "A.out", "B.input")],
    )
    trace = graph.trace_causal_incident(
        incident_id="INC-1",
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate/A-v1",
        evidence_refs=("evidence/INC-1/hypothesis.json",),
        symptom_gos=("B",),
        selected_path=(
            m.CausalEdgeSelection(
                source="A",
                target="B",
                incident_evidence_refs=("evidence/INC-1/hypothesis.json",),
                confirmation_status=m.SUSPECTED,
            ),
        ),
        confirmation_status=m.SUSPECTED,
    )

    with pytest.raises(m.GraphError, match="CONFIRMED"):
        graph.apply_causal_amendment(
            trace,
            impact_seeds=(m.ImpactSeed(m.SEED_CLAIM_OR_OUTPUT, "A.out"),),
            dispositions={"A": m.REWORK_IMPACT, "B": m.REVERIFY},
            new_graph_version=2,
        )


def test_confirmed_amendment_requires_evidence_for_each_affected_go():
    m = load_model()
    graph = m.GoGraph(
        [m.Go("A"), m.Go("B", predecessors={"A"})],
        edges=[edge(m, "A", "B", "A.out", "B.input")],
    )
    complete_go(m, graph, "A", "candidate-A-v1")
    complete_go(m, graph, "B", "candidate-B-v1")
    trace = graph.confirm_causal_trace(
        incident_id="INC-EVIDENCE",
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate-A-v1",
        evidence_refs=("evidence/INC-EVIDENCE/root-cause.json", "evidence/INC-EVIDENCE/path.json"),
        symptom_gos=("B",),
        selected_path=(selection(m, "A", "B", "evidence/INC-EVIDENCE/path.json"),),
    )

    with pytest.raises(m.GraphError, match="impact evidence"):
        graph.apply_causal_amendment(
            trace,
            impact_seeds=(m.ImpactSeed(m.SEED_CLAIM_OR_OUTPUT, "A.out"),),
            dispositions={"A": m.REWORK_IMPACT, "B": m.REVERIFY},
            new_graph_version=2,
        )


def test_causal_amendment_invalidates_minimum_slice_and_reactivates_in_parallel():
    m = load_model()
    graph = m.GoGraph(
        [
            m.Go("R"),
            m.Go("U"),
            m.Go("A", predecessors={"R"}),
            m.Go("B", predecessors={"A"}),
            m.Go("C", predecessors={"A"}),
            m.Go("D", predecessors={"A"}),
        ],
        edges=[
            edge(m, "R", "A", "R.out", "A.base"),
            edge(m, "A", "B", "A.changed", "B.input"),
            edge(m, "A", "C", "A.changed", "C.input"),
            edge(m, "A", "D", "A.stable", "D.input"),
        ],
    )
    for go_id in ["R", "U", "A", "B", "C", "D"]:
        if go_id in graph.active():
            complete_go(m, graph, go_id, f"candidate-{go_id}-v1")
    assert graph.complete_prerequisites()

    trace = graph.confirm_causal_trace(
        incident_id="INC-2",
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate-A-v1",
        evidence_refs=("evidence/INC-2/root-cause.json", "evidence/INC-2/A-B-path.json"),
        symptom_gos=("B",),
        selected_path=(selection(m, "A", "B", "evidence/INC-2/A-B-path.json"),),
    )
    projection = graph.apply_causal_amendment(
        trace,
        impact_seeds=(m.ImpactSeed(m.SEED_CLAIM_OR_OUTPUT, "A.changed"),),
        dispositions={
            "A": m.REWORK_IMPACT,
            "B": m.REVERIFY,
            "C": m.QUARANTINE,
        },
        impact_evidence={
            "A": ("evidence/INC-2/A-impact.json",),
            "B": ("evidence/INC-2/B-impact.json",),
            "C": ("evidence/INC-2/C-impact.json",),
        },
        new_graph_version=2,
    )

    assert projection.affected_gos == ("A", "B", "C")
    assert projection.disposition("D") == m.UNAFFECTED
    assert set(projection.invalidated_receipt_refs) >= {
        "d1-A",
        "d2-A",
        "d2-B",
        "d1-C",
        "d2-C",
    }
    assert "d1-B" not in projection.invalidated_receipt_refs
    assert graph.graph_version == 2
    assert graph.state("R") == m.GO_VERIFIED
    assert graph.state("U") == m.GO_VERIFIED
    assert graph.state("D") == m.GO_VERIFIED
    assert graph.active() == ["A"]
    assert graph.waiting() == ["B", "C"]
    assert graph.waiting_reasons("B") == [
        m.WaitingReason("DEPENDENCY_UNMET", ("A",))
    ]
    assert graph.gos["B"].candidate_id == "candidate-B-v1"
    assert graph.gos["B"].d1_receipt_id == "d1-B"

    complete_go(m, graph, "A", "candidate-A-v2")
    assert graph.active() == ["B", "C"]
    assert graph.waiting() == []
    assert graph.phase("B") == m.VERIFYING
    assert graph.phase("C") == m.IMPLEMENTING
    graph.d2_pass("B", "candidate-B-v1", "d2-B-v2", "verifier-B-v2")
    assert graph.state("B") == m.GO_VERIFIED
    assert graph.amendment_history == [projection]


def complete_go(m, graph, go_id: str, candidate_id: str):
    graph.start_checking(go_id, candidate_id, f"d0-{go_id}")
    graph.d1_pass(go_id, candidate_id, f"d1-{go_id}", f"checker-{go_id}")
    graph.d2_pass(go_id, candidate_id, f"d2-{go_id}", f"verifier-{go_id}")


def edge(m, source: str, target: str, source_ref: str, target_ref: str):
    return m.DependencyEdge(
        source=source,
        target=target,
        justification=f"{target} requires {source} D2 PASS",
        source_claim_or_output_refs=(source_ref,),
        target_input_or_assumption_refs=(target_ref,),
        consumption_evidence_refs=(f"evidence/{source}-{target}.json",),
    )


def selection(m, source: str, target: str, evidence_ref: str):
    return m.CausalEdgeSelection(
        source=source,
        target=target,
        incident_evidence_refs=(evidence_ref,),
        confirmation_status=m.CONFIRMED,
    )
