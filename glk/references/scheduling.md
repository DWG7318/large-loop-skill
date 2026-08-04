# Maximal-Safe Activation

GLK 3.1.0 preserves direct maximal-safe activation.

Run Supervisor maintains two graph-control sets:

```text
GRAPH_WAITING_SET
GRAPH_ACTIVE_SET
```

Every unresolved non-active GO is `WAITING_GO` and records all current
`waiting_reasons`. When those reasons become empty, the GO enters `ACTIVE_GO`
directly.

After every D2 verdict, formal resolution, constraint change, amendment, role
binding, or environment event, Run Supervisor recalculates the graph and adds every
additional conflict-free GO. The resulting `GRAPH_ACTIVE_SET` must be maximal: no
waiting GO can be added without violating a recorded dependency, conflict, resource,
isolation, or safety condition. When different safe selections have different sizes,
choose the maximum-cardinality set; deterministic identity order breaks equal-size
ties.

When mutually conflicting nodes compete for one resource, Owner priority, critical
path, risk, rollback cost, and external timing may select which node activates. The
losing node records the real conflict reason. Priority never creates an edge.

Invalid reasons include easier coordination, model preference, reduced Supervisor
effort, or a desire to serialize the Run. Non-dependency constraints must never be
encoded as fake dependency edges.

After a confirmed causal amendment, only affected GOs are re-projected. A source GO
with no waiting reason enters `ACTIVE_GO` directly. Consuming successors remain
`WAITING_GO` under existing dependency reasons until the source has current D2;
then every safe successor activates in the same maximum-cardinality recalculation.
Unaffected active or verified branches are not replayed.

A D2 PASS alone cannot release a successor. The Supervisor first records an exact
admission of that D2, then appends a separate `GRAPH_EVENT` bound to the current
graph/version/digest. Only that event removes the typed dependency waiting reason
and triggers active-set recomputation.

Liveness and architecture holds constrain activation without becoming fake
dependency edges. Progress reports active GO IDs together with exact required
GO/D2 and required CELL/D1 completion.

GLK 3.1 additionally constrains the maximal safe ACTIVE_GO set with current CPU,
RAM, GPU/VRAM, disk/IO, process, port, external-service, and heavy-validation
reservations. Logical eligibility remains unchanged. Capacity shortage shrinks a
CELL or records a typed resource constraint; it never adds a fake edge.
