---
name: fda-biologic-pmid-enrichment
description: Add verified supporting-literature PMIDs to existing curated FDA biologic records (kb/biologics/*.yaml). A second pass over already-grounded edges that finds pivotal-trial / mechanism papers, attaches an exact-quote EvidenceItem, and verifies it with linkml-reference-validator. Use when adding literature evidence, corroborating indications/targets with PMIDs, or strengthening provenance beyond the FDA label.
---

# FDA Biologic PMID Enrichment

A **second pass** over records already produced by the `fda-biologic-extraction` skill. It does
**not** re-extract or re-ground anything — it adds optional supporting-publication `EvidenceItem`s
to existing edges. The FDA label remains evidence item 1; PMIDs layer after it.

## Hard rules
1. **The quote must be exact.** Copy the `snippet` verbatim from what the validator fetches
   (`lookup`), not from EuropePMC. linkml-reference-validator checks it by substring; paraphrase fails.
2. **Verify before appending.** Every PMID `EvidenceItem` must pass `validate text` (and `just refs`).
3. **Pick genuinely supporting papers.** Indications → a pivotal RCT / efficacy study; targets → a
   binding/mechanism study. Use `supports` honestly: `SUPPORT`, `PARTIAL`, or `REFUTE`.
4. **Don't touch grounding or predicates.** Only append to `evidence:` lists.

## Workflow

### 1) Pick edges to enrich
Choose a record and the indication/target edge(s) to corroborate (e.g. start with `needs_review`
edges or high-value indications).

### 2) Discover candidate papers
```
python scripts/find_literature.py "adalimumab" "rheumatoid arthritis"
python scripts/find_literature.py "adalimumab" "TNF" --extra "binds OR neutralizes OR mechanism"
```
Read the titles + abstract previews; choose the PMID that actually supports the edge.

### 3) Get the verbatim quote from the validator's own copy
```
linkml-reference-validator lookup PMID:###### --format json
```
Copy an exact sentence/phrase from the returned content (this is the text the validator checks
against). For a multi-part quote use ` ... ` to join non-adjacent fragments; bracket editorial
notes are ignored by the validator.

### 4) Verify the quote
```
linkml-reference-validator validate text "<your exact quote>" PMID:######
```
Must print `Valid: True`. If not, copy a cleaner sentence (or `linkml-reference-validator repair`).

### 5) Append the EvidenceItem
Add to the edge's existing `evidence:` list (after the FDA item):
```yaml
      - reference: PMID:######
        reference_title: "<title from lookup>"
        snippet: "<the exact verified quote>"
        supports: SUPPORT            # or PARTIAL / REFUTE
        evidence_source: HUMAN_CLINICAL   # IN_VITRO for binding/mechanism assays
        explanation: "Pivotal RCT demonstrating efficacy of adalimumab in RA."
```

### 6) Confirm
```
just refs kb/biologics/<drug>.yaml      # PMID snippets quote-checked (FDA refs skipped)
just qc   kb/biologics/<drug>.yaml      # full sweep stays green
```
Promote `provenance.agent_type` to `manual_validation_of_automated_agent` if a human verified the record.

## Scripts
- `scripts/find_literature.py` — EuropePMC discovery (PMID + title + abstract preview). Discovery
  only; the quote always comes from `lookup` + `validate text`.

## See also
- The record/evidence shape and enums: `../fda-biologic-extraction/REFERENCE.md`.
- FDA-label snippets are verified separately by `just fda` (that skill); this skill adds PMIDs.
