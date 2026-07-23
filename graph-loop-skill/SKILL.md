---
name: graph-loop-skill
description: Use when the user says GLK, Graph Loop Skill, or legacy LLK/large-loop-skill; or when a complex project requires a Calabash-grounded GO graph with branches, joins, bounded cycles, partial unlock, dynamic graph routing, isolated GO Verification, and CELL-local Planner/Worker/Checker/Router governance. Never trigger together with SLK, MSLK, or another Loop method.
---
# Graph Loop Skill (GLK)
Use `GLK` as the official abbreviation and `$graph-loop-skill` as the Codex
invocation name.

`LLK`, `Large Loop Skill`, and `$large-loop-skill` are legacy names. They may be
recognized for migration, but every new formal run uses GLK identity and rules.
## Canonical Identity
- Product name: `Graph Loop Skill`.
- Abbreviation: `GLK`.
- Invocation: `$graph-loop-skill`.
- Target canonical repository: `https://github.com/DWG7318/graph-loop-skill`.
- Legacy repository: `https://github.com/DWG7318/large-loop-skill`.
- Default branch: `main`.
- Version source: repository `VERSION` and matching `v*` release tag.
- Current specification version: `2.0.0`.
GLK 2.0.0 is a breaking rename and architecture release. It preserves useful LLK
authority-separation ideas but replaces the old project-wide
`Planner -> Worker -> Checker -> Router` interpretation with a two-layer model:
```text
PROJECT / GO GRAPH LAYER
Supervisor <-> Grapher
        ↓ activates GO nodes
GO-scoped Verification receives completed candidates
        ↓ verdicts return to Grapher and Supervisor

CELL EXECUTION LAYER INSIDE EACH ACTIVE GO
Planner -> one active Worker from a Worker Set -> Checker -> Router
```
Planner, Worker, Checker, and Router operate at CELL scope. They do not choose the
next GO or mutate the GO graph.
## Core Definition
GLK is a Calabash-grounded, evidence-routed GO graph execution method.
```text
Owner intent and project evidence
        ↓
Full or Minimum Calabash
        ↓
Supervisor freezes project authority and autonomy
        ↓
Grapher creates a versioned GO Graph
        ↓
Grapher activates one or more READY GO nodes
        ↓
Each active GO executes CELL loops
        ↓
All required CELLs accepted
        ↓
Fresh isolated GO Verification
        ↓
GO verdict
        ↓
Grapher updates graph state and chooses legal next node(s)
        ↓
Terminal graph condition
        ↓
Supervisor final project composition audit
```
GLK is not a Chain method. It may contain paths, but it does not force persistent
Chains or synchronization Levels. A fixed multi-chain plan with full Level barriers
belongs to MSLK.
## Mandatory Calabash Definition Gate
Every GLK project requires a frozen `PROJECT_CALABASH_BASELINE`.

Use the full project Calabash when available. Otherwise Minimum Calabash is
mandatory:
```text
Grandpa -> Product Architecture -> Ontology
```
If no Calabash exists, Supervisor must establish Minimum Calabash from authoritative
Owner statements and verified project evidence before Grapher creates the formal
GO Graph, before Verification Contracts are frozen, and before any role starts
formal execution.

Supervisor may normalize one uniquely supported interpretation. It must not invent
Owner intent. An irreducible product-definition ambiguity is:
```text
CALABASH_DEFINITION_BLOCKED
```
and is Owner-exclusive.

Every GO node records one versioned `GO_CALABASH_TRACE`. Every graph edge records
an `EDGE_AUTHORITY_TRACE`. Every `GO_VERIFICATION_CONTRACT` derives from the GO
trace. A node, edge, or Verification Contract without an authoritative trace is
invalid.

Read
[`references/calabash-and-go-graph.md`](references/calabash-and-go-graph.md)
before graph planning.
## Role Types
GLK has seven authority role types:
```text
SUPERVISOR
GRAPHER
PLANNER
WORKER
CHECKER
ROUTER
VERIFICATION
```
There may be multiple role instances. Every formal decision has exactly one named
authority owner.
### Project-level roles
- **Supervisor** owns Calabash, project authority, frozen contracts, autonomy,
  provisioning, Owner-exclusive escalation, graph-amendment approval, and final
  project composition audit.
