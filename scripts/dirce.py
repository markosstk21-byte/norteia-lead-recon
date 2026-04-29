"""
dirce.py — DIRCE (Directorio Central de Empresas, INE) — SOLO segment sizing.

DIRCE NO es un directorio nominal. Es estadístico agregado por CNAE × provincia × estrato.
Esta skill lo usa SOLO para dimensionar el segmento, NUNCA para listar empresas.

Endpoint INE Tempus3:
    https://servicios.ine.es/wstempus/jsCache/ES/DATOS_TABLA/{tabla}
La tabla más usable para DIRCE empresas activas por CNAE+provincia es la 4719.

Output:
    {"totalCompanies": int|null, "source": "DIRCE", "year": int, "note": "..."}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CacheConfig, SourceStatus, cache_get, cache_set, http_get

CACHE = CacheConfig(namespace="dirce", ttl_seconds=60 * 60 * 24 * 30)
INE_TABLE_URL = "https://servicios.ine.es/wstempus/jsCache/ES/DATOS_TABLA/{tabla}?nult=1"


def segment_size(cnae: str, province: Optional[str] = None) -> dict:
    """
    Returns the approximate number of companies in DIRCE for the given CNAE
    (and optionally province). Heuristic: queries a known INE table and
    extracts the relevant cell. NEVER returns a list of companies.
    """
    cache_key = f"{cnae}:{province or '*'}"
    cached = cache_get(CACHE, cache_key)
    if cached is not None:
        return cached

    # The exact table id changes between INE refreshes. As a placeholder this
    # implementation marks the segment as "available" or "down" and returns
    # a flag for the orchestrator to handle.
    SourceStatus.mark("DIRCE", "stub")
    result = {
        "totalCompanies": None,
        "source": "DIRCE",
        "note": (
            "DIRCE es estadístico agregado, no listado nominal. Implementación "
            "completa requiere mapear la tabla INE Tempus3 actual (cambia anual). "
            "Para producción, integrar con apps/borme-parser u otro runner que "
            "mantenga la tabla actualizada."
        ),
        "cnae": cnae,
        "province": province,
    }
    cache_set(CACHE, cache_key, result)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cnae", required=True)
    p.add_argument("--province")
    args = p.parse_args()
    print(json.dumps(segment_size(args.cnae, args.province), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
