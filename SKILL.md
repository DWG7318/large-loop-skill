---
name: large-loop-skill
description: Use when the user says LLK or large-loop-skill, or when a complex, long-running Codex project needs auditable authority separation, frozen acceptance contracts, independent validation, explicit routing, controlled Loop decomposition, isolation from shared model/workspace contamination, or reliable recovery from stalls and handoff gaps. Do not use for a small single-Worker loop.
---

# Large Loop Skill

## Overview

LLK is a project-neutral Loop Engineering control system. One Supervisor governs an independent brain chain:

`Planner -> Worker -> Checker -> Router`

These are five role types, not necessarily five processes. Multiple Workers or child Loops are allowed, but every formal decision has one named owner and must preserve the same authority boundaries.

## Hard Rules

1. Freeze objective, scope, acceptance, resources, isolation, model bindings, write boundaries, hard brakes, and route rules before execution.
2. Isolate role identity/context, workspace, capabilities, artifacts/evidence, model configuration, secrets, and lifecycle state. Role labels alone are not isolation.
3. Give every role instance its own frozen `model_binding_id`; never inherit one mutable global provider/model/API/tool configuration.
4. Create fresh role contexts for every unrelated project. Worker/Checker and Checker/Router must have different contexts and binding IDs on the same Loop.
5. Every CELL requires a Worker validation receipt and independent Checker validation for the same artifact identity.
6. Only Router answers `Goal verified?` and chooses `done`, `continue`, `replan`, `reject`, or `manual-intervention`.
7. Checker verifies but cannot close. Worker completion is not acceptance. Supervisor and Owner cannot replace Router.
8. Planner chooses CELLs and may propose splitting a coarse Loop, but cannot implement, accept, route, or silently mutate a frozen contract.
9. Worker executes only a formal CELL or rework assignment and never chooses the next CELL or broadens scope.
10. Evidence and authority records are append-only. Corrections supersede; they never erase.
11. Silence, timeouts, partial files, stale green tests, or an unavailable role never imply success.
12. `manual-intervention` is a non-terminal hold, never closure, merge permission, or release permission.
13. Runtime learning may inform a future contract but cannot mutate the active one.
14. LLK output is a candidate handoff and never silently overwrites authoritative project assets.

Violating the letter violates the method. Deadlines, schedules, release pressure, and Owner urgency cannot waive validation or routing. If a required role or evidence surface is unavailable, hold; do not simulate a pass.

LLK is independent from SLK, MSLK, and older Loop doctrines. Those methods may supply lessons but cannot weaken LLK. A project contract may tighten these rules, never relax them.

## Start an LLK

1. Use LLK for complex, long-running, multi-stage, high-risk, or replanning-heavy work. Use SLK for bounded one-Worker work.
2. Keep the current task as Supervisor. Create fresh Planner, Worker, Checker, and Router contexts when agent tools exist; record role, context, workspace, capability, and model binding IDs.
3. Read [references/ROLE_CONTRACTS.md](references/ROLE_CONTRACTS.md) and [references/ISOLATION_AND_MODEL_BINDINGS.md](references/ISOLATION_AND_MODEL_BINDINGS.md) before role launch. Read [references/CONTRACT_AND_STATE.md](references/CONTRACT_AND_STATE.md) before creating the `.large-loop/` control tree.
4. Supervisor drafts and freezes the isolation policy and per-role model binding matrix. Planner writes the project plan, initial Loop contract, CELL strategy, resource bindings, and acceptance mapping inside those boundaries.
5. Checker performs preflight contract QC. Supervisor resolves defects and freezes the accepted revision/hash.
6. Start a same-task heartbeat when available, or record a manual inspection interval. It observes and wakes Supervisor only.
7. Dispatch the first formal CELL only after contract freeze and role binding.

If independent contexts cannot be created, do not claim an active LLK. Supervisor records the non-routing observation state `governance-hold` and the missing capability.

## Isolate Roles and Models

Every role instance receives separate `role_id`, `context_id`, `workspace_id`, `capability_profile_id`, and `model_binding_id`. Worker uses an isolated worktree/sandbox; Checker validates an immutable artifact in a separate validation workspace; Planner and Router cannot write product artifacts. Roles may share a machine, Git repository/object database, or provider service, but never one mutable checkout/working directory, client session, context, or global configuration object.

Model configuration separation is mandatory; model diversity is a second defense. Worker and Checker should use different model/provider families when available. If the same underlying model is approved, they still require different binding IDs, contexts, credentials/tool scopes, and independent evidence, with the reduced diversity recorded as risk. Planner may select only preapproved Worker bindings/fallbacks and cannot silently change any role's model.

Use [references/ISOLATION_AND_MODEL_BINDINGS.md](references/ISOLATION_AND_MODEL_BINDINGS.md) for the isolation matrix, binding schema, switch rules, and failure behavior.

## Run the Chain

| Role | Formal output | Boundary |
|---|---|---|
| Planner | Next authorized CELL, rework assignment, or split/replan proposal | No implementation, QC, or routing |
| Worker | Artifact identity, changes, validation, risks, receipt | No self-acceptance or next-CELL selection |
| Checker | Independent `pass`, `fail`, or `blocked` mapped to acceptance | No implementation or closure |
| Router | `goal_verified`, evidence used, hard brakes, route, next role/action | No planning, implementation, or QC substitution |
| Supervisor | Contract decision, bounded intervention, final project acceptance | No ordinary execution or route substitution |