- **Grapher** is the sole owner of GO Graph structure, node/edge state, READY/ACTIVE
  sets, graph scheduling, legal graph routing, graph revision proposals, bounded
  cycle accounting, and terminal-condition evaluation.
### CELL-level roles
For each active GO, one CELL at a time passes through:
```text
Planner -> active Worker -> Checker -> Router
```
- **Planner** owns the current CELL Contract, attempt design, eligible Worker Set,
  handoff plan, and next CELL proposal inside the already activated GO.
- **Worker** owns product implementation for one active lease and produces an
  immutable candidate plus implementation-side evidence.
- **Checker** independently validates the exact immutable CELL candidate in a clean
  environment and issues a factual pass/fail/blocked result.
- **Router** is the sole authority for the current CELL route. It does not validate,
  implement, plan a GO, or choose a graph edge.
### GO-level role
- **Verification** independently judges one immutable GO candidate against its
  Calabash-grounded `GO_VERIFICATION_CONTRACT`. It does not plan, implement, repair,
  route, or ask Owner.
## Thirty Hard Rules
1. Select GLK exactly once for one project run; never combine, nest, or switch
   methods inside the active run.
2. Freeze a full Calabash or Minimum Calabash before formal GO Graph creation.
3. Every GO node and graph edge must trace to the frozen Calabash or a verified
   graph-runtime fact allowed by the frozen graph contract.
4. Grapher is the sole GO Graph authority; no Planner, Router, Checker, Worker, or
   Verification may choose the next GO.
5. Supervisor approves and freezes graph versions but does not perform ordinary
   graph routing.
6. GO Graph nodes are GOs. CELLs never appear as cross-GO graph nodes or edges.
7. No CELL may consume another GO's unfinished CELL, mutable intermediate state, or
   provisional evidence.
8. Cross-GO input is valid only from a `GO_VERIFIED` source and a frozen named
   output.
9. Conditional edges must use frozen, observable, evidence-based predicates.
10. Every cycle is explicit, bounded, and has an exit condition, iteration budget,
    invariant, and hard brake.
11. Every activated GO has a current `GO_VERIFICATION_CONTRACT` and a fresh sterile
    Verification instance in `READY_WAITING_GO` before its first CELL starts.
12. After Router emits `GO_CANDIDATE_READY`, Checker sends the frozen neutral GO
    package directly to Verification; Supervisor is not an information relay.
13. Verification sends its signed verdict directly to Grapher and Supervisor and
    copies the owning CELL-control set for legal rework.
14. Verification is the sole GO verdict authority.
15. Planner, Checker, and Router are CELL-scope roles even when their instances
    persist across sequential CELLs in one GO.
16. Planner owns the CELL assignment and activates exactly one eligible Worker
    lease for the initial attempt or after a Router-authorized rework/handoff/switch;
    Planner cannot route the result.
17. One CELL may define multiple eligible Worker instances, but exactly one Worker
    lease may be ACTIVE at any time.
18. Concurrent product writes by two Workers in the same CELL are forbidden.
19. Router is the sole authority to continue, rework, hand off, switch Worker,
    replan the CELL, accept the CELL, block, reject, or hand a complete GO candidate
    to Verification; Router never selects the replacement Worker.
20. Worker switching requires the prior lease to be revoked, the workspace sealed,
    and an immutable handoff artifact created before the next Worker activates.
21. If Worker contributions are independently verifiable, split them into separate
    CELLs instead of hiding parallel work inside one CELL.
22. Worker owns ordinary product implementation and product rework. Checker and
    Verification never edit product artifacts and accept their own edits.
23. Every CELL requires Worker evidence and independent Checker validation against
    the exact immutable candidate.
24. Detection is tiered as `CELL_ALWAYS`, `CELL_TRIGGERED`, `GO_BOUNDARY`,
    `GRAPH_EDGE`, and `PROJECT_FINAL`.
