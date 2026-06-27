# FDA Biologics

The U.S. Food & Drug Administration approves **biologic** products — monoclonal antibodies,
fusion proteins, and related large molecules — each with an approved **indication** (the disease
it treats) and, almost always, a well-defined **molecular target** (the gene product it acts on).
Both relationships are stated in the prose of each product's FDA label. This resource reads those
labels and turns them into curated, evidence-backed knowledge-graph edges for the Monarch graph,
taking the **FDA label as the authoritative primary source** for the approval.

Related drug–disease and drug–target information is available in other resources; what this
resource contributes is fidelity to that primary source: each edge is read directly from the
approved label, carries a **verbatim, machine-verified quote** and a pointer to the specific label
version, is grounded to a standard ontology identifier, and — for targets — records the
**direction of effect**. Following the [dismech](https://github.com/monarch-initiative/dismech)
pattern, the source of truth is **hand-curated YAML, one file per biologic** rather than a bulk
download, because the edges are produced by a curator reading a label. Curation is performed by AI
agents working from a fixed procedure (the bundled skills), and every assertion is grounded and
checked against its source text before it is accepted.

## What is curated

Each biologic is one record capturing two kinds of edge:

* **Drug → disease (indication).** The conditions the product is FDA-approved to treat, read from
  the label's *Indications and Usage* section.
* **Drug → gene (molecular target).** The gene product the biologic acts on, read from the label's
  *Mechanism of Action*, together with the **direction** of that effect (a blocker decreases its
  target; an agonist increases it).

Drugs are identified with **NCIT**, diseases with **MONDO**, and gene targets with **HGNC**. Labels
name these things in plain language ("rheumatoid arthritis", "a tumor necrosis factor (TNF)
blocker"); a deterministic grounding step turns each name into the correct identifier — curators
never write an identifier from memory.

Every edge carries its **evidence**: the verbatim quote from the label that supports it, an
explanation of why it supports the edge, and — where available — one or more supporting
publications from the literature.

## Biolink captured

Output is written as KGX **JSON Lines** (nodes and edges), produced by the release pipeline.

### Edges

* **Indications** use the Biolink *treats* family, chosen to match the label's intent:
  `biolink:ameliorates_condition` for treatment of an existing disease,
  `biolink:preventative_for_condition` for prophylaxis/risk-reduction, or `biolink:treats` as the
  general case.
* **Targets** use `biolink:affects` with qualifiers — `qualified_predicate: biolink:causes`, an
  object aspect (activity/abundance), and a direction — so a TNF inhibitor reads as
  *"adalimumab causes decreased activity of TNF."*

Each edge records `knowledge_level: knowledge_assertion` (an FDA approval is an asserted fact) and
`agent_type: text_mining_agent` (the edge was extracted from label prose by an AI agent; it becomes
`manual_validation_of_automated_agent` once a human curator verifies it). Provenance is modeled as
Biolink `RetrievalSource` blocks in the Translator / Drug Approvals KP style: **FDA** as the
`primary_knowledge_source` (with the DailyMed label URL) and this ingest as the
`aggregator_knowledge_source`. Supporting literature is attached as `publications`.

### Nodes

A node is emitted for every drug, disease, and gene. Node names, Biolink categories, and
**equivalent identifiers** (e.g. an HGNC gene's NCBIGene / Ensembl / UniProt cross-references) are
fetched at build time from canonical sources — the [SRI Node Normalizer](https://nodenormalization-sri.renci.org/)
for diseases and genes, and the NCI Thesaurus for drugs — rather than taken from the curated text,
so node details stay authoritative and current.

## Evidence is verified, not trusted

The defining feature of this resource is that **every supporting quote is machine-checked against
its source** before the edge is accepted:

* **FDA label quotes** are verified to be exact substrings of the actual DailyMed Structured Product
  Label (fetched by its setid).
* **Publication quotes** are verified to be exact substrings of the cited PubMed/PMC article.

A paraphrased, reordered, or stitched-together quote fails this check and cannot ship. Identifiers
are likewise verified — diseases and drugs against their ontologies, gene identifiers against the
Monarch API — so an edge is only released when its identifiers resolve and its evidence is real.

## Design decisions

* **Curated from the primary source, not inherited from an aggregator.** Each edge is read directly
  from the approved FDA label rather than imported from a secondary dataset, so the indication
  wording, the molecular target, and the supporting quote are tied to the specific label that
  states them. A curated, per-biologic knowledge base keeps every edge reviewable in isolation and
  carrying its own evidence.
* **Targets with direction of effect.** Biologics have crisp molecular targets, and this resource
  records each one together with the **direction** of the effect (inhibits / activates) and an
  HGNC gene id — detail that target lists elsewhere often omit.
* **Predicate precision.** Rather than one blanket `treats` predicate, each indication is mapped to
  the most specific member of the Biolink treats family that the label supports.
* **Genes stand in for their products.** A biologic physically binds a *protein*; we record the
  **HGNC gene** as the conventional stand-in (the standard gene-or-gene-product convention), with
  the protein and other identifiers preserved as node cross-references.
* **FDA is the primary evidence; literature is corroboration.** For an *approved* indication the
  label itself is the authoritative source, so it is always the first evidence item; pivotal-trial
  and mechanism publications are layered on as additional, independently verified support.
* **Versioned for reproducibility.** FDA labels version independently per product, so each record
  pins its own SPL label; the ontology and service versions used for grounding and node enrichment
  are recorded in a build receipt (`release-metadata.yaml`) validated against the shared
  [kozahub-metadata-schema](https://github.com/monarch-initiative/kozahub-metadata-schema).

## Known limitations

* **Coverage is a curated subset**, not the entire Purple Book — it grows as biologics are curated,
  prioritizing widely-used products with clear indications and targets.
* **Some diseases ground to a parent concept.** Where MONDO has no exact term for a label's wording
  (e.g. "plaque psoriasis"), the edge is grounded to the nearest parent (psoriasis) and flagged for
  human review rather than dropped or forced.
* **Multi-subunit targets are approximate.** A biologic against a heterodimer (e.g. the α4β7
  integrin) is recorded against its most representative subunit gene and flagged for review.
* **Direction is the molecular effect on the target**, not the downstream clinical effect (a
  sclerostin inhibitor is "decreased sclerostin activity", even though the therapeutic result is
  increased bone formation).

## What is produced

The release pipeline emits KGX `nodes` and `edges` JSON Lines plus a schema-validated
`release-metadata.yaml`. These are published as **release artifacts**; the knowledge-graph output
is generated from the curated YAML on each release and is not itself checked into the repository.

## Citation & license

Primary source: FDA Structured Product Labels via [DailyMed](https://dailymed.nlm.nih.gov/).
Disease, drug, and gene identifiers from MONDO, NCI Thesaurus, and HGNC respectively.
License: BSD-3-Clause.
