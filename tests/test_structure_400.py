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
    "assert_acyclic",
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


def test_shared_graph_algorithm_budget_proves_net_reduction():
    model_lines = len(
        (SCRIPTS / "graph_model.py").read_text(encoding="utf-8").splitlines()
    )
    kernel_lines = len(
        (SCRIPTS / "graph_kernel.py").read_text(encoding="utf-8").splitlines()
    )
    assert model_lines <= 1_100
    assert kernel_lines <= 430
    assert model_lines + kernel_lines <= 1_500


def test_active_superpowers_document_surface_stays_bounded():
    docs_root = ROOT / "docs" / "superpowers"
    active_lines = sum(
        len(path.read_text(encoding="utf-8").splitlines())
        for path in docs_root.rglob("*.md")
    )
    assert active_lines <= 1_250


def test_progress_reference_executor_is_absent_but_formal_contract_remains():
    assert not (SCRIPTS / "progress_reporting.py").exists()
    assert not (ROOT / "tests" / "test_progress_reporting_310.py").exists()

    required_literal = '"glk/scripts/progress_reporting.py"'
    validator_source = (SCRIPTS / "validate_glk.py").read_text(encoding="utf-8")
    repository_test_source = (
        ROOT / "tests" / "test_repository_310.py"
    ).read_text(encoding="utf-8")
    assert required_literal not in validator_source
    assert required_literal not in repository_test_source

    for relative in (
        "glk/references/layered-progress.md",
        "glk/templates/CHECKER_PROGRESS_EVENT.yaml",
        "glk/templates/SUPERVISOR_PROGRESS_EVENT.yaml",
        "glk/schemas/glk.schema.json",
    ):
        assert (ROOT / relative).is_file(), relative

    formal_source = (SCRIPTS / "run_validation.py").read_text(encoding="utf-8")
    for token in (
        "CHECKER_PROGRESS_EVENT",
        "SUPERVISOR_PROGRESS_EVENT",
        "PROGRESS_COVERAGE_REQUIRED",
        "PROGRESS_DUPLICATE",
        "PROGRESS_TRIGGER_INVALID",
        "PROGRESS_SCOPE_INVALID",
        "PROGRESS_ORDER_INVALID",
    ):
        assert token in formal_source, token

    regression_tree = ast.parse(
        (ROOT / "tests" / "test_run_validation_310.py").read_text(encoding="utf-8")
    )
    regression_names = {
        node.name for node in regression_tree.body if isinstance(node, ast.FunctionDef)
    }
    assert {
        "test_REDO_current_310_requires_exact_layered_progress_coverage",
        "test_REDO_duplicate_or_wrong_trigger_progress_is_rejected",
        "test_current_310_progress_order_and_version_fail_closed",
    } <= regression_names


def test_progress_reference_removal_proves_net_surface_reduction():
    production_lines = sum(
        len(path.read_text(encoding="utf-8").splitlines())
        for path in SCRIPTS.glob("*.py")
    )
    test_lines = sum(
        len(path.read_text(encoding="utf-8").splitlines())
        for path in (ROOT / "tests").glob("*.py")
    )
    assert production_lines <= 9_400
    assert test_lines <= 11_350
