import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Tuple

from artifact_model import canonical_sha256


GRAPH_CONSTRAINT_TYPES = frozenset(
    {"WRITE_CONFLICT", "RESOURCE", "ISOLATION", "SAFETY"}
)


class GraphKernelError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


RunStateError = GraphKernelError


@dataclass(frozen=True, order=True)
class GraphConstraint:
    kind: str
    references: Tuple[str, ...]


@dataclass(frozen=True, order=True)
class GraphNode:
    go_id: str
    predecessors: Tuple[str, ...]
    required: bool
    conflict_keys: Tuple[str, ...]
    constraints: Tuple[GraphConstraint, ...]
    go_claim_sha256: str
    acceptance_contract_sha256: str


@dataclass(frozen=True, order=True)
class GraphEdge:
    source: str
    target: str
    justification: str
    source_claim_or_output_refs: Tuple[str, ...]
    target_input_or_assumption_refs: Tuple[str, ...]
    consumption_evidence_refs: Tuple[str, ...]


@dataclass(frozen=True)
class FrozenGraphTopology:
    run_id: str
    graph_id: str
    graph_version: int
    baseline_candidate_id: str
    nodes: Tuple[GraphNode, ...]
    edges: Tuple[GraphEdge, ...]
    entry_go_ids: Tuple[str, ...]
    terminal_go_ids: Tuple[str, ...]
    required_go_ids: Tuple[str, ...]
    run_feature_coverage: Tuple[str, ...]
    graph_sha256: str
    explicit: bool


@dataclass(frozen=True)
class GraphStateProjection:
    graph_sha256: str
    verified_go_ids: Tuple[str, ...]
    waiting_go_ids: Tuple[str, ...]
    active_go_ids: Tuple[str, ...]
    applied_event_ids: Tuple[str, ...]


def _required_text(value, code: str, label: str):
    if not isinstance(value, str) or not value:
        raise RunStateError(code, f"{label} is required")


def _required_hash(value, code: str, label: str):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RunStateError(code, f"{label} must be a lowercase sha256")


def _value(subject, field):
    if isinstance(subject, Mapping):
        return subject.get(field)
    return getattr(subject, field, None)


def _sorted_texts(value, code, label, *, allow_empty=True):
    if not isinstance(value, (list, tuple)):
        raise RunStateError(code, f"{label} must be an array")
    items = tuple(sorted(value))
    if (not allow_empty and not items) or any(
        not isinstance(item, str) or not item for item in items
    ):
        raise RunStateError(code, f"{label} contains an invalid identity")
    if len(set(items)) != len(items):
        raise RunStateError(code, f"{label} contains duplicates")
    return items


def _graph_constraint(value):
    if not isinstance(value, Mapping):
        raise RunStateError("GRAPH_CONSTRAINT_INVALID", "mapping required")
    kind = value.get("type")
    if kind not in GRAPH_CONSTRAINT_TYPES:
        raise RunStateError("GRAPH_CONSTRAINT_INVALID", str(kind))
    references = _sorted_texts(
        value.get("references"),
        "GRAPH_CONSTRAINT_INVALID",
        "references",
        allow_empty=False,
    )
    return GraphConstraint(kind=kind, references=references)


def _graph_node(value):
    if not isinstance(value, Mapping):
        raise RunStateError("GRAPH_NODE_INVALID", "mapping required")
    go_id = value.get("go_id")
    _required_text(go_id, "GRAPH_NODE_INVALID", "go_id")
    predecessors = _sorted_texts(
        value.get("predecessors"),
        "GRAPH_NODE_INVALID",
        f"{go_id}.predecessors",
    )
    conflict_keys = _sorted_texts(
        value.get("conflict_keys"),
        "GRAPH_NODE_INVALID",
        f"{go_id}.conflict_keys",
    )
    constraints_raw = value.get("constraints")
    if not isinstance(constraints_raw, (list, tuple)):
        raise RunStateError("GRAPH_CONSTRAINT_INVALID", f"{go_id}.constraints")
    constraints = tuple(sorted((_graph_constraint(item) for item in constraints_raw)))
    if len(set(constraints)) != len(constraints):
        raise RunStateError(
            "GRAPH_CONSTRAINT_INVALID", f"{go_id}.constraints duplicate"
        )
    required = value.get("required")
    if not isinstance(required, bool):
        raise RunStateError("GRAPH_NODE_INVALID", f"{go_id}.required")
    go_claim_sha256 = value.get("go_claim_sha256")
    acceptance_contract_sha256 = value.get("acceptance_contract_sha256")
    _required_hash(
        go_claim_sha256, "GRAPH_NODE_INVALID", f"{go_id}.go_claim_sha256"
    )
    _required_hash(
        acceptance_contract_sha256,
        "GRAPH_NODE_INVALID",
        f"{go_id}.acceptance_contract_sha256",
    )
    return GraphNode(
        go_id=go_id,
        predecessors=predecessors,
        required=required,
        conflict_keys=conflict_keys,
        constraints=constraints,
        go_claim_sha256=go_claim_sha256,
        acceptance_contract_sha256=acceptance_contract_sha256,
    )


