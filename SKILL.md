---
name: norteia-lead-recon
description: |
  Skill orquestadora de NorteIA para descubrimiento e investigación de leads
  B2B en España usando exclusivamente fuentes oficiales abiertas (BORME,
  Cámaras de Comercio, Cartociudad, datos.gob.es, PLACSP, Infosubvenciones,
  BOE, AEPD, OpenStreetMap, DuckDuckGo). Tres modos:
    --discover <geo> <sector>: encuentra candidatos por provincia/municipio
      y CNAE/sector. Output: tabla con razón social, NIF, dirección, dominio
      web resuelto via waterfall, último evento BORME.
    --analyze <NIF|razón-social>: ficha completa de UNA empresa cruzando
      BORME histórico, contratos públicos, subvenciones, AEPD-DPO, geocoding
      y scraping de su web. Modo --premium añade Registro Mercantil (€10-30).
    --cross <id|NIF|nombre>: cruza con Mission Control, outputs previos de
      lead-research-brief y meeting-preaudit-brief, instincts Sinapsis.
  USAR cuando el usuario diga "busca leads de", "descubre empresas de",
  "investiga este lead", "analiza la empresa", "leads sectoriales en",
  "qué sabemos de esta empresa", o invoque /lead-discover, /lead-analyze,
  /lead-cross. Cero dependencia de Google Maps, Apollo, Apify, SerpAPI,
  Hunter o brokers externos. Coste base 0€. NO sustituye a
  lead-research-brief — la alimenta con candidatos pre-investigados.
version: 0.1.0
auto_activate: false
user-invocable: true
brands: [norteia, salgadoia]
triggers:
  - "busca leads de"
  - "descubre empresas de"
  - "investiga este lead"
  - "analiza la empresa"
  - "leads sectoriales en"
  - "/lead-discover"
  - "/lead-analyze"
  - "/lead-cross"
  - "qué sabemos de esta empresa"
  - "qué hay sobre esta empresa"
tags:
  - lead-generation
  - b2b
  - spain-only
  - official-sources
  - borme
  - registro-mercantil
  - gdpr-compliant
  - sales-engine-feeder
---

# norteia-lead-recon

Orquestador de descubrimiento e investigación B2B sobre fuentes oficiales españolas. Cero dependencia de Google Maps, Apollo, SerpAPI, Apify o cualquier broker externo. Coste base 0€.

## Cuándo activarse

- Trigger explícito por slash-command (`/lead-discover`, `/lead-analyze`, `/lead-cross`) o por cualquiera de las frases en `triggers` del frontmatter.
- Trigger implícito: el `skill-router` puede sugerirla cuando detecta utterance de prospección B2B en España.
- NO se activa pasivamente.

## Quick start

```bash
# Discovery sectorial
/lead-discover Sevilla "asesoría fiscal"
/lead-discover Madrid 6920          # alternativa con CNAE directo

# Análisis de UNA empresa
/lead-analyze B12345678
/lead-analyze "Asesores Pérez S.L."
/lead-analyze B12345678 --premium    # incluye Registro Mercantil (€10-30)

# Cross-system (qué tenemos ya en NorteIA)
/lead-cross B12345678
/lead-cross "Asesores Pérez S.L."
```

## Arquitectura

La skill es un orquestador. Las fuentes se consultan vía scripts Python deterministas en `scripts/`:

```
norteia-lead-recon/
├── SKILL.md                       # este archivo
├── README.md                      # quick start operator-facing
├── mappings/cnae.json             # sector legible → CNAE-2009
├── scripts/
│   ├── borme.py                   # BORME via datos.gob.es
│   ├── cartociudad.py             # geocoder IGN
│   ├── aepd.py                    # DPO registry
│   ├── osm.py                     # Overpass API
│   ├── ddg.py                     # DuckDuckGo HTML
│   ├── placsp.py                  # Plataforma Contratación Pública
│   ├── infosubvenciones.py        # SNPSAP
│   ├── dirce.py                   # solo segment sizing (no nominal)
│   ├── domain_resolver.py         # waterfall heurística → DDG → Wayback
│   ├── discover.py                # orquestador modo --discover
│   ├── analyze.py                 # orquestador modo --analyze
│   ├── cross.py                   # orquestador modo --cross
│   └── _common.py                 # cache, normalización NIF/razón social
├── templates/
│   ├── discover.html.jinja        # mapa Leaflet + tabla
│   └── analyze.html.jinja         # timeline registral + ficha
├── tests/
│   ├── test_normalization.py
│   ├── test_cnae_mapping.py
│   ├── test_domain_resolver.py
│   └── test_smoke.py
└── fixtures/                      # ejemplos BORME/PLACSP anonimizados
```

