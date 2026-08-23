# GLK DAG Supervisor and SLK Composition Design

## Status and authority

- Design date: 2026-08-23.
- Status: Owner-approved design; implementation has not started.
- Scope: reconstruct the future GLK method around one GO DAG, one Supervisor,
  and direct reuse of the latest SLK.
- Current release: GLK 3.1.0 remains unchanged until a separately reviewed
  implementation and release plan completes.
- Versioning: this design deliberately does not assign the future release number.
  The implementation plan will select a new, non-overwriting release identity.

This design is the authority for the planned reconstruction. Existing GLK method
files and the unreleased 4.0 structural-slimming design remain historical and
implementation context; they do not override the decisions in this document.

## Problem

Current GLK accumulated its own role system, validation system, runtime controls,
and repeated rules already owned by SLK. That made the method heavy, difficult to
understand, and easy to stop for internally manufactured reasons.

The reconstruction keeps only the graph problem native to GLK. A large project is
decomposed into GO nodes, the nodes are connected by real outcome dependencies,
and each node is constructed by an unchanged SLK Checker and Worker pair. Graph
complexity belongs to one GLK Supervisor.

## Core definition

GLK is a Graph-based Loop Engineering construction technique for large projects.

```text
multiple independent start GOs
        -> dependency-driven DAG execution
        -> one normal-path Fusion GO
        -> one final D2 boundary
        -> completed product
```

One GLK Graph is one Run. Every graph node is one GO. Every GO uses the latest SLK
for its internal linear CELL construction.

GLK has no Stage, Level, batch barrier, graph cycle, or arbitrary waiting group. A
GO starts as soon as all of its declared prerequisites are satisfied. An unrelated
GO never delays it.

## Method composition boundary

GLK does not redefine SLK.

- Every GO directly uses the latest available SLK method baseline selected before
  the GLK Run starts.
- The selected SLK baseline remains fixed for the Run so different GO members do
  not drift across method versions.
- Existing SLK Skills own initial CELL planning, model selection, member creation,
  dispatch, Worker execution, D0, Checker D1, rework, communication recovery, and
  member work recording.
- GLK does not create GLK-specific Checker or Worker instructions.
- GLK does not modify the SLK main Skill or SLK child Skills to accommodate GLK.

The only composition mapping is closure: an ordinary GO uses SLK through D1 and GO
closure, but does not receive a separate Run-level D2. GLK has one final D2 boundary
after Fusion.

## Roles

GLK introduces no new construction role beyond the existing SLK roles.

```text
one GLK Supervisor
one exclusive SLK Checker for every GO
one exclusive SLK Worker for every GO
```

The Supervisor owns all graph complexity. Each Checker and Worker understands SLK
and its own GO assignment; it does not need to understand GLK or the whole Graph.
Members may read the Graph, roster, and Run record, but such reading is not a normal
start prerequisite for Checker or Worker construction.

### Supervisor responsibilities

The Supervisor:

- reads GLK first, then obtains and binds the latest SLK;
- passes a concise GLK understanding check before graph design;
- designs and self-checks the GO DAG with the GLK Graph Design Skill;
- calls SLK planning for every GO's initial linear CELL plan;
- creates the three authoritative Run files;
- creates every Checker, after which each Checker creates its own Worker by SLK;
- receives completed GO handoffs from Checkers;
- performs no ordinary-GO D2 and does not re-check Checker conclusions;
- tracks dependency completion and forwards one complete start handoff when all
  direct prerequisites of a GO are present;
- changes only unstarted graph regions under the amendment rules;
- activates Fusion and performs the final D2 boundary;
- activates the prebuilt D2 Repair GO when final D2 fails;
- archives every Checker and Worker after successful closure while retaining the
  Supervisor conversation.

### Checker and Worker responsibilities

Checker and Worker responsibilities are exactly the latest SLK responsibilities.
GLK supplies a GO assignment containing goal, initial CELL plan, inputs, output
interface, allowed scope, and acceptance facts. SLK governs everything inside that
assignment.

## Graph identity and topology

### GO identifiers

GO identifiers use only numeric names:

```text
GO001
GO002
...
GO999
GO1000
```

Letters such as GO-A are not used. A numeric identifier is a permanent identity,
not an execution order. A later-numbered GO may start before an earlier-numbered GO
when its prerequisites are satisfied.

Role names bind to the GO identifier:

```text
GO012-Checker
GO012-Worker
```

The Supervisor is unique and is not GO-numbered.

### Required DAG properties

The normal construction Graph:

