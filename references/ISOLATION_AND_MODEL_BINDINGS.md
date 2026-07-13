# LLK Isolation and Model Bindings

## Contents

- Isolation Principle
- Mandatory Isolation Layers
- Workspace Topology
- Capability Boundaries
- Per-Role Model Bindings
- Model Diversity
- Binding Selection and Switching
- Failure and Recovery

## Isolation Principle

Isolation is enforced separation of mutable state and authority, not a role name or prompt. Sharing a machine, Git object database, or provider is acceptable only when no role shares mutable context, product workspace, capability profile, model configuration object, secret material, or untracked authority.

If a mandatory boundary cannot be enforced, Supervisor records `governance-hold`. Do not launch or claim an active LLK.

## Mandatory Isolation Layers

| Layer | Required boundary |
|---|---|
| Identity/context | Fresh role context and memory; no shared mutable conversation or hidden cross-role scratchpad |
| Workspace | Separate Worker worktree/sandbox; separate Checker validation workspace; immutable handoff artifact |
| Capability | Least-privilege tool, write, network, and external-side-effect permissions per role |
| Artifact/evidence | Hash-bound attempts, append-only records, and no overwrite of prior receipts/checks/routes |
| Model configuration | One immutable binding per role instance; no mutable global provider/model/API/tool default |
| Secrets | Role-scoped secure-loader references; no raw secret or automatic credential forwarding |
| Lifecycle | Explicit creation, replacement, authority transfer, retention, and teardown records |

Isolation is both launch-time and runtime policy. Heartbeats inspect drift in active IDs, workspaces, capabilities, and model bindings.

## Workspace Topology

- **Supervisor:** governance/control tree; no ordinary product workspace writes. A bounded repair uses a dedicated repair sandbox created from the immutable Worker artifact, never the Worker's mutable directory.
- **Planner:** read-only project/contract snapshot plus plan-proposal output area.
- **Worker:** isolated worktree or sandbox for the assigned Loop/CELL. Parallel Workers never share a mutable working directory.
- **Checker:** separate validation checkout/sandbox created from the exact immutable Worker artifact. Checker writes evidence only, never the Worker workspace or product source.
- **Router:** read-only contract/evidence inputs plus route-record output area.

A shared mutable checkout is forbidden, even when roles execute serially or promise disjoint write times. Git worktrees may share the repository object database, but each role receives a distinct working directory and lock/ownership record. Tests that generate files run in the Checker validation sandbox.

## Capability Boundaries

| Role | Product write | Governance/evidence write | External side effects |
|---|---|---|---|
| Supervisor | Only bounded-repair exception | Contract, registry, intervention, final acceptance | Contract-approved Owner actions only |
| Planner | Denied | Plan, assignment, split/replan proposal | Denied unless explicitly required for planning |
| Worker | Assigned paths in own sandbox | Worker receipt/evidence | Only CELL-approved side effects |
| Checker | Denied | Check report and validation evidence | Non-destructive checks only unless contract says otherwise |
| Router | Denied | Route record only | Denied |

Tool availability does not grant authority. Deny unused tools and record all exceptional elevation. A role cannot expand its own capability profile.

## Per-Role Model Bindings

Every role instance has one active binding record. Worker pools have one binding per candidate Worker.

```yaml
model_binding_id: <immutable-id>
role_id: <role-instance-id>
provider: <provider-name>
model: <model-name/version>
endpoint_ref: <non-secret endpoint reference>
credential_ref: <secure-loader reference>
context_id: <isolated-context-id>
reasoning_profile: <effort/mode reference>
service_profile: <tier/timeout/retry reference>
parameter_profile: <model parameters reference>
tool_profile_id: <least-privilege tool set>
skill_profile_id: <approved skills>
data_policy_id: <retention/residency/redaction policy>
budget: <token/cost/time limits>
fallback_model_binding_ids: [] # Worker bindings only; always empty for other roles
binding_hash: <content hash>
```

