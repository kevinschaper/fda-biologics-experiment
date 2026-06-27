# FDA Biologics ingest — curation QC + tooling
# Layers: structural (linkml-validate) -> ontology terms (linkml-term-validator)
#         -> reference excerpts (linkml-reference-validator)

pkg_dir     := "src/fda_biologics"
schema      := pkg_dir + "/schema/fda_biologics.yaml"
skill       := ".claude/skills/fda-biologic-extraction/scripts"
oak_config  := skill + "/oak_config.yaml"
ref_config  := skill + "/reference_validator_config.yaml"
data_dir    := "kb/biologics"
target      := "BiologicRecord"

# List recipes
default:
    @just --list

# ---- Validation (single file) -------------------------------------------------

# Structural validation against the LinkML schema
validate FILE:
    linkml-validate -s {{schema}} -C {{target}} "{{FILE}}"

# Ontology-term validation (ids resolve + labels match) via oak_config
terms FILE:
    linkml-term-validator validate-data "{{FILE}}" -s {{schema}} -t {{target}} -c {{oak_config}}

# HGNC gene validation via Monarch API (linkml-term-validator can't validate uppercase HGNC)
genes FILE:
    python {{skill}}/validate_genes.py "{{FILE}}"

# Reference-excerpt validation (PMID snippets are real quotes); FDA: refs are skipped
refs FILE:
    linkml-reference-validator validate data "{{FILE}}" -s {{schema}} -t {{target}} --config {{ref_config}}

# All layers on one file
qc FILE: (validate FILE) (terms FILE) (genes FILE) (refs FILE)

# ---- Validation (whole corpus) ------------------------------------------------

[no-cd]
_each RECIPE:
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    files=({{data_dir}}/*.yaml)
    if [ ${#files[@]} -eq 0 ]; then echo "no curated files in {{data_dir}} yet"; exit 0; fi
    for f in "${files[@]}"; do echo "== {{RECIPE}} $f =="; just {{RECIPE}} "$f"; done

validate-all: (_each "validate")
terms-all:    (_each "terms")
genes-all:    (_each "genes")
refs-all:     (_each "refs")

# Full QC sweep over the corpus
qc-all: validate-all terms-all genes-all refs-all

# ---- Curation helpers ---------------------------------------------------------

# Ground a name to a CURIE (disease|drug|gene)
ground TYPE NAME:
    python {{skill}}/ground.py --type {{TYPE}} "{{NAME}}"

# Live Biolink predicate definition / family / membership check
predicate *ARGS:
    python {{skill}}/predicate_info.py {{ARGS}}

# ---- Schema artifacts ---------------------------------------------------------

# Koza transform: curated per-drug YAML -> KGX nodes/edges in output/
# koza only expands globs in config-free mode (which drops our edge columns), so we expand
# the glob into a generated root-level config that keeps the writer's node/edge_properties.
transform:
    python {{pkg_dir}}/_gen_koza_config.py
    koza transform .koza.generated.yaml -o output -f jsonl
    @echo "KGX (jsonl) written under output/"

# Fetch canonical node details (name/category/xref) from NodeNorm + OAK -> data/node_details.json
nodes:
    python scripts/fetch_node_details.py

# Write output/release-metadata.yaml — build receipt with source/ontology versions
metadata:
    python scripts/write_metadata.py

# Full build: enrich nodes from canonical sources -> transform -> write release metadata
release: nodes transform metadata

# Rebuild the committed caches deterministically from canonical sources.
# Term/enum caches (cache/) and the node-detail cache (data/node_details.json) are committed so
# CI runs offline without the OAK sqlite DBs; rebuild + review the diff when ontologies are bumped.
cache-rebuild:
    rm -rf cache
    just terms-all
    just nodes

gen-pydantic:
    gen-pydantic {{schema}} > src/fda_biologics/datamodel.py

gen-docs:
    gen-doc -d docs/schema {{schema}}
