# Graph Loop Skill (GLK) 3.1.0

Canonical repository: https://github.com/DWG7318/large-loop-skill

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

## 3.1 operational safety

GLK 3.1 adds seven narrow operational rules without changing the six roles or D0-D3:

- Worker-only four-level wake of the original Checker, with scoped CELL position,
  bound `WAKE_ACK`, a temporary heartbeat, and `PENDING_WAKE` fallback;
- one visible non-authoritative Run patrol using `gpt-5.6-luna`/`xhigh`, with no
  task creation, subagent, engineering, acceptance, or takeover authority;
- layered progress that distinguishes delivery, D1 acceptance, GO candidate, D2,
  D3, and Owner Acceptance;
- device/cumulative-load-aware `CELL_CAPACITY_GATE` before Worker dispatch.

Supervisor does not use positive-duration or looping `wait_threads`. Method roles
never Pin tasks; only explicit Owner Pin provenance is legal. The patrol reports
`UNAUTHORIZED_THREAD_PIN` or `PIN_PROVENANCE_UNKNOWN` and never unpins on its own.
Wait-all is always forbidden, and every formal role rejects actual
spawn/delegate/hidden/background Agent capability. Patrol difficulty maps light
`LOW`/normal `MEDIUM`/heavy `HIGH` to 10/15/30 minutes and every cycle proves the
same exact seven-check checklist.

Current 3.1 Run packages always execute Layer 11. It requires exact wake, capacity,
patrol, and append-only Checker/Supervisor progress coverage; missing controls
cannot disable the layer. Exact historical 3.0 packages retain an explicit legacy
`NOT_APPLICABLE` result only.

Capacity profiles use measured or conservative CPU, RAM, GPU/VRAM, disk/IO,
network, process/port, duration, context, and evidence facts. Oversized work is split
before dispatch while preserving one GO outcome. A late split into three or more
successors is `CELL_OVERSIZE_SEVERE` and re-evaluates all undispatched work.

## Causal recovery

Each D2 edge binds the producer claim/output, consumer input/assumption, and
consumption evidence. A `GO_CAUSAL_TRACE` binds one incident's confirmed source to
its current immutable candidate, an explicit set of real symptom GOs, and only the
actual-consumption edges selected by incident evidence. Alternative reachable paths
remain excluded unless separately confirmed; these are annotations, not new node
types or states. Only a confirmed selected path may invalidate current evidence.

Amendments use typed candidate, evidence, or claim/output seeds and reject unrelated
refs. Candidate and claim/output seeds require source rework or quarantine; an
evidence-only seed may reverify, and multiple seeds apply the strictest source rule.
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

## 3.0 authority and validation

GLK 3.0 splits Worker D0, Checker D1, Supervisor admission, GO Verifier D2,
Supervisor graph event, Run Verifier D3, and Owner Acceptance into independent
append-only artifacts. A versioned `CELL_MANIFEST` and exact
`GO_CANDIDATE_CLOSURE` prevent premature D2 and permit reuse only for unchanged,
current-valid CELL D1 evidence.

`validate_glk` checks the `REPOSITORY_DISTRIBUTION`; `validate_run` checks one
complete `RUN_PACKAGE` through ten validation layers. Bootstrap is draft-only,
preflight and simulation are derived gates, liveness fails closed, and authority or
repeated architecture failures stop the Run. Progress reports both required GO/D2
and required CELL/D1 completion.

The method lock pins version 3.1.0, this repository, release/commit, schema, Skill,
the real Run validator source bundle, and adapter contract. The 2.4 formal-use
freeze permits historical migration diagnostics but never upgrades unproven 2.4
receipts into current evidence.

GLK defines only the four-operation provenance adapter contract. LCCoding owns
lifecycle and centralized security routing; LCagent or another trusted environment
owns credentials, sessions, issuance, replay/checkpoint, Broker, and runtime
provenance implementations.
