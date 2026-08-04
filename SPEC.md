# GLK Standard Specification 3.1.0

## 1. Identity

Graph Loop Skill (GLK) governs one bounded engineering Run represented honestly as
a directed acyclic GO Execution Graph.

Canonical repository: `https://github.com/DWG7318/large-loop-skill`.
Canonical invocation: `graph-loop-skill`.

GLK owns:

- GO decomposition, graph construction, freezing, and amendment;
- automatic graph activation and `WAITING_GO` reason maintenance;
- bounded CELL implementation and D0-D3 evidence interfaces;
- immediate Run-scoped Owner Acceptance;
- the `LOOP_OWNER_ACCEPTED` handoff.

GLK does not own Proposal, Initialization, Calabash, Workflow, UI, Simulation
World, Feature Slice definition, centralized vulnerability closure, or Delivery.
Those arrive through a frozen Run contract or return to LCCoding.

## 2. Required input

GLK requires one frozen `RUN_CONTRACT` containing:

```text
run_id
feature_slice_id
run_feature
run_scope
baseline references
UI lock when applicable
acceptance claims
evidence requirements
autonomy boundaries
exclusions
candidate binding
fresh Run Supervisor binding
```

Material gaps return `RUN_CONTRACT_INCOMPLETE`. GLK must not invent product intent.

## 3. Suitability

Use GLK only when one Run contains independently verifiable GO outcomes whose
mandatory completion-precedence relations form a free branching or merging graph
that is not honestly one strict line or stable ordered Chains.

The graph must be freezeable, acyclic, and verifiable for the bounded Run.

## 4. Canonical objects

### GO

A GO is one bounded, independently verifiable engineering outcome with one primary
claim. It is not a file, commit, coding step, role, module, team, or vague task.

### CELL

A CELL is the smallest controlled implementation unit inside one GO. CELLs do not
create a second graph, Chain, or Stage topology.

### GO Execution Graph

For graph `G=(V,E)`:

- `V` is the GO set for one Run;
- `E` is the set of mandatory D2 completion-precedence relations;
- edge `A -> B` means B cannot leave `WAITING_GO` because of that dependency until
  A has D2 PASS or an authorized formal resolution that explicitly releases B.

Normal execution is acyclic. Resource conflicts, workspace collisions, safety
holds, priorities, and organizational relationships are not graph edges.

### WAITING_GO

An unresolved GO that cannot yet execute. It records one or more typed
`waiting_reasons` with evidence references. Valid reason classes are:

```text
DEPENDENCY_UNMET
WRITE_CONFLICT
RESOURCE
ISOLATION
SAFETY
```

A non-dependency reason must never be encoded as a fake dependency edge.

### ACTIVE_GO

An unresolved GO whose waiting reasons are empty and that belongs to the maximal
safe `ACTIVE_GO` set. The graph-level state remains `ACTIVE_GO` while its internal
phase changes through implementation, checking, verification, or rework.

### Terminal GO

A required GO with no required successor. Terminal GO completion alone does not
complete the Run; D3 must prove the frozen Run Feature over the final candidate.

## 5. Six roles

GLK has exactly six role types:

```text
Run Supervisor
Worker
Checker
GO Verifier
Run Verifier
Owner
```

No additional control-role type may be silently introduced.

### Run Supervisor

Owns Run control, not technical verdicts. It validates the Run contract, decomposes
the Run Feature into GO claims, freezes and amends the graph, maintains waiting
reasons and the maximal safe ACTIVE_GO set, provisions isolated role instances,
routes receipts and rework, evaluates mechanical completion prerequisites, and
prepares Owner Acceptance.

Every Run requires a fresh Run Supervisor instance. Two Run contracts must not reuse
the same role-binding ID, Supervisor instance identity, conversation/context,
mutable workspace, or evidence root. The same underlying model may be selected
again only through a new Run-scoped binding.

### Worker

Implements one ACTIVE_GO through bounded CELLs and emits D0. A Worker cannot accept
its own work. Multiple ACTIVE_GO nodes require separate, isolated Worker instances.

### Checker

Independently evaluates immutable CELL candidates and signs D1. A Checker cannot
modify and then accept the same candidate. Concurrent GO nodes require isolated
Checker bindings and evidence paths.

### GO Verifier

Independently determines whether accepted CELLs compose one frozen GO claim and
signs D2. D2 may clear dependency waiting reasons on successors.

