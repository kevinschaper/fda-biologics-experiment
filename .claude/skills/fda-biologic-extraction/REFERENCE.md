# Reference

Definitions are **not duplicated here** — they live in the Biolink model and are read live via
`scripts/predicate_info.py`. This file holds the *interpretation* layer (how to map FDA label
language onto the model) and the project conventions.

## Identifier / prefix policy

| Axis | Prefix | Grounded by | Validated by |
|------|--------|-------------|--------------|
| Disease (object) | `MONDO` | OAK `sqlite:obo:mondo` | linkml-term-validator |
| Drug (subject)   | `NCIT` | OAK `sqlite:obo:ncit` | linkml-term-validator |
| Gene/target (object) | `HGNC` | genenames.org REST (alias-aware) | Monarch API `just genes` (api-v3) |

- Subject is the **generic** biologic name; brand names are synonyms, never the grounded id.
- NCIT is the chosen drug space because biologics (large molecules) are poorly covered by CHEBI;
  NCIT covers them and has a sqlite adapter for validation.

## Disease-axis predicate decision table

All three are members of the `treats` family (mixin-aware) and inherit a **strong-evidence**
requirement — FDA approval satisfies it, so emit `knowledge_level: knowledge_assertion`.
Run `python scripts/predicate_info.py --family treats` for the verbatim live definitions.

| FDA label phrasing | Predicate | Notes |
|---|---|---|
| "for the treatment of…", "indicated to treat…", "reduces signs and symptoms of…" (active disease) | `biolink:ameliorates_condition` | acts on an existing condition |
| "for the prevention of…", "for the prophylaxis of…", "to reduce the risk of…" | `biolink:preventative_for_condition` | prevents manifesting |
| general claim, mixed, or genuinely ambiguous | `biolink:treats` | the umbrella; safe default |
| weaker than approval (should not occur in an approved-indication ingest) | `biolink:treats_or_applied_or_studied_to_treat` | flag `needs_review` if seen |

Note: `ameliorates_condition.is_a` is actually `affects` and `preventative_for_condition.is_a`
is `affects_likelihood_of`; they attach to `treats` as **mixins**. So membership checks must be
mixin-aware (`--within treats_or_applied_or_studied_to_treat`), which `predicate_info.py` handles.

Default policy: prefer the most specific predicate the label clearly supports; when the verb is
ambiguous, use `biolink:treats` and set `needs_review: true`.

## Drug→gene (target) predicate — RESOLVED: affects + direction

A target edge is modeled as **`biolink:affects` with qualifiers**, capturing the mechanism and
direction (the distinctive, curatable signal for biologics):

| Field | Value |
|---|---|
| `predicate` | `biolink:affects` |
| `qualified_predicate` | `biolink:causes` |
| `object_aspect_qualifier` | `activity_or_abundance` (default); `activity` for a blocker, `abundance` for a depleting antibody |
| `object_direction_qualifier` | `decreased` for inhibitors/blockers/antagonists; `increased` for agonists |

Reads as *"adalimumab causes decreased activity of TNF."* The HGNC gene stands in for its product
(standard gene-or-gene-product convention). Direction comes from the label's mechanism language
("blocker", "inhibitor", "antagonist" → decreased; "agonist" → increased); if the label gives no
direction, set `object_direction_qualifier: decreased` only when clearly a blocker, else
`needs_review: true`.

## Evidence model (mirrors dismech `EvidenceItem`)

Every claim carries `evidence: [EvidenceItem]`. Reuse dismech's exact slots/enums so the
LinkML schema and validators line up:

`EvidenceItem` slots:
- `reference` — `implements: linkml:authoritative_reference`. `PMID:…` (validated) **or**
  `FDA:<SPL-setid>` (the label; provenance, not quote-checked).
- `snippet` — exact verbatim quote, `implements: linkml:excerpt`. **This is what
  linkml-reference-validator checks** against `reference`. Must be an exact substring — paraphrase = CI fail.
- `supports` — `EvidenceItemSupportEnum`: `SUPPORT` · `REFUTE` · `PARTIAL` · `NO_EVIDENCE` · `WRONG_STATEMENT`.
- `evidence_source` — `EvidenceSourceEnum`: `HUMAN_CLINICAL` · `MODEL_ORGANISM` · `IN_VITRO` ·
  `COMPUTATIONAL` · `OTHER` — **plus `REGULATORY`** (our extension, for the FDA-label item).
- `reference_title` — recommended for PMIDs.
- `explanation` — free text: *why* the snippet supports (or refutes) the claim. Always write it.

Convention for FDA biologics:
- **Item 1 = the FDA label**: `reference: FDA:<SPL-setid>`, `evidence_source: REGULATORY`,
  `snippet` = the verbatim indication/mechanism phrase, `supports: SUPPORT`. Authoritative; the
  reference-validator skips it (not a PMID/PMC).
- **Items 2…n = corroborating PMIDs**: quote-validated; may carry `PARTIAL`/`REFUTE`/etc.

Reference-validator integration: mark slots with `implements: linkml:authoritative_reference`
(reference) and `linkml:excerpt` (snippet); the validator finds claims by those markers, not by
field name. It currently fetches PubMed/PMC only, so `FDA:` references are not quote-checked.

## Edge-case catalog

- **Brand vs generic** (Humira → adalimumab): ground the generic; brand is a synonym.
- **Severity/qualifier stripping**: strip "moderate-to-severe / active / chronic" for grounding,
  keep the full phrase in `original_text`.
- **Negation / limitations of use**: never an edge. Watch for "not indicated", "contraindicated",
  "limitation of use", "should not be used".
- **Combination indications** ("in combination with methotrexate"): the edge is still drug→disease;
  note the co-therapy in `original_text`, don't model it as a separate subject.
- **Multiple indications**: one record per disease.
- **Pediatric/subpopulation indications**: same disease edge; capture the population in
  `original_text` (population qualifiers are out of scope for v1).
- **Ambiguous grounding**: keep all `candidates`, set `needs_review: true`, never auto-pick.

## Growing the overrides table

`scripts/overrides.yaml` is the curated fallback for names search gets wrong (dismech learned this
is necessary). When `ground.py` returns no exact match for a name you've confirmed by hand, add it:
```yaml
drug:
  "ado-trastuzumab emtansine": {curie: NCIT:Cxxxxx, label: "Ado-Trastuzumab Emtansine"}
disease:
  "covid-19": {curie: MONDO:0100096, label: "COVID-19"}
```
Matching is case-insensitive after whitespace normalization.