## Modo `--discover`

**Input**: geo (provincia / municipio / CCAA) + sector (CNAE-2009 código o nombre legible).

**Pipeline**:
1. Normaliza el sector → CNAE consultando `mappings/cnae.json`. Si no hay match exacto, intenta fuzzy.
2. Llama a `dirce.py` para mostrar el tamaño del segmento como **contexto**, NO como listado (DIRCE es agregado, no nominal).
3. Lanza en paralelo:
   - `borme.py --discover --cnae <X> --province <Y>` (eventos BORME últimos 5 años filtrados por CNAE+provincia).
   - `placsp.py --cnae <X> --region <Y>` (adjudicatarios sector público — señal de actividad).
   - `infosubvenciones.py --cnae <X> --region <Y>` (subvencionados).
   - `osm.py --tag <vertical-tag> --bbox <bbox>` (POIs por categoría).
   - Cuando hay federación sectorial conocida, `placsp.py` se complementa con scrape ligero de la federación (vía `_common.py`).
4. **Dedup por NIF** + **fuzzy match razón social** (Levenshtein ≤ 3).
5. Para cada candidato sin dominio web conocido, `domain_resolver.py` aplica waterfall.
6. `cartociudad.py` geocodifica las direcciones registrales.
7. Output:
   - Tabla en chat (top 50, ordenada por señal de actividad).
   - JSON completo en `~/.claude/.cache/lead-recon/<YYYY-MM-DD>/discover-<HHmmss>.json`.
   - HTML twin con mapa Leaflet (OSM tiles, sin Google) usando `templates/discover.html.jinja`.

**Comando exacto a invocar**:
```bash
python "$SKILL_DIR/scripts/discover.py" --geo "<geo>" --sector "<sector>" [--max 50]
```

## Modo `--analyze`

**Input**: NIF/CIF o razón social.

**Pipeline**:
1. Si entrada es razón social, resolución NIF via búsqueda BORME por nombre.
2. `borme.py --analyze --nif <NIF>` → timeline histórico completo de eventos.
3. `cartociudad.py --address <dirección registral>` → lat/lon.
4. En paralelo:
   - `placsp.py --nif <NIF>` → contratos públicos adjudicados.
   - `infosubvenciones.py --nif <NIF>` → subvenciones recibidas.
   - `aepd.py --nif <NIF>` → si la empresa tiene DPO designado.
5. `domain_resolver.py --razon-social <X> --address <Y>` → resolución dominio.
6. Si dominio resuelto: scraping web del lead (vía `apps/worker-py` del proyecto Mapeador si existe `dist/`, fallback fetch + readability).
7. **Si flag `--premium`**: confirma con humano antes de cobrar (€10-30) y llama a `registradores.py` (módulo separado, no incluido en este MVP — placeholder).
8. Output: ficha JSON + HTML twin con timeline visual + flag `lead-research-brief recommended` si la empresa parece cualificada.

**Comando exacto**:
```bash
python "$SKILL_DIR/scripts/analyze.py" --input "<NIF|razón-social>" [--premium]
```

## Modo `--cross`

**Input**: NIF, razón social o id Mission Control.

**Pipeline**:
1. Lookup en Mission Control (HTTP GET; auth via `MISSION_CONTROL_API_KEY` en env del proyecto). Si la API no está configurada, lee `~/Mission Control/leads.json` como fallback.
2. Lookup en `~/.claude/.cache/lead-research-brief/` por NIF o razón social en outputs previos.
3. Lookup en `~/.claude/.cache/meeting-preaudit-brief/` (briefings post-reunión 2).
4. Lookup en `~/.claude/observations.jsonl` por menciones de la empresa.
5. Lookup en `~/.claude/skills/_operator-state.json::projectBlueprints` y `~/.claude/skills/_instincts-index.json` por patrones aplicables.
6. Output: resumen "qué sabemos / qué falta / próxima skill recomendada".