### Run Verifier

Independently determines whether all required verified GO outcomes, graph seams,
and the final candidate compose the frozen Run Feature and signs D3.

GO Verifier and Run Verifier remain distinct roles. Separate Agent instances are the
default. One Agent may perform both only when it remained outside supervision,
implementation, and checking; receives separate clean contexts and workspaces; and
issues separately bound receipts.

### Owner

Performs product acceptance of this bounded Run after D3 PASS.

## 6. Invariants

1. Every node is exactly one GO.
2. Every edge records a mandatory D2 completion-precedence justification.
3. The graph is not a Workflow, Code Graph, business graph, module graph, or
   dependency inventory.
4. GLK has no Chain, Stage, or Barrier.
5. Normal execution is acyclic.
6. GLK has no schedulable intermediate queue between waiting and active execution.
7. Every waiting reason is typed, referenced, observable, and removable by an
   explicit graph event.
8. Every GO with no remaining waiting reason enters `ACTIVE_GO` immediately, subject
   only to the maximal safe set calculation.
9. Run Supervisor must maintain a maximal safe ACTIVE_GO set; arbitrary serialization
   is forbidden.
10. A GO cannot consume an unfinished predecessor or provisional evidence.
11. Non-dependency constraints must not be represented as a fake dependency.
12. Run Supervisor cannot sign D1, D2, or D3 for product work it controlled.
13. D3 consumes valid D2 receipts and does not equal receipt counting.
14. Run Owner Acceptance occurs immediately after D3 PASS.
15. No silent node, edge, claim, baseline, role-binding, or candidate amendment is
    allowed.
16. Causal source and downstream symptom labels are incident annotations, never new
    GO types or graph states.
17. Only a `CONFIRMED` causal trace over actual consumption bindings may invalidate
    current evidence.
18. Causal repair invalidates the minimum proven successor slice and preserves
    maximum-cardinality activation outside and after that slice.

## 7. Graph construction

1. Validate `RUN_CONTRACT` and the fresh Supervisor binding.
2. Decompose the Run Feature into the minimum independently verifiable GO outcomes.
3. Freeze each GO claim, scope, acceptance, evidence, exclusion, and conflict keys.
4. Compare candidate GO pairs for mandatory D2 completion precedence.
5. Add only necessary edges and record their justifications.
6. Remove redundant transitive edges when governance meaning remains intact.
7. Validate acyclicity, entry reachability, terminal coverage, Run Feature coverage,
   and edge necessity.
8. Prove that the topology is not honestly a strict line or stable Chain/Stage plan.
9. Freeze `GRAPH_BASELINE` with graph and candidate hashes.
10. Compute waiting reasons and immediately activate the maximal safe set.

Every D2 precedence edge also binds:

```text
source_claim_or_output_refs
target_input_or_assumption_refs
consumption_evidence_refs
```

These bindings explain which frozen producer claim or output the successor actually
consumes. They do not turn a call graph, data-flow graph, module graph, or file
relationship into a GO edge. An edge without all three bindings may be read as
historical scheduling evidence, but it cannot participate in 3.0.0 causal
recovery.

For a 3.0.0 causal trace, every incoming dependency of the source and traversed
path targets must have this contract. An `unbound incoming dependency` fails causal
recovery closed because it cannot be excluded with evidence; ordinary legacy
scheduling may continue without claiming a causal result.

### Edge test

For candidate edge `A -> B`, ask:

> Can B start and independently complete correctly before A receives D2 PASS?

If yes, no mandatory edge exists. Convenience, preferred order, shared files,
likely code calls, team structure, and visual proximity are insufficient.

## 8. Maximal-safe activation

After every graph-relevant event, Run Supervisor performs one deterministic
activation calculation:

1. Recompute dependency waiting reasons from predecessor D2 or formal resolutions.
2. Recompute frozen non-dependency reasons from write conflicts, resources,
   isolation, and safety evidence.
3. Keep already active, still-valid GO nodes active.
4. Add every additional conflict-free GO whose waiting reasons are empty and, when
   conflict choices exist, select the safe combination with the greatest GO count.
5. Record reasons for every unresolved GO that remains waiting.
6. Prove maximality: no waiting GO can be added without violating a recorded
   constraint, and no alternative safe selection would activate more GO nodes.

Owner priority and critical-path value may choose among mutually conflicting GO
nodes; they cannot leave an otherwise activatable GO idle. “Simpler coordination,”
Supervisor preference, and model convenience are invalid waiting reasons.