25. Worker, Checker, Router, Verification, Grapher, and Planner identities require
    explicit context, workspace, capability, model-binding, evidence, and lifecycle
    isolation appropriate to their authority.
26. All routine work inside `PROJECT_AUTONOMY_ENVELOPE` proceeds without Owner
    confirmation or per-action authorization.
27. Only a proven Owner-exclusive objective, product-definition, credential, legal,
    destructive, irreversible, materially costly, physical, or external-account
    matter may reach Owner.
28. Plans, graph versions, receipts, evidence, verdicts, worker leases, handoffs,
    and authority decisions are append-only; only declared current-state indexes are
    mutable.
29. Missing roles, unavailable environments, stale evidence, silence, timeout,
    partial artifacts, or green self-tests never imply acceptance.
30. Project completion requires the terminal graph condition, all required terminal
    GO verdicts, graph composition checks, safety gates, final evidence, and
    `PROJECT_GOAL` when configured.

Schedule, cost, model confidence, or Owner urgency cannot waive these rules.
## Method Selection Gate
Use GLK when the project needs one or more of:
- arbitrary GO dependencies;
- conditional branches;
- partial downstream unlock;
- joins with `ALL`, `ANY`, or bounded quorum semantics;
- fallback paths;
- bounded cycles;
- runtime graph-route choices from verified evidence;
- graph revisions after new facts;
- multiple concurrently active GO nodes without a fixed Level barrier;
- a CELL Worker Set with controlled sequential switching or specialization.
Use MSLK instead when the work can be frozen as fixed persistent Chains and ordered
full-barrier Levels.

Use SLK instead when one stable execution owner and one coherent serial domain are
sufficient.

If GLK's graph, isolation, or role capabilities cannot be provided, record
`METHOD_SELECTION_FAILED`; preserve evidence and stop new formal work. The active run
never converts itself to another method.
## Exclusive Method Lock
After GLK selection:
- invoke GLK once;
- do not load SLK, MSLK, legacy LLK, or another Loop topology;
- do not borrow Chain/Level barriers and call them graph routing;
- do not hide roles as subagents or background jobs;
- do not change method identity to bypass a blocker;
- preserve all accepted evidence if the run stops.
Shared principles do not make methods composable.
## Visible Roles and Lifecycle
Every formal role is a visible Codex conversation under the same project. Hidden
agents, subagents, background workers, and `delegate_task` are forbidden.

Persistent project roles:
```text
one Supervisor
one Grapher
```
GO/CELL roles may be created or unarchived when formal work is ready:
```text
Planner
Checker
Router
one or more eligible Worker conversations
fresh Verification per GO candidate attempt
```
A GO's fresh Verification instance is created before its first CELL, enters
`READY_WAITING_GO`, and remains sterile until direct handoff.
A role without authorized work is archived. An archived role performs no hidden
work.

Every role instance records:
```text
role_id
role_type
conversation_id
context_id
workspace_id
capability_profile_id
model_binding_id
evidence_path
lifecycle_state
authority_scope
```
Read
[`references/role-authority-and-isolation.md`](references/role-authority-and-isolation.md)
before role launch.
## Project Autonomy Envelope
Before execution, Supervisor freezes `PROJECT_AUTONOMY_ENVELOPE` containing:
- authorized repository and write roots;
- allowed local build, test, scan, and evidence commands;
- approved non-destructive Git operations;
- temporary databases, fixtures, browsers, ports, and local services;
- model/tool budgets;
- approved reversible recovery operations;
- forbidden external, destructive, credential, legal, financial, or production
  actions.

Routine work inside the envelope requires no Owner approval at CELL, Worker-switch,
GO, graph-edge, branch, join, loop-iteration, or project-control boundaries.

No role may ask Owner to confirm ordinary implementation, select between technically
equivalent options, approve continuation, inspect code/logs/tests, troubleshoot a
recoverable issue, or repeat an action an authorized role can perform.

A routine request is:
```text
AUTONOMY_VIOLATION
```
Only Supervisor may contact Owner, and only with one precise proven Owner-exclusive
decision or action.
## GO Graph Contract
Grapher authors and maintains one versioned `PROJECT_GO_GRAPH`.

