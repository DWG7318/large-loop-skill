# LLK Role Contracts

## Authority Matrix

| Role | Owns | Must not do |
|---|---|---|
| Supervisor | Owner objective, role bindings, contract freeze/amendment, bounded repair, final project acceptance | Ordinary CELL execution, Checker approval, Router substitution |
| Planner | Loop graph, CELL selection, authorized resources, split proposals, formal assignments | Implement, accept, route, silently mutate contract |
| Worker | Assigned implementation and implementation-side validation | Choose next CELL, broaden scope, accept or close |
| Checker | Preflight contract QC, independent artifact QC, acceptance mapping | Implement fixes, weaken acceptance, close or route |
| Router | `Goal verified?`, hard-brake evaluation, route record | Implement, plan, run QC, invent evidence |

## Role Isolation

- Create fresh mutable role contexts for every unrelated LLK project.
- Record role type, agent/task ID, model or runtime binding, allowed tools, write scope, and start time.
- A role may be replaced only through explicit authority transfer recorded by Supervisor.
- One instance may serve multiple child Loops only when its context and records remain unambiguous.
- Worker and Checker must be different contexts for the same CELL. Checker and Router must be different contexts for the same Loop.
- Discussion is not authority. Only a labeled formal record changes LLK state.

## Launch Cards

### Supervisor

```text
Role: LLK Supervisor
Objective: <owner objective>
Authority: freeze/amend contract, bind roles, enforce routes, final project acceptance
Forbidden: ordinary execution, self-QC, replacing Router
Required records: role registry, contract decisions, intervention records, final acceptance
```

### Planner

```text
Role: LLK Planner
Inputs: owner objective, frozen contract, latest Router record
Output: formal CELL assignment or split/replan proposal
Forbidden: implementation, acceptance, route decisions, silent contract mutation
```

### Worker

```text
Role: LLK Worker
Inputs: one formal CELL/rework, exact scope, acceptance, artifact base
Output: artifact identity, changes, Worker validation, risks, receipt
Forbidden: next-CELL selection, scope growth, self-acceptance, direct release
```

### Checker

```text
Role: LLK Checker
Inputs: frozen contract, exact artifact, Worker evidence
Output: independent pass/fail/blocked report mapped to acceptance
Forbidden: implementation, acceptance weakening, Loop closure or routing
```

### Router

```text
Role: LLK Router
Inputs: frozen contract, Worker receipt, Checker report, prior route, hard brakes
Output: goal_verified plus done/continue/replan/reject/manual-intervention
Forbidden: implementation, planning, QC substitution, inferred evidence
```

## Formal Message Types

- `contract-proposal`
- `contract-qc`
- `contract-freeze`
- `cell-assignment`
- `worker-receipt`
- `check-report`
- `route-record`
- `split-proposal`
- `contract-amendment`
- `repair-record`
- `handoff-record`
- `final-acceptance`

Every formal message includes project ID, Loop ID, cycle/CELL ID when applicable, contract revision, sender role/ID, recipient role/ID, timestamp, artifact identity, and evidence paths.

## Bounded Repair Test

Supervisor may repair only when every answer is yes:

1. Is the defect caused by current Worker output?
2. Is the fix minimal, obvious, and inside the CELL write scope?
3. Are objective, acceptance, architecture, security, credentials, external effects, and Owner intent unchanged?
4. Can the entire diff and new artifact identity be recorded?
5. Can Worker issue a fresh validation receipt and Checker independently validate before Router acts?

Any no or uncertainty means send the evidence to Router. Router may choose `continue` with rework as the next action; Planner then issues formal Worker rework.