## 9. State and phase model

Graph states:

```text
DRAFT
FROZEN
WAITING_GO
ACTIVE_GO
GO_VERIFIED
GO_BLOCKED
GO_REJECTED
SUPERSEDED
CANCELLED
```

Canonical graph path:

```text
DRAFT -> FROZEN -> WAITING_GO | ACTIVE_GO
WAITING_GO -> ACTIVE_GO
ACTIVE_GO -> GO_VERIFIED
```

Internal phases while graph state remains `ACTIVE_GO`:

```text
IMPLEMENTING -> CHECKING -> VERIFYING
CHECKING -> REWORK -> CHECKING
VERIFYING -> REWORK -> CHECKING
```

This separation prevents a GO from vacating the active graph set merely because it
is being checked or verified.

## 10. Verification and evidence de-duplication

- D0 proves local implementation behavior against Worker intent.
- D1 proves the immutable CELL candidate against its frozen local contract.
- D2 proves that accepted CELLs compose one frozen GO claim.
- D3 proves only that verified GO outcomes, graph seams, and the final candidate
  compose the frozen Run Feature.

Every receipt binds schema version, graph version, candidate identity and hash,
actor binding, execution context, evidence, and issue time. D2 must consume valid D1
for the same candidate. D3 must consume valid D2 receipts for the accepted graph
version.

Repeat a lower-layer check only when the candidate or environment changed, evidence
expired or conflicts, graph composition changes its meaning, regression scope
expanded, or a specific new risk requires it. Record the reason and scope delta.

## 11. Causal recovery

### Source and symptom annotations

For one incident, `CAUSAL_SOURCE` identifies the GO whose candidate, claim, output,
or evidence first introduced the confirmed defect. `DOWNSTREAM_SYMPTOM` identifies
one or more GOs where that defect became observable through consumption. They are
incident annotations, not a new GO type, state, role, or topology. A source GO may
appear at any position in the DAG and may also be the observation GO.

A versioned `GO_CAUSAL_TRACE` binds the incident, graph version, observation GO,
source GO, source candidate, evidence, symptom set, actual-consumption path, and
`SUSPECTED` or `CONFIRMED` status. A `SUSPECTED` trace is retained as evidence but
must not revoke candidates or receipts.

For `CONFIRMED`, `source_candidate_ref` must equal the source GO's current immutable
candidate. If the incident crossed a GO edge, that source must retain its current D2 receipt.
The symptom set is explicit: each member must be a real GO, the source
must not be a symptom, and the observation GO must be included. The local
source-equals-observation exception uses empty symptom and path sets.

### Reverse causal slice

Run Supervisor computes a reverse causal slice from the observation GO toward the
confirmed source. The incident record explicitly selects each traversed edge and
binds incident evidence plus a confirmation status to it. It may traverse only edges whose
`source_claim_or_output_refs`, `target_input_or_assumption_refs`, and
`consumption_evidence_refs` prove actual consumption for this incident. The trace
must contain a continuous selected path from the source to every symptom.
Alternative reachable edges are recorded as excluded unless incident evidence separately confirms
them; selected paths, excluded incoming edges, and the stopping reason are revalidated
when an amendment is applied. Mere ancestor reachability,
source-code calls, file proximity, or shared modules are insufficient.

### Minimal impact projection

After a confirmed source changes, `GRAPH_AMENDMENT` starts from explicit typed
`CANDIDATE`, `EVIDENCE`, or `CLAIM_OR_OUTPUT` impact seeds. A claim/output seed starts
only at successor edges that consume that ref. A current source candidate or
trace/source-D2 evidence seed first invalidates the source validity, then propagates
conservatively through its bound consumers. Unrelated refs fail closed. Later steps
follow consumption from an already affected GO. Every GO receives one projection disposition:

```text
UNAFFECTED
REVERIFY
REWORK
QUARANTINE
```

Seed meaning constrains the source disposition before any mutation. A `CANDIDATE`
seed requires source `REWORK` or `QUARANTINE` and invalidates that candidate plus
its current D0/D1/D2 receipts; `REVERIFY` is forbidden. An `EVIDENCE` seed may
use `REVERIFY` when the candidate and D1 remain valid, or a deeper disposition when
the evidence supports it. A `CLAIM_OR_OUTPUT` seed cannot preserve the same current
artifact through `REVERIFY`; it requires `REWORK` or `QUARANTINE`. For multiple
seeds, the strictest source disposition required by any seed wins. These source
rules do not widen downstream impact: each successor keeps its own evidence-backed
disposition, and unrelated branches remain `UNAFFECTED`.

