# State Machine

Version 3.0.0 separates technical verdicts from control events.

Graph state and internal execution phase are separate.

## Graph state

```text
DRAFT -> FROZEN -> WAITING_GO | ACTIVE_GO
WAITING_GO -> ACTIVE_GO
ACTIVE_GO -> GO_VERIFIED
```

Exceptional terminal or hold states are:

```text
GO_BLOCKED
GO_REJECTED
SUPERSEDED
CANCELLED
```

`SUPERSEDED` and `CANCELLED` require a formal resolution and never imply success.

## ACTIVE_GO phase

```text
IMPLEMENTING -> CHECKING -> VERIFYING
CHECKING -> REWORK -> CHECKING
VERIFYING -> REWORK -> CHECKING
```

A GO remains in `GRAPH_ACTIVE_SET` throughout these phases. This prevents checking
or verification latency from silently releasing its conflict locks or making the
graph appear less concurrent than it is.

Every state event records Run ID, graph version, GO ID, candidate identity when
applicable, actor binding, evidence, and timestamp.

## Causal amendment projection

A confirmed causal amendment does not add a graph state. It preserves historical
`GO_VERIFIED` events and receipts append-only, removes their current-validity only
where the impact slice proves invalidation, and projects affected GOs into existing
`WAITING_GO` or `ACTIVE_GO` under the new graph version. `SUSPECTED` traces cause no
state projection.

`RUN_AUTHORITY_HOLD` is immediate after a proven technical authority violation.
`RUN_ARCHITECTURE_HOLD` follows two consecutive HIGH findings on the same
architecture path. Missing or expired liveness evidence projects the affected role
as unreachable; no failed read produces healthy state.

The derived progress projection contains required GO count, D2-verified required GO
count, required CELL count, D1-accepted required CELL count, exact IDs, active GOs,
typed waiting reasons, unreachable bindings, holds, graph version, and CELL
manifest versions.
