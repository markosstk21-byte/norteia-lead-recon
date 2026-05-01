"""
osm.py — Overpass API (OpenStreetMap) para POI lookup por categoría + bounding box.

Endpoint público: https://overpass-api.de/api/interpreter
Rate-limit: ~1 req/sec, máx 25k entries por query.

Uso:
    python osm.py --tag "office=tax_advisor" --province Sevilla
    python osm.py --tag "office=consulting" --bbox 37.0,−6.0,37.5,−5.5
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CacheConfig, SourceStatus, cache_get, cache_set, emit_observation, http_get

CACHE = CacheConfig(namespace="osm", ttl_seconds=60 * 60 * 24 * 7)
OVERPASS_URL = "https://overpass-api.de/api/interpreter?data={query}"

# Bounding boxes aproximadas por provincia española. Best-effort, redondeadas.
# Para producción usar shapefile oficial.
PROVINCE_BBOX = {
    "Sevilla": (37.0, -6.5, 38.0, -5.0),
    "Madrid": (40.2, -4.0, 40.8, -3.4),
    "Barcelona": (41.2, 1.3, 42.0, 2.5),
    "Valencia": (39.2, -1.0, 39.8, 0.0),
    "Málaga": (36.5, -5.5, 37.2, -4.0),
    "Bilbao": (43.1, -3.2, 43.5, -2.7),
    "Bizkaia": (43.0, -3.4, 43.5, -2.4),
    "Zaragoza": (41.3, -1.5, 41.9, -0.6),
}


def query_overpass(tag: str, bbox: tuple[float, float, float, float], timeout: int = 30) -> list[dict]:
    """
    tag: "office=tax_advisor" or "shop=*" — Overpass tag pair.
    bbox: (south, west, north, east) WGS84.
    """
    cache_key = f"{tag}:{bbox}"
    cached = cache_get(CACHE, cache_key)
    if cached is not None:
        return cached

    s, w, n, e = bbox
    if "=*" in tag:
        key = tag.split("=")[0]
        ql = f'[out:json][timeout:{timeout}];(node["{key}"]({s},{w},{n},{e});way["{key}"]({s},{w},{n},{e});relation["{key}"]({s},{w},{n},{e}););out center tags;'
    else:
        k, v = tag.split("=")
        ql = f'[out:json][timeout:{timeout}];(node["{k}"="{v}"]({s},{w},{n},{e});way["{k}"="{v}"]({s},{w},{n},{e});relation["{k}"="{v}"]({s},{w},{n},{e}););out center tags;'

    url = OVERPASS_URL.format(query=urllib.parse.quote(ql))
    status, body = http_get(url, timeout=timeout + 5)
    if status != 200:
        SourceStatus.mark("OSM", f"http-{status}")
        emit_observation("source_unavailable", {"source": "OSM-Overpass", "status": status})
        return []

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        SourceStatus.mark("OSM", "parse-error")
        return []

    SourceStatus.mark("OSM", "ok")
    results: list[dict] = []
    for el in payload.get("elements", []):
        tags = el.get("tags", {})
        center = el.get("center") or {}
        lat = el.get("lat") or center.get("lat")
        lon = el.get("lon") or center.get("lon")
        if not (lat and lon):
            continue
        name = tags.get("name") or tags.get("brand")
        if not name:
            continue
        results.append({
            "razonSocial": name,
            "lat": lat,
            "lon": lon,
            "address": _build_address(tags),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "website": tags.get("website") or tags.get("contact:website"),
            "email": tags.get("email") or tags.get("contact:email"),
            "tags": tags,
            "source": "OSM",
        })
    cache_set(CACHE, cache_key, results)
    return results


def _build_address(tags: dict) -> str | None:
    parts = []
    if tags.get("addr:street"):
        s = tags["addr:street"]
        if tags.get("addr:housenumber"):
            s += f" {tags['addr:housenumber']}"
        parts.append(s)
    if tags.get("addr:postcode"):
        parts.append(tags["addr:postcode"])
    if tags.get("addr:city"):
        parts.append(tags["addr:city"])
    return ", ".join(parts) if parts else None


def discover(tag: str, province: str | None = None, bbox: str | None = None) -> list[dict]:
    if bbox:
        s, w, n, e = [float(x) for x in bbox.split(",")]
        bb = (s, w, n, e)
    elif province and province in PROVINCE_BBOX:
        bb = PROVINCE_BBOX[province]
    else:
        return []
    return query_overpass(tag, bb)


def main() -> None:
    p = argparse.ArgumentParser(description="OSM Overpass adapter")
    p.add_argument("--tag", required=True, help="Overpass tag, e.g. office=tax_advisor")
    p.add_argument("--province")
    p.add_argument("--bbox", help="south,west,north,east")
    args = p.parse_args()
    print(json.dumps(discover(args.tag, args.province, args.bbox), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
