from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple


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

    def __init__(self, gos: Iterable[Go]):
        go_list = list(gos)
        self.gos: Dict[str, Go] = {go.go_id: go for go in go_list}
        if len(self.gos) != len(go_list):
            raise GraphError("duplicate GO id")
        for go in go_list:
            missing = go.predecessors - set(self.gos)
            if missing:
                raise GraphError(
                    f"missing predecessors for {go.go_id}: {sorted(missing)}"
                )
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
                go.phase = IMPLEMENTING
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