Required fields:
```text
graph_id / graph_version / graph_hash
Calabash baseline hash
node registry
edge registry
start set
terminal condition
ready predicate
resource/conflict groups
branch predicates
join semantics
bounded-cycle contracts
named output contracts
Verification bindings
criticality and risk
graph evidence paths
```
### Node contract
Every GO node defines:
```text
GO_ID
GO_CALABASH_TRACE
outcome claim
required predecessor states
required named inputs
frozen outputs
GO_VERIFICATION_CONTRACT
resource/conflict groups
risk and criticality
CELL planning boundary
terminal or optional status
```
### Edge types
GLK supports:
```text
HARD_DEPENDENCY
CONDITIONAL
JOIN_ALL
JOIN_ANY
JOIN_QUORUM
FALLBACK
LOOP_BACK
CONFLICT
```
Every edge defines a source, target, required source verdict/output, predicate,
evidence source, and invalidation behavior.

A `CONFLICT` is a scheduling constraint, not evidence that one GO depends on another.
### READY set
Grapher is the sole writer of:
```text
GRAPH_READY_SET
GRAPH_ACTIVE_SET
GRAPH_BLOCKED_SET
GRAPH_TERMINAL_SET
```
A GO becomes READY only when every required predecessor verdict/output, branch
predicate, conflict constraint, Verification binding, role/environment binding,
autonomy rule, and safety condition passes.

Grapher may activate all READY nodes or a recorded subset constrained by resource,
risk, conflict, or critical-path policy. It must record why a READY node was deferred.
### Partial unlock
Unlike MSLK, GLK may unlock one successor as soon as its own edge predicates pass.
It does not wait for an unrelated full-Level barrier.
### Bounded cycles
Every `LOOP_BACK` edge records:
```text
loop_id
entry node
source and target
iteration counter
maximum iterations
invariant
exit predicate
required evidence
hard brake
failure route
```
An unbounded or self-modifying cycle is invalid.

Read
[`references/calabash-and-go-graph.md`](references/calabash-and-go-graph.md).
## Graph Revision
Grapher may propose a versioned graph amendment when evidence reveals:
- missing or invalid node boundaries;
- a new verified dependency;
- a false branch assumption;
- a join or conflict defect;
- a bounded loop requirement;
- a dead end or unreachable terminal condition;
- changed risk or resource constraints.
Grapher cannot silently mutate the active graph.

Procedure:
```text
GRAPH_AMENDMENT_PROPOSED
→ impact analysis
→ Calabash trace check
→ affected GO/output invalidation analysis
→ Supervisor approval or rejection
→ no-side-effect graph simulation
→ GRAPH_REVISION_SIMULATION_PASS
→ new graph version activation
```
Accepted historical nodes, evidence, and routes remain append-only. A changed GO
outcome or product definition may require a Calabash amendment and Owner-exclusive
decision.
## CELL Control Contract
Grapher activates a GO, not a CELL.

Inside the GO, Planner prepares one formal CELL at a time:
```text
CELL_ID / ATTEMPT_ID
GO_ID / graph version
objective
authoritative inputs
allowed and forbidden write scope
output artifact
acceptance criteria
detection allocation
dependencies inside the same GO
Worker Set
handoff and switch rules
completion criteria
```
Planner cannot use another GO's unfinished CELL as input.

Planner activates exactly one eligible Worker lease for the initial attempt. After a
Checker verdict, any further activation must follow Router's recorded route. Router
may return `CELL_REPLAN` but never chooses the Worker.

Read
[`references/cell-worker-set-and-handoff.md`](references/cell-worker-set-and-handoff.md).
## Multiple Workers in One CELL
A CELL may have a versioned `CELL_WORKER_SET`:
```text
worker_id
specialization
model binding
capability profile
workspace template
eligibility predicate
allowed scope
handoff role
priority
```
Valid uses include:
- primary/alternate recovery;
- tool or language specialization;
- bounded sequential handoff;
- a model switch after evidence shows the active binding is unsuitable.
Exactly one Worker owns:
```text
ACTIVE_WORKER_LEASE
```
for the CELL at any moment.

