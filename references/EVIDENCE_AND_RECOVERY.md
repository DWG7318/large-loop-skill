# LLK Evidence and Recovery

## Contents

- Evidence Standard
- Double-Validation Gate
- Router Record
- Heartbeat Inspection
- Recovery Matrix
- Recovery Packet
- Closure Evidence

## Evidence Standard

Evidence is append-only, attributable, reproducible where possible, and bound to:

- project, Loop, cycle, and CELL IDs;
- contract revision/hash;
- role and agent/task ID;
- context, workspace, capability-profile, and model-binding IDs;
- artifact identity;
- command or inspection method;
- timestamp, environment, result, and retained output path.

Never treat prose confidence, a completion receipt, or a screenshot alone as proof when a stronger machine-readable check exists.

## Double-Validation Gate

### Pass 1: Worker

Worker records changed paths, exact artifact identity, implementation-side commands or inspections, results, known risks, and unresolved items. Worker may report `complete` but never `accepted`.

### Pass 2: Checker

Checker confirms artifact identity, independently executes or reproduces the contract-defined checks, inspects relevant diffs/outputs, maps every acceptance item to evidence, and reports:

```yaml
status: pass | fail | blocked
artifact: <identity>
acceptance:
  - item: <criterion>
    result: pass | fail | blocked
    evidence: <path or record id>
failed_items: []
next_required_action: <specific action>
```

If the artifact changes, both passes expire. If Checker cannot independently validate, the result is `blocked`, never an inherited pass.

## Router Record

Router records:

```yaml
goal_verified: true | false
route: done | continue | replan | reject | manual-intervention
contract_revision: <revision/hash>
artifact: <identity>
evidence_used: []
hard_brakes: []
reason: <decision rationale>
next_role: <role or none>
next_action: <formal action>
```

`done` requires `goal_verified: true`. Other routes require `goal_verified: false` unless the contract explicitly defines a verified intermediate Loop that continues at the parent level. `manual-intervention` is a hold, never closure, merge permission, release permission, or a substitute for Router.

## Heartbeat Inspection

Use a same-task recurring heartbeat when available; otherwise record a manual inspection cadence. At each tick inspect once:

1. current formal state and active role;
2. last append-only record and age;
3. expected receiver and acknowledgement;
4. workspace/process activity without exposing secrets;
5. blocker or hard-brake signals;
6. one required wake-up or recovery action.

The heartbeat observes and wakes Supervisor. It cannot approve, route, dispatch, edit, or create a detached replacement project. Stop it only after final closure is recorded.

## Recovery Matrix

| Condition | State/action |
|---|---|
| Worker silent, workspace unchanged | `stalled-unconfirmed`; request checkpoint; replacement/authority transfer waits for Router routing or a frozen amendment. |
| Workspace changing without receipt | Preserve snapshot; prevent conflicting writes; request formal checkpoint. |
| Sender complete, receiver silent | `handoff-risk`; resend exact record and require acknowledgement. |
| Checker unavailable before Router can act | Supervisor records `governance-hold`; never let Worker/Supervisor inherit QC. |
| Router unavailable | Supervisor records `governance-hold`; never let Checker/Supervisor/Owner close, merge, or release through LLK. |
| Artifact changed after pass | Start a new attempt; Worker issues a fresh receipt, then Checker independently validates. |
| Contract defect discovered | Router selects `replan`; preserve output and enter amendment QC. |
| Role context lost | Supervisor records `governance-hold`, preserves state, and prepares the recovery packet; Router or a frozen amendment decides replacement, transfer, and restart point. |

## Recovery Packet

After Router routing or a frozen amendment authorizes replacement, the new role receives only verified continuity material:

- frozen contract and current revision/hash;
- role registry and explicit new binding;
- isolation-policy and model-binding revisions/hashes;
- current state and last Router record;
- active CELL assignment;
- artifact identity and retained workspace snapshot;
- evidence index and unresolved blockers;
- expected next formal output.

Do not pass invented summaries as authoritative history. Conflicts between records trigger manual inspection.

## Closure Evidence

Before final acceptance, Supervisor verifies:

- every required Loop has `route: done` and `goal_verified: true`;
- every accepted final artifact has two current validation passes;
- dependency and parent composition checks pass;
- rejected, superseded, and blocked artifacts remain labeled;
- handoff lists exact files, hashes, evidence, destination, and rollback notes;
- no raw secret or unintended local path is present;
- monitoring termination and final queue record are appended.

Post-Loop learning is a new record for future contracts. It cannot rewrite the closed evidence chain.
