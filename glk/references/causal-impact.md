# Causal Slice, Invalidation, and Reactivation

## Incident annotations

`CAUSAL_SOURCE` and `DOWNSTREAM_SYMPTOM` are versioned annotations inside one
`GO_CAUSAL_TRACE`. They never create a GO type, state, role, or edge. The source may
be any GO in the DAG, including the observation GO.

A trace binds the current graph version, source candidate, evidence, symptoms, and
actual-consumption path. `SUSPECTED` is recordable evidence. Only `CONFIRMED` may
authorize graph-level invalidation.

Every incoming dependency of the confirmed source and traversed path targets must
be bound. An unbound incoming dependency fails causal recovery closed while leaving
ordinary legacy scheduling available.

## Reverse causal slice

Begin at the observation GO and walk incoming D2 edges only when the edge's source
claim/output refs, target input/assumption refs, and consumption evidence prove that
the observed defect traversed that edge. Record excluded incoming edges. Stop at the
confirmed source; ancestor reachability alone is not causality.

## Minimal forward impact

Use changed candidate, claim, output, or evidence refs as seeds. On the first hop,
include only successors consuming a seed. Continue through bound outgoing edges of
an affected GO. Classify every GO as `UNAFFECTED`, `REVERIFY`, `REWORK`, or
`QUARANTINE`. Historical candidates and receipts stay append-only while invalidated
references lose current-validity for the amended graph version.

## Reactivation

Re-project only affected GOs. A waiting-clear source enters `ACTIVE_GO` directly;
consuming successors use existing `DEPENDENCY_UNMET` reasons in `WAITING_GO`. When
the repaired source obtains current D2, all safe successors enter the
maximum-cardinality active set in the same recalculation. There is no schedulable
intermediate queue, full-graph replay, Chain, Level, or Barrier.
