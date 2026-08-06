import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Tuple

from artifact_model import canonical_sha256


GRAPH_CONSTRAINT_TYPES = frozenset({"WRITE_CONFLICT", "RESOURCE", "ISOLATION", "SAFETY"})


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


@dataclass(frozen=True, order=True)
class SelectedCell:
    cell_id: str
    candidate_id: str
    candidate_sha256: str
    d0_artifact_sha256: str
    d1_artifact_sha256: str


@dataclass(frozen=True, order=True)
class CurrentD2Fact:
    go_id: str
    artifact_sha256: str
    candidate_id: str
    candidate_sha256: str
    verifier_binding_ref: str
    execution_context_ref: str
    verdict: str


@dataclass(frozen=True)
class D3Eligibility:
    eligible: bool
    required_go_ids: Tuple[str, ...]
    admitted_d2_artifact_sha256s: Tuple[str, ...]
    graph_id: str
    graph_version: int
    graph_sha256: str
    applied_graph_event_ids: Tuple[str, ...]
    final_candidate_id: str
    final_candidate_sha256: str
    graph_seam_claims: Tuple[str, ...]
    graph_seam_evidence_refs: Tuple[str, ...]
    failure_codes: Tuple[str, ...]


@dataclass(frozen=True)
class RunClosureProjection:
    d3_eligible: bool
    current_d3_sha256: str | None
    d3_admitted: bool
    owner_acceptance_sha256: str | None
    owner_verdict: str | None
    bounded_index_sha256: str | None
    security_handoff_sha256: str | None
    security_status: str | None
    lccoding_security_accepted: bool


def _required_text(value, code: str, label: str):
    if not isinstance(value, str) or not value:
        raise RunStateError(code, f"{label} is required")


def _required_hash(value, code: str, label: str):
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise RunStateError(code, f"{label} must be a lowercase sha256")


def _value(subject, field):
    if isinstance(subject, Mapping):
        return subject.get(field)
    return getattr(subject, field, None)


def _sorted_texts(value, code, label, *, allow_empty=True):
    if not isinstance(value, (list, tuple)):
        raise RunStateError(code, f"{label} must be an array")
    items = tuple(sorted(value))
    if (not allow_empty and not items) or any(not isinstance(item, str) or not item for item in items):
        raise RunStateError(code, f"{label} contains an invalid identity")
    if len(set(items)) != len(items):
        raise RunStateError(code, f"{label} contains duplicates")
    return items


def manifest_closure_payload(manifest):
    cells = tuple(
        sorted(
            (
                {
                    "cell_id": _value(cell, "cell_id"),
                    "cell_contract_sha256": _value(cell, "cell_contract_sha256"),
                    "required": _value(cell, "required"),
                }
                for cell in _value(manifest, "required_cells") or ()
            ),
            key=lambda cell: cell["cell_id"],
        )
    )
    return {
        "run_id": _value(manifest, "run_id"),
        "graph_id": _value(manifest, "graph_id"),
        "graph_version": _value(manifest, "graph_version"),
        "go_id": _value(manifest, "go_id"),
        "manifest_id": _value(manifest, "manifest_id"),
        "manifest_version": _value(manifest, "manifest_version"),
        "go_contract_sha256": _value(manifest, "go_contract_sha256"),
        "required_cells": cells,
        "prior_manifest_sha256": _value(manifest, "prior_manifest_sha256"),
    }


def manifest_closure_sha256_from_mapping(manifest):
    return canonical_sha256(manifest_closure_payload(manifest))


def go_candidate_payload(manifest, selected_cells):
    selected = tuple(
        sorted(
            (
                {
                    "cell_id": _value(item, "cell_id"),
                    "candidate_id": _value(item, "candidate_id"),
                    "candidate_sha256": _value(item, "candidate_sha256"),
                    "d0_artifact_sha256": _value(item, "d0_artifact_sha256"),
                    "d1_artifact_sha256": _value(item, "d1_artifact_sha256"),
                }
                for item in selected_cells
            ),
            key=lambda item: item["cell_id"],
        )
    )
    return {
        "go_id": _value(manifest, "go_id"),
        "manifest_id": _value(manifest, "manifest_id"),
        "manifest_version": _value(manifest, "manifest_version"),
        "manifest_closure_sha256": _value(manifest, "closure_sha256"),
        "selected_cells": selected,
    }


