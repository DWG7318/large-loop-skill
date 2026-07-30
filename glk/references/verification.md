# Verification

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
