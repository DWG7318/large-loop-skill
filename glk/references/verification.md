# Verification

GLK 3.1.0 validates independent append-only artifacts and their cross-artifact
lineage.

## D0-D3

- D0 proves that one CELL candidate behaves as its Worker intended.
- D1 proves that the immutable CELL candidate satisfies its frozen contract.
- D2 proves that accepted CELL candidates compose one frozen GO claim.
- D3 proves that verified GO outcomes, graph seams, and the final candidate compose
  the frozen Run Feature.

Every receipt binds schema and graph versions, candidate ID and hash, role binding,
execution context, evidence, verdict, and timestamp.

D2 must consume D1 PASS for the same candidate and use a context independent from
the Checker. D3 must consume D2 receipts for the accepted graph version and must not
pass by receipt counting alone.

Repetition is valid only for changed candidates/environments, stale or contradictory
evidence, expanded regression scope, graph-composition effects, or specific new
risks. Record the source layer, reason, scope delta, and result.

A causal amendment keeps old receipts as immutable history but may remove their
current-validity for the new graph version. Repeat D1/D2 only for GOs classified
`REVERIFY`, `REWORK`, or `QUARANTINE`; an `UNAFFECTED` GO does not repeat evidence
merely because it is reachable from the source.

A `CONFIRMED` cross-GO causal trace binds the source GO's current immutable candidate
and current D2 receipt. Each selected consumption edge carries incident evidence and
`CONFIRMED` status; reachability without that evidence cannot invalidate a receipt.

D2 requires the exact current admitted `GO_CANDIDATE_CLOSURE`, whose selected CELL
tuples cover every required manifest entry. D3 requires exact current admitted D2
for every required GO and graph-seam evidence. Eligibility functions and validation
reports are derived non-authoritative and never issue D2 or D3.

The complete Run package passes ten validation layers before formal preflight. The
repository validator remains separately scoped to `REPOSITORY_DISTRIBUTION`.
