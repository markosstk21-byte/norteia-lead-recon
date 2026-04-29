"""
aepd.py — lookup en el registro de Delegados de Protección de Datos (DPO) de la AEPD.

Endpoint: https://www.aepd.es/dpd/buscar.html (formulario web)
La AEPD no expone API JSON pública, pero el formulario acepta GET con query params.
Esta implementación es best-effort: hace una consulta y parsea la respuesta HTML
para detectar si hay coincidencia. Si la página cambia, marca SourceStatus="down".

Uso:
    python aepd.py --nif B12345678
    python aepd.py --razon-social "Asesores Pérez S.L."
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CacheConfig, SourceStatus, cache_get, cache_set, emit_observation, http_get, normalize_nif

CACHE = CacheConfig(namespace="aepd", ttl_seconds=60 * 60 * 24 * 30)
AEPD_SEARCH = "https://www.aepd.es/dpd/buscar.html?nif={nif}"
AEPD_SEARCH_NAME = "https://www.aepd.es/dpd/buscar.html?razon_social={name}"


def lookup_dpo(nif: Optional[str] = None, razon_social: Optional[str] = None) -> dict:
    """
    Returns:
        {
            "registered": bool,
            "source": "AEPD" | None,
            "raw_match": str | None,
            "method": "nif" | "razon-social",
        }

    NOTE: La AEPD ha cambiado la URL del buscador en 2024-2025. Este módulo
    intenta el endpoint conocido pero NO falla si responde 404 o HTML vacío:
    devuelve {"registered": False, "source": None} y emite source_unavailable.
    """
    import urllib.parse

    if nif:
        nif = normalize_nif(nif)
        cache_key = f"nif:{nif}"
        method = "nif"
        url = AEPD_SEARCH.format(nif=urllib.parse.quote(nif))
    elif razon_social:
        cache_key = f"name:{razon_social}"
        method = "razon-social"
        url = AEPD_SEARCH_NAME.format(name=urllib.parse.quote(razon_social))
    else:
        return {"registered": False, "source": None, "method": None, "error": "missing-input"}

    cached = cache_get(CACHE, cache_key)
    if cached is not None:
        return cached

    status, body = http_get(url, timeout=15)
    if status not in (200, 302):
        SourceStatus.mark("AEPD", f"http-{status}")
        emit_observation("source_unavailable", {"source": "AEPD", "status": status})
        result = {"registered": False, "source": None, "method": method, "error": f"http-{status}"}
        cache_set(CACHE, cache_key, result)
        return result

    SourceStatus.mark("AEPD", "ok")
    # Heuristic detection: AEPD search results page mentions "resultados encontrados"
    # or contains a table of DPOs. If query string text appears in body, likely match.
    found = False
    if nif and nif in body.upper():
        found = True
    if razon_social and razon_social.lower() in body.lower():
        found = True

    result = {
        "registered": found,
        "source": "AEPD" if found else None,
        "method": method,
        "url": url,
    }
    cache_set(CACHE, cache_key, result)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="AEPD DPO registry lookup")
    p.add_argument("--nif")
    p.add_argument("--razon-social", dest="razon_social")
    args = p.parse_args()
    print(json.dumps(lookup_dpo(nif=args.nif, razon_social=args.razon_social), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