def go_candidate_sha256_from_mapping(manifest, selected_cells):
    return canonical_sha256(go_candidate_payload(manifest, selected_cells))


def derive_d3_eligibility(
    topology,
    graph_state,
    current_d2_by_go,
    admitted_d2_digests,
    final_candidate,
    graph_seam_claims,
    graph_seam_evidence_refs,
):
    """Derive immutable D3 input facts without issuing or interpreting a verdict."""
    if not isinstance(topology, FrozenGraphTopology) or not isinstance(
        graph_state, GraphStateProjection
    ):
        raise RunStateError(
            "D3_ELIGIBILITY_INPUT_INVALID", "current graph facts are required"
        )
    if not isinstance(current_d2_by_go, Mapping):
        raise RunStateError(
            "D3_ELIGIBILITY_INPUT_INVALID", "current_d2_by_go must be a mapping"
        )
    required = topology.required_go_ids
    failures = set()
    facts = {}
    for go_id, fact in current_d2_by_go.items():
        if not isinstance(fact, CurrentD2Fact) or fact.go_id != go_id:
            raise RunStateError("D3_ELIGIBILITY_INPUT_INVALID", str(go_id))
        facts[go_id] = fact
    if set(facts) != set(required):
        failures.add("R17_D3_REQUIRED_GO_SET_MISMATCH")
    if not set(required).issubset(graph_state.verified_go_ids):
        failures.add("R17_D3_GRAPH_EVENTS_INCOMPLETE")
    if graph_state.graph_sha256 != topology.graph_sha256:
        failures.add("R17_D3_GRAPH_DIGEST_MISMATCH")

    admitted = set(admitted_d2_digests)
    selected_digests = []
    for go_id in required:
        fact = facts.get(go_id)
        if fact is None:
            continue
        selected_digests.append(fact.artifact_sha256)
        if fact.verdict != "D2_PASS" or fact.artifact_sha256 not in admitted:
            failures.add("R17_D3_D2_SET_MISMATCH")
    if len(selected_digests) != len(required):
        failures.add("R17_D3_D2_SET_MISMATCH")

    candidate_id = _value(final_candidate, "candidate_id")
    candidate_sha256 = _value(final_candidate, "candidate_sha256")
    try:
        _required_text(candidate_id, "D3_FINAL_CANDIDATE_INVALID", "candidate_id")
        _required_hash(
            candidate_sha256, "D3_FINAL_CANDIDATE_INVALID", "candidate_sha256"
        )
    except RunStateError:
        failures.add("D3_FINAL_CANDIDATE_INVALID")
        candidate_id = candidate_id or ""
        candidate_sha256 = candidate_sha256 or ""
    try:
        seam_claims = _sorted_texts(
            tuple(graph_seam_claims),
            "R17_D3_GRAPH_SEAM_EVIDENCE_MISSING",
            "graph_seam_claims",
            allow_empty=False,
        )
        seam_evidence = _sorted_texts(
            tuple(graph_seam_evidence_refs),
            "R17_D3_GRAPH_SEAM_EVIDENCE_MISSING",
            "graph_seam_evidence_refs",
            allow_empty=False,
        )
    except RunStateError:
        failures.add("R17_D3_GRAPH_SEAM_EVIDENCE_MISSING")
        seam_claims = ()
        seam_evidence = ()
    return D3Eligibility(
        eligible=not failures,
        required_go_ids=required,
        admitted_d2_artifact_sha256s=tuple(selected_digests),
        graph_id=topology.graph_id,
        graph_version=topology.graph_version,
        graph_sha256=topology.graph_sha256,
        applied_graph_event_ids=graph_state.applied_event_ids,
        final_candidate_id=candidate_id,
        final_candidate_sha256=candidate_sha256,
        graph_seam_claims=seam_claims,
        graph_seam_evidence_refs=seam_evidence,
        failure_codes=tuple(sorted(failures)),
    )


def _graph_constraint(value):
    if not isinstance(value, Mapping):
        raise RunStateError("GRAPH_CONSTRAINT_INVALID", "mapping required")
    kind = value.get("type")
    if kind not in GRAPH_CONSTRAINT_TYPES:
        raise RunStateError("GRAPH_CONSTRAINT_INVALID", str(kind))
    references = _sorted_texts(value.get("references"), "GRAPH_CONSTRAINT_INVALID", "references", allow_empty=False)
    return GraphConstraint(kind=kind, references=references)


