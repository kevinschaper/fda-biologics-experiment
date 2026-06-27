"""Koza transform: curated BiologicRecord (per-drug YAML) -> KGX nodes + edges.

Indications  -> ChemicalOrDrugOrTreatmentToDiseaseOrPhenotypicFeatureAssociation (treats family)
Targets      -> ChemicalAffectsGeneAssociation (affects + qualifiers)

Provenance (knowledge_level / agent_type / RetrievalSource blocks) is record-level and applied
to every edge. Only PMID references become `publications`; FDA-label refs stay as sources.
"""
import json
import uuid
from pathlib import Path

import koza
from biolink_model.datamodel import pydanticmodel_v2 as bl

INGEST = "infores:monarch-fda-biologics"

# Canonical node details (name/category/xref) fetched from NodeNorm + OAK by `just nodes`.
# Falls back to the curated matched_label when the cache is absent (so the transform still runs).
_DETAILS_PATH = Path("data/node_details.json")
NODE_DETAILS = json.loads(_DETAILS_PATH.read_text()) if _DETAILS_PATH.exists() else {}
NODE_CLASS = {"biolink:Drug": bl.Drug, "biolink:Disease": bl.Disease, "biolink:Gene": bl.Gene}


def _node(curie, fallback_name, fallback_category, **extra):
    d = NODE_DETAILS.get(curie) or {}
    category = d.get("category") or fallback_category
    cls = NODE_CLASS.get(category, bl.NamedThing)
    return cls(id=curie, name=d.get("name") or fallback_name, category=[category],
               xref=d.get("xref") or [], provided_by=[INGEST], **extra)


def _retrieval_sources(prov):
    out = []
    for s in prov.get("sources") or []:
        out.append(bl.RetrievalSource(
            id=f"uuid:{uuid.uuid4()}",
            resource_id=s["resource_id"],
            resource_role=s["resource_role"],
            upstream_resource_ids=s.get("upstream_resource_ids") or [],
            source_record_urls=s.get("source_record_urls") or [],
        ))
    return out


def _role(prov, role):
    return [s["resource_id"] for s in (prov.get("sources") or []) if s["resource_role"] == role]


def _pmids(evidence):
    return [e["reference"] for e in (evidence or []) if str(e.get("reference", "")).startswith("PMID:")]


@koza.transform_record()
def transform_record(koza_tx, record):
    bio = record["biologic"]
    drug_id = bio["id"]

    # needs_review = grounding not human-verified -> do not emit to KGX. A flagged subject taints
    # every edge in the record, so skip the whole record; a flagged (or id-less) claim is skipped
    # individually. Such edges stay parked in the KB until a curator clears the flag.
    if bio.get("needs_review"):
        return

    prov = record.get("provenance") or {}
    common = dict(
        knowledge_level=prov.get("knowledge_level", "knowledge_assertion"),
        agent_type=prov.get("agent_type", "text_mining_agent"),
        primary_knowledge_source=(_role(prov, "primary_knowledge_source") or ["infores:fda"])[0],
        aggregator_knowledge_source=_role(prov, "aggregator_knowledge_source") or [INGEST],
        sources=_retrieval_sources(prov),
    )

    edges = []
    used = {}  # endpoint id -> (category, fallback_name) — only nodes on emitted edges are written

    for ind in record.get("indications") or []:
        obj = ind["object"]
        if ind.get("needs_review") or not obj.get("id"):
            continue
        used[obj["id"]] = ("biolink:Disease", obj.get("matched_label") or obj.get("name"))
        edges.append(bl.ChemicalOrDrugOrTreatmentToDiseaseOrPhenotypicFeatureAssociation(
            id=f"uuid:{uuid.uuid4()}",
            subject=drug_id, predicate=ind["predicate"], object=obj["id"],
            publications=_pmids(ind.get("evidence")), **common))

    for tgt in record.get("targets") or []:
        obj = tgt["object"]
        if tgt.get("needs_review") or not obj.get("id"):
            continue
        used[obj["id"]] = ("biolink:Gene", obj.get("matched_label") or obj.get("name"))
        edges.append(bl.ChemicalAffectsGeneAssociation(
            id=f"uuid:{uuid.uuid4()}",
            subject=drug_id, predicate=tgt["predicate"], object=obj["id"],
            qualified_predicate=tgt.get("qualified_predicate"),
            object_aspect_qualifier=tgt.get("object_aspect_qualifier"),
            object_direction_qualifier=tgt.get("object_direction_qualifier"),
            publications=_pmids(tgt.get("evidence")), **common))

    if not edges:
        return  # no confident edges -> don't emit an orphan drug node

    nodes = [_node(drug_id, bio.get("name"), "biolink:Drug", synonym=bio.get("synonyms") or [])]
    nodes += [_node(oid, fname, cat) for oid, (cat, fname) in used.items()]
    koza_tx.write(*nodes)
    koza_tx.write(*edges)
