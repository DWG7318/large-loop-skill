# State Machine

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