Historical candidates and D0-D3 receipts remain append-only. Invalidated items lose
`current-validity` only for the new graph version and remain addressable as history.
Unproven descendants remain `UNAFFECTED`; full-graph replay is forbidden.

### Safe reactivation

Affected GOs are re-projected as unresolved in the amended graph. A repaired source
with no waiting reason enters `ACTIVE_GO` directly. A consuming successor remains
`WAITING_GO` with the existing `DEPENDENCY_UNMET` reason until a current source D2
clears it. After that D2, every safe successor enters the maximum-cardinality active
set in the same recalculation. No schedulable intermediate queue, Chain, Barrier,
or arbitrary serial replay is introduced.

GO-local defect reproduction and repair discipline stays outside this graph
topology. GLK consumes its frozen candidate and D0/D1 evidence at the handoff
boundary; it does not copy a separate defect micro-loop.

## 12. Formal resolution

`SUPERSEDED` and `CANCELLED` do not imply success. A formal resolution requires a
versioned graph amendment, authority binding, evidence, successor-release decision,
and Required-set decision.

A Required GO stops blocking Run completion only when it has D2 PASS or an approved
amendment removes/replaces it. A formal resolution releases successors only when its
contract explicitly says so.

## 13. Graph amendment

A frozen graph changes only through `GRAPH_AMENDMENT`, recording reason, before and
after versions, affected claims, confirmed causal-trace reference when applicable,
impact seeds and slice, active-work impact, candidate/evidence/receipt invalidation,
reactivation projection, rollback, authority, and issue time.

Product-definition changes return to LCCoding/Calabash rather than being hidden as
graph edits.

## 14. Owner Acceptance

After D3 PASS, Run Supervisor provides the exact candidate, bounded Run Feature,
entry points, roles, concise steps, visible outcomes, limitations, and D3-covered
invisible risks.

Allowed verdicts:

```text
LOOP_OWNER_ACCEPTED
LOOP_PRODUCT_REWORK
PRODUCT_DEFINITION_CHANGE
NEW_FEATURE_REQUEST
```

This is immediate acceptance for the current Run, never a deferred project-end
mega-acceptance.

## 15. Security boundary

GLK performs Run-contract-local safety checks only. It does not issue centralized
vulnerability closure.

After required Runs are Owner-accepted, GLK emits a versioned security handoff that
binds the accepted candidate and scope. LCCoding owns the independent centralized
audit, repair loop, closure, and Post-Security Owner Acceptance.

## 16. Failure rules

Stop or reject when:

- a node is not a GO;
- an edge lacks mandatory D2 precedence justification;
- the execution graph is cyclic;
- a successor activates before its dependency waiting reason is cleared;
- an activatable independent GO is arbitrarily left idle;
- a waiting reason lacks evidence or release conditions;
- a resource or coordination preference is encoded as a dependency edge;
- an undeclared seventh role controls the Run;
- a Supervisor binding is reused across Runs;
- D1/D2 candidate identities differ;
- technical receipts are self-signed by controlled work;
- D3 blindly repeats D2 or passes by receipt counting;
- Owner Acceptance is postponed to project end;
- graph amendments are silent;
- the topology is honestly a strict line or stable Chain/Stage plan.
- a suspected or unbound causal path invalidates a receipt;
- an unrelated descendant is replayed without consumption evidence;
- a causal repair creates a new role, GO type, intermediate queue, Chain, or Barrier;
- multiple newly unblocked successors are serialized without a real constraint.

## 17. Completion

A GLK Run completes only when all Required GO claims are resolved under the frozen
graph, terminal coverage is complete, D3 passes on the final candidate, evidence and
candidate identities are synchronized, the Owner signs `LOOP_OWNER_ACCEPTED`, and
the LCCoding security handoff is emitted.

## 18. Breaking 3.0 authority contract

The 2.4 formal-use freeze prohibits starting a new formal 2.4 Run. Historical 2.4
packages remain immutable and readable for audit or migration classification, but
their free-form bindings, mixed receipts, and template-level pass claims cannot
establish 3.0 current evidence.

GLK 3.0 separates these append-only artifacts and authorities:

