# GLK Standard Specification 2.3.1

## 1. Identity

Graph Loop Skill (GLK) governs one bounded engineering Run represented honestly as
a directed acyclic GO Execution Graph.

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

## 11. Formal resolution

`SUPERSEDED` and `CANCELLED` do not imply success. A formal resolution requires a
versioned graph amendment, authority binding, evidence, successor-release decision,
and Required-set decision.

A Required GO stops blocking Run completion only when it has D2 PASS or an approved
amendment removes/replaces it. A formal resolution releases successors only when its
contract explicitly says so.

## 12. Graph amendment

A frozen graph changes only through `GRAPH_AMENDMENT`, recording reason, before and
after versions, affected claims, active-work impact, candidate/evidence invalidation,
rollback, authority, and issue time.

Product-definition changes return to LCCoding/Calabash rather than being hidden as
graph edits.

## 13. Owner Acceptance

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

## 14. Security boundary

GLK performs Run-contract-local safety checks only. It does not issue centralized
vulnerability closure.

After required Runs are Owner-accepted, GLK emits a versioned security handoff that
binds the accepted candidate and scope. LCCoding owns the independent centralized
audit, repair loop, closure, and Post-Security Owner Acceptance.

## 15. Failure rules

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

## 16. Completion

A GLK Run completes only when all Required GO claims are resolved under the frozen
graph, terminal coverage is complete, D3 passes on the final candidate, evidence and
candidate identities are synchronized, the Owner signs `LOOP_OWNER_ACCEPTED`, and
the LCCoding security handoff is emitted.
