import importlib.util
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "glk" / "scripts" / "graph_model.py"


def load_model():
    spec = importlib.util.spec_from_file_location("glk_causal_review_model", MODEL_PATH)
    if spec is None or spec.loader is None:
        pytest.fail("cannot load GLK graph model")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_equal(actual, expected, label):
    if actual != expected:
        pytest.fail(f"{label}: expected {expected!r}, got {actual!r}")


def test_confirmed_trace_rejects_nonexistent_current_source_candidate():
    m = load_model()
    graph = two_go_graph(m)
    with pytest.raises(m.GraphError, match="current source candidate"):
        graph.confirm_causal_trace(
            incident_id="INC-CURRENT",
            observed_at_go="B",
            source_go="A",
            source_candidate_ref="candidate-that-does-not-exist",
            evidence_refs=("evidence/root.json", "evidence/A-B-incident.json"),
            symptom_gos=("B",),
            selected_path=(selection(m, "A", "B", "evidence/A-B-incident.json"),),
        )


def test_confirmed_downstream_trace_requires_current_source_d2():
    m = load_model()
    graph = two_go_graph(m)
    graph.start_checking("A", "candidate-A-v1", "d0-A")
    graph.d1_pass("A", "candidate-A-v1", "d1-A", "checker-A")
    with pytest.raises(m.GraphError, match="current source D2"):
        graph.confirm_causal_trace(
            incident_id="INC-D2",
            observed_at_go="B",
            source_go="A",
            source_candidate_ref="candidate-A-v1",
            evidence_refs=("evidence/root.json", "evidence/A-B-incident.json"),
            symptom_gos=("B",),
            selected_path=(selection(m, "A", "B", "evidence/A-B-incident.json"),),
        )


def test_local_source_equals_observation_uses_empty_symptom_and_path_sets():
    m = load_model()
    graph = m.GoGraph([m.Go("A")])
    graph.start_checking("A", "candidate-A-v1", "d0-A")
    trace = graph.confirm_causal_trace(
        incident_id="INC-LOCAL",
        observed_at_go="A",
        source_go="A",
        source_candidate_ref="candidate-A-v1",
        evidence_refs=("evidence/local-root.json",),
        symptom_gos=(),
        selected_path=(),
    )
    require_equal(trace.symptom_gos, (), "local symptom set")
    require_equal(trace.causal_path, (), "local selected path")


@pytest.mark.parametrize(
    ("seed_kind", "seed_ref"),
    [
        ("CANDIDATE", "candidate-A-v1"),
        ("EVIDENCE", "evidence/root.json"),
        ("CLAIM_OR_OUTPUT", "A.out"),
    ],
)
def test_typed_candidate_evidence_and_output_seeds_propagate(seed_kind, seed_ref):
    m = load_model()
    graph, trace = completed_two_go_incident(m)
    projection = graph.apply_causal_amendment(
        trace,
        impact_seeds=(m.ImpactSeed(seed_kind, seed_ref),),
        dispositions={"A": m.REWORK_IMPACT, "B": m.REVERIFY},
        impact_evidence={
            "A": ("evidence/A-impact.json",),
            "B": ("evidence/B-impact.json",),
        },
        new_graph_version=2,
    )
    require_equal(projection.affected_gos, ("A", "B"), f"{seed_kind} impact")


def test_unrelated_typed_seed_is_rejected():
    m = load_model()
    graph, trace = completed_two_go_incident(m)
    with pytest.raises(m.GraphError, match="unrelated impact seed"):
        graph.apply_causal_amendment(
            trace,
            impact_seeds=(m.ImpactSeed(m.SEED_EVIDENCE, "evidence/unrelated.json"),),
            dispositions={"A": m.REWORK_IMPACT, "B": m.REVERIFY},
            impact_evidence={
                "A": ("evidence/A-impact.json",),
                "B": ("evidence/B-impact.json",),
            },
            new_graph_version=2,
        )