def _graph_edge(value):
    if not isinstance(value, Mapping):
        raise RunStateError("GRAPH_EDGE_INVALID", "mapping required")
    source = value.get("source")
    target = value.get("target")
    justification = value.get("justification")
    for label, item in (
        ("source", source),
        ("target", target),
        ("justification", justification),
    ):
        _required_text(item, "GRAPH_EDGE_INVALID", label)
    if source == target:
        raise RunStateError("R08_GRAPH_CYCLE", f"self edge {source}")
    return GraphEdge(
        source=source,
        target=target,
        justification=justification,
        source_claim_or_output_refs=_sorted_texts(
            value.get("source_claim_or_output_refs"),
            "GRAPH_EDGE_INVALID",
            "source_claim_or_output_refs",
            allow_empty=False,
        ),
        target_input_or_assumption_refs=_sorted_texts(
            value.get("target_input_or_assumption_refs"),
            "GRAPH_EDGE_INVALID",
            "target_input_or_assumption_refs",
            allow_empty=False,
        ),
        consumption_evidence_refs=_sorted_texts(
            value.get("consumption_evidence_refs"),
            "GRAPH_EDGE_INVALID",
            "consumption_evidence_refs",
            allow_empty=False,
        ),
    )


def graph_topology_payload(topology):
    nodes = tuple(
        {
            "go_id": node.go_id,
            "predecessors": node.predecessors,
            "required": node.required,
            "conflict_keys": node.conflict_keys,
            "constraints": tuple(
                {"type": constraint.kind, "references": constraint.references}
                for constraint in node.constraints
            ),
            "go_claim_sha256": node.go_claim_sha256,
            "acceptance_contract_sha256": node.acceptance_contract_sha256,
        }
        for node in topology.nodes
    )
    edges = tuple(
        {
            "source": edge.source,
            "target": edge.target,
            "justification": edge.justification,
            "source_claim_or_output_refs": edge.source_claim_or_output_refs,
            "target_input_or_assumption_refs": edge.target_input_or_assumption_refs,
            "consumption_evidence_refs": edge.consumption_evidence_refs,
        }
        for edge in topology.edges
    )
    return {
        "graph_id": topology.graph_id,
        "graph_version": topology.graph_version,
        "nodes": nodes,
        "edges": edges,
        "entry_go_ids": topology.entry_go_ids,
        "terminal_go_ids": topology.terminal_go_ids,
        "required_go_ids": topology.required_go_ids,
        "run_feature_coverage": topology.run_feature_coverage,
    }


