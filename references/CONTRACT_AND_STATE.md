# LLK Contract and State

## Contents

- Control Tree
- Frozen Project Contract
- Isolation and Model Bindings
- Loop Contract
- State Machine
- CELL Contract
- Split Proposal
- Amendment Rules

## Control Tree

Create only what the project needs, using this default shape:

```text
.large-loop/
  project-contracts/r0001.md
  config/
    isolation-policies/r0001.md
    model-bindings/r0001.json
  role-registry.json
  workspace-registry.json
  state.json
  events.jsonl
  evidence-index.jsonl
  loops/
    <loop-id>/
      contracts/r0001.md
      cells/<cell-id>/
        attempts/<attempt-id>/
          assignment.md
          worker-receipt.md
          check-report.md
          route-record.md
      splits/
      handoff/
```

Keep authoritative project assets outside this tree. LLK artifacts are candidate outputs until accepted and applied by the owning project.

## Frozen Project Contract

Record at minimum:

- project ID, Owner objective, source project, and authoritative asset boundaries;
- in-scope and out-of-scope work;
- measurable project acceptance and hard brakes;
- role/context/workspace/capability/model bindings and separation constraints;
- approved per-role providers, models, endpoint/credential references, tools, skills, parameters, budgets, fallbacks, and escalation choices;
- Loop graph and dependency rules;
- Worker isolation and write scopes;
- double-validation methods;
- Router route conditions;
- heartbeat/manual inspection interval and timeout thresholds;
- handoff, release, rollback, and amendment rules;
- contract revision and content hash.

Never store raw credentials. Store only secure-loader names or secret references.

## Isolation and Model Bindings

The frozen isolation policy and model-binding matrix are contract revisions. Every active role registry entry points to immutable policy/binding IDs and hashes. There is no implicit global model configuration. Read `ISOLATION_AND_MODEL_BINDINGS.md` for required fields and switch rules.

## Loop Contract

Each Loop defines objective, parent/children, dependencies, CELL sequence or selection policy, inputs, outputs, artifact identity method, Worker write scope, Worker validation, Checker independent validation, route conditions, hard brakes, and parent composition contribution.

## State Machine

```text
draft -> contract-qc -> frozen -> planning -> executing -> checking -> routing
                                                        ^             |
                                                        |             +-> continue -> planning -> next CELL/rework
                                                        |             +-> replan -> amendment -> contract-qc
                                                        |             +-> done
                                                        |             +-> reject
                                                        |             +-> manual-intervention
```

Observation overlays do not replace chain state:

- `stalled-unconfirmed`: activity or silence lacks a formal checkpoint.
- `handoff-risk`: sender output exists but receiver acknowledgement is missing.
- `governance-hold`: Supervisor observes that required authority is unavailable or that runtime isolation/model binding differs from the frozen contract before a formal route can be issued; it has no routing or closure effect.
- `paused`: Supervisor or Owner intentionally suspends dispatch.

## CELL Contract

A formal CELL assignment includes:

- CELL ID and objective;
- exact input/base artifact;
- allowed and forbidden paths/actions;
- expected outputs;
- acceptance items;
- Worker validation commands/methods;
- Checker independent validation commands/methods;
- resource, capability-profile, workspace, and model binding IDs;
- timeout, blocker, and rollback instructions;
- required receipt fields.

Changing any field after dispatch requires cancellation/rework or a contract amendment. Informal chat cannot alter a CELL.

## Split Proposal

Planner emits a `split-proposal` with:

```yaml
parent_loop: <id>
reason: <why current granularity fails>
children:
  - id: <child-id>
    objective: <bounded result>
    depends_on: []
    write_scope: []
    acceptance_map: []
    evidence_required: []
parallel_safe: <true|false>
composition_check: <parent-level integration acceptance>
parent_close_condition: <all required children done and goal_verified plus composition>
```

Required transition:

1. Parent enters `split-proposed`; no new child execution starts.
2. Supervisor checks objective continuity and authority boundaries.
3. Checker performs preflight QC for completeness, independence claims, acceptance coverage, and conflicts.
4. Supervisor records rejection or freezes a new contract revision.
5. Planner dispatches approved children in dependency order or safe parallel groups.

## Amendment Rules

An amendment writes a new immutable revision file and preserves every prior revision. Append the reason, changed fields, risk impact, new revision/hash, Checker preflight result, Supervisor approval, and restart point. Rework writes a new attempt directory; never overwrite an earlier assignment, receipt, check, or route record. Any artifact produced under an obsolete contract stays traceable but cannot satisfy the new revision without explicit revalidation.
