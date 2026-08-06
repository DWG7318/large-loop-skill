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


CANONICAL_GRAPH_DEFINITIONS = {
    "GraphConstraint",
    "GraphNode",
    "GraphEdge",
    "FrozenGraphTopology",
    "GraphStateProjection",
    "graph_topology_payload",
    "recompute_graph_topology",
    "maximum_compatible_ids",
    "project_graph_state",
}


def test_extracted_graph_definitions_have_one_current_owner():
    owners = {name: [] for name in CANONICAL_GRAPH_DEFINITIONS}
    for path in sorted(SCRIPTS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in owners:
                owners[node.name].append(path.name)
    assert owners == {
        name: ["graph_kernel.py"] for name in CANONICAL_GRAPH_DEFINITIONS
    }


def test_first_slice_size_budget_prevents_duplicate_growth():
    kernel_lines = len(
        (SCRIPTS / "graph_kernel.py").read_text(encoding="utf-8").splitlines()
    )
    state_lines = len(
        (SCRIPTS / "run_state.py").read_text(encoding="utf-8").splitlines()
    )
    validator_lines = len(
        (SCRIPTS / "run_validation.py").read_text(encoding="utf-8").splitlines()
    )
    assert kernel_lines <= 420
    assert state_lines <= 760
    assert kernel_lines + state_lines <= 1_030
    assert validator_lines <= 2_148


def test_repository_distribution_requires_graph_kernel():
    validator_source = (SCRIPTS / "validate_glk.py").read_text(encoding="utf-8")
    repository_test_source = (
        ROOT / "tests" / "test_repository_310.py"
    ).read_text(encoding="utf-8")
    required_literal = '"glk/scripts/graph_kernel.py"'
    assert required_literal in validator_source
    assert required_literal in repository_test_source


def test_formal_projection_has_no_private_duplicate_selector():
    tree = ast.parse((SCRIPTS / "graph_kernel.py").read_text(encoding="utf-8"))
    definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    assert "maximum_compatible_ids" in definitions
    assert "_maximum_compatible_go_ids" not in definitions


def test_compatibility_model_uses_kernel_selector_without_private_copy():
    path = SCRIPTS / "graph_model.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = _imports(path)
    go_graph = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "GoGraph"
    )
    methods = {node.name for node in go_graph.body if isinstance(node, ast.FunctionDef)}
    assert "maximum_compatible_ids" in imports.get("graph_kernel", set())
    assert "_maximum_compatible_subset" not in methods


def test_compatibility_model_uses_kernel_acyclicity_without_private_copy():
    path = SCRIPTS / "graph_model.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = _imports(path)
    go_graph = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "GoGraph"
    )
    methods = {node.name for node in go_graph.body if isinstance(node, ast.FunctionDef)}
    assert {"GraphKernelError", "assert_acyclic"} <= imports.get("graph_kernel", set())
    assert "_assert_acyclic" not in methods