def test_candidate_seed_forbids_source_reverify_and_preserves_current_state_on_rejection():
    m = load_model()
    graph, trace = completed_two_go_incident(m)
    with pytest.raises(m.GraphError, match="CANDIDATE seed.*REWORK or QUARANTINE"):
        graph.apply_causal_amendment(
            trace,
            impact_seeds=(m.ImpactSeed(m.SEED_CANDIDATE, "candidate-A-v1"),),
            dispositions={"A": m.REVERIFY, "B": m.REVERIFY},
            impact_evidence={
                "A": ("evidence/A-impact.json",),
                "B": ("evidence/B-impact.json",),
            },
            new_graph_version=2,
        )
    require_equal(graph.gos["A"].candidate_id, "candidate-A-v1", "rejected candidate")
    require_equal(graph.gos["A"].d0_receipt_id, "d0-A", "rejected D0")
    require_equal(graph.gos["A"].d1_receipt_id, "d1-A", "rejected D1")
    require_equal(graph.gos["A"].d2_receipt_id, "d2-A", "rejected D2")


def test_candidate_seed_cannot_be_weakened_by_evidence_or_output_seed():
    m = load_model()
    for companion in (
        m.ImpactSeed(m.SEED_EVIDENCE, "evidence/root.json"),
        m.ImpactSeed(m.SEED_CLAIM_OR_OUTPUT, "A.out"),
    ):
        graph, trace = completed_two_go_incident(m)
        with pytest.raises(m.GraphError, match="strictest source disposition"):
            graph.apply_causal_amendment(
                trace,
                impact_seeds=(
                    m.ImpactSeed(m.SEED_CANDIDATE, "candidate-A-v1"),
                    companion,
                ),
                dispositions={"A": m.REVERIFY, "B": m.REVERIFY},
                impact_evidence={
                    "A": ("evidence/A-impact.json",),
                    "B": ("evidence/B-impact.json",),
                },
                new_graph_version=2,
            )


def test_candidate_seed_rework_invalidates_source_candidate_and_all_receipts():
    m = load_model()
    graph, trace = completed_two_go_incident(m)
    projection = graph.apply_causal_amendment(
        trace,
        impact_seeds=(m.ImpactSeed(m.SEED_CANDIDATE, "candidate-A-v1"),),
        dispositions={"A": m.REWORK_IMPACT, "B": m.REVERIFY},
        impact_evidence={
            "A": ("evidence/A-impact.json",),
            "B": ("evidence/B-impact.json",),
        },
        new_graph_version=2,
    )
    source_item = next(item for item in projection.items if item.go_id == "A")
    require_equal(
        source_item.invalidated_candidate_refs,
        ("candidate-A-v1",),
        "candidate invalidation",
    )
    require_equal(
        source_item.invalidated_receipt_refs,
        ("d0-A", "d1-A", "d2-A"),
        "candidate receipt invalidation",
    )
    require_equal(graph.gos["A"].candidate_id, None, "current candidate cleared")
    require_equal(graph.gos["A"].d0_receipt_id, None, "current D0 cleared")
    require_equal(graph.gos["A"].d1_receipt_id, None, "current D1 cleared")
    require_equal(graph.gos["A"].d2_receipt_id, None, "current D2 cleared")
    require_equal(graph.phase("A"), m.REWORK, "candidate reactivation phase")


def test_claim_or_output_seed_forbids_reusing_same_current_source_artifact():
    m = load_model()
    graph, trace = completed_two_go_incident(m)
    with pytest.raises(m.GraphError, match="CLAIM_OR_OUTPUT seed.*current artifact"):
        graph.apply_causal_amendment(
            trace,
            impact_seeds=(m.ImpactSeed(m.SEED_CLAIM_OR_OUTPUT, "A.out"),),
            dispositions={"A": m.REVERIFY, "B": m.REVERIFY},
            impact_evidence={
                "A": ("evidence/A-impact.json",),
                "B": ("evidence/B-impact.json",),
            },
            new_graph_version=2,
        )