**Comando exacto**:
```bash
python "$SKILL_DIR/scripts/cross.py" --input "<NIF|razón-social|id>"
```

## Cache (TTL escalonado)

Ruta canónica: `~/.claude/.cache/lead-recon/<YYYY-MM-DD>/`

| Capa | TTL | Razón |
|---|---|---|
| BORME por NIF+fecha | indefinida | Immutable post-publicación |
| DIRCE | 30 días | Cambia anual |
| Cámaras + sectoriales | 7 días | Variable |
| Cartociudad por dirección | 90 días | Geocoding casi nunca cambia |
| DDG / búsquedas web | 7 días | Web cambia |
| Scraping web del lead | 24h | Variable |
| AEPD DPO | 30 días | Lento |
| OSM Overpass | 7 días | Variable |
| PLACSP por NIF o CNAE | 7 días | Boletines diarios |
| Infosubvenciones | 7 días | Boletines diarios |

`_common.py` implementa la caché key-value en JSON sobre disco.

## Anti-claim guard

Si en la conversación el operador afirma "esta empresa es ya cliente" / "tengo email del decisor" / "ya hablé con ellos" y `--cross` no encuentra evidencia → emite observation `assertion_mismatch` y warn explícito en chat. **Nunca** escribe a Mission Control sin OK humano.

## Integraciones

- **Lee**:
  - `~/.claude/skills/_operator-state.json::projectBlueprints` (sectores foco).
  - Mission Control (read-only API o JSON local).
  - `~/.claude/.cache/lead-research-brief/` y `~/.claude/.cache/meeting-preaudit-brief/`.
  - `~/.claude/observations.jsonl` (Sinapsis).
- **Escribe**:
  - `~/.claude/skills/_operator-state.json::leadReconStats` (lastRun, totalCandidates, sectoresUsados).
  - `~/.claude/observations.jsonl` con types: `tool_lead_recon`, `assertion_mismatch`, `source_unavailable`.
  - Mission Control: solo con flag `--push` y confirmación humana.
  - Postgres del Mapeador: solo con flag `--ingest` y proyecto activo (autodetección por presencia de `apps/web/.env.local` con `DATABASE_URL`).

## Legal

- Output `--discover` solo contiene datos públicos: razón social, NIF, CNAE, dirección registral, dominio, estado registral.
- Output `--analyze` puede incluir nombres de administradores extraídos de BORME (públicos por ley).
- **Antes de outreach** el proyecto Mapeador debe tener LIA + ROPA + opt-out generados con `packages/legal-pack`. Esta skill NO sustituye al pack legal — lo enlaza.

## NO hace

- NO consulta Google / Apollo / Hunter / SerpAPI / Apify / Bright Data.
- NO scrapea Páginas Amarillas / QDQ / LinkedIn (ToS).
- NO automatiza LinkedIn (ban + ToS).
- NO envía emails (eso es `salgadoia-sales-engine`).
- NO genera ficha narrativa deep — eso es `lead-research-brief`.
- NO sustituye al pack legal — lo enlaza.
- NO lista empresas desde DIRCE (DIRCE es agregado, no nominal — solo dimensiona).

## Flujo recomendado para ciclo comercial completo

1. `/lead-discover Sevilla "asesoría fiscal"` → tabla candidatos.
2. Operador selecciona top-N → `/lead-analyze <NIF>` para cada uno.
3. Para cualificados: `lead-research-brief` (skill existente) genera ficha narrativa.
4. Cuando hay reunión 2: `meeting-preaudit-brief` (skill existente) prepara pre-informe.
5. Si el lead avanza: `norteia-contracts` genera el pack contractual.

## Standalone vs delegate

La skill incluye scripts Python ejecutables propios (mini-parsers internos). Cuando el proyecto Mapeador de Leads tenga `apps/borme-parser/dist/` y `apps/worker-py/` corriendo, la skill detecta su presencia y delega:

- `apps/borme-parser` activo → la skill llama a su endpoint HTTP en lugar de parsear localmente.
- `apps/worker-py` activo → la skill llama al worker para scraping web pesado en lugar de fetch + readability.

Autodetección en `_common.py::detect_project_runners()`.
