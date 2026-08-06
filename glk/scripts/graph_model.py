from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from graph_kernel import (
    GraphKernelError,
    assert_acyclic,
    causal_impact_slice,
    maximum_compatible_ids,
    select_causal_path,
    validate_source_seed_disposition,
)


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

SEED_CANDIDATE = "CANDIDATE"
SEED_EVIDENCE = "EVIDENCE"
SEED_CLAIM_OR_OUTPUT = "CLAIM_OR_OUTPUT"
IMPACT_SEED_KINDS = {SEED_CANDIDATE, SEED_EVIDENCE, SEED_CLAIM_OR_OUTPUT}

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


def _kernel_fact(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except GraphKernelError as error:
        raise GraphError(error.detail) from error


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
class CausalEdgeSelection:
    source: str
    target: str
    incident_evidence_refs: Tuple[str, ...]
    confirmation_status: str

    def __post_init__(self):
        if not self.source or not self.target or self.source == self.target:
            raise GraphError("causal edge selection requires distinct endpoints")
        if (
            not self.incident_evidence_refs
            or any(not reference for reference in self.incident_evidence_refs)
        ):
            raise GraphError("causal edge selection requires incident evidence")
        if self.confirmation_status not in {CONFIRMED, SUSPECTED}:
            raise GraphError("causal edge selection has invalid confirmation status")


@dataclass(frozen=True)
class CausalPathStep:
    edge: DependencyEdge
    incident_evidence_refs: Tuple[str, ...]
    confirmation_status: str

    @property
    def source(self) -> str:
        return self.edge.source

    @property
    def target(self) -> str:
        return self.edge.target


def _causal_steps(facts):
    return tuple(
        CausalPathStep(edge=edge, incident_evidence_refs=refs, confirmation_status=status)
        for edge, refs, status in facts
    )


@dataclass(frozen=True)
class GoCausalTrace:
    incident_id: str
    graph_version: int
    observed_at_go: str
    source_go: str
    source_candidate_ref: str
    evidence_refs: Tuple[str, ...]
    symptom_gos: Tuple[str, ...]
    causal_path: Tuple[CausalPathStep, ...]
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
class ImpactSeed:
    kind: str
    ref: str

    def __post_init__(self):
        if self.kind not in IMPACT_SEED_KINDS:
            raise GraphError(f"invalid impact seed kind: {self.kind}")
        if not self.ref:
            raise GraphError("impact seed ref is required")


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
    impact_seeds: Tuple[ImpactSeed, ...]
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
    d2_receipt_sha256: Optional[str] = None
    d2_admission_id: Optional[str] = None
    admitted_d2_sha256: Optional[str] = None
    graph_event_id: Optional[str] = None
    checker_context_ref: Optional[str] = None
    verifier_context_ref: Optional[str] = None
    reactivation_phase: Optional[str] = None
    resolution: Optional[FormalResolution] = None
    cell_manifest_id: Optional[str] = None
    cell_manifest_version: Optional[int] = None
    cell_manifest_sha256: Optional[str] = None
    required_cell_ids: Tuple[str, ...] = ()
    d0_receipt_ids_by_cell: Dict[str, str] = field(default_factory=dict)
    d1_receipt_ids_by_cell: Dict[str, str] = field(default_factory=dict)
    go_candidate_closure_sha256: Optional[str] = None
    resource_claims: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.go_id:
            raise GraphError("GO id is required")
        if any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, int)
            or value < 0
            for key, value in self.resource_claims.items()
        ):
            raise GraphError("GO resource claims must be non-negative integer mappings")


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
        resource_capacity: Optional[Mapping[str, int]] = None,
    ):
        go_list = list(gos)
        self.gos: Dict[str, Go] = {go.go_id: go for go in go_list}
        self.graph_version = graph_version
        self.edges = tuple(edges)
        self.amendment_history = []
        self.resource_capacity = dict(resource_capacity or {})
        if len(self.gos) != len(go_list):
            raise GraphError("duplicate GO id")
        if graph_version < 1:
            raise GraphError("graph version must be positive")
        if any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, int)
            or value < 0
            for key, value in self.resource_capacity.items()
        ):
            raise GraphError("resource capacity must be a non-negative integer mapping")
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
        try:
            assert_acyclic(self.gos, {go_id: go.predecessors for go_id, go in self.gos.items()})
        except GraphKernelError as error:
            raise GraphError("cycle detected") from error
        self._refresh_active_set()

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
        symptom_gos: Tuple[str, ...],
        selected_path: Tuple[CausalEdgeSelection, ...],
    ) -> GoCausalTrace:
        return self.trace_causal_incident(
            incident_id=incident_id,
            observed_at_go=observed_at_go,
            source_go=source_go,
            source_candidate_ref=source_candidate_ref,
            evidence_refs=evidence_refs,
            symptom_gos=symptom_gos,
            selected_path=selected_path,
            confirmation_status=CONFIRMED,
        )

    def trace_causal_incident(
        self,
        incident_id: str,
        observed_at_go: str,
        source_go: str,
        source_candidate_ref: str,
        evidence_refs: Tuple[str, ...],
        symptom_gos: Tuple[str, ...],
        selected_path: Tuple[CausalEdgeSelection, ...],
        confirmation_status: str,
    ) -> GoCausalTrace:
        selected_facts, excluded_edges = _kernel_fact(
            select_causal_path,
            self.gos,
            self.edges,
            observed_at_go=observed_at_go,
            source_go=source_go,
            source_candidate_ref=source_candidate_ref,
            evidence_refs=tuple(evidence_refs),
            symptom_gos=tuple(symptom_gos),
            selected_path=tuple(selected_path),
            confirmation_status=confirmation_status,
        )
        path = _causal_steps(selected_facts)
        return GoCausalTrace(
            incident_id=incident_id,
            graph_version=self.graph_version,
            observed_at_go=observed_at_go,
            source_go=source_go,
            source_candidate_ref=source_candidate_ref,
            evidence_refs=tuple(evidence_refs),
            symptom_gos=tuple(symptom_gos),
            causal_path=path,
            excluded_edges=excluded_edges,
            stopping_reason="confirmed source reached",
            confirmation_status=confirmation_status,
        )

    def apply_causal_amendment(
        self,
        trace: GoCausalTrace,
        impact_seeds: Tuple[ImpactSeed, ...],
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
        if not impact_seeds:
            raise GraphError("causal amendment requires impact seeds")
        for symptom_go in trace.symptom_gos:
            if symptom_go not in self.gos:
                raise GraphError(f"unknown symptom GO: {symptom_go}")
        if any(not isinstance(seed, ImpactSeed) for seed in impact_seeds):
            raise GraphError("causal amendment requires typed impact seeds")
        try:
            reconstructed = tuple(
                CausalEdgeSelection(
                    source=step.source,
                    target=step.target,
                    incident_evidence_refs=step.incident_evidence_refs,
                    confirmation_status=step.confirmation_status,
                )
                for step in trace.causal_path
            )
        except (AttributeError, TypeError) as error:
            raise GraphError("selected path evidence has an invalid shape") from error
        try:
            expected_facts, expected_excluded = _kernel_fact(
                select_causal_path,
                self.gos,
                self.edges,
                observed_at_go=trace.observed_at_go,
                source_go=trace.source_go,
                source_candidate_ref=trace.source_candidate_ref,
                evidence_refs=trace.evidence_refs,
                symptom_gos=trace.symptom_gos,
                selected_path=reconstructed,
                confirmation_status=trace.confirmation_status,
            )
            expected_path = _causal_steps(expected_facts)
        except GraphError as error:
            if "unknown symptom GO" in str(error):
                raise
            raise GraphError(f"selected path evidence is no longer valid: {error}") from error
        if (
            trace.causal_path != expected_path
            or trace.excluded_edges != expected_excluded
            or trace.stopping_reason != "confirmed source reached"
        ):
            raise GraphError("selected path evidence is incomplete or stale")

        affected = set(
            _kernel_fact(
                causal_impact_slice,
                self.gos,
                self.edges,
                trace,
                tuple(impact_seeds),
            )
        )

        provided = set(dispositions)
        if provided != affected:
            raise GraphError(
                "impact dispositions must cover exactly the affected GO slice"
            )
        for go_id, disposition in dispositions.items():
            self._go(go_id)
            if disposition not in IMPACT_DISPOSITIONS - {UNAFFECTED}:
                raise GraphError("affected GO requires a non-UNAFFECTED disposition")
        _kernel_fact(
            validate_source_seed_disposition,
            trace,
            tuple(impact_seeds),
            dispositions,
        )
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
            impact_seeds=tuple(impact_seeds),
            items=tuple(items),
        )
        for go_id in affected:
            go = self.gos[go_id]
            disposition = dispositions[go_id]
            go.state = "FROZEN"
            go.phase = None
            go.waiting = []
            go.d2_receipt_id = None
            go.d2_receipt_sha256 = None
            go.d2_admission_id = None
            go.admitted_d2_sha256 = None
            go.graph_event_id = None
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

    def clear_constraint(self, go_id: str, constraint: str):
        go = self._go(go_id)
        if constraint not in go.constraints:
            raise GraphError(f"constraint is not present on {go_id}: {constraint}")
        go.constraints.remove(constraint)
        self._refresh_active_set()

    def bind_cell_manifest(
        self,
        go_id: str,
        manifest_id: str,
        manifest_version: int,
        manifest_sha256: str,
        required_cell_ids: Iterable[str],
    ):
        go = self._go(go_id)
        cells = tuple(sorted(required_cell_ids))
        if not manifest_id or not isinstance(manifest_version, int) or manifest_version < 1:
            raise GraphError("CELL manifest identity and positive version are required")
        if len(manifest_sha256) != 64:
            raise GraphError("CELL manifest sha256 is required")
        if not cells or len(set(cells)) != len(cells) or any(not cell_id for cell_id in cells):
            raise GraphError("CELL manifest requires a unique non-empty required CELL set")
        if go.cell_manifest_version is not None and manifest_version <= go.cell_manifest_version:
            raise GraphError("CELL manifest amendment version must increase")
        go.cell_manifest_id = manifest_id
        go.cell_manifest_version = manifest_version
        go.cell_manifest_sha256 = manifest_sha256
        go.required_cell_ids = cells
        go.d0_receipt_ids_by_cell = {}
        go.d1_receipt_ids_by_cell = {}
        go.go_candidate_closure_sha256 = None

    def record_cell_d1(
        self,
        go_id: str,
        manifest_sha256: str,
        cell_id: str,
        d0_receipt_id: str,
        d1_receipt_id: str,
    ):
        go = self._go(go_id)
        if not go.cell_manifest_sha256 or manifest_sha256 != go.cell_manifest_sha256:
            raise GraphError("CELL D1 must bind the current CELL manifest")
        if cell_id not in go.required_cell_ids:
            raise GraphError("CELL D1 is not in the required CELL set")
        if not d0_receipt_id or not d1_receipt_id:
            raise GraphError("CELL D0 and D1 receipt identities are required")
        go.d0_receipt_ids_by_cell[cell_id] = d0_receipt_id
        go.d1_receipt_ids_by_cell[cell_id] = d1_receipt_id
        go.go_candidate_closure_sha256 = None

    def record_candidate_closure(
        self,
        go_id: str,
        manifest_sha256: str,
        selected_cell_ids: Iterable[str],
        closure_sha256: str,
    ):
        go = self._go(go_id)
        selected = tuple(sorted(selected_cell_ids))
        if not go.cell_manifest_sha256 or manifest_sha256 != go.cell_manifest_sha256:
            raise GraphError("GO candidate closure must bind the current CELL manifest")
        if selected != go.required_cell_ids:
            raise GraphError("GO candidate closure requires the exact required CELL set")
        if set(go.d1_receipt_ids_by_cell) != set(go.required_cell_ids):
            raise GraphError("GO candidate closure requires every required CELL D1")
        if len(closure_sha256) != 64:
            raise GraphError("GO candidate closure sha256 is required")
        go.go_candidate_closure_sha256 = closure_sha256

    def start_checking(self, go_id: str, candidate_id: str, d0_receipt_id: str):
        go = self._go(go_id)
        self._require_active_phase(go, {IMPLEMENTING, REWORK})
        if not candidate_id or not d0_receipt_id:
            raise GraphError("candidate and D0 receipt identities are required")
        go.candidate_id = candidate_id
        go.d0_receipt_id = d0_receipt_id
        go.d1_receipt_id = None
        go.d2_receipt_id = None
        go.d2_receipt_sha256 = None
        go.d2_admission_id = None
        go.admitted_d2_sha256 = None
        go.graph_event_id = None
        go.checker_context_ref = None
        go.verifier_context_ref = None
        go.go_candidate_closure_sha256 = None
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
        go_candidate_closure_sha256: Optional[str] = None,
    ):
        go = self._go(go_id)
        if not go.d1_receipt_id:
            raise GraphError("D2 requires a valid D1 PASS receipt")
        self._require_active_phase(go, {VERIFYING})
        self._require_candidate(go, candidate_id)
        if go.required_cell_ids:
            if not go.go_candidate_closure_sha256:
                raise GraphError("D2 requires a current exact GO candidate closure")
            if go_candidate_closure_sha256 != go.go_candidate_closure_sha256:
                raise GraphError("D2 must bind the current exact GO candidate closure")
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

    def record_d2_verdict(
        self,
        go_id: str,
        candidate_id: str,
        d2_receipt_id: str,
        d2_receipt_sha256: str,
        verifier_context_ref: str,
        go_candidate_closure_sha256: Optional[str] = None,
    ):
        """Record a formal 3.0 D2 verdict without applying graph control."""
        go = self._go(go_id)
        if not go.d1_receipt_id:
            raise GraphError("D2 requires a valid D1 PASS receipt")
        self._require_active_phase(go, {VERIFYING})
        self._require_candidate(go, candidate_id)
        if go.required_cell_ids:
            if not go.go_candidate_closure_sha256:
                raise GraphError("D2 requires a current exact GO candidate closure")
            if go_candidate_closure_sha256 != go.go_candidate_closure_sha256:
                raise GraphError("D2 must bind the current exact GO candidate closure")
        if not d2_receipt_id or not verifier_context_ref:
            raise GraphError("D2 receipt and GO Verifier context are required")
        if verifier_context_ref == go.checker_context_ref:
            raise GraphError("GO Verifier must be independent from the Checker")
        if (
            not isinstance(d2_receipt_sha256, str)
            or len(d2_receipt_sha256) != 64
            or any(character not in "0123456789abcdef" for character in d2_receipt_sha256)
        ):
            raise GraphError("D2 receipt sha256 is required")
        go.d2_receipt_id = d2_receipt_id
        go.d2_receipt_sha256 = d2_receipt_sha256
        go.verifier_context_ref = verifier_context_ref
        go.d2_admission_id = None
        go.admitted_d2_sha256 = None
        go.graph_event_id = None

    def admit_d2(self, go_id: str, d2_receipt_sha256: str, admission_id: str):
        """Mechanically bind one exact D2 digest without changing GO state."""
        go = self._go(go_id)
        self._require_active_phase(go, {VERIFYING})
        if not admission_id or d2_receipt_sha256 != go.d2_receipt_sha256:
            raise GraphError("D2 admission must bind the exact current D2 digest")
        go.d2_admission_id = admission_id
        go.admitted_d2_sha256 = d2_receipt_sha256

    def apply_d2_graph_event(
        self,
        go_id: str,
        d2_receipt_sha256: str,
        admission_id: str,
        graph_event_id: str,
    ):
        """Apply successor release only after exact D2 admission and a distinct event."""
        go = self._go(go_id)
        self._require_active_phase(go, {VERIFYING})
        if (
            not graph_event_id
            or admission_id != go.d2_admission_id
            or d2_receipt_sha256 != go.admitted_d2_sha256
            or d2_receipt_sha256 != go.d2_receipt_sha256
        ):
            raise GraphError("graph event requires the exact admitted current D2")
        go.graph_event_id = graph_event_id
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

        occupied_keys: Set[str] = set()
        occupied_resources: Dict[str, int] = {}
        for active_id in active_ids:
            occupied_keys.update(self.gos[active_id].conflict_keys)
            for resource, amount in self.gos[active_id].resource_claims.items():
                occupied_resources[resource] = occupied_resources.get(resource, 0) + amount
        chosen = list(
            maximum_compatible_ids(
                candidates,
                {go_id: self.gos[go_id].conflict_keys for go_id in candidates},
                {go_id: self.gos[go_id].resource_claims for go_id in candidates},
                self.resource_capacity,
                occupied_keys,
                occupied_resources,
            )
        )
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
            resource_conflicts = self._resource_conflicts(go_id, final_active)
            if not conflicts and not resource_conflicts:
                raise GraphError(
                    f"activation calculation was not maximal; {go_id} can be added"
                )
            go.state = WAITING_GO
            go.phase = None
            go.waiting = (
                [WaitingReason("CONFLICT", conflicts)]
                if conflicts
                else [WaitingReason("RESOURCE", resource_conflicts)]
            )

    def _resource_conflicts(self, go_id: str, active_ids: List[str]) -> Tuple[str, ...]:
        usage: Dict[str, int] = {}
        for active_id in active_ids:
            for resource, amount in self.gos[active_id].resource_claims.items():
                usage[resource] = usage.get(resource, 0) + amount
        return tuple(
            sorted(
                resource
                for resource, amount in self.gos[go_id].resource_claims.items()
                if resource in self.resource_capacity
                and usage.get(resource, 0) + amount > self.resource_capacity[resource]
            )
        )

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
