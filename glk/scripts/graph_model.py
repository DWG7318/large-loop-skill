from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple


WAITING_GO = "WAITING_GO"
ACTIVE_GO = "ACTIVE_GO"
GO_VERIFIED = "GO_VERIFIED"
BLOCKED = "BLOCKED"
SUPERSEDED = "SUPERSEDED"
CANCELLED = "CANCELLED"

IMPLEMENTING = "IMPLEMENTING"
CHECKING = "CHECKING"
VERIFYING = "VERIFYING"
REWORK = "REWORK"

CONFIRMED = "CONFIRMED"
SUSPECTED = "SUSPECTED"

UNAFFECTED = "UNAFFECTED"
REVERIFY = "REVERIFY"
REWORK_IMPACT = "REWORK"
QUARANTINE = "QUARANTINE"

IMPACT_DISPOSITIONS = {UNAFFECTED, REVERIFY, REWORK_IMPACT, QUARANTINE}

WAITING_REASON_TYPES = {
    "DEPENDENCY_UNMET",
    "WRITE_CONFLICT",
    "RESOURCE",
    "ISOLATION",
    "SAFETY",
    "CONFLICT",
}


class GraphError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class WaitingReason:
    kind: str
    references: Tuple[str, ...] = ()

    def __post_init__(self):
        if self.kind not in WAITING_REASON_TYPES:
            raise GraphError(f"invalid waiting reason type: {self.kind}")


@dataclass(frozen=True)
class FormalResolution:
    resolution_id: str
    kind: str
    amendment_id: str
    releases_successors: bool
    removes_required: bool

    def __post_init__(self):
        if self.kind not in {SUPERSEDED, CANCELLED}:
            raise GraphError("formal resolution kind must be SUPERSEDED or CANCELLED")
        if not self.resolution_id or not self.amendment_id:
            raise GraphError("formal resolution requires resolution and amendment identities")


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    justification: str
    source_claim_or_output_refs: Tuple[str, ...]
    target_input_or_assumption_refs: Tuple[str, ...]
    consumption_evidence_refs: Tuple[str, ...]

    def __post_init__(self):
        if not self.source or not self.target:
            raise GraphError("dependency edge endpoints are required")
        if not self.justification:
            raise GraphError("dependency edge D2 justification is required")
        if self.source == self.target:
            raise GraphError("dependency edge cannot target its source")
        bindings = [
            self.source_claim_or_output_refs,
            self.target_input_or_assumption_refs,
            self.consumption_evidence_refs,
        ]
        if any(not values or any(not value for value in values) for values in bindings):
            raise GraphError("dependency edge requires complete consumption bindings")


@dataclass(frozen=True)
class GoCausalTrace:
    incident_id: str
    graph_version: int
    observed_at_go: str
    source_go: str
    source_candidate_ref: str
    evidence_refs: Tuple[str, ...]
    symptom_gos: Tuple[str, ...]
    causal_path: Tuple[DependencyEdge, ...]
    excluded_edges: Tuple[DependencyEdge, ...]
    stopping_reason: str
    confirmation_status: str

    def __post_init__(self):
        if self.confirmation_status not in {CONFIRMED, SUSPECTED}:
            raise GraphError("causal trace status must be CONFIRMED or SUSPECTED")
        if not self.incident_id or not self.source_candidate_ref or not self.evidence_refs:
            raise GraphError("causal trace requires incident, candidate, and evidence refs")
        if self.source_go in self.symptom_gos:
            raise GraphError("causal source GO cannot be a symptom annotation")
        if self.source_go != self.observed_at_go and self.observed_at_go not in self.symptom_gos:
            raise GraphError("observation GO must be a downstream symptom annotation")


@dataclass(frozen=True)
class ImpactItem:
    go_id: str
    disposition: str
    invalidated_candidate_refs: Tuple[str, ...] = ()
    invalidated_receipt_refs: Tuple[str, ...] = ()
    evidence_refs: Tuple[str, ...] = ()

    def __post_init__(self):
        if self.disposition not in IMPACT_DISPOSITIONS:
            raise GraphError(f"invalid impact disposition: {self.disposition}")


