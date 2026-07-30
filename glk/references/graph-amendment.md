# Graph Amendment and Formal Resolution

A frozen graph changes only through `GRAPH_AMENDMENT`. Record:

```text
before and after graph versions
reason and evidence
affected claims
active-work impact
candidate and evidence invalidation
confirmed causal-trace reference when applicable
changed-ref seeds and minimum impact slice
invalidated receipt references and current-validity projection
WAITING_GO / ACTIVE_GO reactivation projection
rollback
authority binding
timestamp
```

Product-definition changes exit to LCCoding/Calabash.

`SUPERSEDED` and `CANCELLED` require `FORMAL_RESOLUTION`. The resolution states
whether successors are released and whether an approved amendment removed/replaced
the GO from the Required set. Neither flag may be inferred from a terminal label.

Active candidates affected by an amendment are quarantined until explicitly rebound
to the new graph version.

A causal amendment requires `CONFIRMED` trace status and actual-consumption edge
bindings. `SUSPECTED` traces remain evidence only. The first forward impact hop must
consume an explicit changed ref; unproven descendants stay `UNAFFECTED`. Historical
receipts remain append-only, and reactivation uses the existing maximal-safe
scheduler without an intermediate queue or full-graph replay.
