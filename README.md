# Graph Loop Skill (GLK)

Current version: **4.0.0**

GLK is the Graph-based Loop Engineering method for one large engineering Run. It expresses the Run as a multi-start directed acyclic graph (DAG) of necessary Nodes; every Node contains one or more Runs on one fixed latest-SLK baseline.

```text
multiple start Nodes
        -> dependency-driven Node activation
        -> one Fusion Node
        -> one final D2
        -> completed Run
```

## Core boundary

- One Graph is one Run; every node is numerically named such as `Node001`.
- Nodes start as soon as all direct prerequisites exist. Every join uses `ALL`; unrelated work does not wait.
- One Supervisor owns graph design, member setup, routing, Fusion, final D2, and archival.
- Every Node contains one or more complete SLK Runs. GLK does not duplicate SLK's CELL, D0, D1, D2, rework, communication, record, or model guidance.
- Normal construction ends in one Fusion Node. A prebuilt conditional D2 Repair Node is used only when final D2 fails.
- `$slk-select-models` is the single model-selection authority for SLK, CLK, and GLK.

## Run artifacts

- `GLK-GRAPH.md`: Supervisor-owned Node DAG and interface-contract authority; all members may read.
- `GLK-ROSTER.md`: Supervisor-owned visible-member roster; all members may read.
- `GLK-RUN-<RUN-ID>.md`: one shared append-only Run record; every member records its own facts.

## Skill collection

GLK 4.0.0 contains four sibling Skill directories:

| Skill | Purpose |
| --- | --- |
| `skills/graph-loop-skill/SKILL.md` | Method identity, SLK composition, Supervisor boundary, and routing |
| `skills/glk-design-graph/SKILL.md` | DAG design, static checks, initial SLK planning, and Run artifacts |
| `skills/glk-run-graph/SKILL.md` | SLK setup, Node activation, handoff routing, and unstarted-region amendments |
| `skills/glk-close-run/SKILL.md` | Fusion, final D2, D2 Repair, archival, and Owner conclusion |

The collection intentionally contains no separate GLK Checker, Worker, model-selection, runtime-control, patrol, or verification-role Skill.

## Fusion

Fusion starts from the Run baseline in its own independent worktree. It consumes only direct predecessor candidates and owns code overlap, implementation conflicts, interface adaptation, real integration construction, and integration testing. A mechanical Git merge is not Fusion completion.

## Validation

```powershell
python scripts/validate_repository.py
python scripts/quick_validate.py skills
python -m pytest -q
```

See [README.zh-CN.md](README.zh-CN.md), [MIGRATION.md](MIGRATION.md), and [VALIDATION-REPORT.md](VALIDATION-REPORT.md).
