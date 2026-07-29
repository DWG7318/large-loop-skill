---
name: graph-loop-skill
description: Use for one frozen engineering Run whose independently verifiable GO outcomes form a directed acyclic GO execution graph that cannot be represented honestly as a strict line or stable Chain/Stage plan.
version: 2.3.1
---

# Graph Loop Skill (GLK) 2.3.1

## Mandatory load chain

Before formal execution, read `SPEC.md` completely. Then read the relevant files
under `glk/references/` and use the versioned templates plus
`glk/schemas/glk.schema.json`.

Authority order is:

```text
Owner decisions
-> frozen RUN_CONTRACT
-> SPEC.md
-> relevant references
-> templates and executable schema
-> examples
```

Missing or conflicting authority is `GLK_CONTRACT_BLOCKED`; fail closed.

## Canonical identity

GLK governs one bounded Run as a directed acyclic GO-to-GO execution graph. Nodes
are independently verifiable GO outcomes. Edges are mandatory D2
completion-precedence relations. GLK is not a Workflow, Code Graph, business graph,
dependency inventory, Chain map, or Stage plan.

## Six roles

GLK has exactly:

```text
Run Supervisor
Worker
Checker
GO Verifier
Run Verifier
Owner
```

Every Run receives a fresh Run Supervisor instance and isolated binding. Never reuse
one Supervisor instance, context, mutable workspace, or evidence root across Runs.
Concurrent active GO nodes receive isolated Worker, Checker, and GO Verifier
instances without adding role types.

## Method

1. Load and validate one frozen `RUN_CONTRACT`.
2. Construct the minimum complete GO set.
3. Freeze every GO claim, evidence boundary, predecessor, and conflict key.
4. Add only mandatory D2 predecessor edges using the edge test.
5. Validate acyclicity, reachability, terminal coverage, and Run Feature coverage.
6. Freeze `GRAPH_BASELINE`.
7. Classify unresolved non-active nodes as `WAITING_GO` with typed
   `waiting_reasons`.
8. Immediately activate the maximal safe set of waiting-clear GO nodes.
9. Execute each active GO through Worker D0, independent Checker D1, and independent
   GO Verifier D2.
10. Recompute the graph after every relevant event; newly unblocked GO nodes enter
    `ACTIVE_GO` directly.
11. After all Required GO outcomes resolve, obtain independent Run Verifier D3.
12. Conduct immediate Run Owner Acceptance and emit `LOOP_OWNER_ACCEPTED` or the
    appropriate rework/change verdict.
13. Emit the accepted candidate's standardized security handoff to LCCoding.

## Hard constraints

- no schedulable intermediate queue between waiting and active execution;
- multi-GO activation capability is mandatory;
- Run Supervisor maintains a maximal safe `ACTIVE_GO` set;
- among conflicting safe alternatives, activate the greatest possible GO count;
- arbitrary serialization is forbidden;
- non-dependency constraints never become fake dependency edges;
- execution is acyclic;
- six roles only;
- Run Supervisor never signs D1, D2, or D3;
- D2 consumes D1 for the same immutable candidate;
- D3 consumes D2 and tests graph seams plus the final Run claim;
- no silent graph, role-binding, candidate, or evidence amendment;
- centralized vulnerability closure remains owned by LCCoding.

## Required references

- graph construction: `glk/references/go-graph-construction.md`
- scheduling: `glk/references/scheduling.md`
- state: `glk/references/state-machine.md`
- roles and isolation: `glk/references/roles-and-isolation.md`
- verification: `glk/references/verification.md`
- amendments and resolutions: `glk/references/graph-amendment.md`
- Owner Acceptance and security handoff:
  `glk/references/owner-acceptance.md` and
  `glk/references/security-boundary.md`
