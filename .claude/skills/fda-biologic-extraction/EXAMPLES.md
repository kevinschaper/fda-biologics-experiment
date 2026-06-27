# Worked example

Snapshot for orientation — **not authoritative**. Always re-run the scripts; ids/defs come
from the live ontologies and Biolink model, which evolve.

## Input (excerpt of an FDA label)

> **HUMIRA (adalimumab)** — INDICATIONS AND USAGE
> HUMIRA is a tumor necrosis factor (TNF) blocker indicated for the treatment of adults with
> moderately to severely active rheumatoid arthritis. … *Limitation of use: not for use in …*

## Step through

**1. Extract (names + verbatim quotes, no IDs)**
- subject: `adalimumab` (brand `Humira` → synonym)
- indication: `rheumatoid arthritis` (strip "moderately to severely active"); quote the phrase
- target: `TNF`; direction: blocker (decreases)
- For each claim, note *why* the quote supports the edge (`explanation`).
- Ignore the "Limitation of use" sentence (negation → not an edge).

**2. Predicate (disease axis)** — "for the treatment of … active rheumatoid arthritis" acts on an
existing disease:
```
$ python scripts/predicate_info.py --check biolink:ameliorates_condition --within treats_or_applied_or_studied_to_treat
{"predicate": "ameliorates condition", "curie": "biolink:ameliorates_condition", ... "member": true}
```

**3. Ground**
```
$ python scripts/ground.py --type drug "adalimumab"          # -> [{"curie":"NCIT:...","match_type":"exact",...}]
$ python scripts/ground.py --type disease "rheumatoid arthritis"  # -> [{"curie":"MONDO:...","match_type":"exact",...}]
$ python scripts/ground.py --type gene "TNF"                 # -> [{"curie":"HGNC:11892","match_type":"exact_symbol",...}]
```

**4. Emit `kb/biologics/adalimumab.yaml`**
```yaml
biologic:
  name: adalimumab
  id: NCIT:...
  synonyms: [Humira]
indications:
  - predicate: biolink:ameliorates_condition
    object: {name: rheumatoid arthritis, id: MONDO:..., matched_label: rheumatoid arthritis}
    label_section: INDICATIONS AND USAGE
    evidence:
      - reference: FDA:<SPL-setid>
        snippet: "indicated for the treatment of adults with moderately to severely active rheumatoid arthritis"
        supports: SUPPORT
        evidence_source: REGULATORY
        explanation: "The INDICATIONS section names RA as an approved treatment population, which directly asserts the ameliorates_condition edge."
    needs_review: false
    candidates: []
targets:
  - predicate: biolink:affects
    object: {name: TNF, id: HGNC:11892, matched_label: TNF}
    qualified_predicate: biolink:causes
    object_aspect_qualifier: activity_or_abundance
    object_direction_qualifier: decreased       # "blocker" → decreased
    label_section: INDICATIONS AND USAGE
    evidence:
      - reference: FDA:<SPL-setid>
        snippet: "a tumor necrosis factor (TNF) blocker"
        supports: SUPPORT
        evidence_source: REGULATORY
        explanation: "The label states the mechanism is TNF blockade → decreased TNF activity."
    needs_review: false
    candidates: []
provenance:
  knowledge_level: knowledge_assertion
  agent_type: text_mining_agent
  source_version: "5"                  # the label's SPL Version (or effective date)
  retrieved: "2026-06-26"               # date the label was fetched — QUOTE it (bare YAML dates fail validation)
  sources:
    - resource_id: infores:fda
      resource_role: primary_knowledge_source
      source_record_urls: [https://dailymed.nlm.nih.gov/dailymed/spl.cfm?setid=<real-SPL-setid>]
    - resource_id: infores:monarch-fda-biologics
      resource_role: aggregator_knowledge_source
      upstream_resource_ids: [infores:fda]
```

## Layering a corroborating PMID (optional)

Add a second `EvidenceItem` under the claim. This one IS quote-validated, so `snippet` must be an
exact substring of the abstract/full text:
```yaml
      - reference: PMID:########
        reference_title: "Adalimumab for rheumatoid arthritis: ..."
        snippet: "<exact quote copied from the paper>"
        supports: SUPPORT          # or PARTIAL / REFUTE / NO_EVIDENCE / WRONG_STATEMENT
        evidence_source: HUMAN_CLINICAL
        explanation: "Pivotal randomized trial demonstrating efficacy in RA."
```
