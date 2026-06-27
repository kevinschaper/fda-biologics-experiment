---
name: fda-biologic-extraction
description: Extract drug→disease (and drug→target) edges from FDA biologic product labels / Purple Book text and ground the names to ontology CURIEs (MONDO disease, NCIT drug, HGNC gene). Use when curating FDA biologics, pulling indications or molecular targets from drug labels, building the fda-biologics edges YAML, or when a subagent is handed FDA label text and must emit schema-conforming, grounded association records.
---

# FDA Biologic Extraction

Turn FDA biologic label / Purple Book text into grounded, schema-conforming edge records.
The content uses **names, not IDs** — your job is to extract the relationship and the
surface names, then let the scripts assign the CURIEs.

## Hard rules (read first)

1. **Never write a CURIE from memory.** Every `MONDO:`, `NCIT:`, `HGNC:` id MUST come from
   `scripts/ground.py`. Inventing IDs is the #1 failure mode — they look plausible and are wrong.
2. **Never write a predicate from memory.** Get the definition + verify the choice with
   `scripts/predicate_info.py` against the live Biolink model.
3. **Reject negation/hedging.** Contraindications, "not indicated for…", "limitation of use",
   warnings — these are NOT edges. Only positive approved indications/targets become edges.
4. **When grounding is not a confident exact match, set `needs_review: true`** and keep the
   candidate list. Do not silently pick among ambiguous candidates.
5. **Every claim needs evidence.** At minimum the FDA-label `EvidenceItem` (verbatim `snippet` +
   `explanation` of why it supports the edge). PMID `snippet`s must be exact quotes — they are
   machine-checked by linkml-reference-validator; paraphrases will fail CI.

## Workflow

### 1) Extract (names only, no IDs)
- **Subject**: the biologic — use the **generic/proper name** (e.g. adalimumab), record the
  brand (Humira) as a synonym.
- **Indications**: disease *names* from the INDICATIONS AND USAGE section. Strip severity
  qualifiers ("moderately-to-severely active rheumatoid arthritis" → "rheumatoid arthritis")
  but keep the original phrase verbatim in `original_text`.
- **Targets** (optional, drug→gene): the molecular target *name* only if the label states one
  (e.g. TNF, PD-1, HER2), plus the **direction** of effect (blocker/inhibitor → `decreased`,
  agonist → `increased`). Modeled as `biolink:affects` + qualifiers — see REFERENCE.md.
- Capture the `label_section`, the **verbatim quote** (`snippet`), and write an **`explanation`**
  of *why* that quote supports the edge — for every claim.
- If you cite a supporting publication, capture its **PMID** + an exact `snippet` from it.
- **Capture the label's version** (per-record provenance): the real DailyMed **SPL setid** (from the
  label URL), the label **`source_version`** (its "Version" number or effective date), and
  **`retrieved`** (the date you fetched it). Use the real setid in the `FDA:` reference and
  `source_record_urls` — never a placeholder.

### 2) Pick the predicate (disease axis)
Read the live definitions, then match the indication's intent:
```
python scripts/predicate_info.py --family treats     # defs for treats / ameliorates / preventative
```
- acts on an **existing** disease (treat active disease) → `biolink:ameliorates_condition`
- **prophylaxis / prevention / risk-reduction** → `biolink:preventative_for_condition`
- general claim, or genuinely unclear → `biolink:treats`

See REFERENCE.md for the phrasing→predicate table and the rationale (these inherit a
strong-evidence requirement, which FDA approval satisfies).

### 3) Ground every name
```
python scripts/ground.py --type disease "rheumatoid arthritis"
python scripts/ground.py --type drug    "adalimumab"
python scripts/ground.py --type gene    "TNF"
```
Returns JSON candidates `[{curie,label,score,match_type,source}]`, best first. Empty list ⇒ no
match ⇒ `needs_review: true`.

### 4) Select & verify
- Accept only a confident single match (`match_type: exact`/`exact_symbol`) whose label aligns
  with the source name. Otherwise → `needs_review: true` + attach `candidates`.
- Verify the predicate is a real member of the treats family:
```
python scripts/predicate_info.py --check biolink:ameliorates_condition --within treats_or_applied_or_studied_to_treat
```

