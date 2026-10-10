# Migration to GLK 4.1.0

GLK 4.1.0 preserves the four-Skill Node-DAG collection and corrects the unpublished 4.0.0 Supervisor topology.

## New Runs

One GLK Run creates exactly one shared Supervisor Agent. Every ordinary, Fusion, and D2 Repair child SLK registers its Supervisor role against that same Agent without creating another conversation. Each child remains an independent SLK Run with an isolated Checker, Worker, SLK token, central record, worktree, CELL loop, D0/D1/D2 evidence, and archive.

Every Supervisor action binds the complete scope:

```text
GLK_RUN_ID + NODE_ID + SLK_RUN_ID + CELL_ID
```

Missing or colliding scope, a second Supervisor Agent identity, or a cross-child Checker/Worker reference fails closed.

## Existing Runs and releases

Published tags and Releases remain immutable. An existing Run continues under the exact method version with which it started. Do not silently rebind an active child Run.

GLK 4.0.0 was an unpublished intermediate candidate and has no migration authority. New Runs use 4.1.0. Historical 3.x evidence stays historical and is never promoted merely because the current topology is simpler.

## Preserved boundaries

- Node DAG, multi-start execution, `ALL` joins, dependency-driven release, and one normal Fusion Node remain unchanged.
- Child SLK construction, D0, D1, child D2, recovery, communication evidence, central record, token, worktree, and archive remain owned by SLK.
- Fusion child SLKs complete their own D2 before the same shared Supervisor performs the distinct GLK final D2.
- Conditional D2 Repair remains a child SLK Run and returns to the same GLK final-D2 boundary.
- No coordinator, broker, Router, hidden Agent, or runtime layer is added.

## Concept mapping

| Unreleased 4.0.0 wording | GLK 4.1.0 |
| --- | --- |
| One GLK Supervisor plus separate child Supervisor Agents | One shared Supervisor Agent with child-run-scoped role bindings |
| Indirect GLK-to-child-Supervisor handoff | Direct shared-Supervisor action under the exact four-part scope |
| Child isolation implied by separate Supervisors | Child isolation proved by distinct Checker, Worker, token, record, workspace, evidence, and archive |
| Supervisor count grows with child count | Supervisor Agent count is exactly one per GLK Run |
