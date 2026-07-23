# CELL Worker Set and Handoff

## One CELL, multiple eligible Workers

A CELL may bind more than one Worker when it needs failover, specialization, model
switching, or a bounded sequential handoff.

It still has one acceptance contract and one active implementation owner.

```text
CELL_WORKER_SET
  Worker-A: primary
  Worker-B: specialist
  Worker-C: recovery

ACTIVE_WORKER_LEASE = exactly one
```

Multiple eligible Workers do not create parallel implementation inside one CELL.

## When to split instead

Split into separate CELLs when Worker outputs can be:

- independently accepted;
- safely composed;
- assigned disjoint outcomes;
- run concurrently without one mutable artifact owner.

Do not use a large CELL Worker Set to avoid proper decomposition.

## Worker Set contract

```text
CELL_ID
worker_set_version
worker_id
role/specialization
model_binding_id
capability_profile_id
workspace_template
eligibility predicate
allowed write scope
handoff type
priority
maximum attempts
```

## Active lease

Planner grants and revokes `ACTIVE_WORKER_LEASE` under the frozen CELL Contract.
The first lease follows initial CELL planning. Every later lease requires a prior
Router route (`WORKER_REWORK`, `WORKER_HANDOFF`, or `WORKER_SWITCH`).

The lease records:

```text
lease_id
CELL_ID
ATTEMPT_ID
worker_id
base_artifact_id
workspace_id
allowed scope
start time
expiry/hard brake
```

Only the lease holder may write product artifacts.

## Planner and Router

Planner selects an eligible Worker based on the frozen CELL Contract and Worker Set
and grants the initial lease.

Router may route `WORKER_REWORK`, planned `WORKER_HANDOFF`, unplanned
`WORKER_SWITCH`, `CELL_REPLAN`, block, or rejection. Router never selects or
activates the next Worker.

After a non-initial route, Planner grants a new lease only after the old lease is
revoked and the handoff state is immutable.

## Handoff

A handoff package contains:

```text
CELL Contract/version
GO and graph version
old worker/attempt
base artifact
latest immutable checkpoint
validated completed work
validated unresolved work
failure/blocker evidence
remaining objective
forbidden scope
new attempt ID
```

It excludes hidden reasoning and mutable workspace state.

## Switch sequence

1. current Worker emits candidate/checkpoint/blocker/failure receipt;
2. Checker validates the receipt and artifact usability;
3. Router emits `WORKER_HANDOFF` or `WORKER_SWITCH`;
4. Planner revokes the old lease;
5. old workspace is sealed read-only;
6. Planner selects a replacement from the eligible set;
7. Planner grants one new lease under the Router route;
8. new Worker starts from a fresh workspace and immutable handoff.

## Planned sequential specialization

A planned sequential handoff is allowed when one indivisible CELL needs distinct
specialized operations but only one mutable owner at a time.

Each handoff still goes through Checker and Router. A downstream specialist cannot
start merely because the prior Worker says it is done.

## Collision

Two active leases or concurrent writes are `ACTIVE_WORKER_COLLISION`.

- stop all affected Worker activity;
- quarantine candidates;
- preserve evidence;
- restore the last valid baseline;
- inspect authorization and workspace locks;
- Router decides a single legal recovery route.

## Worker replacement is not Owner work

Routine failure, model mismatch, timeout, or capability mismatch is resolved internally
through Worker switch. It does not require Owner confirmation.