| Artifact | Sole authority | Meaning |
|---|---|---|
| D0 | Worker | exact CELL candidate production evidence |
| D1 | Checker | independent verdict on exact CELL candidate/D0 |
| Supervisor admission | Run Supervisor | mechanical admission of an exact digest |
| D2 | GO Verifier | exact GO closure verdict |
| Graph event | Run Supervisor | dependency release and active-set recomputation |
| D3 | Run Verifier | exact required GO/D2 and graph-seam verdict |
| Owner Acceptance | Owner | bounded Run decision on admitted current D3 |

The Run Supervisor cannot issue, hold an issuance capability for, or invoke D0-D3.
An admission cannot alter a technical verdict, and a D2 receipt cannot carry graph
control.

## 19. CELL manifest and GO closure

Each GO freezes one versioned `CELL_MANIFEST` with the exact required CELL set,
contract digests, closure hash, prior-manifest digest, and amendment reference when
applicable. Adding, deleting, or replacing a CELL contract requires a frozen
amendment; historical manifests are never rewritten.

D1 binds the current CELL manifest, CELL contract, exact candidate/D0, Checker
context, evidence, provenance, and expiry. It does not bind the future GO closure.
Only after all required CELLs have current admitted D0 and D1 PASS artifacts may the
designated Worker derive `GO_CANDIDATE_CLOSURE`. That closure selects the exact CELL
candidate, D0, and D1 digests and derives the GO candidate generation/hash consumed
by D2.

If one CELL changes, only that CELL requires new D0/D1 when the remaining D1
artifacts retain identical manifest version, contract, candidate, evidence,
provenance, expiry, and impact facts. Any selected tuple change invalidates the old
GO closure. A single-CELL GO follows the same rule without a bypass.

## 20. Run package and validation scopes

`RUN_PACKAGE_INDEX` is a versioned append-only control artifact with
`index_version`, `prior_index_sha256`, and current ledger heads. It does not list
itself as a formal inventory item and is not an oracle. The loader independently
scans declared formal and evidence roots, recomputes digests, rejects omitted or
extra objects, path escape, symlinks, duplicate digests, forks, and multiple heads,
then deep-freezes the loaded subject.

Repository and Run validation are separate products:

```text
validate_glk -> REPOSITORY_DISTRIBUTION
validate_run -> RUN_PACKAGE
```

`validate_run` loads once and applies ten validation layers:

1. serialization and schema;
2. package and index integrity;
3. Run/Graph/GO/CELL/reference identity;
4. adapter-backed provenance, authority, capability, and isolation;
5. candidate, digest, admission, and receipt lineage;
6. CELL manifest and GO candidate closure;
7. recomputed graph identity, coverage, predecessors, and acyclicity;
8. D2 admission and independent graph events;
9. D3 closure, graph seams, and Run Verifier isolation;
10. Owner Acceptance and post-acceptance security handoff.

The validator never trusts a self-reported verdict, actor, timestamp, acyclicity
flag, receipt list, or graph digest when it can recompute the fact.

## 21. Provenance adapter boundary

GLK defines exactly four abstract adapter operations:

```text
resolve_binding
verify_issuance
verify_isolation
check_liveness
```

Requests and results bind contract version, request digest, role binding, Run and
scope, artifact digest, status, evidence reference, and observation time. A trusted
adapter must attest role capability, issuance, required isolation dimensions, and
liveness. Free role or context strings are never sufficient.

GLK does not implement sessions, credentials, key custody, production issuance,
Broker services, replay, checkpoints, or Agent runtime provenance. LCagent or an
external trusted execution environment owns those implementations. GLK owns only
the abstract evidence contract and adapter interface.

## 22. Preflight and no-side-effect simulation

Bootstrap creates only a `DRAFT_SCAFFOLD` with unresolved values. It cannot create
current formal evidence or claim that a Run is complete.

Formal preflight requires the exact method lock, one canonical declared
installation, complete six-role bindings and capabilities, trusted adapter-backed
readiness evidence, a ten-layer valid package, a successful no-side-effect
simulation, and no active hold. `PREFLIGHT_REPORT` and `SIMULATION_REPORT` are
derived non-authoritative projections. Only a separate Supervisor admission may
record a mechanical gate result.

Simulation uses a separate simulation root and must prove that formal ledger and
index digests are unchanged. It rehearses every technical receipt followed by its
independent admission, graph-event release, liveness failure, architecture hold,
Owner gate, and maximal-safe fork activation.