### 5) Emit one file per drug
Write **one YAML file per biologic** to `kb/biologics/<generic-name>.yaml` (subject hoisted
once, then `indications[]` / `targets[]`). One file = one label = one subagent's owned unit, so
parallel curation never conflicts. CI re-validates with linkml-term-validator (ids must resolve)
and linkml-reference-validator (PMID `snippet`s must really appear in the cited paper).

## Output record (one file per drug)
```yaml
biologic:
  name: adalimumab
  id: NCIT:C1789
  synonyms: [Humira]
indications:
  - predicate: biolink:ameliorates_condition          # see predicate decision table
    object: {name: rheumatoid arthritis, id: MONDO:0008383, matched_label: rheumatoid arthritis}
    label_section: INDICATIONS AND USAGE
    evidence:
      - reference: FDA:<SPL-setid>                     # the approving label (authoritative source)
        snippet: "...moderately to severely active rheumatoid arthritis"   # verbatim
        supports: SUPPORT                              # EvidenceItemSupportEnum
        evidence_source: REGULATORY                    # EvidenceSourceEnum (label-derived)
        explanation: "INDICATIONS names RA as an approved treatment population, asserting the edge."
      - reference: PMID:########                        # optional corroborating literature (validated)
        reference_title: "..."
        snippet: "<exact quote from the paper>"
        supports: SUPPORT
        evidence_source: HUMAN_CLINICAL
        explanation: "Pivotal RCT showing efficacy in RA."
    needs_review: false
    candidates: []        # populated when grounding/predicate choice is uncertain
targets:
  - predicate: biolink:affects                      # drug→gene = affects + direction
    object: {name: TNF, id: HGNC:11892, matched_label: TNF}
    qualified_predicate: biolink:causes
    object_aspect_qualifier: activity_or_abundance  # activity / abundance / …
    object_direction_qualifier: decreased           # inhibitor/blocker → decreased; agonist → increased
    label_section: INDICATIONS AND USAGE
    evidence:
      - reference: FDA:<SPL-setid>
        snippet: "a tumor necrosis factor (TNF) blocker"
        supports: SUPPORT
        evidence_source: REGULATORY
        explanation: "Label states the mechanism is TNF blockade → decreased TNF activity."
    needs_review: false
provenance:
  knowledge_level: knowledge_assertion
  agent_type: text_mining_agent              # you are extracting from label prose — see note below
  source_version: "5"                         # the label's SPL Version (or effective date)
  retrieved: 2026-06-26                        # date you fetched the label
  sources:                                    # Translator RetrievalSource blocks (applied to every edge)
    - resource_id: infores:fda
      resource_role: primary_knowledge_source
      source_record_urls: [https://dailymed.nlm.nih.gov/dailymed/spl.cfm?setid=<real-SPL-setid>]
    - resource_id: infores:monarch-fda-biologics
      resource_role: aggregator_knowledge_source
      upstream_resource_ids: [infores:fda]
```
FDA labels version independently per drug, so `source_version` + `retrieved` are the per-record
version anchor; the overall build records ontology/service versions in `output/release-metadata.yaml`.
Every claim carries an `evidence[]` list (dismech `EvidenceItem` model): the FDA label is item 1
(`evidence_source: REGULATORY`, not PMID-validated); optional PMIDs layer after it and ARE
quote-validated. Always write the `explanation`.

**agent_type (set carefully):** you are an AI extracting edges from label text → use
`text_mining_agent`. It becomes `manual_validation_of_automated_agent` only after a human curator
verifies the record. Never `manual_agent` (that claims a human authored it). `knowledge_level`
stays `knowledge_assertion` — FDA approval is an asserted fact regardless of who extracted it.

## Scripts
- `scripts/ground.py` — name → CURIE candidates (OAK for MONDO/NCIT, genenames.org for HGNC).
  Search-first, then `scripts/overrides.yaml`, else empty (→ needs_review). Uses the oaklib
  Python API; first run downloads the ontology SQLite (NCIT is large, ~500MB).
- `scripts/predicate_info.py` — live Biolink predicate definitions + family/membership check
  (bmt, SchemaView fallback). Always in sync with the pinned Biolink version.
- `scripts/oak_config.yaml` — prefix→adapter map, **shared with linkml-term-validator**.
- `scripts/overrides.yaml` — curated name→CURIE overrides; grow it as you hit misses.

## See also
- REFERENCE.md — predicate decision table, prefix policy, edge-case catalog, drug→gene TODO.
- EXAMPLES.md — one fully worked label → records.