def test_evidence_seed_allows_source_reverify_with_candidate_and_d1_preserved():
    m = load_model()
    graph, trace = completed_two_go_incident(m)
    projection = graph.apply_causal_amendment(
        trace,
        impact_seeds=(m.ImpactSeed(m.SEED_EVIDENCE, "evidence/root.json"),),
        dispositions={"A": m.REVERIFY, "B": m.REVERIFY},
        impact_evidence={
            "A": ("evidence/A-impact.json",),
            "B": ("evidence/B-impact.json",),
        },
        new_graph_version=2,
    )
    source_item = next(item for item in projection.items if item.go_id == "A")
    require_equal(source_item.invalidated_candidate_refs, (), "evidence candidate validity")
    require_equal(source_item.invalidated_receipt_refs, ("d2-A",), "evidence receipts")
    require_equal(graph.gos["A"].candidate_id, "candidate-A-v1", "evidence candidate")
    require_equal(graph.gos["A"].d1_receipt_id, "d1-A", "evidence D1")
    require_equal(graph.phase("A"), m.VERIFYING, "evidence reactivation phase")


def test_explicit_multiple_symptoms_require_confirmed_paths_to_each_go():
    m = load_model()
    graph = m.GoGraph(
        [m.Go("A"), m.Go("B", predecessors={"A"}), m.Go("C", predecessors={"A"})],
        edges=[edge(m, "A", "B", "A.out", "B.in"), edge(m, "A", "C", "A.out", "C.in")],
    )
    complete_go(m, graph, "A", "candidate-A-v1")
    trace = graph.confirm_causal_trace(
        incident_id="INC-MULTI-SYMPTOM",
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate-A-v1",
        evidence_refs=("evidence/root.json", "evidence/A-B.json", "evidence/A-C.json"),
        symptom_gos=("B", "C"),
        selected_path=(
            selection(m, "A", "B", "evidence/A-B.json"),
            selection(m, "A", "C", "evidence/A-C.json"),
        ),
    )
    require_equal(trace.symptom_gos, ("B", "C"), "explicit symptom set")

    with pytest.raises(m.GraphError, match="selected path.*every symptom"):
        graph.confirm_causal_trace(
            incident_id="INC-OMITTED-SYMPTOM",
            observed_at_go="B",
            source_go="A",
            source_candidate_ref="candidate-A-v1",
            evidence_refs=("evidence/root.json", "evidence/A-B.json"),
            symptom_gos=("B", "C"),
            selected_path=(selection(m, "A", "B", "evidence/A-B.json"),),
        )


def test_amendment_rejects_forged_unknown_symptom():
    m = load_model()
    graph, trace = completed_two_go_incident(m)
    forged = replace(trace, symptom_gos=("B", "UNKNOWN-GO"))
    with pytest.raises(m.GraphError, match="unknown symptom GO"):
        apply_standard_amendment(m, graph, forged)


def test_hand_built_trace_with_unknown_symptom_fails_closed_before_path_shape():
    m = load_model()
    graph, trace = completed_two_go_incident(m)
    forged = m.GoCausalTrace(
        incident_id=trace.incident_id,
        graph_version=trace.graph_version,
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate-A-v1",
        evidence_refs=trace.evidence_refs,
        symptom_gos=("B", "UNKNOWN-GO"),
        causal_path=(edge(m, "A", "B", "A.out", "B.in"),),
        excluded_edges=(),
        stopping_reason="confirmed source reached",
        confirmation_status=m.CONFIRMED,
    )
    with pytest.raises(m.GraphError, match="unknown symptom GO"):
        apply_standard_amendment(m, graph, forged)


