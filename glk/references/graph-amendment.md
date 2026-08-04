# Graph Amendment and Formal Resolution

GLK 3.1.0 amendments remain versioned and append-only.

A frozen graph changes only through `GRAPH_AMENDMENT`. Record:

```text
before and after graph versions
reason and evidence
affected claims
active-work impact
candidate and evidence invalidation
confirmed causal-trace reference when applicable
typed candidate/evidence/claim-or-output seeds and minimum impact slice
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

A causal amendment requires a current-candidate-bound `CONFIRMED` source, confirmed
incident-selected actual-consumption paths to every symptom, and complete excluded-edge
evidence. `SUSPECTED` traces remain evidence only. Claim/output seeds begin only at a
consumer of that ref; current source candidate or confirmation-evidence seeds first
invalidate source validity. Unrelated seeds fail closed and unproven descendants stay
`UNAFFECTED`. Historical
receipts remain append-only, and reactivation uses the existing maximal-safe
scheduler without an intermediate queue or full-graph replay.

Record `source_go` and `source_disposition` explicitly. A `CANDIDATE` or
`CLAIM_OR_OUTPUT` seed forbids source `REVERIFY`; it requires `REWORK` or
`QUARANTINE`. A candidate seed invalidates the old candidate and its D0/D1/D2
current-validity. An evidence-only seed may use `REVERIFY`. Multiple seeds apply the
strictest source requirement, while downstream GOs retain independent impact
evidence and dispositions.

CELL membership or contract changes require a frozen `CELL_MANIFEST_AMENDMENT` and
a new manifest closure. Architecture-hold recovery is limited to a frozen amendment
plus complete affected revalidation, or sealing the Run and starting a new one. A
report cannot clear a formal hold.
