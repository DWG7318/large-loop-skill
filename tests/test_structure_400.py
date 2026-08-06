import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "glk" / "scripts"
GRAPH_NAMES = {
    "FrozenGraphTopology",
    "GraphStateProjection",
    "project_graph_state",
    "recompute_graph_topology",
}


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module: {alias.name for alias in node.names}
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    }


def test_run_validator_consumes_graph_facts_from_canonical_kernel():
    imports = _imports(SCRIPTS / "run_validation.py")
    assert GRAPH_NAMES <= imports.get("graph_kernel", set())
    assert not (GRAPH_NAMES & imports.get("run_state", set()))
