# Canonical Dictionary

Version: 3.1.0. Canonical repository:
`https://github.com/DWG7318/large-loop-skill`.

- **Run**: one bounded engineering execution governed by one frozen Run contract.
- **GO**: one bounded independently verifiable engineering outcome.
- **GO Execution Graph**: one Run's directed acyclic GO-to-GO D2 precedence graph.
- **Edge**: mandatory rule that a successor waits for predecessor D2 or an explicit formal resolution.
- **WAITING_GO**: unresolved GO with one or more typed, evidenced waiting reasons.
- **ACTIVE_GO**: unresolved GO in the maximal safe active set.
- **Execution phase**: IMPLEMENTING, CHECKING, VERIFYING, or REWORK inside ACTIVE_GO.
- **D2**: independent GO claim verdict bound to accepted CELL receipts and one candidate.
- **D3**: independent Run Feature verdict over verified GO outcomes and graph seams.
- **GO_CAUSAL_TRACE**: versioned incident evidence binding one current-candidate
  source GO, an explicit symptom set, and evidence-selected actual-consumption paths.
- **Causal impact slice**: minimum successor set whose current candidate or evidence
  validity is affected by typed candidate, evidence, or claim/output seeds.
- **Seed-disposition invariant**: the strictest typed seed fixes the minimum source
  disposition; artifact-invalidating seeds cannot reuse the same current artifact.
- **Loop Owner Acceptance**: immediate product acceptance of this bounded Run.
- **Technical receipt**: one independent append-only D0, D1, D2, or D3 artifact
  issued only by its designated technical authority.
- **Supervisor admission**: mechanical acceptance or rejection of one exact
  artifact digest; never a technical verdict.
- **GO_CANDIDATE_CLOSURE**: exact current CELL candidate/D0/D1 tuple set from which
  one GO generation and hash are derived.
- **Derived non-authoritative**: a report or projection that cannot itself advance
  formal state.
- **RUN_AUTHORITY_HOLD / RUN_ARCHITECTURE_HOLD**: fail-closed Run stops for proven
  authority failure or repeated architecture failure on one path.
