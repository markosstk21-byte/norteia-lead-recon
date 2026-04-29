"""
ddg.py — DuckDuckGo HTML scraping (sin API key) para resolución de dominio.

Endpoint: https://html.duckduckgo.com/html/?q=...

Cache: 7 días. Rate-limit auto-impuesto: max 1 query/2s.

Uso:
    python ddg.py --query '"Asesores Pérez S.L." Sevilla'
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CacheConfig, SourceStatus, cache_get, cache_set, emit_observation, http_get

CACHE = CacheConfig(namespace="ddg", ttl_seconds=60 * 60 * 24 * 7)
DDG_HTML = "https://html.duckduckgo.com/html/?q={q}"

_LAST_REQ_TS: float = 0.0
_RATE_LIMIT_SECONDS = 2.0


def _throttle() -> None:
    global _LAST_REQ_TS
    delta = time.time() - _LAST_REQ_TS
    if delta < _RATE_LIMIT_SECONDS:
        time.sleep(_RATE_LIMIT_SECONDS - delta)
    _LAST_REQ_TS = time.time()


def search(query: str, max_results: int = 10) -> list[dict]:
    """
    Returns a list of {url, title, snippet}. Empty list if DDG blocks.

    The DDG HTML page wraps results in <a class="result__a" href="...">title</a>
    plus a snippet div. Parser is minimal — best-effort.
    """
    if not query:
        return []
    cached = cache_get(CACHE, query)
    if cached is not None:
        return cached

    _throttle()
    url = DDG_HTML.format(q=urllib.parse.quote(query))
    status, body = http_get(url, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) norteia-lead-recon/0.1",
    })
    if status != 200 or "result__a" not in body:
        SourceStatus.mark("DDG", f"http-{status}")
        emit_observation("source_unavailable", {"source": "DDG", "status": status})
        return []

    SourceStatus.mark("DDG", "ok")
    # DDG HTML responses use redirect URLs like "//duckduckgo.com/l/?uddg=..."
    # We parse those and decode the real target URL.
    results: list[dict] = []
    pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    for m in pattern.finditer(body):
        href = html.unescape(m.group(1))
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        real = _decode_ddg_redirect(href) or href
        results.append({"url": real, "title": title})
        if len(results) >= max_results:
            break

    cache_set(CACHE, query, results)
    return results


def _decode_ddg_redirect(href: str) -> Optional[str]:
    """Decodes DDG's //duckduckgo.com/l/?uddg=<encoded_url> redirect."""
    if "uddg=" not in href:
        return None
    parsed = urllib.parse.urlparse(href if href.startswith("http") else "https:" + href)
    qs = urllib.parse.parse_qs(parsed.query)
    return urllib.parse.unquote(qs.get("uddg", [""])[0]) or None


def main() -> None:
    p = argparse.ArgumentParser(description="DuckDuckGo HTML search")
    p.add_argument("--query", required=True)
    p.add_argument("--max", type=int, default=10)
    args = p.parse_args()
    print(json.dumps(search(args.query, args.max), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
