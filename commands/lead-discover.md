---
description: Descubre candidatos B2B en una geografía + sector usando solo fuentes oficiales españolas (BORME, PLACSP, OSM, Cartociudad). Sin Google, sin Apollo.
---

# /lead-discover

Lanza el modo `--discover` de la skill `norteia-lead-recon`.

**Uso esperado**: `/lead-discover <geo> <sector>`

Ejemplos:
- `/lead-discover Sevilla "asesoría fiscal"`
- `/lead-discover Madrid 6920`
- `/lead-discover Barcelona "consultoría tecnológica"`

## Qué hace

1. Resuelve el sector → CNAE.
2. Lanza en paralelo: BORME (eventos registrales), PLACSP (adjudicatarios contratos públicos), OSM Overpass (POIs por categoría).
3. Dedup por NIF + fuzzy razón social.
4. Resuelve dominio web vía waterfall (heurística → DuckDuckGo → Wayback).
5. Geocodifica direcciones con Cartociudad.
6. Escribe JSON snapshot + HTML twin con mapa Leaflet.

## Comando real a ejecutar

```bash
python "$HOME/.claude/skills/_library/norteia-lead-recon/scripts/discover.py" --geo "$1" --sector "$2"
```

Pasa $1 = geo, $2 = sector. El intérprete imprime el resumen JSON; el snapshot completo está en `~/.claude/.cache/lead-recon/<today>/discover-<HHMMSS>.json` y el HTML twin junto.

## Después

- Selecciona top-N candidatos cualificados.
- Para cada uno: `/lead-analyze <NIF>` para ficha completa.
- Para los más cualificados: lanzar la skill `lead-research-brief` para deep-dive.