Standby Workers do not inspect mutable active state, write product artifacts, poll,
or perform hidden work.

The one-active rule is per CELL. Grapher may activate multiple independent GO nodes,
so different CELLs may each have one active Worker concurrently when graph conflicts,
resource limits, write scopes, and isolation all permit it.

The active Worker emits either an immutable candidate, a checkpoint/handoff, a
blocker receipt, or an execution-failure receipt.
### Worker switch
A legal switch is:
```text
Worker receipt
→ Checker validates the state or blocker
→ Router emits WORKER_HANDOFF or WORKER_SWITCH
→ Planner revokes old lease
→ old workspace sealed
→ immutable handoff package
→ Planner selects an eligible replacement
→ Planner grants new lease under the Router route
→ replacement starts in a fresh workspace
```
The replacement receives the frozen CELL Contract, immutable artifact/checkpoint,
validated failure facts, and remaining objective. It does not inherit hidden reasoning
or a mutable previous workspace.

If two Workers are active for one CELL, record:
```text
ACTIVE_WORKER_COLLISION
```
Stop the CELL, quarantine both candidates, restore the last valid baseline, and route
through Router.
## Planner Authority
Planner may:
- derive one CELL from the active GO's frozen outcome;
- define same-GO CELL dependencies;
- prepare the Worker Set, select one eligible Worker, and grant the active lease;
- prepare rework, worker-switch, and immutable handoff assignments;
- propose splitting an over-broad CELL;
- maintain the GO's CELL ledger.
Planner may not:
- implement;
- validate;
- accept;
- route;
- change a GO outcome;
- choose a graph node or edge;
- alter Calabash or graph state.
If a CELL can be split into independently acceptable outcomes, Planner must split it.
Multiple Workers inside one CELL are not a substitute for correct CELL granularity.
## Worker Authority
Only the Worker holding the current active lease may:
- edit product artifacts inside the CELL scope;
- run implementation-side checks;
- create a candidate or checkpoint;
- issue a formal completion, blocker, handoff, or execution-failure receipt.
A Worker never self-accepts, chooses another Worker, chooses the next CELL, changes
the GO, or contacts Owner.

Worker product rework remains Worker-owned.
## Checker Authority
Checker independently validates the exact immutable candidate in a clean environment.

Checker may inspect files, diffs, tests, scans, runtime behavior, evidence, boundaries,
and blocker facts. It issues:
```text
CHECKER_PASS
CHECKER_FAIL
CHECKER_BLOCKED
CHECKER_SCOPE_VIOLATION
CHECKER_ENVIRONMENT_BLOCKED
```
Checker does not edit product artifacts, select a graph path, activate a Worker,
modify acceptance, or close a GO.
## Router Authority
Router consumes the frozen CELL Contract, Worker receipt, Checker verdict, active
lease state, and GO CELL ledger.

Valid routes:
```text
CELL_ACCEPTED
WORKER_REWORK
WORKER_HANDOFF
WORKER_SWITCH
CELL_REPLAN
CELL_BLOCKED
CELL_REJECTED
GO_CANDIDATE_READY
MANUAL_INTERVENTION
```
`MANUAL_INTERVENTION` is valid only after Supervisor has proved an Owner-exclusive
item or a required external action. It is a non-terminal hold.

Router does not:
- rerun Checker work;
- implement;
- author a CELL;
- choose a GO edge;
- update the GO Graph;
- issue a GO verdict;
- substitute for Grapher or Verification.
When the final required CELL is accepted, Router may emit
`GO_CANDIDATE_READY`. Checker then freezes the GO candidate and sends the neutral
package directly to the pre-bound fresh Verification instance.
## GO Verification
Before a GO's first CELL, Supervisor creates a fresh sterile Verification instance
and Grapher indexes:
```text
GO_VERIFICATION_BINDING
Verification role template
fresh conversation/context/environment binding
model binding
direct intake route
evidence path
GO_VERIFICATION_CONTRACT
```
A materially changed candidate, contract, Calabash trace, dependency, or environment
requires a fresh Verification attempt.

