---
name: graph-loop-skill
description: Govern one frozen engineering Run whose independently verifiable GO outcomes form a dependency DAG with maximal-safe parallel activation.
version: 3.1.0
---

# Graph Loop Skill (GLK) 3.1.0

Canonical repository: https://github.com/DWG7318/large-loop-skill

## Authority order

Read `SPEC.md` completely, then the relevant files under `glk/references/`, the
versioned templates, and `glk/schemas/glk.schema.json`.

```text
Owner and LCCoding gateway decisions
-> frozen RUN_CONTRACT and GLK_METHOD_LOCK
-> SPEC.md
-> references
-> executable schema and templates
-> examples
```

Missing, conflicting, stale, or unverifiable authority fails closed.

## Method identity

GLK governs one bounded Run as a GO-to-GO dependency DAG. It has exactly six role
types:

```text
Run Supervisor
Worker
Checker
GO Verifier
Run Verifier
Owner
```

Every Run receives a fresh Run Supervisor instance. The Supervisor may issue only
control artifacts; it cannot issue, hold an issuance capability for, or invoke
D0, D1, D2, or D3.

## Execution flow

1. Freeze `RUN_CONTRACT`, `GLK_METHOD_LOCK`, the adapter profile, six role
   bindings, and `GRAPH_BASELINE`.
2. Recompute graph identity, node/edge coverage, predecessor equivalence, and
   acyclicity from the actual DAG.
3. Keep unresolved nodes as `WAITING_GO` with typed reasons. Nodes with no waiting
   reason enter the maximal safe `ACTIVE_GO` set directly.
4. For every GO, freeze a versioned `CELL_MANIFEST` and exact required CELL set.
5. A Worker issues D0 for one exact CELL candidate; a Checker independently issues
   D1 for the same candidate and contract.
6. Supervisor admissions mechanically bind exact D0 and D1 digests. They do not
   create technical verdicts.
7. After every required CELL has a current D1 PASS, the designated Worker derives
   `GO_CANDIDATE_CLOSURE` from exact CELL candidate, D0, and D1 digests.
8. A GO Verifier issues D2 only for the admitted current closure. An admitted D2
   still cannot release successors by itself.
9. The Supervisor appends a separate `GRAPH_EVENT` that consumes the exact admitted
   D2 and recomputes the maximal safe active set.
10. A Run Verifier issues D3 only for the exact current required GO/D2 closure,
    graph digest, graph events, and seam evidence.
11. The Supervisor mechanically admits exact D3. The Owner alone issues Owner
    Acceptance for the admitted D3.
12. Only after `LOOP_OWNER_ACCEPTED` may the Supervisor append the security handoff;
    LCCoding still owns centralized security closure.

There is no schedulable intermediate state between `WAITING_GO` and `ACTIVE_GO`.
Arbitrary serialization and fake dependency edges are invalid. Independent GO
branches activate concurrently up to the maximum-cardinality safe set.

## Independent append-only artifacts

D0, D1, `SUPERVISOR_ADMISSION`, D2, `GRAPH_EVENT`, D3, and
`OWNER_ACCEPTANCE` are separate append-only artifacts. Each binds its unique
authority, candidate and digest, Run/Graph/GO/CELL scope, execution context,
non-empty evidence, provenance reference, and timestamp.

`RUN_PACKAGE_INDEX` is a versioned append-only control artifact. It is not an
oracle: the loader scans declared formal roots, rejects omissions, extra unindexed
formal objects, bad digests, escaping paths, forks, and multiple heads, then freezes
the loaded subject.

## CELL closure and limited reuse

D1 binds the current CELL manifest, CELL contract, exact CELL candidate/D0,
Checker context, evidence, and provenance. D1 never binds a future GO closure.
`GO_CANDIDATE_CLOSURE` is formed only after every required CELL has current admitted
D0 and D1 PASS evidence.

A changed CELL must produce a new D0 and D1. An unchanged CELL's D1 may be reused
only when manifest version, contract, candidate, D0/D1 evidence, provenance, expiry,
and impact are all current-valid. Any selected tuple change produces a new GO
closure; an old closure cannot satisfy D2.

## Causal recovery

Each dependency edge binds `source_claim_or_output_refs`, target input/assumption
refs, and actual consumption evidence. `GO_CAUSAL_TRACE` treats `CAUSAL_SOURCE` and
`DOWNSTREAM_SYMPTOM` as incident annotations, not node types or states.

Only a `CONFIRMED` source bound to its current immutable candidate/D2 and an explicit
symptom set may select incident-evidenced causal edges. Reachability alone is not
causality. Unselected reachable edges remain excluded.

A graph amendment uses typed `CANDIDATE`, `EVIDENCE`, or `CLAIM_OR_OUTPUT` seeds.
Unrelated refs fail closed. Candidate or claim/output seeds require source rework or
quarantine; an evidence-only seed may reverify. Multiple seeds use the strictest
source disposition. Only the proven successor impact slice loses current-validity;
`UNAFFECTED` branches remain current and no full-graph replay occurs.

## Validation boundaries

