"""
infosubvenciones.py — Sistema Nacional de Publicidad de Subvenciones y Ayudas Públicas (SNPSAP).

Endpoint: https://www.infosubvenciones.es/bdnstrans/GE/es/concesiones
La web pública permite búsqueda por NIF beneficiario y por organismo.
NO expone API JSON estable, así que parseamos HTML best-effort.

Para producción, idealmente usar `apps/borme-parser` del Mapeador como
runner, ya que ese package puede tener un parser más robusto.

Uso:
    python infosubvenciones.py --nif B12345678
    python infosubvenciones.py --keyword "kit digital" --province Sevilla
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CacheConfig, SourceStatus, cache_get, cache_set, emit_observation, http_get, normalize_nif

CACHE = CacheConfig(namespace="snpsap", ttl_seconds=60 * 60 * 24 * 7)

SNPSAP_BASE = "https://www.infosubvenciones.es"
SNPSAP_SEARCH_NIF = SNPSAP_BASE + "/bdnstrans/GE/es/concesiones?numero={nif}"


def by_nif(nif: str) -> list[dict]:
    """
    Returns subvenciones recibidas por la empresa con NIF dado.
    Best-effort HTML parsing.
    """
    nif = normalize_nif(nif)
    cache_key = f"nif:{nif}"
    cached = cache_get(CACHE, cache_key)
    if cached is not None:
        return cached

    url = SNPSAP_SEARCH_NIF.format(nif=urllib.parse.quote(nif))
    status, body = http_get(url, timeout=20)
    if status != 200:
        SourceStatus.mark("Infosubvenciones", f"http-{status}")
        emit_observation("source_unavailable", {"source": "Infosubvenciones", "status": status})
        return []

    SourceStatus.mark("Infosubvenciones", "ok")
    # Heuristic table extraction — SNPSAP results live in a <table> with rows of awards.
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.DOTALL | re.IGNORECASE)
    awards: list[dict] = []
    for row in rows[:50]:
        # Strip tags, normalize whitespace
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL | re.IGNORECASE)
        cells_clean = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if not cells_clean or all(not c for c in cells_clean):
            continue
        # Detect rows that mention an amount (€) — those are likely award rows
        if any("€" in c or re.search(r"\d+,\d{2}", c) for c in cells_clean):
            awards.append({"raw": cells_clean})

    cache_set(CACHE, cache_key, awards)
    return awards


def main() -> None:
    p = argparse.ArgumentParser(description="Infosubvenciones (SNPSAP) lookup")
    p.add_argument("--nif")
    args = p.parse_args()
    if not args.nif:
        print(json.dumps({"error": "missing --nif"}))
        sys.exit(2)
    print(json.dumps(by_nif(args.nif), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
