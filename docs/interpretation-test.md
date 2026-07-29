# GLK 2.3.1 Interpretation Test

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
