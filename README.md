# Graph Loop Skill (GLK)

Graph Loop Skill is a Calabash-grounded Loop Engineering method for complex projects
whose GO relationships form a real graph rather than one serial loop or fixed
multi-chain Levels.

Current version: **2.0.0**

```text
Calabash
   ↓
Supervisor freezes authority
   ↓
Grapher owns GO Graph
   ↓
READY GO node(s)
   ↓
Planner -> active Worker -> Checker -> Router
   ↓
fresh GO Verification
   ↓
Grapher routes verified graph state
```

## Identity

- Product: **Graph Loop Skill**
- Abbreviation: **GLK**
- Invocation: `$graph-loop-skill`
- Legacy product: Large Loop Skill / LLK
- Legacy repository: `DWG7318/large-loop-skill`
- Target canonical repository after rename: `DWG7318/graph-loop-skill`

## Key Difference from MSLK

MSLK is a fixed multi-chain method with ordered Levels and full barriers.

GLK supports:

- arbitrary GO dependencies;
- conditional branches;
- partial unlock;
- joins;
- fallbacks;
- bounded cycles;
- evidence-driven graph revisions;
- multiple concurrently active GO nodes;
- multiple eligible Workers inside one CELL, with exactly one active Worker lease.

## Role Boundary

Project layer:

```text
Supervisor <-> Grapher
```

CELL layer inside an active GO:

```text
Planner -> one active Worker -> Checker -> Router
```

GO acceptance:

```text
fresh isolated Verification
```

Router never chooses a GO. Grapher never accepts a CELL. Verification never routes.

## Calabash

Every GLK run requires full Calabash or at least:

```text
Grandpa -> Product Architecture -> Ontology
```

If missing, Supervisor establishes Minimum Calabash from authoritative Owner intent
and verified project evidence before the formal GO Graph is created.

## Install

Copy `graph-loop-skill/` into the Codex skills directory and invoke:

```text
$graph-loop-skill
```

See `MIGRATION-LLK-TO-GLK.md` before upgrading an old LLK installation.