## 23. Liveness, monitor, and architecture stops

Read failure, missing evidence, or stale observation never implies health. A role
whose observation deadline expires becomes unreachable. `MONITOR_CONTROL` has one
deterministic key and one append-only head, binds the exact indexed liveness
attestations for all current roles and the current adapter profile, and references
the existing Supervisor task/callback. It cannot create another task or schedule a
cron job.

A proven technical authority violation immediately produces `RUN_AUTHORITY_HOLD`.
Two consecutive HIGH architecture findings on the same path produce
`RUN_ARCHITECTURE_HOLD`, even when findings from another path are interleaved.
Recovery is limited to frozen amendment plus revalidation, or sealing the Run and
starting a new Run. Local rework cannot clear an architecture hold.

## 24. Formal and derived objects

Formal artifacts are append-only objects with one issuer and indexed lineage.
Validation, preflight, simulation, liveness, migration, and progress reports are
derived non-authoritative objects. They do not participate in technical verdicts,
cannot be indexed as receipts, and cannot advance state by themselves.

Formal progress reports both `required GO/D2` completion and `required CELL/D1`
completion, including exact counts and IDs, active GO IDs, typed waiting reasons,
blocked or unreachable role bindings, current holds, graph version, and CELL
manifest versions.

## 25. Method lock and migration

Every formal Run binds `GLK_METHOD_LOCK` to:

```text
https://github.com/DWG7318/large-loop-skill
graph-loop-skill
3.1.0
exact commit and release tag
schema and Skill bundle digests
real Run validator source-bundle digest
adapter profile and contract version
```

Preflight inspects only caller-declared installation roots. Missing, duplicate,
stale, or conflicting installations produce `GLK_SUPPLY_CHAIN_CONFLICT`; it does
not scan undeclared roots or fetch a remote repository.

Migration may preserve compatible GO topology, actual-consumption edges, causal
traces, and amendment history. Contracts and bindings require revalidation. Mixed
mutable receipts and sample bootstrap pass claims are excluded from the current
formal model. An unproven 2.4 receipt remains historical-only and can never become
3.1 current evidence through a migration report.

## 26. External ownership boundary

LCCoding owns project lifecycle, product-definition routing, centralized security
audit, and delivery policy. LCagent or a trusted execution environment owns session,
credential, issuance, replay/checkpoint, Broker, and runtime provenance mechanisms.
GLK remains a lightweight engineering method: it defines GO-DAG authority,
dependency unlock, maximal-safe activation, evidence contracts, and fail-closed
validation without implementing those external systems.

## 27. Worker-only Checker wake

Only the Worker completing its current formal CELL may invoke the four-level wake
ladder for the original Checker frozen at dispatch. The scoped message contains
GO ID, CELL ordinal, current Required CELL total, and delivered/check semantics.
The same CELL keeps its ordinal across rework. `BLOCKED` and
`EXECUTION_FAILURE` retain the same Run/GO/CELL/Round identity.

The levels are direct send at T+0, read/list and same-task unarchive/re-resolution
at T+2, one deterministic temporary heartbeat at T+4, and append-only
`PENDING_WAKE` at T+6. Each ACK window is at most 120 seconds and uses an injected
clock. The Checker first emits `WAKE_ACK` bound to Run, GO, CELL, Round, Checker
binding, thread, and host. Matching ACK or proven same-scope processing stops all
later levels and cleans temporary state. IDs are never guessed and replacement
roles are never created.

Worker readiness proves send, read, list, unarchive, bounded wait, heartbeat
upsert/delete, and pending-write capability. Other roles fail as
`WAKE_ROLE_FORBIDDEN`; this mechanism is not a general message bus.

## 28. Supervisor waiting, patrol, subagents, and Pin

The Supervisor ends its turn after dispatch/control work. Positive-duration or
looping `wait_threads` is `SUPERVISOR_WAIT_FORBIDDEN`; only a zero-time snapshot or
read is allowed. Only the Worker ladder may wait for a bounded ACK.

Each Run has one visible `RUN_PATROL_CONVERSATION` and one heartbeat, using
`gpt-5.6-luna` with `xhigh` and a frozen 10/15/30-minute interval. The patrol is not
a seventh authority role. It reports only unexplained stoppage, pending wake,
subagent misuse, Supervisor wait, duplicate patrol, Pin provenance, and terminal
closure. It cannot inspect product quality, repair, accept, plan, take over, or
re-dispatch.

