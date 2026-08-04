# Layered realtime progress

Progress states are distinct: `DELIVERED`, `D1_ACCEPTED`, `GO_CANDIDATE_READY`, `D2_VERIFIED`, `RUN_VERIFIED`, and `OWNER_ACCEPTED`.

- Worker reports the current scoped CELL delivery position. Delivery, green tests, checking start, or rework never increments acceptance.
- Checker ACKs first, then reports its current D1 accepted CELL count. Only the first current-valid admitted D1 PASS for a Required CELL increments it; FAIL, REWORK, BLOCKED, duplicate, or stale D1 does not.
- Checker sends the Supervisor no per-CELL noise. It emits one deduplicated GO-boundary milestone only after every current Required CELL is D1 accepted and a current GO candidate closure exists. A candidate is not a D2 verdict.
- Supervisor reports only material GO, outer Level reference, Graph, Run, hold, or Required-set changes. It shows required CELL/D1, required GO/D2, ACTIVE_GO, WAITING_GO reasons, holds, graph version, manifest version, plan version, capacity-profile version, and cumulative-load version. It emits no single percentage.
- Verifiers emit verdicts only. Patrol emits operational alerts only.

Numerators come from current-valid receipts/verdicts. Denominators come from current versioned Required sets. A manifest, graph, or CELL-plan amendment must recompute the current denominator. Historical projections remain immutable; a split itself adds no accepted progress.
