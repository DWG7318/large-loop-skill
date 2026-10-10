# GLK 4.1.0 Interpretation Test

A conforming Agent answers:

1. How many Supervisor Agents exist in one GLK Run? **Exactly one shared Supervisor Agent.**
2. Does each child SLK get a new Supervisor conversation? **No; its independent Supervisor role binding resolves to the shared Agent.**
3. What remains independent per child SLK? **Run ID, Checker, Worker, SLK token, central record, worktree, CELL loop, D0/D1/D2 evidence, recovery, and archive.**
4. What is the mandatory Supervisor scope? **`GLK_RUN_ID + NODE_ID + SLK_RUN_ID + CELL_ID`.**
5. What happens on missing or colliding scope? **The action fails closed without guessing or replacement.**
6. May a Checker or Worker dispatch, check, wait for, or deliver across child SLKs? **No.**
7. Does a child SLK D2 equal the GLK final D2? **No; child D2 closes the child Run, while final D2 establishes the whole Graph after Fusion.**
8. Does Fusion get a separate Supervisor Agent? **No; Fusion child SLKs use the same shared Agent and independent child bindings.**
9. Does D2 Repair get a separate Supervisor Agent? **No; it uses the same shared Agent and returns to the same GLK final-D2 boundary.**
10. Is a visible coordinator, broker, Router, hidden Agent, or runtime layer added? **No.**
11. What is the Graph topology? **A multi-start acyclic Node DAG with `ALL` joins and one normal Fusion terminal.**
12. When does a Node release successors? **After every required child SLK has a usable closed delivery; unrelated paths continue.**
13. Does the Supervisor use `wait_threads` to monitor construction? **No; messages activate one bounded routing or boundary action.**
14. Which files control a Run? **`GLK-GRAPH.md`, `GLK-ROSTER.md`, and `GLK-RUN-<RUN-ID>.md`.**
15. Which version defines this interpretation? **GLK 4.1.0.**