def test_diamond_uses_only_incident_selected_path_and_excludes_alternative():
    m = load_model()
    graph = diamond_graph(m)
    complete_go(m, graph, "A", "candidate-A-v1")
    complete_go(m, graph, "M1", "candidate-M1-v1")
    complete_go(m, graph, "M2", "candidate-M2-v1")
    complete_go(m, graph, "B", "candidate-B-v1")

    trace = graph.confirm_causal_trace(
        incident_id="INC-DIAMOND",
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate-A-v1",
        evidence_refs=("evidence/root.json", "evidence/only-M1-path.json"),
        symptom_gos=("B",),
        selected_path=(
            selection(m, "A", "M1", "evidence/only-M1-path.json"),
            selection(m, "M1", "B", "evidence/only-M1-path.json"),
        ),
    )
    require_equal(
        tuple((step.source, step.target) for step in trace.causal_path),
        (("A", "M1"), ("M1", "B")),
        "selected causal path",
    )
    require_equal(
        tuple((item.source, item.target) for item in trace.excluded_edges),
        (("A", "M2"), ("M2", "B")),
        "excluded alternative path",
    )


def test_amendment_revalidates_selected_path_exclusions_and_stopping_reason():
    m = load_model()
    graph, trace = completed_two_go_incident(m)
    forged = replace(trace, excluded_edges=(), stopping_reason="guessed")
    with pytest.raises(m.GraphError, match="selected path evidence"):
        apply_standard_amendment(m, graph, forged)


def two_go_graph(m):
    return m.GoGraph(
        [m.Go("A"), m.Go("B", predecessors={"A"})],
        edges=[edge(m, "A", "B", "A.out", "B.in")],
    )


def completed_two_go_incident(m):
    graph = two_go_graph(m)
    complete_go(m, graph, "A", "candidate-A-v1")
    complete_go(m, graph, "B", "candidate-B-v1")
    trace = graph.confirm_causal_trace(
        incident_id="INC-STANDARD",
        observed_at_go="B",
        source_go="A",
        source_candidate_ref="candidate-A-v1",
        evidence_refs=("evidence/root.json", "evidence/A-B-incident.json"),
        symptom_gos=("B",),
        selected_path=(selection(m, "A", "B", "evidence/A-B-incident.json"),),
    )
    return graph, trace


def diamond_graph(m):
    return m.GoGraph(
        [
            m.Go("A"),
            m.Go("M1", predecessors={"A"}),
            m.Go("M2", predecessors={"A"}),
            m.Go("B", predecessors={"M1", "M2"}),
        ],
        edges=[
            edge(m, "A", "M1", "A.out", "M1.in"),
            edge(m, "A", "M2", "A.out", "M2.in"),
            edge(m, "M1", "B", "M1.out", "B.m1"),
            edge(m, "M2", "B", "M2.out", "B.m2"),
        ],
    )


def edge(m, source, target, source_ref, target_ref):
    return m.DependencyEdge(
        source=source,
        target=target,
        justification=f"{target} requires {source} D2 PASS",
        source_claim_or_output_refs=(source_ref,),
        target_input_or_assumption_refs=(target_ref,),
        consumption_evidence_refs=(f"evidence/{source}-{target}-contract.json",),
    )


def selection(m, source, target, evidence_ref):
    return m.CausalEdgeSelection(
        source=source,
        target=target,
        incident_evidence_refs=(evidence_ref,),
        confirmation_status=m.CONFIRMED,
    )


def complete_go(m, graph, go_id, candidate_id):
    graph.start_checking(go_id, candidate_id, f"d0-{go_id}")
    graph.d1_pass(go_id, candidate_id, f"d1-{go_id}", f"checker-{go_id}")
    graph.d2_pass(go_id, candidate_id, f"d2-{go_id}", f"verifier-{go_id}")


def apply_standard_amendment(m, graph, trace):
    return graph.apply_causal_amendment(
        trace,
        impact_seeds=(m.ImpactSeed(m.SEED_CLAIM_OR_OUTPUT, "A.out"),),
        dispositions={"A": m.REWORK_IMPACT, "B": m.REVERIFY},
        impact_evidence={
            "A": ("evidence/A-impact.json",),
            "B": ("evidence/B-impact.json",),
        },
        new_graph_version=2,
    )
