import importlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"


def _load_kernel():
    sys.modules.pop("graph_kernel", None)
    sys.path.insert(0, str(SCRIPTS))
    try:
        return importlib.import_module("graph_kernel")
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.fixture
def kernel():
    module = _load_kernel()
    try:
        yield module
    finally:
        sys.modules.pop("graph_kernel", None)


def test_recompute_single_go_topology_from_frozen_identity():
    assert (SCRIPTS / "graph_kernel.py").is_file(), "canonical graph kernel is missing"
    kernel = _load_kernel()
    baseline = {
        "run_id": "RUN-400",
        "graph_id": "GRAPH-400",
        "graph_version": 1,
        "candidate_id": "GRAPH-CANDIDATE-400",
    }

    topology = kernel.recompute_graph_topology(baseline, ("GO-001",))

    assert topology.run_id == "RUN-400"
    assert topology.graph_id == "GRAPH-400"
    assert topology.required_go_ids == ("GO-001",)
    assert topology.entry_go_ids == ("GO-001",)
    assert topology.terminal_go_ids == ("GO-001",)
    assert topology.graph_sha256 == kernel.canonical_sha256(
        kernel.graph_topology_payload(topology)
    )
    assert topology.explicit is False


def _node(kernel, go_id, predecessors=(), conflict_keys=()):
    return kernel.GraphNode(
        go_id=go_id,
        predecessors=predecessors,
        required=True,
        conflict_keys=conflict_keys,
        constraints=(),
        go_claim_sha256="a" * 64,
        acceptance_contract_sha256="b" * 64,
    )


def test_project_graph_state_selects_deterministic_maximal_safe_set(kernel):
    topology = kernel.FrozenGraphTopology(
        run_id="RUN-400",
        graph_id="GRAPH-400",
        graph_version=1,
        baseline_candidate_id="GRAPH-CANDIDATE-400",
        nodes=(
            _node(kernel, "GO-A", conflict_keys=("PORT-1",)),
            _node(kernel, "GO-B", conflict_keys=("PORT-1",)),
            _node(kernel, "GO-C", conflict_keys=("PORT-2",)),
        ),
        edges=(),
        entry_go_ids=("GO-A", "GO-B", "GO-C"),
        terminal_go_ids=("GO-A", "GO-B", "GO-C"),
        required_go_ids=("GO-A", "GO-B", "GO-C"),
        run_feature_coverage=("CLAIM-400",),
        graph_sha256="c" * 64,
        explicit=True,
    )

    projection = kernel.project_graph_state(topology)

    assert projection.active_go_ids == ("GO-A", "GO-C")
    assert projection.waiting_go_ids == ("GO-B",)
    assert projection.verified_go_ids == ()
    assert not hasattr(projection, "ready_go_ids")


def test_run_state_reexports_exact_kernel_graph_objects(kernel):
    sys.modules.pop("run_state", None)
    sys.path.insert(0, str(SCRIPTS))
    try:
        state = importlib.import_module("run_state")
    finally:
        sys.path.remove(str(SCRIPTS))
        sys.modules.pop("run_state", None)

    expected = (
        "GraphConstraint",
        "GraphNode",
        "GraphEdge",
        "FrozenGraphTopology",
        "GraphStateProjection",
        "graph_topology_payload",
        "recompute_graph_topology",
        "project_graph_state",
    )
    for name in expected:
        assert getattr(state, name) is getattr(kernel, name)
    assert state.RunStateError is kernel.GraphKernelError


def test_maximum_compatible_ids_respects_conflicts_resources_and_tie_order(kernel):
    selected = kernel.maximum_compatible_ids(
        candidate_ids=("GO-C", "GO-B", "GO-A"),
        conflict_keys_by_id={
            "GO-A": ("PORT-1",),
            "GO-B": ("PORT-1",),
            "GO-C": ("PORT-2",),
        },
        resource_claims_by_id={
            "GO-A": {"cpu": 1},
            "GO-B": {"cpu": 1},
            "GO-C": {"cpu": 2},
        },
        resource_capacity={"cpu": 3},
    )

    assert selected == ("GO-A", "GO-C")


def test_assert_acyclic_rejects_cycle_with_canonical_error(kernel):
    with pytest.raises(kernel.GraphKernelError) as captured:
        kernel.assert_acyclic(
            ("GO-A", "GO-B"),
            {"GO-A": ("GO-B",), "GO-B": ("GO-A",)},
        )

    assert captured.value.code == "R08_GRAPH_CYCLE"