Verification receives:
- relevant Calabash baseline and hashes;
- GO trace and Verification Contract;
- immutable GO candidate and frozen inputs;
- accepted CELL receipt index;
- neutral evidence index;
- environment and authorized commands;
- safety boundaries.
It does not initially receive Checker recommendations, Worker/Checker transcripts,
hidden reasoning, prior unrelated verdicts, or mutable state.

Valid verdicts:
```text
GO_VERIFIED
GO_EVIDENCE_GAP
GO_REWORK_REQUIRED
GO_DEFINITION_DEFECT
GO_BLOCKED
GO_REJECTED
```
Verification sends the signed verdict directly to Grapher and Supervisor and copies
Planner/Checker/Router for legal local action.
- `GO_VERIFIED`: Grapher freezes outputs and evaluates outgoing edges.
- `GO_EVIDENCE_GAP`: Grapher keeps node unverified; Planner may create evidence work.
- `GO_REWORK_REQUIRED`: Planner creates new CELL work under the same GO outcome.
- `GO_DEFINITION_DEFECT`: Grapher proposes node/graph revision; Supervisor checks
  Calabash continuity.
- `GO_BLOCKED`: Grapher may route other independent nodes; Supervisor handles shared
  resources or Owner-exclusive matters.
- `GO_REJECTED`: Grapher follows a frozen fallback/reject edge or project hard brake.
Read
[`references/verification-and-evidence.md`](references/verification-and-evidence.md).
## Detection System
Every role-capability manifest records what is actually available. Every GO has a
versioned detection profile with five tiers:
```text
CELL_ALWAYS
CELL_TRIGGERED
GO_BOUNDARY
GRAPH_EDGE
PROJECT_FINAL
```
- `CELL_ALWAYS`: every candidate.
- `CELL_TRIGGERED`: when an explicit impact predicate is true.
- `GO_BOUNDARY`: fresh Verification of the complete GO.
- `GRAPH_EDGE`: named output, branch, join, conflict-release, or loop-edge checks.
- `PROJECT_FINAL`: terminal composition, security, release, and handoff checks.
A valid receipt records command/action, version/configuration, candidate identity,
result, evidence path, and trigger predicate where applicable.

`NOT_TRIGGERED` is valid only with evidence that the frozen predicate was false.
Plain `not applicable`, inherited evidence, or another role's receipt is invalid.

Read
[`references/detection-autonomy-and-recovery.md`](references/detection-autonomy-and-recovery.md).
## Isolation
Separate role labels are not enough.

At minimum isolate:
- conversation and context;
- mutable workspace;
- runtime state;
- model binding;
- capability profile;
- evidence path;
- lifecycle identity;
- decision input.
Checker and Verification must never share mutable workspaces, databases, browser
profiles, ports, temp paths, success markers, evidence paths, or conversation context.

Worker switching must never reuse one mutable Worker workspace.

Grapher must not inherit Planner or Router hidden reasoning; it receives formal graph
events and signed GO verdicts.

Same-model use is allowed only with distinct role bindings and environments. Model
diversity is an additional defense, not the definition of independence.
## Readiness Eval
Before formal work, every project-level role and every role template that may be
instantiated must pass the GLK readiness Eval with exactly `25/25`.

This includes:
```text
Supervisor
Grapher
Planner template
Worker template(s)
Checker template
Router template
Verification template
```
A changed skill, Eval, role template, model binding, capability profile, or authority
scope invalidates the related receipt.
## Mandatory Simulation Gate
After readiness and before formal execution, run a no-side-effect simulation that
rehearses:
1. Calabash gate and GO/edge traceability;
2. one graph start node;
3. one fork and partial unlock;
4. one join;
5. one bounded loop or its explicit absence;
6. one CELL `Planner -> Worker -> Checker -> Router` pass;
7. one CELL Worker Set with a single active lease;
8. one planned `WORKER_HANDOFF` and one recovery `WORKER_SWITCH` with immutable
   handoff;
