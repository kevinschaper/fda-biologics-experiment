# fda-biologics-ingest

A curated knowledge base + Koza ingest of **FDA biologic** edges for the Monarch graph:

- **drug → disease** — approved indications (`biolink:treats` family: `ameliorates_condition` / `preventative_for_condition`)
- **drug → gene** — molecular targets (`biolink:affects` + qualifiers, e.g. *causes decreased activity of TNF*)

Following the [dismech](https://github.com/monarch-initiative/dismech) pattern, the source of
truth is hand-curated YAML (one file per biologic) rather than a download. Names are grounded to
**NCIT** (drug), **MONDO** (disease), and **HGNC** (gene); every claim carries verbatim evidence
that is deterministically verified.

## Layout

```
kb/biologics/<drug>.yaml              # source of truth — one record per biologic
src/fda_biologics/schema/             # LinkML schema (the record contract)
src/fda_biologics/transform.py        # Koza transform: records -> KGX nodes/edges
scripts/                              # node enrichment + release-metadata
.claude/skills/                       # extraction + PMID-enrichment skills (curation tooling)
cache/, references_cache/             # committed derived caches -> offline, reproducible QC
output/                              # KGX jsonl + release-metadata.yaml (generated)
```

## Usage

```bash
just install            # uv sync deps
just qc kb/biologics/adalimumab.yaml   # all 5 layers on one record
just qc-all             # full sweep (structural, terms, genes, fda, refs)
just test               # offline QC gate (structural + terms + fda; what CI runs)
just release            # enrich nodes -> transform -> write release-metadata
```

## QC layers
| Layer | Checks | Source |
|---|---|---|
| `validate` | schema-structural | linkml-validate |
| `terms` | MONDO/NCIT ids resolve + labels match | linkml-term-validator (cached) |
| `genes` | HGNC ids are real `biolink:Gene` | Monarch API |
| `fda` | FDA snippets are exact label quotes | DailyMed SPL (cached) |
| `refs` | PMID snippets are exact quotes | linkml-reference-validator |

Curation is done with the two bundled skills under `.claude/skills/`.
