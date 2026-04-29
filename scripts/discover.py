"""
discover.py — orquestador del modo --discover.

Recibe geo + sector, lanza fuentes en paralelo, dedup + fuzzy match,
resuelve dominio, geocodifica, escribe JSON + HTML twin, emite observation.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    SourceStatus, emit_observation, levenshtein, load_cnae_mapping, normalize_razon_social,
    now_iso, province_code, resolve_sector, today_dir, update_operator_state_section,
    write_html_twin, write_snapshot,
)

import borme
import dirce
import domain_resolver
import infosubvenciones
import osm
import placsp
import cartociudad


def _provincial_bbox_for(province: str) -> tuple[float, float, float, float] | None:
    return osm.PROVINCE_BBOX.get(province)


def discover(geo: str, sector: str, max_results: int = 50) -> dict:
    """Main discovery pipeline. Returns the full payload (JSON-serializable)."""
    sector_resolution = resolve_sector(sector)
    cnae_codes = sector_resolution["cnae"]
    label = sector_resolution["label"] or sector
    province = geo

    payload: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "skill": "norteia-lead-recon",
        "mode": "discover",
        "timestamp": now_iso(),
        "query": {
            "geo": {"raw": geo, "province": province, "provinceCode": province_code(province)},
            "sector": {"input": sector, "cnae": cnae_codes, "matchedVia": sector_resolution["matched_via"], "label": label},
        },
        "segmentSize": dirce.segment_size(cnae_codes[0] if cnae_codes else "", province) if cnae_codes else None,
        "candidates": [],
        "totalCandidates": 0,
        "totalUnresolvedDomain": 0,
        "sourcesAvailability": {},
        "writes": {},
    }

    # --- Phase 1: parallel discovery ---
    raw_candidates: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(borme.discover_by_cnae_province, cnae_codes, province, 1): "BORME",
            pool.submit(placsp.discover, cnae_codes, province, 1): "PLACSP",
        }
        # OSM if we have a known bbox + tag
        cnae_mapping = load_cnae_mapping()
        tag = cnae_mapping.get("verticalToOverpassTag", {}).get(label)
        if tag and _provincial_bbox_for(province):
            futures[pool.submit(osm.discover, tag, province, None)] = "OSM"

        for fut in as_completed(futures):
            src = futures[fut]
            try:
                items = fut.result() or []
            except Exception as e:  # noqa: BLE001
                emit_observation("source_unavailable", {"source": src, "error": str(e)})
                items = []
            for it in items:
                it["_source"] = src
                raw_candidates.append(it)

    # --- Phase 2: dedup + fuzzy ---
    deduped: list[dict] = []
    seen_keys: list[str] = []
    for c in raw_candidates:
        rs = c.get("razonSocial") or c.get("adjudicatario") or ""
        if not rs:
            continue
        key = normalize_razon_social(rs)
        is_dup = False
        for sk in seen_keys:
            if levenshtein(key, sk) <= 3:
                is_dup = True
                break
        if not is_dup:
            seen_keys.append(key)
            deduped.append(c)

    deduped = deduped[:max_results]

    # --- Phase 3: per-candidate enrichment ---
    enriched: list[dict] = []
    unresolved_domain = 0
    for cand in deduped:
        rs = cand.get("razonSocial") or cand.get("adjudicatario") or ""
        addr = cand.get("address") or cand.get("registralAddress")

        domain_info = domain_resolver.resolve(rs, city=province)
        if not domain_info.get("resolved"):
            unresolved_domain += 1

        geo_info = cartociudad.geocode(addr) if addr else None

        enriched.append({
            "razonSocial": rs,
            "nif": cand.get("nif"),
            "cnae": cnae_codes[0] if cnae_codes else None,
            "registralAddress": addr,
            "geocoded": geo_info,
            "domain": domain_info,
            "lastBormeEvent": cand.get("lastBormeEvent"),
            "signals": {
                "publicContractsCount": 1 if cand.get("_source") == "PLACSP" else 0,
                "subsidiesReceived": None,
                "dpoRegistered": None,
            },
            "sourcesHit": [cand.get("_source")],
            "recommendedNextSkill": "lead-research-brief",
        })

    payload["candidates"] = enriched
    payload["totalCandidates"] = len(enriched)
    payload["totalUnresolvedDomain"] = unresolved_domain
    payload["sourcesAvailability"] = SourceStatus.snapshot()

    # --- Phase 4: persist ---
    snapshot_path = write_snapshot("discover", payload)
    html_path = _render_html_twin(payload)
    payload["writes"] = {
        "snapshot": str(snapshot_path),
        "htmlTwin": str(html_path) if html_path else None,
        "operatorState": "merged" if update_operator_state_section("leadReconStats", {
            "lastRun": now_iso(),
            "lastMode": "discover",
            "lastQuery": payload["query"],
            "lastTotal": payload["totalCandidates"],
        }) else "skipped",
    }
    emit_observation("tool_lead_recon", {
        "phase": "discover.complete",
        "candidates": len(enriched),
        "unresolved_domains": unresolved_domain,
    })

    return payload


def _render_html_twin(payload: dict) -> Path | None:
    """Renders the discover HTML twin using the Leaflet template. Best-effort."""
    template_path = Path(__file__).resolve().parent.parent / "templates" / "discover.html.jinja"
    if not template_path.exists():
        return None
    template = template_path.read_text(encoding="utf-8")
    # Naive {{json}} substitution to avoid pulling Jinja2 as a dep
    rendered = template.replace("{{PAYLOAD_JSON}}", json.dumps(payload, ensure_ascii=False))
    rendered = rendered.replace("{{TITLE}}", f"Discover: {payload['query']['sector']['input']} en {payload['query']['geo']['raw']}")
    return write_html_twin("discover", rendered)


def main() -> None:
    p = argparse.ArgumentParser(description="norteia-lead-recon — discover orchestrator")
    p.add_argument("--geo", required=True, help="Provincia, municipio o CCAA")
    p.add_argument("--sector", required=True, help="CNAE o nombre de sector")
    p.add_argument("--max", type=int, default=50)
    args = p.parse_args()
    payload = discover(args.geo, args.sector, args.max)
    print(json.dumps({
        "totalCandidates": payload["totalCandidates"],
        "totalUnresolvedDomain": payload["totalUnresolvedDomain"],
        "sourcesAvailability": payload["sourcesAvailability"],
        "writes": payload["writes"],
        "topPreview": payload["candidates"][:5],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