@dataclass(frozen=True)
class ImpactProjection:
    incident_id: str
    from_graph_version: int
    to_graph_version: int
    changed_refs: Tuple[str, ...]
    items: Tuple[ImpactItem, ...]

    @property
    def affected_gos(self) -> Tuple[str, ...]:
        return tuple(
            item.go_id for item in self.items if item.disposition != UNAFFECTED
        )

    @property
    def invalidated_receipt_refs(self) -> Tuple[str, ...]:
        return tuple(
            sorted(
                {
                    receipt
                    for item in self.items
                    for receipt in item.invalidated_receipt_refs
                }
            )
        )

    def disposition(self, go_id: str) -> str:
        for item in self.items:
            if item.go_id == go_id:
                return item.disposition
        raise GraphError(f"impact projection has no GO: {go_id}")


@dataclass
class Go:
    go_id: str
    predecessors: Set[str] = field(default_factory=set)
    required: bool = True
    conflict_keys: Set[str] = field(default_factory=set)
    constraints: Set[str] = field(default_factory=set)
    state: str = "FROZEN"
    phase: Optional[str] = None
    waiting: List[WaitingReason] = field(default_factory=list)
    candidate_id: Optional[str] = None
    d0_receipt_id: Optional[str] = None
    d1_receipt_id: Optional[str] = None
    d2_receipt_id: Optional[str] = None
    checker_context_ref: Optional[str] = None
    verifier_context_ref: Optional[str] = None
    reactivation_phase: Optional[str] = None
    resolution: Optional[FormalResolution] = None

    def __post_init__(self):
        if not self.go_id:
            raise GraphError("GO id is required")


