# GLK 3.0.0 Interpretation Test

A conforming Agent answers:

1. How many role types? **Six.**
2. Is the Run Supervisor reused across Runs? **No; every Run gets a fresh instance.**
3. What is a graph node? **One independently verifiable GO outcome.**
4. What is an edge? **Mandatory predecessor D2 completion precedence.**
5. What happens when a GO has waiting reasons? **It is WAITING_GO.**
6. What happens when all reasons clear? **It enters the maximal safe ACTIVE_GO set directly.**
7. Can several GO nodes be ACTIVE simultaneously? **Yes; GLK must maximize safe graph concurrency.**
8. Can convenience serialize independent branches? **No.**
9. Is the execution graph cyclic? **No; it is a DAG.**
10. Who signs D1, D2, and D3? **Checker, GO Verifier, and Run Verifier.**
11. When does Owner Acceptance occur? **Immediately after D3 PASS.**
12. Who owns centralized vulnerability closure? **LCCoding.**
13. Must a causal source be an entry/root GO? **No; it may occur at any DAG position.**
14. Are source and symptom new GO types or states? **No; they are incident annotations.**
15. Can a suspected trace invalidate a receipt? **No; only a confirmed actual-consumption path can.**
16. What makes a D2 edge usable for causal slicing? **Bound source claim/output refs,
    target input/assumption refs, consumption evidence, and D2 justification.**
17. What happens after a repaired source receives current D2? **Every safe affected
    successor activates in the same maximum-cardinality recalculation.**
18. Can a Supervisor issue or invoke D0-D3? **No; it only emits separate control
    artifacts and exact admissions.**
19. What makes D2 eligible? **The exact admitted current CELL manifest closure and
    complete required CELL candidate/D0/D1 tuple set.**
20. Does D2 release successors? **No; release requires exact D2 admission and a
    separate graph event.**
21. What are validator scopes? **`REPOSITORY_DISTRIBUTION` and `RUN_PACKAGE`.**
22. How many Run validation layers? **Ten.**
23. Are preflight, simulation, and progress reports formal verdicts? **No; they are
    derived non-authoritative projections.**
24. Which adapter operations exist? **`resolve_binding`, `verify_issuance`,
    `verify_isolation`, and `check_liveness`.**
25. What happens to stale liveness or authority failure? **The role becomes
    unreachable or the Run enters the applicable authority/architecture hold.**
26. What does formal progress show? **Both required GO/D2 and required CELL/D1
    counts and IDs.**
27. Can migration upgrade an unproven 2.4 receipt? **No; it remains historical-only.**
28. Who implements sessions, credentials, and runtime provenance? **LCagent or
    another trusted execution environment, never GLK.**