- is directed and acyclic;
- has two or more independently startable zero-indegree GOs;
- uses only real outcome-consumption dependencies;
- allows forks and joins;
- uses `ALL` semantics for every join;
- contains no ordinary optional GO and no empty or placeholder GO;
- gives every ordinary GO a path from a start GO and a path toward Fusion;
- has one normal-path terminal Fusion GO.

File or directory overlap does not create a dependency. A dependency exists only
when the target GO genuinely consumes the source GO's outcome.

### GO contract

Every GO records:

- GO identifier and one-sentence outcome;
- explicit start prerequisites;
- direct predecessor GO identifiers;
- authoritative inputs;
- output interface contract;
- allowed construction scope;
- initial SLK CELL plan;
- Checker and Worker binding;
- direct successor GO identifiers;
- completion and evidence expectations.

The output interface contract states what is delivered, in what form, how it is
used, and how the owning Checker establishes it during D1. This enables dependent
GO construction and final Fusion without hidden assumptions.

### Start semantics

All start GOs receive their complete SLK handoff from the Supervisor and may start
concurrently.

For a dependent GO, the Supervisor receives each direct predecessor's completed
handoff. The Supervisor does not inspect or validate those handoffs. When every
declared predecessor handoff is present, it sends one complete SLK start handoff to
the dependent GO's Checker. The Checker therefore does not track partial graph
readiness or wait for other predecessor messages.

Only the affected descendant path waits when a GO remains active, blocked, or in
SLK rework. Other startable GOs continue.

## Graph Design Skill

The Supervisor uses one dedicated GLK Graph Design Skill before members start. The
Skill performs design and static reasoning, not trial construction.

It checks that:

1. every GO has a necessary, non-empty construction outcome;
2. there are no ordinary optional GOs;
3. multiple valid start GOs exist;
4. the normal path has exactly one Fusion terminal;
5. every non-start GO has explicit prerequisites;
6. every producer output matches each consumer input;
7. every ordinary GO is reachable and can reach Fusion;
8. the topology is acyclic and contains no Stage, Level, or batch barrier;
9. parallel workspaces and runtime resources can be isolated;
10. GO identifiers, role bindings, and the roster agree;
11. a static dependency walk reaches Fusion without an orphan or dead end;
12. the D2 Repair GO has only the final-D2-failure activation condition.

The Supervisor freezes the Graph after this check. Presenting the GO logic diagram
to the Owner is recommended but optional. If the Owner does not want to review it,
the Supervisor proceeds from its own completed design check.

## Owner-facing logic diagram

The Owner-facing view contains only:

- GO identifier and one-sentence outcome;
- dependency arrows;
- start GOs;
- Fusion GO;
- the conditional D2 Repair tail.

The Owner is not asked to review CELLs, tests, models, member arrangements, or full
GO contracts. Owner review does not become a mandatory construction gate.

## Member creation and communication

After Graph freeze, the Supervisor creates every Checker, and every Checker creates
its exclusive Worker through the latest SLK. Fusion and D2 Repair members are also
created before construction.

Before the first GO starts, communication is tested for:

```text
Supervisor <-> every Checker
every Checker <-> its own Worker
```

There is no Checker-to-Checker communication relationship.

An inactive prebuilt member remains idle; it does not use Wait threads, watch other
members, or start construction early. The Supervisor sends a direct start handoff
when the GO becomes startable.

A legal graph amendment may create a previously unknown GO. This is the necessary
exception to prebuilding every member: the Supervisor creates and tests the new
Checker/Worker pair immediately after accepting the graph amendment and before the
GO starts.

## Handoff and receipt behavior

An ordinary GO Checker uses SLK to determine whether all planned CELLs have D1
conclusions, any exemption is valid, the promised output interface is usable, and
the candidate and evidence are complete. It records its own facts and sends the GO
completion handoff to the Supervisor.

The Supervisor does not perform completeness confirmation, code inspection, test
reruns, or a second verdict. It forwards according to the Graph and makes a
reasonable attempt to confirm that the destination Checker received and recorded
the handoff.

Receipt confirmation is a destination member's entry in the shared Run record, not
a backward reply to an upstream Checker. If a handoff is missing or unusable as a
message, the destination Checker records the communication problem and tells the
Supervisor. The Supervisor restores or resends the unchanged handoff. A transport
problem is not treated as a construction failure.

The Supervisor does not remain online in Wait threads. A Checker completion message
activates it; it performs routing work and then returns to an inactive state.

## Authoritative Run files

Every GLK Run has exactly three method-control files at the project root:

```text
GLK-GRAPH.md
GLK-ROSTER.md
GLK-RUN-<RUN-ID>.md
```

### `GLK-GRAPH.md`