9. one failed candidate routed to Worker rework;
10. one `GO_CANDIDATE_READY` direct Verification handoff;
11. one GO verdict returned to Grapher;
12. one graph edge activation;
13. one routine issue resolved without Owner confirmation;
14. one graph revision proposal and simulation;
15. the terminal graph composition check.
Record `SIMULATION_PASS` only when every invariant holds. Missing capability fails
closed.
## Dispatch and Non-Interference
After Planner grants the formal active Worker lease and dispatches the assignment,
Planner, Checker, and Router do not poll or concurrently modify the CELL.

The active Worker owns the lease until it sends:
```text
WORKER_COMPLETION_RECEIPT
WORKER_HANDOFF_RECEIPT
WORKER_BLOCKER_RECEIPT
WORKER_EXECUTION_FAILURE
```
Checker then validates. Router acts only after Checker verdict.

During active GO Verification, Worker, Planner, Checker, Router, Grapher, and
Supervisor do not inject suggestions into the Verification context.
## Progress
GLK progress is graph-state progress, not a misleading single CELL count.

Maintain:
```text
verified required GO / total required GO
READY nodes
ACTIVE nodes
VERIFYING nodes
BLOCKED nodes
terminal condition status
bounded cycle counters
accepted CELL count as a secondary metric
```
A high CELL count does not imply project completion.

## Markdown and Context Boundary
Every governed Markdown artifact has a hard maximum of 1000 physical lines,
including blanks and fenced content.
Maintain one mutable `GRAPH_CONTINUATION_INDEX` below 200 lines containing only:
```text
Calabash and graph version
READY / ACTIVE / VERIFYING / BLOCKED sets
active GO/CELL and Worker lease
cycle counters and conflict locks
latest signed verdicts
current blockers
next authorized actions
```
Historical plans, graph events, routes, evidence, and handoffs remain in append-only
semantic shards. Split before the next append would cross the limit; never delete
evidence merely to make a file smaller.
After context compaction or role recovery, reload the index, governing contracts,
latest immutable candidate, and signed receipts before acting.

## Recovery
Never recover by guessing.
### Worker unavailable
- freeze or recover the latest immutable checkpoint;
- Checker validates checkpoint usability;
- Router emits `WORKER_HANDOFF`, `WORKER_SWITCH`, or `CELL_BLOCKED`;
- Planner revokes the old lease before activating a replacement.
### Planner, Checker, or Router context lost
- Supervisor records `GOVERNANCE_HOLD`;
- preserve artifacts and append-only records;
- create a recovery packet from frozen contracts and receipts;
- rebind a fresh role instance;
- rerun affected readiness and simulation;
- Router resumes only from a proven state.
### Verification unavailable
- node remains `VERIFYING` or `GO_BLOCKED`;
- previous verdict cannot be reused for a changed candidate;
- launch a fresh preflighted Verification attempt.
### Grapher unavailable
- freeze graph routing;
- active CELL work may finish only when its acceptance cannot be invalidated;
- no new GO activates;
- restore Grapher from graph version, event ledger, and signed verdicts.
### Graph deadlock
Grapher records:
```text
GRAPH_DEADLOCK
```
with blocked nodes, unmet predicates, cycles, conflicts, and terminal reachability.
It proposes a versioned amendment or triggers a hard brake. It never invents a pass.
## Final Project Acceptance
Grapher may record `GRAPH_TERMINAL_REACHED` only when the frozen terminal condition
is satisfied.

