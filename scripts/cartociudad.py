"""
cartociudad.py — geocoder español oficial (IGN — Instituto Geográfico Nacional).

Endpoint público: https://www.cartociudad.es/geocoder/api/geocoder/findJsonp?q=...
Devuelve callback JSONP. Para parseo limpio sustituimos `&callback=...` por nada
y parseamos la respuesta como JSON.

Cache: 90 días por dirección normalizada.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CacheConfig, SourceStatus, cache_get, cache_set, http_get, normalize_razon_social

CARTOCIUDAD_FIND = "https://www.cartociudad.es/geocoder/api/geocoder/findJsonp?q={q}"
CARTOCIUDAD_FIND_PLAIN = "https://www.cartociudad.es/geocoder/api/geocoder/find?q={q}"

CACHE = CacheConfig(namespace="cartociudad", ttl_seconds=60 * 60 * 24 * 90)


def geocode(address: str) -> Optional[dict]:
    """Returns {"lat": float, "lon": float, "formatted": str, "type": "address|portal|..."} or None."""
    if not address:
        return None
    key = normalize_razon_social(address)
    cached = cache_get(CACHE, key)
    if cached is not None:
        return cached

    import urllib.parse
    q = urllib.parse.quote(address)
    # Try plain JSON first; fall back to JSONP if needed
    status, body = http_get(CARTOCIUDAD_FIND_PLAIN.format(q=q), timeout=15)
    payload: Optional[dict] = None
    if status == 200 and body.strip().startswith("{"):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = None
    if payload is None:
        status, body = http_get(CARTOCIUDAD_FIND.format(q=q), timeout=15)
        if status == 200:
            # Strip JSONP wrapper: "callback({...})"
            m = re.search(r"\{.*\}", body, flags=re.DOTALL)
            if m:
                try:
                    payload = json.loads(m.group(0))
                except json.JSONDecodeError:
                    payload = None
    if payload is None:
        SourceStatus.mark("Cartociudad", f"http-{status}")
        return None

    # Cartociudad response shape (v2): list under root or {"results": [...]}.
    candidates = payload if isinstance(payload, list) else payload.get("results") or []
    if not candidates:
        cache_set(CACHE, key, None)
        return None
    top = candidates[0]
    result = {
        "lat": top.get("lat"),
        "lon": top.get("lng") or top.get("lon"),
        "formatted": top.get("address"),
        "type": top.get("type"),
        "province": top.get("province"),
        "muni": top.get("muni"),
        "source": "Cartociudad",
    }
    SourceStatus.mark("Cartociudad", "ok")
    cache_set(CACHE, key, result)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="Cartociudad geocoder")
    p.add_argument("--address", required=True)
    args = p.parse_args()
    print(json.dumps(geocode(args.address), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