def _graph_node(value):
    if not isinstance(value, Mapping):
        raise RunStateError("GRAPH_NODE_INVALID", "mapping required")
    go_id = value.get("go_id")
    _required_text(go_id, "GRAPH_NODE_INVALID", "go_id")
    predecessors = _sorted_texts(value.get("predecessors"), "GRAPH_NODE_INVALID", f"{go_id}.predecessors")
    conflict_keys = _sorted_texts(value.get("conflict_keys"), "GRAPH_NODE_INVALID", f"{go_id}.conflict_keys")
    constraints_raw = value.get("constraints")
    if not isinstance(constraints_raw, (list, tuple)):
        raise RunStateError("GRAPH_CONSTRAINT_INVALID", f"{go_id}.constraints")
    constraints = tuple(sorted((_graph_constraint(item) for item in constraints_raw)))
    if len(set(constraints)) != len(constraints):
        raise RunStateError("GRAPH_CONSTRAINT_INVALID", f"{go_id}.constraints duplicate")
    required = value.get("required")
    if not isinstance(required, bool):
        raise RunStateError("GRAPH_NODE_INVALID", f"{go_id}.required")
    go_claim_sha256 = value.get("go_claim_sha256")
    acceptance_contract_sha256 = value.get("acceptance_contract_sha256")
    _required_hash(go_claim_sha256, "GRAPH_NODE_INVALID", f"{go_id}.go_claim_sha256")
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


def assert_acyclic(node_ids, predecessors_by_id):
    visiting, visited = set(), set()
    def visit(go_id):
        if go_id in visiting:
            raise RunStateError("R08_GRAPH_CYCLE", go_id)
        if go_id in visited:
            return
        visiting.add(go_id)
        for predecessor in sorted(predecessors_by_id[go_id]):
            visit(predecessor)
        visiting.remove(go_id)
        visited.add(go_id)
    for go_id in sorted(node_ids):
        visit(go_id)


def recompute_graph_topology(baseline, fallback_go_ids=()):
    run_id = _value(baseline, "run_id")
    graph_id = _value(baseline, "graph_id")
    graph_version = _value(baseline, "graph_version")
    baseline_candidate_id = _value(baseline, "candidate_id")
    for label, value in (("run_id", run_id), ("graph_id", graph_id), ("candidate_id", baseline_candidate_id)):
        _required_text(value, "GRAPH_BASELINE_INVALID", label)
    if not isinstance(graph_version, int) or isinstance(graph_version, bool) or graph_version < 1:
        raise RunStateError("GRAPH_BASELINE_INVALID", "graph_version")

    raw_nodes = _value(baseline, "nodes")
    explicit = isinstance(raw_nodes, (list, tuple)) and bool(raw_nodes)
    if explicit:
        nodes = tuple(sorted((_graph_node(item) for item in raw_nodes), key=lambda item: item.go_id))
    else:
        derived = tuple(sorted(set(fallback_go_ids)))
        if len(derived) != 1:
            raise RunStateError("GRAPH_TOPOLOGY_REQUIRED", "only a single-GO graph can be derived safely")
        nodes = (GraphNode(derived[0], (), True, (), (), "0" * 64, "0" * 64),)
    if len({node.go_id for node in nodes}) != len(nodes):
        raise RunStateError("GRAPH_NODE_DUPLICATE", "duplicate GO identity")
    node_ids = {node.go_id for node in nodes}

    raw_edges = _value(baseline, "edges") if explicit else ()
    if not isinstance(raw_edges, (list, tuple)):
        raise RunStateError("GRAPH_EDGE_INVALID", "edges must be an array")
    edges = tuple(sorted((_graph_edge(item) for item in raw_edges), key=lambda item: (item.source, item.target)))
    edge_pairs = {(edge.source, edge.target) for edge in edges}
    if len(edge_pairs) != len(edges):
        raise RunStateError("GRAPH_EDGE_DUPLICATE", "duplicate source/target pair")
    if any(edge.source not in node_ids or edge.target not in node_ids for edge in edges):
        raise RunStateError("GRAPH_EDGE_ENDPOINT_INVALID", "edge endpoint is not a GO")
    incoming = {go_id: set() for go_id in node_ids}
    outgoing = {go_id: set() for go_id in node_ids}
    for edge in edges:
        incoming[edge.target].add(edge.source)
        outgoing[edge.source].add(edge.target)
    for node in nodes:
        if set(node.predecessors) != incoming[node.go_id]:
            raise RunStateError("GRAPH_PREDECESSOR_MISMATCH", node.go_id)

    assert_acyclic(node_ids, incoming)

    derived_entries = tuple(sorted(go_id for go_id in node_ids if not incoming[go_id]))
    derived_terminals = tuple(sorted(go_id for go_id in node_ids if not outgoing[go_id]))
    derived_required = tuple(sorted(node.go_id for node in nodes if node.required))
    if explicit:
        entry_go_ids = _sorted_texts(_value(baseline, "entry_go_ids"), "GRAPH_ENTRY_SET_INVALID", "entry_go_ids")
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
            raise RunStateError("GRAPH_ENTRY_SET_INVALID", "declared entry set differs from topology")
        if terminal_go_ids != derived_terminals:
            raise RunStateError("GRAPH_TERMINAL_SET_INVALID", "declared terminal set differs from topology")
        if required_go_ids != derived_required:
            raise RunStateError("GRAPH_REQUIRED_GO_COVERAGE_INVALID", "declared required GO set differs from nodes")
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
        raise RunStateError("GRAPH_REQUIRED_GO_COVERAGE_INVALID", "required GO is unreachable")

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
        raise RunStateError("GRAPH_DIGEST_MISMATCH", "declared graph hash differs from recomputation")
    return dataclasses.replace(provisional, graph_sha256=graph_sha256)