Supervisor then performs final composition audit:
- all required terminal GO nodes are `GO_VERIFIED`;
- every consumed graph output matches the frozen producer artifact;
- branch, join, conflict, and loop records are complete;
- no required node is orphaned, stale, or silently skipped;
- graph and Calabash hashes match the accepted versions;
- PROJECT_FINAL detection passes;
- safety and hard brakes are clear;
- final evidence index and candidate handoff exist;
- `PROJECT_GOAL` is satisfied when configured.
Only Supervisor publishes the final queue. GLK output is a candidate handoff and
never silently overwrites production or authoritative release assets.
## State Model
### Worker lease
```text
ELIGIBLE
→ ACTIVE
→ CHECKPOINTED | CANDIDATE_DELIVERED | BLOCKED | FAILED
→ REVOKED
```
Exactly one ACTIVE lease per CELL.
### CELL
```text
PLANNED
→ WORKER_LEASE_GRANTED
→ WORKER_ACTIVE
→ CANDIDATE_DELIVERED
→ CHECKER_VALIDATING
→ CELL_ACCEPTED
```
Alternative routes:
```text
WORKER_REWORK
WORKER_HANDOFF
WORKER_SWITCH
CELL_REPLAN
CELL_BLOCKED
CELL_REJECTED
```
### GO node
```text
PLANNED
→ WAITING_DEPENDENCY
→ READY
→ ACTIVE
→ CELLS_ACCEPTED
→ VERIFYING
→ GO_VERIFIED
```
Alternative states:
```text
GO_EVIDENCE_GAP
GO_REWORK_REQUIRED
GO_DEFINITION_DEFECT
GO_BLOCKED
GO_REJECTED
SUPERSEDED
SKIPPED_BY_FROZEN_BRANCH
```
### Graph
```text
DRAFT
→ FROZEN
→ ACTIVE
→ GRAPH_TERMINAL_REACHED
→ PROJECT_ACCEPTED
```
Revision states:
```text
GRAPH_AMENDMENT_PROPOSED
GRAPH_REVISION_SIMULATING
GRAPH_REVISION_ACTIVE
GRAPH_DEADLOCK
GOVERNANCE_HOLD
```
## Launch Checklist
Confirm:
- canonical GLK 2.0.0 identity and legacy migration plan;
- GLK sole-method lock;
- full or Minimum Calabash baseline;
- GO and edge Calabash traces;
- frozen graph version, start set, terminal condition, and bounded-cycle rules;
- Supervisor and Grapher readiness;
- all instantiable role templates at `25/25`;
- no-side-effect `SIMULATION_PASS`;
- `PROJECT_AUTONOMY_ENVELOPE`;
- explicit graph authority and CELL authority boundaries;
- every activated GO has Verification binding;
- every CELL has one Planner, Checker, Router scope and a Worker Set;
- exactly one active Worker lease per CELL;
- immutable handoff and switch rules;
- separate Worker, Checker, Router, Verification, Planner, Grapher environments;
- layered detection profiles;
- append-only graph/evidence/lease ledgers;
- recovery and Owner-exclusive escalation;
- terminal project composition criteria.
## Red Flags
Stop when any appears:
- “LLK and GLK are interchangeable names in an active run.”
- “Planner may choose the next GO.”
- “Router can update the graph.”
- “Grapher can decide whether a CELL passed.”
- “Two Workers can edit the same CELL at the same time.”
- “Standby Worker can quietly prepare in the background.”
- “Worker switch can reuse the dirty old workspace.”
- “Checker can fix product code and accept its own fix.”
- “GO-B can start from GO-A/CELL-03.”
- “Verification can infer success without Calabash.”
- “Supervisor must relay Checker evidence to Verification.”
- “A branch condition can be invented after seeing the desired result.”
- “A loop may continue until the model feels satisfied.”
- “Please ask Owner whether routine work should continue.”
- “Many accepted CELLs mean the graph is complete.”
Every red flag means stop, preserve evidence, restore authority and isolation, and
resume only from a valid frozen state.
## Version Note
Version `2.0.0` renames Large Loop Skill (LLK) to Graph Loop Skill (GLK) and adds:
- mandatory Calabash or Minimum Calabash;
- project-level Supervisor/Grapher separation;
- GO-only graph nodes and evidence-routed edges;
- conditional branches, joins, partial unlock, fallbacks, and bounded cycles;
- CELL-local Planner/Worker/Checker/Router roles;
- multiple eligible Workers per CELL with exactly one active lease;
- immutable Worker handoff and switch;
- isolated GO Verification;
- MSLK-derived autonomy, isolation, evidence, detection, and GO-boundary rules;
- explicit migration from old Router-owned project closure to
  Verification/Grapher/Supervisor layered authority.
