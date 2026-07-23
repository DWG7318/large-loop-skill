# Migration: LLK to GLK 2.0.0

## Rename

```text
Large Loop Skill (LLK) -> Graph Loop Skill (GLK)
$large-loop-skill      -> $graph-loop-skill
large-loop-skill/      -> graph-loop-skill/
```

This is a breaking method migration, not a cosmetic rename.

## Old authority model

Legacy LLK described:

```text
Supervisor
  ↓
Planner -> Worker -> Checker -> Router
```

and allowed Router to answer a project/Loop-level `Goal verified?`.

## New authority model

```text
Project definition and contract: Supervisor
GO Graph and GO routing:         Grapher
CELL planning:                   Planner
CELL implementation:             one active Worker
CELL validation:                 Checker
CELL route:                      Router
GO verdict:                      Verification
Project final acceptance:        Supervisor
```

Planner/Worker/Checker/Router now operate only at CELL scope.

## Active-run rule

An active LLK run remains bound to its frozen LLK contract. Do not silently reinterpret
old evidence under GLK 2.0.0.

To migrate:

1. stop new LLK dispatch;
2. preserve all artifacts, evidence, and route records;
3. establish full or Minimum Calabash;
4. map old Loop/child-Loop outcomes to GO graph nodes;
5. create GO and edge Calabash traces;
6. create graph terminal conditions and bounded cycles;
7. provision Grapher and GO Verification;
8. define CELL Worker Sets and one-active-worker leases;
9. rerun all role readiness Evals;
10. run GLK no-side-effect simulation;
11. start a new GLK run from the last accepted immutable state.

## Repository rename

Merge the GLK files in the legacy repository first, then rename the GitHub repository
from `large-loop-skill` to `graph-loop-skill`. GitHub normally redirects old web and
clone URLs, but installed local skill folders must still be renamed manually.
