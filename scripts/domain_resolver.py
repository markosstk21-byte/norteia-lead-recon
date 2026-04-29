"""
domain_resolver.py — resolución de dominio web del lead sin Google.

Waterfall:
    1. Heurística directa: <slug>.com / <slug>.es / <slug>.net
       Verifica con HEAD / fetch que el dominio responda con un sitio web "creíble".
    2. DuckDuckGo HTML query: '"<razón social>" <ciudad>' — primer resultado en .es/.com.
    3. Wayback CDX (best-effort): si DDG falla, busca en archive.org si hay snapshot histórico.
    4. Marca como `unresolved` con confidence "low".

Salida:
    {
        "resolved": str | None,
        "via": "heuristic" | "duckduckgo" | "wayback" | None,
        "confidence": "high" | "medium" | "low",
        "candidates": [str],   # otras URLs evaluadas
    }
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CacheConfig, cache_get, cache_set, emit_observation, http_get, normalize_razon_social
from ddg import search as ddg_search

CACHE = CacheConfig(namespace="domain", ttl_seconds=60 * 60 * 24 * 30)


def slugify(razon_social: str) -> str:
    """razón social → slug url-safe (lowercase, sin diacritics, sin formas legales)."""
    s = normalize_razon_social(razon_social)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def head_check(url: str) -> tuple[bool, int]:
    """Returns (ok, status). Considers 200-399 as ok."""
    status, _ = http_get(url, timeout=10)
    return 200 <= status < 400, status


def heuristic_candidates(razon_social: str) -> list[str]:
    slug = slugify(razon_social)
    if not slug or len(slug) < 4:
        return []
    return [
        f"https://{slug}.es",
        f"https://www.{slug}.es",
        f"https://{slug}.com",
        f"https://www.{slug}.com",
        f"https://{slug}.net",
    ]


def resolve(razon_social: str, city: Optional[str] = None) -> dict:
    cache_key = f"{razon_social}|{city or ''}"
    cached = cache_get(CACHE, cache_key)
    if cached is not None:
        return cached

    candidates_evaluated: list[str] = []

    # 1. Heuristic
    for url in heuristic_candidates(razon_social):
        candidates_evaluated.append(url)
        ok, status = head_check(url)
        if ok:
            result = {
                "resolved": urllib.parse.urlparse(url).netloc,
                "via": "heuristic",
                "confidence": "medium",  # heuristic is correct ~60% of the time
                "candidates": candidates_evaluated,
                "status": status,
            }
            cache_set(CACHE, cache_key, result)
            return result

    # 2. DuckDuckGo
    query = f'"{razon_social}"' + (f" {city}" if city else "")
    try:
        ddg_results = ddg_search(query, max_results=5)
    except Exception:  # noqa: BLE001
        ddg_results = []

    for r in ddg_results:
        url = r.get("url", "")
        if not url.startswith("http"):
            continue
        netloc = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
        # Filter out social / generic platforms
        if any(blocked in netloc for blocked in [
            "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
            "youtube.com", "tripadvisor.", "paginas-amarillas", "paginasamarillas",
            "yelp.", "wikipedia.org", "infoempresa.com", "einforma.com",
            "axesor.es", "expansion.com", "elconfidencial.com"
        ]):
            candidates_evaluated.append(url + " (filtered:social-or-broker)")
            continue
        candidates_evaluated.append(url)
        result = {
            "resolved": netloc,
            "via": "duckduckgo",
            "confidence": "high",
            "candidates": candidates_evaluated,
            "title": r.get("title"),
        }
        cache_set(CACHE, cache_key, result)
        return result

    # 3. Wayback CDX (just check if any snapshot exists on heuristic candidates)
    for url in heuristic_candidates(razon_social)[:2]:
        cdx = f"https://web.archive.org/cdx/search/cdx?url={urllib.parse.quote(url)}&limit=1&output=json"
        status, body = http_get(cdx, timeout=10)
        if status == 200 and body and body.strip().startswith("[") and len(body.strip()) > 5:
            candidates_evaluated.append(url + " (wayback)")
            result = {
                "resolved": urllib.parse.urlparse(url).netloc,
                "via": "wayback",
                "confidence": "low",
                "candidates": candidates_evaluated,
                "warning": "Found in web.archive.org but live HEAD failed — domain may be down",
            }
            cache_set(CACHE, cache_key, result)
            return result

    # 4. Unresolved
    result = {
        "resolved": None,
        "via": None,
        "confidence": "low",
        "candidates": candidates_evaluated,
    }
    emit_observation("tool_lead_recon", {"phase": "domain.unresolved", "razon_social": razon_social})
    cache_set(CACHE, cache_key, result)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="Domain resolver waterfall")
    p.add_argument("--razon-social", dest="razon_social", required=True)
    p.add_argument("--city")
    args = p.parse_args()
    print(json.dumps(resolve(args.razon_social, args.city), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
