# GO Graph Construction

Build the minimum GO set that covers the frozen Run Feature. Every GO has one
primary claim, explicit scope, acceptance, evidence, predecessors, conflict keys,
and candidate binding.

Add edge `A -> B` only when B cannot start and independently complete correctly
before A receives D2 PASS. Record that justification on the edge. Preferred order,
shared files, likely calls, team structure, and scheduling convenience are not edge
evidence.

Every new edge binds source claim/output refs, target input/assumption refs, and
consumption evidence. These bindings support causal slicing but do not authorize
edges derived only from call graphs, data-flow graphs, files, or module structure.

Validate:

- every node is a GO;
- no GO claim overlaps another ambiguously;
- every edge is necessary;
- the graph is acyclic;
- every node is reachable from an entry;
- required terminal coverage proves the Run Feature;
- conflict keys are scheduling constraints, not dependency edges.

Freeze the result as a versioned `GRAPH_BASELINE` with a graph hash before product
implementation begins.