Never store raw API keys. Distinct roles always have distinct binding IDs, even when provider/model values match. Worker, Checker, and Router cannot reuse one binding record or mutable client/session object.

## Model Diversity

Separate configuration is mandatory. Different underlying models/providers are the preferred default for Worker and Checker because diversity reduces correlated reasoning and blind spots. It is additional defense, not a replacement for context, workspace, capability, and evidence isolation.

When constraints require the same underlying model:

- keep distinct binding IDs, contexts, tool/skill profiles, and invocation sessions;
- use separately scoped credential references when available;
- record reduced diversity and compensating evidence in the contract;
- require Checker to derive its judgment from frozen acceptance and independently reproduced evidence, not Worker rationale.

Router should also use a binding independent from Checker. Supervisor and Planner configurations are separately frozen so a global setting change cannot silently alter the chain.

## Binding Selection and Switching

Supervisor owns the frozen binding matrix. Planner may select a Worker or Worker fallback only when both the binding and trigger condition are preauthorized. Planner cannot change Supervisor, Planner, Checker, or Router bindings. Only Worker bindings may contain `fallback_model_binding_ids`; every non-Worker binding keeps that field empty.

Checker preflight must reject any non-Worker fallback entry. At runtime, detecting such an entry or attempted activation is configuration drift and immediately causes `governance-hold`.

For every switch, append old/new binding IDs, trigger, role/context IDs, budget impact, artifact/attempt impact, and effective time.

- A frozen role instance is never rebound in place. Every binding change creates a new role instance and context only after Router routing or a frozen amendment authorizes replacement; every non-Worker change also requires explicit authority transfer or a recovery packet when the prior instance is unavailable.
- Planner alone activates a preauthorized Worker fallback, and only at an authorized dispatch point or contract-defined Worker failure handback. It creates a new Worker role/context and attempt; the fallback never inherits another Worker's validation receipt.
- Any Supervisor, Planner, Checker, or Router binding/provider/model/tool/skill/credential change requires `governance-hold`, contract amendment, independent preflight QC by a Checker that is not approving its own unreviewed binding, and Supervisor freeze. Being listed as a fallback cannot bypass this rule.
- An unlisted Worker binding/provider/model/tool/skill/credential change requires the same hold, amendment, independent preflight QC, and Supervisor freeze.
- A role never approves its own unreviewed binding change.
- Every non-Worker replacement receives a complete recovery packet after the amended binding is frozen; Checker and Router replacements must preserve the exact validation/route pointer.
- Global environment/default changes do not alter frozen bindings; mismatch causes `governance-hold`.

## Failure and Recovery

| Failure | Response |
|---|---|
| Binding missing or loader unavailable | Record `governance-hold`; do not borrow another role's credentials/client; a reachable Router chooses the formal next route |
| Runtime binding hash differs from contract | Record `governance-hold`, stop role, preserve outputs, append drift evidence; Supervisor cannot restore-and-resume unilaterally, and a reachable Router must choose restoration/revalidation through `continue` or amendment through `replan` |
| Shared mutable context/workspace detected | Record `governance-hold`, quarantine the attempt and preserve evidence; Router decides rework/replan before clean isolation and double validation |
| Unauthorized model switch | Record `governance-hold`, invalidate affected attempt evidence; Router must route `replan` before amendment/preflight QC |
| Credential exposed in records | Record `governance-hold`, stop dispatch, append a superseding redaction record, and require Owner-approved rotation; Router controls resumption |
| Worker model/provider unavailable | Planner may use only a preauthorized Worker fallback under its frozen trigger; otherwise hold for Router routing and amendment |
| Non-Worker model/provider unavailable | Record `governance-hold`; replacement always requires amendment, independent preflight QC, Supervisor freeze, and authority transfer |

`governance-hold` grants Supervisor authority only to stop dispatch, preserve/quarantine state, and append the observation. It does not authorize restoration, replacement, resume, or route. Recovery never copies mutable conversation history wholesale. Transfer only the frozen contract, formal records, immutable artifact, evidence index, approved binding, and explicit role authority.
