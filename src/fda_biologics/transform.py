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
    prov = record.get("provenance") or {}

    common = dict(
        knowledge_level=prov.get("knowledge_level", "knowledge_assertion"),
        agent_type=prov.get("agent_type", "text_mining_agent"),
        primary_knowledge_source=(_role(prov, "primary_knowledge_source") or ["infores:fda"])[0],
        aggregator_knowledge_source=_role(prov, "aggregator_knowledge_source") or [INGEST],
        sources=_retrieval_sources(prov),
    )

    nodes = {drug_id: _node(drug_id, bio.get("name"), "biolink:Drug",
                            synonym=bio.get("synonyms") or [])}
    edges = []

    for ind in record.get("indications") or []:
        obj = ind["object"]
        nodes.setdefault(obj["id"], _node(
            obj["id"], obj.get("matched_label") or obj.get("name"), "biolink:Disease"))
        edges.append(bl.ChemicalOrDrugOrTreatmentToDiseaseOrPhenotypicFeatureAssociation(
            id=f"uuid:{uuid.uuid4()}",
            subject=drug_id, predicate=ind["predicate"], object=obj["id"],
            publications=_pmids(ind.get("evidence")), **common))

    for tgt in record.get("targets") or []:
        obj = tgt["object"]
        nodes.setdefault(obj["id"], _node(
            obj["id"], obj.get("matched_label") or obj.get("name"), "biolink:Gene"))
        edges.append(bl.ChemicalAffectsGeneAssociation(
            id=f"uuid:{uuid.uuid4()}",
            subject=drug_id, predicate=tgt["predicate"], object=obj["id"],
            qualified_predicate=tgt.get("qualified_predicate"),
            object_aspect_qualifier=tgt.get("object_aspect_qualifier"),
            object_direction_qualifier=tgt.get("object_direction_qualifier"),
            publications=_pmids(tgt.get("evidence")), **common))

    koza_tx.write(*nodes.values())
    koza_tx.write(*edges)