def maximum_compatible_ids(candidate_ids, conflict_keys_by_id, resource_claims_by_id=None,
                           resource_capacity=None, occupied_conflict_keys=(), occupied_resources=None):
    candidates = tuple(sorted(set(candidate_ids)))
    claims_by_id = resource_claims_by_id or {}
    capacities = resource_capacity or {}
    best = ()

    def search(index, chosen, used_keys, used_resources):
        nonlocal best
        if len(chosen) + len(candidates) - index < len(best):
            return
        if index == len(candidates):
            if len(chosen) > len(best) or (len(chosen) == len(best) and chosen < best):
                best = chosen
            return
        candidate_id = candidates[index]
        keys = set(conflict_keys_by_id.get(candidate_id, ()))
        claims = claims_by_id.get(candidate_id, {})
        resources_fit = all(
            used_resources.get(resource, 0) + amount <= capacities.get(resource, 0)
            for resource, amount in claims.items() if resource in capacities
        )
        if not (keys & used_keys) and resources_fit:
            next_resources = dict(used_resources)
            for resource, amount in claims.items():
                next_resources[resource] = next_resources.get(resource, 0) + amount
            search(index + 1, chosen + (candidate_id,), used_keys | keys, next_resources)
        search(index + 1, chosen, used_keys, used_resources)

    search(0, (), set(occupied_conflict_keys), dict(occupied_resources or {}))
    return best


def project_graph_state(topology, verified_go_ids=(), applied_event_ids=()):
    if not isinstance(topology, FrozenGraphTopology):
        raise RunStateError("GRAPH_TOPOLOGY_INVALID", "FrozenGraphTopology required")
    verified = _sorted_texts(tuple(verified_go_ids), "GRAPH_VERIFIED_SET_INVALID", "verified_go_ids")
    node_by_id = {node.go_id: node for node in topology.nodes}
    if not set(verified).issubset(node_by_id):
        raise RunStateError("GRAPH_VERIFIED_SET_INVALID", "unknown GO")
    eligible = tuple(node for node in topology.nodes if node.go_id not in verified
                     and set(node.predecessors).issubset(verified) and not node.constraints)
    active = maximum_compatible_ids((node.go_id for node in eligible),
                                    {node.go_id: node.conflict_keys for node in eligible})
    waiting = tuple(sorted(set(node_by_id) - set(verified) - set(active)))
    return GraphStateProjection(
        graph_sha256=topology.graph_sha256,
        verified_go_ids=verified,
        waiting_go_ids=waiting,
        active_go_ids=active,
        applied_event_ids=tuple(applied_event_ids),
    )
