# Graph Amendment and Formal Resolution

A frozen graph changes only through `GRAPH_AMENDMENT`. Record:

```text
before and after graph versions
reason and evidence
affected claims
active-work impact
candidate and evidence invalidation
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