def recompute_graph_topology(baseline, fallback_go_ids=()):
    run_id = _value(baseline, "run_id")
    graph_id = _value(baseline, "graph_id")
    graph_version = _value(baseline, "graph_version")
    baseline_candidate_id = _value(baseline, "candidate_id")
    for label, value in (
        ("run_id", run_id),
        ("graph_id", graph_id),
        ("candidate_id", baseline_candidate_id),
    ):
        _required_text(value, "GRAPH_BASELINE_INVALID", label)
    if (
        not isinstance(graph_version, int)
        or isinstance(graph_version, bool)
        or graph_version < 1
    ):
        raise RunStateError("GRAPH_BASELINE_INVALID", "graph_version")

    raw_nodes = _value(baseline, "nodes")
    explicit = isinstance(raw_nodes, (list, tuple)) and bool(raw_nodes)
    if explicit:
        nodes = tuple(
            sorted((_graph_node(item) for item in raw_nodes), key=lambda item: item.go_id)
        )
    else:
        derived = tuple(sorted(set(fallback_go_ids)))
        if len(derived) != 1:
            raise RunStateError(
                "GRAPH_TOPOLOGY_REQUIRED",
                "only a single-GO graph can be derived safely",
            )
        nodes = (
            GraphNode(derived[0], (), True, (), (), "0" * 64, "0" * 64),
        )
    if len({node.go_id for node in nodes}) != len(nodes):
        raise RunStateError("GRAPH_NODE_DUPLICATE", "duplicate GO identity")
    node_ids = {node.go_id for node in nodes}

    raw_edges = _value(baseline, "edges") if explicit else ()
    if not isinstance(raw_edges, (list, tuple)):
        raise RunStateError("GRAPH_EDGE_INVALID", "edges must be an array")
    edges = tuple(
        sorted(
            (_graph_edge(item) for item in raw_edges),
            key=lambda item: (item.source, item.target),
        )
    )
    edge_pairs = {(edge.source, edge.target) for edge in edges}
    if len(edge_pairs) != len(edges):
        raise RunStateError("GRAPH_EDGE_DUPLICATE", "duplicate source/target pair")
    if any(edge.source not in node_ids or edge.target not in node_ids for edge in edges):
        raise RunStateError(
            "GRAPH_EDGE_ENDPOINT_INVALID", "edge endpoint is not a GO"
        )
    incoming = {go_id: set() for go_id in node_ids}
    outgoing = {go_id: set() for go_id in node_ids}
    for edge in edges:
        incoming[edge.target].add(edge.source)
        outgoing[edge.source].add(edge.target)
    for node in nodes:
        if set(node.predecessors) != incoming[node.go_id]:
            raise RunStateError("GRAPH_PREDECESSOR_MISMATCH", node.go_id)

    visiting = set()
    visited = set()

    def visit(go_id):
        if go_id in visiting:
            raise RunStateError("R08_GRAPH_CYCLE", go_id)
        if go_id in visited:
            return
        visiting.add(go_id)
        for predecessor in sorted(incoming[go_id]):
            visit(predecessor)
        visiting.remove(go_id)
        visited.add(go_id)

    for go_id in sorted(node_ids):
        visit(go_id)

    derived_entries = tuple(sorted(go_id for go_id in node_ids if not incoming[go_id]))
    derived_terminals = tuple(
        sorted(go_id for go_id in node_ids if not outgoing[go_id])
    )
    derived_required = tuple(sorted(node.go_id for node in nodes if node.required))
    if explicit:
        entry_go_ids = _sorted_texts(
            _value(baseline, "entry_go_ids"),
            "GRAPH_ENTRY_SET_INVALID",
            "entry_go_ids",
        )
        terminal_go_ids = _sorted_texts(
            _value(baseline, "terminal_go_ids"),
            "GRAPH_TERMINAL_SET_INVALID",
            "terminal_go_ids",
        )
        required_go_ids = _sorted_texts(
            _value(baseline, "required_go_ids"),
            "GRAPH_REQUIRED_GO_COVERAGE_INVALID",
            "required_go_ids",
        )
        run_feature_coverage = _sorted_texts(
            _value(baseline, "run_feature_coverage"),
            "GRAPH_REQUIRED_GO_COVERAGE_INVALID",
            "run_feature_coverage",
            allow_empty=False,
        )
        if entry_go_ids != derived_entries:
            raise RunStateError(
                "GRAPH_ENTRY_SET_INVALID",
                "declared entry set differs from topology",
            )
        if terminal_go_ids != derived_terminals:
            raise RunStateError(
                "GRAPH_TERMINAL_SET_INVALID",
                "declared terminal set differs from topology",
            )
        if required_go_ids != derived_required:
            raise RunStateError(
                "GRAPH_REQUIRED_GO_COVERAGE_INVALID",
                "declared required GO set differs from nodes",
            )
    else:
        entry_go_ids = derived_entries
        terminal_go_ids = derived_terminals
        required_go_ids = derived_required
        run_feature_coverage = ("DERIVED-SINGLE-GO",)

    reachable = set(entry_go_ids)
    queue = list(entry_go_ids)
    while queue:
        source = queue.pop(0)
        for target in sorted(outgoing[source]):
            if target not in reachable:
                reachable.add(target)
                queue.append(target)
    if not set(required_go_ids).issubset(reachable):
        raise RunStateError(
            "GRAPH_REQUIRED_GO_COVERAGE_INVALID", "required GO is unreachable"
        )

    provisional = FrozenGraphTopology(
        run_id=run_id,
        graph_id=graph_id,
        graph_version=graph_version,
        baseline_candidate_id=baseline_candidate_id,
        nodes=nodes,
        edges=edges,
        entry_go_ids=entry_go_ids,
        terminal_go_ids=terminal_go_ids,
        required_go_ids=required_go_ids,
        run_feature_coverage=run_feature_coverage,
        graph_sha256="",
        explicit=explicit,
    )
    graph_sha256 = canonical_sha256(graph_topology_payload(provisional))
    declared_hash = _value(baseline, "graph_hash")
    if explicit and declared_hash != graph_sha256:
        raise RunStateError(
            "GRAPH_DIGEST_MISMATCH",
            "declared graph hash differs from recomputation",
        )
    return dataclasses.replace(provisional, graph_sha256=graph_sha256)