`validate_glk` reports scope `REPOSITORY_DISTRIBUTION` and checks the published
method package. `validate_run` reports scope `RUN_PACKAGE` and loads one complete
Run package exactly once before applying ten validation layers:

1. serialization and schema;
2. package/index integrity;
3. Run/Graph/GO/CELL/reference identity;
4. adapter-backed provenance, sole authority, capability, and isolation;
5. candidate, digest, admission, and receipt lineage;
6. CELL manifest and GO candidate closure;
7. recomputed DAG structure;
8. D2 admission and graph-event separation;
9. D3 closure and Run Verifier isolation;
10. Owner Acceptance and post-acceptance handoff.

Validation reports, preflight reports, simulation reports, and progress projections
are derived non-authoritative objects. They never become receipts, admissions, graph
events, or technical verdicts.

## Provenance adapter boundary

GLK defines exactly four abstract adapter operations:

```text
resolve_binding
verify_issuance
verify_isolation
check_liveness
```

GLK does not implement sessions, credentials, key custody, production issuance,
Broker services, replay, checkpoints, or an Agent runtime. LCagent or another trusted
execution environment implements those capabilities and returns verifiable
attestations through this boundary.

## Preflight, simulation, liveness, and stops

Bootstrap creates only `DRAFT_SCAFFOLD`. Formal preflight requires the exact method
lock, one canonical declared installation, the complete six-role binding set,
trusted adapter evidence, a ten-layer valid technical package, the applicable
3.1 operational-control gate, readiness evidence, a
no-side-effect simulation, and no active hold.

Read failure never implies health. Deadline expiry yields an unreachable role
projection. `MONITOR_CONTROL` binds exactly one visible patrol conversation and one
heartbeat with one deterministic key and append-only head. The patrol uses
`gpt-5.6-luna` with `xhigh`; the patrol is not a seventh authority role.

A technical authority violation produces `RUN_AUTHORITY_HOLD` immediately. Two
consecutive HIGH architecture findings on the same path produce
`RUN_ARCHITECTURE_HOLD`. Recovery requires a frozen amendment plus revalidation, or
sealing the Run and starting a new one.

## Progress and boundaries

Formal progress reports both `required GO/D2` and `required CELL/D1` counts and IDs,
plus active GO IDs, waiting reasons, unreachable bindings, holds, graph version, and
CELL manifest versions.

## GLK 3.1 operational rules

Only Worker may wake its original frozen Checker. It sends a scoped
`GO <GO_ID> CELL <ordinal>/<Required CELL total> 已交付，请检查` message and escalates
through direct send, same-task read/list/unarchive, one temporary heartbeat, then
`PENDING_WAKE`. Every level waits at most 120 seconds through an injected clock.
Checker first returns a Run/GO/CELL/Round-bound `WAKE_ACK`. Success stops escalation
and cleans temporary state; IDs are never guessed and replacement roles are never
created.

Supervisor must not remain online with positive-duration or looping
`wait_threads`. The unique patrol checks only unexplained stoppage, pending wake,
actual subagent evidence, forbidden Supervisor wait, duplicate patrol/heartbeat,
Pin provenance, and terminal closure. A GO, CELL, Round, plan step, visible task, or
the word `子任务` is not a subagent; actual `spawn_agent`, `delegate_task`, hidden
Agent, or background Agent evidence is forbidden.

No method role or patrol may call `set_thread_pinned(true)` or an equivalent Pin.
Only explicit Owner UI or item-specific Run authorization is legal. Report Agent
Pin as `UNAUTHORIZED_THREAD_PIN`; report unknown provenance as
`PIN_PROVENANCE_UNKNOWN` and must not unpin automatically.

Layered progress distinguishes `DELIVERED`, `D1_ACCEPTED`,
`GO_CANDIDATE_READY`, `D2_VERIFIED`, `RUN_VERIFIED`, and `OWNER_ACCEPTED`.
Worker delivery never increments D1. Checker counts current-valid admitted D1 PASS
once and emits only a GO-boundary milestone to Supervisor. Supervisor reports only
material global changes with D1/Required CELL, D2/Required GO, ACTIVE_GO,
WAITING_GO, holds, and graph/manifest/plan/capacity/load versions; no percentage.

Before dispatch, Supervisor binds current `DEVICE_CAPACITY_PROFILE`,
`CUMULATIVE_ENGINEERING_LOAD`, and total-cost `CELL_WORK_ESTIMATE` evidence.
`CELL_CAPACITY_GATE` is `PASS`, `SPLIT_REQUIRED`, or `CAPACITY_BLOCKED`; only PASS
dispatches. Worker cannot self-split. Post-dispatch splitting records
`POST_DISPATCH_CELL_SPLIT`; three or more successors also require
`CELL_OVERSIZE_SEVERE` and remaining-plan re-evaluation. Resource claims constrain
maximal-safe ACTIVE_GO without fake dependency edges.

The 2.4 formal-use freeze prevents new 2.4 Runs. Migration preserves compatible GO
topology and causal history, revalidates contracts, and keeps unproven 2.4 receipts
historical-only; it never upgrades them into current evidence.

LCCoding owns project lifecycle, product-definition routing, and centralized
security closure. GLK remains a lightweight engineering method and does not replace
LCCoding or LCagent.
