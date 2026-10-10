# Historical GLK DAG and SLK Composition Design

## Status

This 2026-08-23 design produced the published GLK 3.2.0 reconstruction. It is retained only as provenance and does not define the current Supervisor topology.

The current authority is:

```text
docs/superpowers/specs/2026-10-11-glk-4.1.0-shared-supervisor-design.md
```

GLK 4.1.0 uses exactly one shared Supervisor Agent per GLK Run. Every child SLK remains an independent Run, but its Supervisor role binding resolves to that shared Agent. Historical implementation detail remains recoverable from Git history and must not be copied into a current Run.