The Supervisor creates and modifies the sole Graph authority. All members may read
it. It contains topology, GO contracts, start conditions, output interfaces, Fusion,
and D2 Repair activation.

### `GLK-ROSTER.md`

The Supervisor creates and modifies the sole member roster. All members may read
it. It records Supervisor and GO member identities, visible conversation IDs,
communication results, replacements, and archive state. Replaced members remain in
history and new bindings are appended.

### `GLK-RUN-<RUN-ID>.md`

The Supervisor creates the sole shared Run record. Every member appends truthful
facts about its own assignments, execution, checks, errors, rework, exemptions,
handoffs, receipts, and evidence locations. Existing entries are preserved. GLK
does not create a separate method record for every GO.

## Workspace isolation and code overlap

Parallel GO construction uses independent worktrees and, where relevant, separate
temporary databases, ports, caches, test paths, and runtime resources.

Two GOs that modify the same file but do not consume one another remain independent.
They produce separately accepted candidates. They do not merge one another or use
one GO worktree as a hidden main line.

If overlap is so extensive that the GO outcomes are not independently meaningful,
the Supervisor redraws the boundaries of the affected unstarted GOs. It does not
invent a dependency solely to serialize file writes.

## Fusion GO

Fusion is a normal GO executed by its own exclusive SLK Checker and Worker pair.
It is the normal construction path's last GO.

Fusion:

- starts only after every direct predecessor handoff is present;
- runs in its own independent worktree;
- starts from the Run's determined baseline;
- consumes only direct predecessor candidates, not every historical GO candidate;
- understands each input's output interface and functional intent;
- resolves overlapping code ownership, conflicting implementations, and interface
  adaptation;
- performs real integration construction and integration testing;
- produces the one final GLK candidate for Supervisor D2.

Fusion is not a mechanical Git merge. It owns final code integration. The same
principle is suitable for CLK: independent Chains produce accepted candidates and
CLK Fusion owns their final code integration.

## D0, D1, and final D2

- D0 is the latest SLK Worker's minimum pre-delivery check.
- D1 is the latest SLK Checker's isolated CELL check and GO closure basis.
- D2 is one Graph-level final boundary owned by the GLK Supervisor after Fusion D1.

There is one D2 boundary, but it may have another attempt after D2 Repair. Before
each D2 attempt, the Supervisor uses the highest capability model permitted for the
Run. D2 does not repeat every CELL D1. It checks Graph completion, dependency and
interface composition, Fusion integration, exemptions, omitted or duplicated
capability, and satisfaction of the whole Run goal.

## D1 rework and D2 Repair GO

The method distinguishes these mechanisms by trigger, scope, members, and return
path.

| Property | D1 rework | D2 Repair GO |
|---|---|---|
| Trigger | Current GO Checker | GLK Supervisor |
| Condition | One CELL fails D1 | Final D2 fails after Fusion |
| Scope | Current GO's SLK loop | Prebuilt conditional GLK GO |
| Members | Current Checker and Worker | Dedicated Checker and Worker |
| GO identity | No new GO | Reserved numeric GO identity |
| Return | Continue current D1 | Return to the same final D2 boundary |

The full name `D2 Repair GO` is used in GLK documentation. Plain `Repair GO` is not
used. D1 uses the term rework or返工 and never activates D2 Repair.

D2 Repair is the only optional GO in GLK. It is not empty: its fixed start condition
is a failed final D2, its input is the D2 defect package and Fusion candidate, and
its output is a corrected final candidate with repair evidence. Its Checker and
Worker are prebuilt and communication-tested. If D2 passes initially, the unused
pair is archived. If D2 Repair itself requires D1 rework or another D2 attempt finds
remaining defects, the same D2 Repair Checker and Worker continue under SLK; another
D2 Repair GO is not created.

## Exemptions and required outputs

An SLK exemption may allow a GO to close only when the deviation does not make the
GO's promised output interface unusable.

If the required output interface is unavailable, the GO remains active. The
Supervisor uses existing SLK adjustment and recovery paths for the same GO, such as
CELL replanning, simple CELL splitting, model adjustment, implementation-path
adjustment, or member recovery. The defect is not moved to a new GO or silently
passed downstream.

Dependent descendants remain unopened while unrelated Graph paths continue.

## Graph amendments

The Supervisor may amend only the unstarted region when new engineering facts show
that a GO should be inserted, deleted, merged, or redrawn. Every amendment preserves:

- the Run goal;
- acyclicity;
- real outcome dependencies;
- `ALL` join semantics;
- one normal Fusion terminal;
- completed and active GO contracts and evidence;
- no ordinary optional or empty GO;
- direct-input and direct-output interface consistency.

