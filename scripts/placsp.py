"""
placsp.py — Plataforma de Contratación del Sector Público.

Endpoints relevantes:
    https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom
    Diversos feeds Atom anuales con licitaciones publicadas.

Cobertura: empresas adjudicatarias de contratos públicos. Es señal de
ACTIVIDAD, no exhaustivo (hay pymes que nunca facturan a sector público).

Uso:
    python placsp.py --cnae 6920 --province Sevilla --years 1
    python placsp.py --nif B12345678
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CacheConfig, SourceStatus, cache_get, cache_set, emit_observation, http_get, normalize_nif

CACHE = CacheConfig(namespace="placsp", ttl_seconds=60 * 60 * 24 * 7)

# PLACSP publishes annual Atom feeds. Operator should verify exact URL pattern
# (changes occasionally). This template targets the perfilesContratanteCompleto stream.
PLACSP_FEED_TEMPLATE = (
    "https://contrataciondelestado.es/sindicacion/sindicacion_643/"
    "licitacionesPerfilesContratanteCompleto3_{year}.atom"
)


def fetch_feed(year: int) -> Optional[str]:
    cache_key = f"feed:{year}"
    cached = cache_get(CACHE, cache_key)
    if cached is not None:
        return cached
    url = PLACSP_FEED_TEMPLATE.format(year=year)
    status, body = http_get(url, timeout=30)
    if status != 200 or "<feed" not in body[:500]:
        SourceStatus.mark("PLACSP", f"http-{status}")
        emit_observation("source_unavailable", {"source": "PLACSP", "year": year, "status": status})
        return None
    cache_set(CACHE, cache_key, body)
    return body


def parse_feed_entries(xml_text: str) -> list[dict]:
    """Parses Atom feed entries — extracts adjudicatario per entry when available."""
    out: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", "", ns) or "").strip()
        summary = (entry.findtext("atom:summary", "", ns) or "").strip()
        link_el = entry.find("atom:link", ns)
        link = link_el.get("href") if link_el is not None else None
        # Heuristic: extract adjudicatario name and NIF from summary text
        adj_match = re.search(r"Adjudicatario[:\s]+([^\n]+)", summary, re.IGNORECASE)
        nif_match = re.search(r"\b([A-HJNPQRSUVW]\d{7}[0-9A-J]|\d{8}[A-Z])\b", summary)
        out.append({
            "title": title,
            "adjudicatario": adj_match.group(1).strip() if adj_match else None,
            "nif": nif_match.group(1).upper() if nif_match else None,
            "link": link,
            "summary_excerpt": summary[:300],
        })
    return out


def discover(cnae: list[str], province: Optional[str], years: int = 1) -> list[dict]:
    """
    Returns adjudicatarios filtered by best-effort CNAE/province match in entry text.
    Note: PLACSP feeds don't expose CNAE as a structured field — filtering is textual.
    """
    SourceStatus.mark("PLACSP", "ok")
    current_year = datetime.utcnow().year
    candidates: list[dict] = []
    cnae_keywords = []
    # Map CNAE codes to keywords likely to appear in contract titles
    keyword_map = {
        "6920": ["asesoría", "consultoría tributaria", "auditoría"],
        "7022": ["consultoría", "consultoria"],
        "6201": ["software", "desarrollo aplicación"],
        "6202": ["consultoría informática"],
        "8559": ["formación", "curso"],
    }
    for c in cnae or []:
        cnae_keywords.extend(keyword_map.get(c, []))

    for offset in range(years):
        year = current_year - offset
        body = fetch_feed(year)
        if not body:
            continue
        for entry in parse_feed_entries(body):
            text_blob = f"{entry['title']} {entry.get('summary_excerpt', '')}".lower()
            if cnae_keywords and not any(k.lower() in text_blob for k in cnae_keywords):
                continue
            if province and province.lower() not in text_blob:
                continue
            candidates.append(entry)

    emit_observation("tool_lead_recon", {"phase": "placsp.discover", "count": len(candidates)})
    return candidates


def by_nif(nif: str, years: int = 5) -> list[dict]:
    """Returns contracts where the adjudicatario NIF matches."""
    nif = normalize_nif(nif)
    current_year = datetime.utcnow().year
    matched: list[dict] = []
    for offset in range(years):
        body = fetch_feed(current_year - offset)
        if not body:
            continue
        for entry in parse_feed_entries(body):
            if (entry.get("nif") or "").upper() == nif:
                matched.append(entry)
    return matched


def main() -> None:
    p = argparse.ArgumentParser(description="PLACSP adapter")
    p.add_argument("--discover", action="store_true")
    p.add_argument("--nif")
    p.add_argument("--cnae", nargs="*", default=[])
    p.add_argument("--province")
    p.add_argument("--years", type=int, default=1)
    args = p.parse_args()
    if args.nif:
        out = by_nif(args.nif, args.years)
    else:
        out = discover(args.cnae, args.province, args.years)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
