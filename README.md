# Graph Loop Skill (GLK) 2.4.0

GLK governs one bounded engineering Run as a directed acyclic graph of
independently verifiable GO outcomes.

## Canonical flow

```text
frozen RUN_CONTRACT
-> fresh Run Supervisor instance
-> frozen GO execution DAG
-> WAITING_GO nodes with explicit reasons
-> maximal safe ACTIVE_GO set
-> parallel D0 / independent D1 / independent D2 per GO
-> confirmed causal trace and minimum successor invalidation when repair crosses GOs
-> direct activation of newly unblocked successors
-> independent Run D3
-> immediate Run Owner Acceptance
-> LOOP_OWNER_ACCEPTED
-> LCCoding security handoff
```

## Six roles

1. Run Supervisor
2. Worker
3. Checker
4. GO Verifier
5. Run Verifier
6. Owner

Every Run receives a fresh Supervisor instance. Multiple active GO nodes use
isolated instances of the existing implementation and verification role types; no
extra role type is created.

## Graph execution rule

There is no schedulable intermediate queue between waiting and active work. An
unresolved GO is `WAITING_GO` only while one or more recorded dependency, conflict,
resource, isolation, or safety reasons remain. When all reasons clear, it enters the
maximal safe `ACTIVE_GO` set immediately.

GLK must exploit independent branches concurrently. Arbitrary serialization and
fake dependency edges are invalid. When conflict choices admit different safe sets,
activate the alternative containing the greatest number of GO nodes.

## Causal recovery

Each D2 edge binds the producer claim/output, consumer input/assumption, and
consumption evidence. A `GO_CAUSAL_TRACE` distinguishes one incident's confirmed
source GO from downstream symptom GOs; these are annotations, not new node types or
states. Only a confirmed actual-consumption path may invalidate current evidence.

After repair, GLK re-projects only the proven impact slice. Historical receipts stay
append-only, unaffected branches remain valid, the source enters `ACTIVE_GO` when
waiting-clear, and newly unlocked successors reactivate together under the same
maximum-cardinality scheduler. No schedulable intermediate queue or full-graph
replay is introduced.

## Verification

- D0: Worker implementation evidence.
- D1: independent immutable CELL verdict.
- D2: independent GO composition verdict.
- D3: independent Run Feature and graph-seam verdict.

D3 consumes valid D2 evidence instead of rerunning every lower-level check. The
Owner accepts the bounded Run immediately after D3 PASS. Project-wide centralized
security closure remains owned by LCCoding.

Read [SPEC.md](SPEC.md) before using GLK. The executable templates, schema, model,
and validator live under [glk](glk/).
