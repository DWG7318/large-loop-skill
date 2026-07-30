# Causal Slice, Invalidation, and Reactivation

## Incident annotations

`CAUSAL_SOURCE` and `DOWNSTREAM_SYMPTOM` are versioned annotations inside one
`GO_CAUSAL_TRACE`. They never create a GO type, state, role, or edge. The source may
be any GO in the DAG, including the observation GO.

A trace binds the current graph version, source candidate, evidence, explicit
symptom set, and incident-selected actual-consumption path. `SUSPECTED` is
recordable evidence. Only `CONFIRMED` may authorize graph-level invalidation.

A confirmed source binds the GO's current immutable candidate. When the incident
crosses an edge, the source also requires a current D2 receipt. Every symptom is a
real GO reached by a confirmed selected path, the observation belongs to the
symptom set, and the source is excluded. A local source-equals-observation incident
uses empty symptom and selected-path sets.

Every incoming dependency of the confirmed source and traversed path targets must
be bound. An unbound incoming dependency fails causal recovery closed while leaving
ordinary legacy scheduling available.

## Reverse causal slice

Begin at the observation GO and walk only incident-selected incoming D2 edges when the edge's source
claim/output refs, target input/assumption refs, and consumption evidence prove that
the observed defect traversed that edge. Every selected edge has its own incident
evidence and confirmation status, and the selected edges must reach every explicit
symptom. Record unselected alternative paths and incoming context as excluded edges.
Revalidate the selected path, exclusions, and stopping reason before amendment.
Stop at the confirmed source; ancestor reachability alone is not causality.

## Minimal forward impact

Use typed `CANDIDATE`, `EVIDENCE`, or `CLAIM_OR_OUTPUT` seeds. A claim/output seed
starts only at successors that consume that ref. A current source candidate or
trace/source-D2 evidence seed invalidates source validity first and then follows all
bound source consumers; unrelated refs fail closed. Continue through bound outgoing
edges of an affected GO. Classify every GO as `UNAFFECTED`, `REVERIFY`, `REWORK`, or
`QUARANTINE`. Historical candidates and receipts stay append-only while invalidated
references lose current-validity for the amended graph version.

## Reactivation

Re-project only affected GOs. A waiting-clear source enters `ACTIVE_GO` directly;
consuming successors use existing `DEPENDENCY_UNMET` reasons in `WAITING_GO`. When
the repaired source obtains current D2, all safe successors enter the
maximum-cardinality active set in the same recalculation. There is no schedulable
intermediate queue, full-graph replay, Chain, Level, or Barrier.
