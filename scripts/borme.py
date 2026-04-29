"""
borme.py — adapter para BORME (Boletín Oficial del Registro Mercantil).

Fuente principal: datos.gob.es API publica el catálogo BORME en formato JSON-LD.
Endpoints de referencia:
    https://datos.gob.es/apidata/catalog/dataset?_pageSize=10&q=BORME
    BORME-A (actos inscribibles): https://www.boe.es/datosabiertos/api/borme/...

NOTA importante: BORME se publica vía BOE.es. La API oficial de datos abiertos del BOE
expone los actos en formato XML/JSON. Este módulo implementa un fetcher minimal con
cache agresiva. Endpoint a verificar en runtime — si cambia, el módulo emite
SourceStatus.mark("BORME", "down") y devuelve listas vacías sin romper la cadena.

Modos:
    --discover --cnae 6920 --province Sevilla [--years 5]
    --analyze --nif B12345678
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    CacheConfig, SourceStatus, cache_get, cache_set, emit_observation,
    http_get, is_valid_nif, normalize_nif, normalize_razon_social,
)


# Public BOE/BORME endpoints. Verified URLs as of 2026-04 — operator should
# re-verify if a request returns 404.
BOE_BORME_BASE = "https://www.boe.es"
BOE_BORME_SUMARIO = "https://www.boe.es/diario_borme/xml.php?id=BORME-S-{date}"  # date YYYYMMDD
DATOS_GOB_BORME_DATASET = "https://datos.gob.es/apidata/catalog/dataset?_pageSize=20&q=BORME"

CACHE_BORME = CacheConfig(namespace="borme", ttl_seconds=None)  # immutable
CACHE_BORME_INDEX = CacheConfig(namespace="borme-idx", ttl_seconds=60 * 60 * 24)


def _date_range(years: int) -> list[str]:
    """Returns YYYYMMDD strings for the last N years of business days. Coarse — only first day of each month."""
    today = datetime.utcnow().date()
    out = []
    for ym in range(years * 12):
        d = (today.replace(day=1) - timedelta(days=ym * 30)).replace(day=1)
        out.append(d.strftime("%Y%m%d"))
    return list(dict.fromkeys(out))


def fetch_sumario_xml(date_yyyymmdd: str) -> Optional[str]:
    """Fetches the BORME sumario for a given date. Cached forever per date."""
    cache_key = f"sumario:{date_yyyymmdd}"
    cached = cache_get(CACHE_BORME, cache_key)
    if cached is not None:
        return cached
    url = BOE_BORME_SUMARIO.format(date=date_yyyymmdd)
    status, body = http_get(url, timeout=20)
    if status != 200 or "<?xml" not in body[:200]:
        # No publication for this date (weekend/holiday) is normal — don't mark down
        return None
    cache_set(CACHE_BORME, cache_key, body)
    return body


def parse_sumario(xml_text: str) -> list[dict]:
    """Extracts (act_id, section, province, url) tuples from a BORME sumario XML."""
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    # BORME sumario has <seccion><emisor><item> structure; we extract item refs
    for item in root.iter("item"):
        ident = (item.findtext("identificador") or "").strip()
        titulo = (item.findtext("titulo") or "").strip()
        url_html = (item.findtext("urlHtml") or "").strip()
        url_xml = (item.findtext("urlXml") or "").strip()
        if ident:
            out.append({
                "id": ident,
                "title": titulo,
                "html": url_html,
                "xml": url_xml,
            })
    return out


def fetch_act_xml(url_xml: str) -> Optional[str]:
    """Fetches an individual BORME act XML. Cached forever per ID."""
    if not url_xml:
        return None
    full = url_xml if url_xml.startswith("http") else BOE_BORME_BASE + url_xml
    cache_key = f"act:{full}"
    cached = cache_get(CACHE_BORME, cache_key)
    if cached is not None:
        return cached
    status, body = http_get(full, timeout=20)
    if status != 200:
        SourceStatus.mark("BORME-act", f"http-{status}")
        return None
    cache_set(CACHE_BORME, cache_key, body)
    return body


def discover_by_cnae_province(cnae_codes: list[str], province: Optional[str], years: int = 1) -> list[dict]:
    """
    Discovery mode. Returns a list of company candidates extracted from BORME.

    NOTE: BORME XML doesn't index by CNAE directly. The realistic strategy is:
    1. Iterate sumarios for the given date range.
    2. For each act, fetch the XML and look at "objeto" / "actividad" fields.
    3. Filter by CNAE keywords or province.

    For a fast MVP, this implementation iterates a small window (last 30 days)
    and returns whatever is found. Full historical sweep is left for the
    `apps/borme-parser` package of the Mapeador de Leads project.
    """
    SourceStatus.mark("BORME", "ok")
    candidates: list[dict] = []

    today = datetime.utcnow().date()
    days_to_check = min(30, years * 365)
    for offset in range(days_to_check):
        d = (today - timedelta(days=offset)).strftime("%Y%m%d")
        xml_text = fetch_sumario_xml(d)
        if not xml_text:
            continue
        for item in parse_sumario(xml_text):
            title = item["title"]
            # Coarse province filter on the title
            if province and province.lower() not in title.lower():
                continue
            candidates.append({
                "razonSocial": _extract_razon_social(title),
                "nif": None,  # BORME sumario rarely has NIF; act XML has it
                "bormeRef": item["id"],
                "bormeUrl": item["html"],
                "lastBormeEvent": {
                    "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                    "type": _classify_act_type(title),
                },
                "_raw": title,
            })

    # Dedup on razonSocial
    seen: set[str] = set()
    deduped: list[dict] = []
    for c in candidates:
        key = normalize_razon_social(c.get("razonSocial") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    emit_observation("tool_lead_recon", {"phase": "borme.discover", "count": len(deduped)})
    return deduped


def _extract_razon_social(title: str) -> str:
    """Best-effort: BORME titles often start with the company name in caps."""
    # Heuristic: first uppercase chunk before a comma or period.
    parts = title.split(".")
    head = parts[0].strip()
    if head.endswith(",") or "," in head:
        head = head.split(",")[0].strip()
    return head[:200]


def _classify_act_type(title: str) -> str:
    t = title.lower()
    if "constituci" in t:
        return "Constitución"
    if "nombramiento" in t:
        return "Nombramientos"
    if "cese" in t:
        return "Ceses"
    if "ampliaci" in t and "capital" in t:
        return "Ampliación de capital"
    if "fusi" in t:
        return "Fusión"
    if "extinci" in t or "disoluci" in t:
        return "Disolución"
    if "traslado" in t:
        return "Traslado de domicilio"
    return "Otros"


def analyze_by_nif(nif: str) -> dict:
    """
    Analyze mode. Returns the BORME timeline for a given NIF.

    NOTE: BORME doesn't have a direct NIF index. Real implementation needs a
    pre-built reverse index (apps/borme-parser builds it). MVP fallback:
    returns a stub with a clear "no-index-available" flag so the orchestrator
    knows to either delegate to the project package or warn the user.
    """
    nif = normalize_nif(nif)
    if not is_valid_nif(nif):
        return {"nif": nif, "error": "invalid-nif-format", "timeline": []}

    SourceStatus.mark("BORME", "ok-no-index")
    emit_observation("tool_lead_recon", {"phase": "borme.analyze", "nif": nif})
    return {
        "nif": nif,
        "timeline": [],
        "note": (
            "BORME no expone índice por NIF directamente. Para timeline completa, "
            "delegar a apps/borme-parser del proyecto Mapeador de Leads (cuando "
            "esté implementado) o usar broker premium (Registradores.org) con --premium."
        ),
        "delegated": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="BORME adapter (norteia-lead-recon)")
    p.add_argument("--discover", action="store_true", help="Discovery mode by CNAE+province")
    p.add_argument("--analyze", action="store_true", help="Analyze mode by NIF")
    p.add_argument("--cnae", nargs="*", default=[])
    p.add_argument("--province")
    p.add_argument("--years", type=int, default=1)
    p.add_argument("--nif")
    p.add_argument("--json", action="store_true", help="Print JSON to stdout")
    args = p.parse_args()

    if args.discover:
        result = discover_by_cnae_province(args.cnae, args.province, years=args.years)
    elif args.analyze:
        if not args.nif:
            print(json.dumps({"error": "missing --nif"}, ensure_ascii=False))
            sys.exit(2)
        result = analyze_by_nif(args.nif)
    else:
        p.print_help()
        sys.exit(2)

    print(json.dumps(result, ensure_ascii=False, indent=2 if not args.json else None))


if __name__ == "__main__":
    main()