GO, CELL, Round, plan step, visible stable task, and text `子任务` are not
subagents. Closed evidence of `spawn_agent`, `delegate_task`, hidden Agent, or
background Agent is forbidden.

Every method role and the patrol permanently lacks `set_thread_pinned(true)` and
equivalent Pin capability. Only an explicit Owner UI choice or item-specific
current-Run authorization is legal. Agent/method Pin is
`UNAUTHORIZED_THREAD_PIN`, even after later Unpin. Unknown provenance is
`PIN_PROVENANCE_UNKNOWN`; patrol must not unpin because an Owner choice may be
present. Pin is separate from archive, lifecycle, progress, and role indexing.

Terminal patrol closure is `LOOP_TERMINAL`, heartbeat deletion, `PATROL_CLOSED`,
then conversation archive.

## 29. Layered realtime progress

The progress stages are `DELIVERED`, `D1_ACCEPTED`, `GO_CANDIDATE_READY`,
`D2_VERIFIED`, `RUN_VERIFIED`, and `OWNER_ACCEPTED`.

Worker delivery never increments acceptance. Checker ACKs first and reports the
finest D1 count; only one current-valid admitted D1 PASS per Required CELL counts.
Checker sends the Supervisor one deduplicated GO-boundary milestone only after the
current Required CELL set is accepted and a current GO candidate closure exists.
Candidate readiness is not D2 verification.

Supervisor emits only material GO, outer Level reference, Graph, Run, hold, or
Required-version changes. It shows current Required CELL/D1, Required GO/D2,
ACTIVE_GO, WAITING_GO reasons, holds, graph/manifest/plan/capacity/load versions,
and never a single percentage. Verifiers emit verdicts only; patrol reports no
engineering progress.

Numerators come from current receipts/verdicts and denominators from versioned
Required sets. Amendments recompute current denominators while historical
projections remain immutable. Splitting a CELL adds no accepted progress.

## 30. Device and cumulative-load CELL capacity

Before plan freeze the Supervisor binds append-only `DEVICE_CAPACITY_PROFILE` and
`CUMULATIVE_ENGINEERING_LOAD` records with explicit CPU, RAM, GPU/VRAM
applicability, disk/IO, network/external, process/port, safe concurrency,
command-duration, context, and evidence facts. Unknown, stale, unitless,
free-text-only, or unproved capacity fails closed.

Every `CELL_WORK_ESTIMATE` covers total engineering cost: scope, dependencies,
artifacts, build/test matrix, independent Checker reproduction, regression,
evidence/hash/cleanup, context recovery, external tools/services, rollback/retry,
and cumulative baseline coupling. Small diffs do not erase full-regression cost.

`CELL_CAPACITY_GATE` is exactly `PASS`, `SPLIT_REQUIRED`, or `CAPACITY_BLOCKED`.
Only PASS allows dispatch. Pre-dispatch successors preserve one GO outcome and
acceptance, remain independently deliverable/D1-checkable, and each pass the gate.
A Worker cannot self-split; actual excess emits `CELL_SCOPE_EXCEEDED` and returns
to the original Checker/planning authority.

Late splitting records `POST_DISPATCH_CELL_SPLIT`. Three or more successors also
record `CELL_OVERSIZE_SEVERE` and force every undispatched CELL to be re-evaluated;
counts 6/7/8 are always severe. Boundary measurements update cumulative load.

DAG eligibility and device safety are separate. The maximal safe ACTIVE_GO set
also respects CPU, RAM, GPU/VRAM, disk/IO, process, port, external-service, and
heavy-validation reservations. Capacity never creates a fake dependency.

## 31. GLK 3.1 validation surface

The accepted ten validation layers remain technical authority layers. A current
3.1 package adds an operational-control gate for Worker wake, patrol uniqueness,
Pin provenance capability exclusion, capacity lineage, and severe-split
re-evaluation. Repository validation remains `REPOSITORY_DISTRIBUTION`; Run
validation remains `RUN_PACKAGE`. All reports are derived non-authoritative.

Preflight requires the 3.0 trust and isolation gates plus exact operational
capabilities, one patrol, current capacity/load, PASS dispatch gates, current
progress denominators, and no-side-effect operational simulation. Simulation uses
fake time and local facts and never mutates formal ledger/index bytes.