One cycle is exactly one ordered `Planner -> Worker -> Checker -> Router` pass. Only the active role acts. Other roles may observe but cannot inject competing decisions. Every formal message records the sender's current context, workspace, capability-profile, and model-binding IDs.

Route semantics:

- `done`: goal verified; Loop closes formally.
- `continue`: stay under the frozen contract. Router specifies whether Planner assigns the next CELL or formal rework of the current CELL.
- `replan`: pause execution for contract/Loop-graph amendment and preflight QC.
- `reject`: a hard brake or terminal failure ends this contract path.
- `manual-intervention`: wait for missing authority, evidence, credential, external action, or decision without closure or release.

If Owner deliberately acts outside LLK, label the project `unverified/outside-LLK`; never record that action as LLK completion.

## Split a Coarse Loop

Planner must challenge granularity before dispatch and when a Loop becomes broad, coupled, ambiguous, or hard to validate. A split proposal names the parent, reason, child objectives, dependencies, isolated write scopes, acceptance/evidence mappings, parent composition check, closure condition, and concurrency proof.

The parent enters `split-proposed`. Supervisor reviews objective continuity; Checker performs preflight QC; Supervisor rejects or freezes a revised contract. Only then may Planner launch children. Parallel children require launch and acceptance independence; otherwise run in dependency order. Parent closure requires every required child to have a terminal `done` record with `goal_verified: true`, plus the parent composition check.

Use the exact schema in [references/CONTRACT_AND_STATE.md](references/CONTRACT_AND_STATE.md).

## Enforce Validation and Repair

Worker validation is the implementation-side pass. Checker must independently rerun, reproduce, or inspect the contract-defined acceptance against the exact same immutable artifact. Quoting Worker output is not independent. If Checker cannot validate, report `blocked`. Any artifact change invalidates both passes.

Supervisor may directly repair a Worker defect only when every bounded-repair test in [references/ROLE_CONTRACTS.md](references/ROLE_CONTRACTS.md) passes. Record the reason and exact diff, create a new artifact identity, and send the repair record to Worker. Worker must validate the repaired artifact and issue a fresh receipt; Checker then independently validates it; Router alone routes it. If Worker is unavailable before producing that receipt, Supervisor records `governance-hold` rather than substituting its own evidence; a reachable Router may later route the blocker to `manual-intervention`.

If direct repair is unsafe or uncertain, send the existing evidence to Router. Router may choose `continue` with formal rework as the next action; Planner then issues that rework to Worker.

## Recover Without Guessing

Before accepting evidence or recovering a stall, read [references/EVIDENCE_AND_RECOVERY.md](references/EVIDENCE_AND_RECOVERY.md). At every heartbeat/manual inspection, check current role, last formal record, expected receiver, acknowledgement age, workspace activity, and hard brakes.

- Activity without a handoff: mark `stalled-unconfirmed`, preserve the workspace, prevent conflicting writes, and request a checkpoint.
- Sender complete but receiver silent: mark `handoff-risk`, record the last valid output and expected receiver, then require acknowledgement.
- Required role unavailable before it can issue a formal route: Supervisor records `governance-hold`; this observation neither routes nor closes.
- Lost role context: Supervisor records `governance-hold`, preserves state, and prepares the recovery packet; Router or an amended contract decides replacement and resume.

Never auto-advance. Resume only after Router routing or a frozen amendment identifies the replacement, transfer, and restart point. See [references/EVIDENCE_AND_RECOVERY.md](references/EVIDENCE_AND_RECOVERY.md).

## Close the Project

Router closes each successful Loop with `done`. Supervisor closes the LLK project only after every required Loop has `route: done` and `goal_verified: true`, two current validations exist per accepted final artifact, dependency/composition checks pass, hard brakes are clear, and the exact candidate handoff, final queue record, and append-only evidence index exist. Stop monitoring only after closure is recorded.

## Authority Reference

| Question | Sole authority |
|---|---|
| What CELL or rework comes next? | Planner, under Router's recorded route |
| How is the assigned CELL implemented? | Worker |
| Does the artifact satisfy CELL acceptance? | Checker |
| Is the goal verified and where does control go? | Router |
| Is the contract frozen/amended and project finally accepted? | Supervisor |

## Red Flags

- "Worker tested it, so it is accepted."
- "Checker approved, so the Loop is closed."
- "Router is unavailable; Owner/Supervisor can substitute."
- "Planner already dispatched the silent split."
- "Separate prompts make one shared workspace/model configuration isolated."
- "One checkout is safe because roles write at different times."
- "Planner can switch models now and document it later."
- "The repair is tiny, so old evidence still counts."
- "No update means it probably finished."
- "We can change acceptance now and document it later."

Every red flag means stop, preserve evidence, restore the correct authority boundary, and wait for Router routing or a frozen amendment before resuming.

## References

- [references/ROLE_CONTRACTS.md](references/ROLE_CONTRACTS.md): role launch contracts, authority matrix, formal messages, and bounded repair.
- [references/ISOLATION_AND_MODEL_BINDINGS.md](references/ISOLATION_AND_MODEL_BINDINGS.md): mandatory isolation layers, per-role model binding schema, diversity, and switching.
- [references/CONTRACT_AND_STATE.md](references/CONTRACT_AND_STATE.md): versioned control tree, frozen contracts, states, CELL attempts, and split schema.
- [references/EVIDENCE_AND_RECOVERY.md](references/EVIDENCE_AND_RECOVERY.md): double-validation evidence, Router records, heartbeat, recovery, and closure.
