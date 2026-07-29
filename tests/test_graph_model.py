import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "glk" / "scripts" / "graph_model.py"


def load_model():
    if not MODEL_PATH.exists():
        pytest.fail("GLK 2.3.1 graph model does not exist")
    spec = importlib.util.spec_from_file_location("glk_graph_model", MODEL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
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


def complete_go(m, graph, go_id: str, candidate_id: str):
    graph.start_checking(go_id, candidate_id, f"d0-{go_id}")
    graph.d1_pass(go_id, candidate_id, f"d1-{go_id}", f"checker-{go_id}")
    graph.d2_pass(go_id, candidate_id, f"d2-{go_id}", f"verifier-{go_id}")
