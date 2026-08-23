# Migration to GLK 3.2.0

GLK 3.2.0 is a method reconstruction. It removes the active 3.1 runtime/kernel surface and keeps only GLK's distinct value: Supervisor-owned DAG orchestration over complete latest-SLK GO Loops.

## New Runs

New GLK Runs use:

```text
graph-loop-skill
glk-design-graph
glk-run-graph
glk-close-run
```

Bind the current latest SLK before the Run starts and keep that SLK version fixed for every GO. Create `GLK-GRAPH.md`, `GLK-ROSTER.md`, and `GLK-RUN-<RUN-ID>.md`; do not restore old runtime indexes, role systems, patrol, or extra verification layers.

## Existing Runs and releases

An active 3.1.0 or older Run remains governed by the exact version under which it began. Keep its evidence, artifacts, role bindings, and decisions unchanged. Do not reinterpret or rewrite them as 3.2.0.

Published tags and Releases remain immutable recovery points. GLK 3.2.0 uses a new version identity and does not move, replace, or overwrite an older tag or Release.

## Concept mapping

| Previous active surface | GLK 3.2.0 |
| --- | --- |
| GLK-owned CELL roles and runtime controls | Latest SLK inside each GO |
| Multiple graph/runtime authority files | `GLK-GRAPH.md` plus one roster and one shared Run record |
| GO-level additional verification | SLK D0/D1 inside the GO; one final Graph D2 after Fusion |
| Runtime graph queues and patrol | Message-activated Supervisor routes direct dependency completion |
| Separate GLK model policy | `$slk-select-models` |
| Final merge behavior | Fusion owns real integration in its own worktree |

Historical implementation details remain available through Git history and old version tags; they are not active 3.2 instructions.
