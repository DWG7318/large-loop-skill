# Device and cumulative engineering load capacity

Before plan freeze the Run Supervisor binds a versioned `DEVICE_CAPACITY_PROFILE` and `CUMULATIVE_ENGINEERING_LOAD` to the Run contract, graph, method lock, and evidence. Required facts use explicit units: CPU and safe concurrency, available RAM, GPU/VRAM applicability, disk/IO, network/external limits, processes/ports, measured or conservative command/build/test durations, and context/evidence budgets. Unknown, stale, free-text-only, or unproved facts fail closed.

Every CELL has a `CELL_WORK_ESTIMATE` for total engineering cost: implementation scope, inputs/dependencies, generated artifacts, test matrix, independent Checker reproduction, affected regression, evidence/hash/cleanup, context recovery, external tools/services, rollback/retry, and cumulative baseline coupling. A small diff with a full regression remains heavy.

`CELL_CAPACITY_GATE` has exactly `PASS`, `SPLIT_REQUIRED`, or `CAPACITY_BLOCKED`. Only PASS permits Worker dispatch. A pre-dispatch split creates a versioned amendment whose successors preserve one GO outcome and acceptance, are independently deliverable/D1-checkable, and each pass the gate. Splitting creates neither a GO nor a subagent.

The Supervisor updates cumulative load after important GO, outer Level, Graph boundaries, and material estimate deviations. Actual time, peak memory, regression growth, file/dependency/evidence growth, and context recovery must re-evaluate every undispatched CELL. Later work becomes smaller or receives a larger proven budget.

A Worker that exceeds the frozen scope records `CELL_SCOPE_EXCEEDED` with immutable checkpoint/evidence and returns to the original Checker/planning authority. It cannot self-split or create another Worker. Any late split records `POST_DISPATCH_CELL_SPLIT`; three or more successors also record `CELL_OVERSIZE_SEVERE` and force remaining-plan re-evaluation. Counts 6/7/8 are always severe.

Logical DAG independence and physical safety remain separate. Maximal-safe activation includes CPU, RAM, GPU/VRAM, disk/IO, process, port, external-service, and heavy-validation reservations. Capacity shortage uses a typed resource constraint or smaller CELL, never a fake dependency edge.

When a split changes the Required set, plan/manifest versions advance and current progress must recompute its denominator; old `25/30` remains historical rather than current truth.