class GoGraph:
    """Run-scoped acyclic GO graph with maximal-safe automatic activation.

    Every unresolved GO is either WAITING_GO with typed reasons or ACTIVE_GO.
    ACTIVE_GO remains the graph-level state while the GO moves through
    implementation, checking, rework, and GO verification phases.
    """

    def __init__(
        self,
        gos: Iterable[Go],
        edges: Iterable[DependencyEdge] = (),
        graph_version: int = 1,
    ):
        go_list = list(gos)
        self.gos: Dict[str, Go] = {go.go_id: go for go in go_list}
        self.graph_version = graph_version
        self.edges = tuple(edges)
        self.amendment_history = []
        if len(self.gos) != len(go_list):
            raise GraphError("duplicate GO id")
        if graph_version < 1:
            raise GraphError("graph version must be positive")
        for go in go_list:
            missing = go.predecessors - set(self.gos)
            if missing:
                raise GraphError(
                    f"missing predecessors for {go.go_id}: {sorted(missing)}"
                )
        edge_pairs = set()
        for edge in self.edges:
            if edge.source not in self.gos or edge.target not in self.gos:
                raise GraphError("dependency edge endpoint is not a GO")
            if edge.source not in self.gos[edge.target].predecessors:
                raise GraphError("dependency edge must match the target predecessor set")
            pair = (edge.source, edge.target)
            if pair in edge_pairs:
                raise GraphError("duplicate dependency edge")
            edge_pairs.add(pair)
        self._assert_acyclic()
        self._refresh_active_set()

    def _assert_acyclic(self):
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def visit(go_id: str):
            if go_id in visiting:
                raise GraphError("cycle detected")
            if go_id in visited:
                return
            visiting.add(go_id)
            for predecessor in self.gos[go_id].predecessors:
                visit(predecessor)
            visiting.remove(go_id)
            visited.add(go_id)

        for go_id in self.gos:
            visit(go_id)

    def active(self) -> List[str]:
        return sorted(
            go.go_id for go in self.gos.values() if go.state == ACTIVE_GO
        )

    def waiting(self) -> List[str]:
        return sorted(
            go.go_id for go in self.gos.values() if go.state == WAITING_GO
        )

    def state(self, go_id: str) -> str:
        return self._go(go_id).state

    def phase(self, go_id: str) -> Optional[str]:
        return self._go(go_id).phase

    def predecessors(self, go_id: str) -> Set[str]:
        return set(self._go(go_id).predecessors)

    def waiting_reasons(self, go_id: str) -> List[WaitingReason]:
        return list(self._go(go_id).waiting)

    def confirm_causal_trace(
        self,
        incident_id: str,
        observed_at_go: str,
        source_go: str,
        source_candidate_ref: str,
        evidence_refs: Tuple[str, ...],
    ) -> GoCausalTrace:
        return self.trace_causal_incident(
            incident_id=incident_id,
            observed_at_go=observed_at_go,
            source_go=source_go,
            source_candidate_ref=source_candidate_ref,
            evidence_refs=evidence_refs,
            confirmation_status=CONFIRMED,
        )

    def trace_causal_incident(
        self,
        incident_id: str,
        observed_at_go: str,
        source_go: str,
        source_candidate_ref: str,
        evidence_refs: Tuple[str, ...],
        confirmation_status: str,
    ) -> GoCausalTrace:
        self._go(observed_at_go)
        self._go(source_go)
        path = self._reverse_causal_slice(source_go, observed_at_go)
        if source_go != observed_at_go and not path:
            raise GraphError("no bound consumption path connects source and observation")
        self._assert_causal_slice_fully_bound(path, source_go)
        symptom_gos = () if source_go == observed_at_go else (observed_at_go,)
        excluded_edges = self._excluded_incoming_edges(path, source_go)
        return GoCausalTrace(
            incident_id=incident_id,
            graph_version=self.graph_version,
            observed_at_go=observed_at_go,
            source_go=source_go,
            source_candidate_ref=source_candidate_ref,
            evidence_refs=tuple(evidence_refs),
            symptom_gos=symptom_gos,
            causal_path=path,
            excluded_edges=excluded_edges,
            stopping_reason="confirmed source reached",
            confirmation_status=confirmation_status,
        )

    def apply_causal_amendment(
        self,
        trace: GoCausalTrace,
        changed_refs: Tuple[str, ...],
        dispositions: Mapping[str, str],
        new_graph_version: int,
        impact_evidence: Optional[Mapping[str, Tuple[str, ...]]] = None,
    ):
        if trace.confirmation_status != CONFIRMED:
            raise GraphError("causal amendment requires a CONFIRMED trace")
        if trace.graph_version != self.graph_version:
            raise GraphError("causal trace does not bind the current graph version")
        if new_graph_version <= self.graph_version:
            raise GraphError("causal amendment must advance the graph version")
        if not changed_refs or any(not reference for reference in changed_refs):
            raise GraphError("causal amendment requires changed refs")
        source = self._go(trace.source_go)
        self._go(trace.observed_at_go)
        if source.candidate_id != trace.source_candidate_ref:
            raise GraphError("causal trace does not bind the current source candidate")
        expected_path = self._reverse_causal_slice(
            trace.source_go, trace.observed_at_go
        )
        if trace.causal_path != expected_path:
            raise GraphError("causal amendment requires the confirmed current path")
        if trace.excluded_edges != self._excluded_incoming_edges(
            expected_path, trace.source_go
        ):
            raise GraphError("causal amendment requires complete excluded-edge evidence")

        affected = self._forward_impact_slice(trace.source_go, set(changed_refs))
        if trace.source_go != trace.observed_at_go:
            causal_first_hops = [
                edge for edge in trace.causal_path if edge.source == trace.source_go
            ]
            if not any(
                set(edge.source_claim_or_output_refs) & set(changed_refs)
                for edge in causal_first_hops
            ):
                raise GraphError("changed refs do not intersect the confirmed causal path")

        provided = set(dispositions)
        if provided != affected:
            raise GraphError(
                "impact dispositions must cover exactly the affected GO slice"
            )
        for go_id, disposition in dispositions.items():
            self._go(go_id)
            if disposition not in IMPACT_DISPOSITIONS - {UNAFFECTED}:
                raise GraphError("affected GO requires a non-UNAFFECTED disposition")
        if (
            impact_evidence is None
            or set(impact_evidence) != affected
            or any(
                not references or any(not reference for reference in references)
                for references in impact_evidence.values()
            )
        ):
            raise GraphError("impact evidence must cover every affected GO")

        items = []
        for go_id in sorted(self.gos):
            go = self.gos[go_id]
            if go_id not in affected:
                items.append(ImpactItem(go_id=go_id, disposition=UNAFFECTED))
                continue
            disposition = dispositions[go_id]
            if disposition == REVERIFY:
                if not go.candidate_id or not go.d1_receipt_id:
                    raise GraphError("REVERIFY requires a current candidate and D1 receipt")
                candidates = ()
                receipts = tuple(value for value in [go.d2_receipt_id] if value)
            else:
                candidates = tuple(value for value in [go.candidate_id] if value)
                receipts = tuple(
                    value
                    for value in [go.d0_receipt_id, go.d1_receipt_id, go.d2_receipt_id]
                    if value
                )
            items.append(
                ImpactItem(
                    go_id=go_id,
                    disposition=disposition,
                    invalidated_candidate_refs=candidates,
                    invalidated_receipt_refs=receipts,
                    evidence_refs=tuple(impact_evidence[go_id]),
                )
            )

        projection = ImpactProjection(
            incident_id=trace.incident_id,
            from_graph_version=self.graph_version,
            to_graph_version=new_graph_version,
            changed_refs=tuple(changed_refs),
            items=tuple(items),
        )
        for go_id in affected:
            go = self.gos[go_id]
            disposition = dispositions[go_id]
            go.state = "FROZEN"
            go.phase = None
            go.waiting = []
            go.d2_receipt_id = None
            go.verifier_context_ref = None
            if disposition == REVERIFY:
                go.reactivation_phase = VERIFYING
                continue
            go.reactivation_phase = (
                REWORK if disposition == REWORK_IMPACT else IMPLEMENTING
            )
            go.candidate_id = None
            go.d0_receipt_id = None
            go.d1_receipt_id = None
            go.checker_context_ref = None
        self.graph_version = new_graph_version
        self.amendment_history.append(projection)
        self._refresh_active_set()
        return projection

    def _reverse_causal_slice(
        self, source_go: str, observed_at_go: str
    ) -> Tuple[DependencyEdge, ...]:
        if source_go == observed_at_go:
            return ()

        forward = {source_go}
        changed = True
        while changed:
            changed = False
            for edge in self.edges:
                if edge.source in forward and edge.target not in forward:
                    forward.add(edge.target)
                    changed = True

        reverse = {observed_at_go}
        changed = True
        while changed:
            changed = False
            for edge in self.edges:
                if edge.target in reverse and edge.source not in reverse:
                    reverse.add(edge.source)
                    changed = True

        if observed_at_go not in forward:
            return ()
        return tuple(
            sorted(
                (
                    edge
                    for edge in self.edges
                    if edge.source in forward and edge.target in reverse
                ),
                key=lambda edge: (edge.source, edge.target),
            )
        )

    def _excluded_incoming_edges(
        self, path: Tuple[DependencyEdge, ...], source_go: str
    ) -> Tuple[DependencyEdge, ...]:
        path_targets = {edge.target for edge in path} | {source_go}
        path_set = set(path)
        return tuple(
            sorted(
                (
                    edge
                    for edge in self.edges
                    if edge.target in path_targets and edge not in path_set
                ),
                key=lambda edge: (edge.source, edge.target),
            )
        )

    def _assert_causal_slice_fully_bound(
        self, path: Tuple[DependencyEdge, ...], source_go: str
    ):
        governed_targets = {edge.target for edge in path} | {source_go}
        bound_pairs = {(edge.source, edge.target) for edge in self.edges}
        for target in governed_targets:
            for predecessor in self.gos[target].predecessors:
                if (predecessor, target) not in bound_pairs:
                    raise GraphError(
                        f"unbound incoming dependency on causal path: {predecessor}->{target}"
                    )

    def _forward_impact_slice(
        self, source_go: str, changed_refs: Set[str]
    ) -> Set[str]:
        affected = {source_go}
        queue = []
        for edge in self.edges:
            if edge.source == source_go and (
                set(edge.source_claim_or_output_refs) & changed_refs
            ):
                if edge.target not in affected:
                    affected.add(edge.target)
                    queue.append(edge.target)

        while queue:
            current = queue.pop(0)
            for edge in self.edges:
                if edge.source == current and edge.target not in affected:
                    affected.add(edge.target)
                    queue.append(edge.target)
        return affected

    def clear_constraint(self, go_id: str, constraint: str):
        go = self._go(go_id)
        if constraint not in go.constraints:
            raise GraphError(f"constraint is not present on {go_id}: {constraint}")
        go.constraints.remove(constraint)
        self._refresh_active_set()

    def start_checking(self, go_id: str, candidate_id: str, d0_receipt_id: str):
        go = self._go(go_id)
        self._require_active_phase(go, {IMPLEMENTING, REWORK})
        if not candidate_id or not d0_receipt_id:
            raise GraphError("candidate and D0 receipt identities are required")
        go.candidate_id = candidate_id
        go.d0_receipt_id = d0_receipt_id
        go.d1_receipt_id = None
        go.d2_receipt_id = None
        go.checker_context_ref = None
        go.verifier_context_ref = None
        go.phase = CHECKING

    def d1_pass(
        self,
        go_id: str,
        candidate_id: str,
        d1_receipt_id: str,
        checker_context_ref: str,
    ):
        go = self._go(go_id)
        self._require_active_phase(go, {CHECKING})
        self._require_candidate(go, candidate_id)
        if not d1_receipt_id or not checker_context_ref:
            raise GraphError("D1 receipt and Checker context are required")
        go.d1_receipt_id = d1_receipt_id
        go.checker_context_ref = checker_context_ref
        go.phase = VERIFYING

    def d1_fail(self, go_id: str, candidate_id: str):
        go = self._go(go_id)
        self._require_active_phase(go, {CHECKING})
        self._require_candidate(go, candidate_id)
        go.phase = REWORK

    def d2_pass(
        self,
        go_id: str,
        candidate_id: str,
        d2_receipt_id: str,
        verifier_context_ref: str,
    ):
        go = self._go(go_id)
        if not go.d1_receipt_id:
            raise GraphError("D2 requires a valid D1 PASS receipt")
        self._require_active_phase(go, {VERIFYING})
        self._require_candidate(go, candidate_id)
        if not d2_receipt_id or not verifier_context_ref:
            raise GraphError("D2 receipt and GO Verifier context are required")
        if verifier_context_ref == go.checker_context_ref:
            raise GraphError("GO Verifier must be independent from the Checker")
        go.d2_receipt_id = d2_receipt_id
        go.verifier_context_ref = verifier_context_ref
        go.state = GO_VERIFIED
        go.phase = None
        go.waiting = []
        self._refresh_active_set()

    def cancel(self, go_id: str):
        self._go(go_id)
        raise GraphError("cancellation requires a formal resolution")

    def apply_resolution(self, go_id: str, resolution: FormalResolution):
        go = self._go(go_id)
        if go.state == GO_VERIFIED:
            raise GraphError("a verified GO cannot be resolved away")
        go.resolution = resolution
        go.state = resolution.kind
        go.phase = None
        go.waiting = []
        self._refresh_active_set()

    def complete_prerequisites(self) -> bool:
        return all(
            (not go.required)
            or go.state == GO_VERIFIED
            or bool(go.resolution and go.resolution.removes_required)
            for go in self.gos.values()
        )

    def _refresh_active_set(self):
        active_ids = self.active()
        candidates: List[str] = []
        for go_id in sorted(self.gos):
            go = self.gos[go_id]
            if go.state in {GO_VERIFIED, BLOCKED, SUPERSEDED, CANCELLED, ACTIVE_GO}:
                continue

            reasons = self._base_waiting_reasons(go)
            conflicting_active = [
                active_id
                for active_id in active_ids
                if self.gos[active_id].conflict_keys & go.conflict_keys
            ]
            if not reasons and conflicting_active:
                reasons.append(WaitingReason("CONFLICT", tuple(conflicting_active)))

            if reasons:
                go.state = WAITING_GO
                go.phase = None
                go.waiting = reasons
                continue
            candidates.append(go_id)

        chosen = self._maximum_compatible_subset(candidates)
        chosen_set = set(chosen)
        final_active = active_ids + chosen
        for go_id in candidates:
            go = self.gos[go_id]
            if go_id in chosen_set:
                go.state = ACTIVE_GO
                go.phase = go.reactivation_phase or IMPLEMENTING
                go.reactivation_phase = None
                go.waiting = []
                continue
            conflicts = tuple(
                active_id
                for active_id in final_active
                if self.gos[active_id].conflict_keys & go.conflict_keys
            )
            if not conflicts:
                raise GraphError(
                    f"activation calculation was not maximal; {go_id} can be added"
                )
            go.state = WAITING_GO
            go.phase = None
            go.waiting = [WaitingReason("CONFLICT", conflicts)]

    def _maximum_compatible_subset(self, candidates: List[str]) -> List[str]:
        active_keys: Set[str] = set()
        for go_id in self.active():
            active_keys.update(self.gos[go_id].conflict_keys)

        compatible = [
            go_id
            for go_id in sorted(candidates)
            if not (self.gos[go_id].conflict_keys & active_keys)
        ]
        best: List[str] = []

        def search(index: int, chosen: List[str], used_keys: Set[str]):
            nonlocal best
            if len(chosen) + len(compatible) - index < len(best):
                return
            if index == len(compatible):
                if len(chosen) > len(best) or (
                    len(chosen) == len(best) and tuple(chosen) < tuple(best)
                ):
                    best = list(chosen)
                return
            go_id = compatible[index]
            keys = self.gos[go_id].conflict_keys
            if not (keys & used_keys):
                search(index + 1, chosen + [go_id], used_keys | keys)
            search(index + 1, chosen, used_keys)

        search(0, [], set(active_keys))
        return best

    def _base_waiting_reasons(self, go: Go) -> List[WaitingReason]:
        unmet = tuple(
            sorted(
                predecessor
                for predecessor in go.predecessors
                if not self._predecessor_satisfied(self.gos[predecessor])
            )
        )
        reasons: List[WaitingReason] = []
        if unmet:
            reasons.append(WaitingReason("DEPENDENCY_UNMET", unmet))
        for constraint in sorted(go.constraints):
            kind, separator, reference = constraint.partition(":")
            refs = (reference,) if separator and reference else ()
            reasons.append(WaitingReason(kind, refs))
        return reasons

    @staticmethod
    def _predecessor_satisfied(go: Go) -> bool:
        return go.state == GO_VERIFIED or bool(
            go.resolution and go.resolution.releases_successors
        )

    def _go(self, go_id: str) -> Go:
        try:
            return self.gos[go_id]
        except KeyError as exc:
            raise GraphError(f"unknown GO: {go_id}") from exc

    @staticmethod
    def _require_active_phase(go: Go, phases: Set[str]):
        if go.state != ACTIVE_GO or go.phase not in phases:
            expected = ", ".join(sorted(phases))
            raise GraphError(f"{go.go_id} is not ACTIVE_GO in phase {expected}")

    @staticmethod
    def _require_candidate(go: Go, candidate_id: str):
        if not candidate_id or go.candidate_id != candidate_id:
            raise GraphError("receipt candidate does not match the frozen candidate")
