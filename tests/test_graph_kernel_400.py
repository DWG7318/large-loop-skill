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