An accepted or active GO is not renumbered or structurally rewritten. A removed or
merged unstarted GO identifier is never reused. Its roster history remains, for
example `REMOVED_BEFORE_START` or `MERGED_INTO_GO031`.

The Supervisor updates `GLK-GRAPH.md`, the roster, and the shared Run record. A new
GO receives a new numeric identity and a new SLK Checker/Worker pair before start.
Owner review is unnecessary unless the amendment changes the Run goal; optional
Owner review of the revised logic diagram remains available.

## Model selection

There is one model-selection authority for SLK, CLK, and GLK:

```text
$slk-select-models
```

GLK does not create a competing model-selection Skill or model table.

- The original conversation selects the GLK Supervisor model before creating it.
- The Supervisor uses the same SLK Skill to select each GO Checker and Worker model
  before member creation.
- A Checker is normally a strong professional coding model and not weaker than its
  Worker.
- A Worker remains a reliable professional coding model and may be one capability
  level lower when the CELL, machine, and accumulated workload allow sufficient
  margin.
- SLK governs capability-related rework changes.
- Owner model choices remain valid.
- Final D2 uses the highest capability model permitted for the Run.

CLK will also consume this one model-selection authority rather than maintain a
separate definition.

## Owner boundary

The original conversation and Owner choose GLK and define the Run goal, boundary,
and desired result. The original conversation creates the Supervisor, verifies
two-way communication, hands over the work, and exits engineering activity while
remaining available as an Owner contact and Supervisor recovery entry.

The Supervisor may offer the GO logic diagram to the Owner. Viewing or approving it
is optional. An Owner who declines to view it does not block construction.

After successful final D2, the Owner receives one concise conclusion containing GO
completion, D0/D1/D2 result, exemption count, whether D2 Repair ran, and the shared
Run record path. Owner approval is not required to make a passed Run complete.

## Skill architecture

GLK contains one main Skill and three GLK-native child Skills:

```text
graph-loop-skill
|-- glk-design-graph
|-- glk-run-graph
`-- glk-close-run
```

- `graph-loop-skill` owns identity, selection, the DAG definition, the Supervisor
  boundary, method artifacts, and routing to child Skills and latest SLK.
- `glk-design-graph` owns Graph design, static validation, initial GO planning,
  artifact initialization, optional Owner diagram, and preconstruction setup.
- `glk-run-graph` owns Supervisor member setup, start activation, GO handoff routing,
  dependency release, progress continuity, and legal unstarted-region amendments.
- `glk-close-run` owns Fusion activation, final D2, D2 Repair, final reporting, and
  member archiving.

All GO-local planning, model selection, member behavior, construction, D0, D1,
rework, communication recovery, and work recording remain latest-SLK calls. GLK
does not duplicate their content.

## CLK alignment

This GLK reconstruction produces two follow-up requirements for CLK without merging
the methods:

1. CLK's sole authoritative structure file is `CLK-CHAIN-MAP.md`, created and
   modified by its Supervisor and readable by all members.
2. CLK uses `$slk-select-models` as the single model-selection authority and adopts
   the same Fusion code-ownership principle: independent Chain candidates remain
   isolated until Fusion integrates them in its own worktree.

CLK remains Chain-based. It does not adopt GLK DAG routing or GLK artifacts.

## Non-goals

This reconstruction does not:

- modify SLK;
- copy SLK child Skills into GLK;
- introduce Checker-to-Checker communication;
- introduce Stage, Level, barrier, READY queue, patrol, or Wait-thread monitoring;
- add Grapher, Router, Planner, Verifier, or other GLK-specific construction roles;
- add ordinary optional, empty, or placeholder GOs;
- treat file overlap as a dependency;
- make Owner Graph review a mandatory gate;
- implement an Agent Runtime, session transport, or deployment engine;
- select or publish a release version in the design-only commit.

## Design acceptance criteria

The future implementation is faithful only when:

- a new user can understand the GLK main flow without reading old GLK versions;
- GLK-native Skills are limited to the main Skill and three child Skills;
- Checker and Worker instructions come from the selected latest SLK bytes rather
  than GLK copies;
- the Graph is a multi-start DAG with `ALL` joins and one normal Fusion terminal;
- only Supervisor performs graph routing and only after receiving Checker handoffs;
- ordinary GO completion never triggers a Supervisor D2;
- Fusion owns overlapping code integration in an independent worktree;
- the final D2 boundary and D2 Repair behavior match this design;
- the three authoritative Run files and their write permissions are unambiguous;
- no ordinary GO, identity, or historical record is silently reused or overwritten;
- existing published releases remain immutable.
