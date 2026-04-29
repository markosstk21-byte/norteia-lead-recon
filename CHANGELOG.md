# Changelog

Todos los cambios notables a `norteia-lead-recon` se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) y el versionado sigue [SemVer](https://semver.org/lang/es/).

## [Unreleased] — v0.1.1 — Honestidad y diagnóstico

> Cambios in-flight tras la auditoría post-publicación pública (2026-04-29).
> Foco: cerrar el gap entre lo que la skill **promete** y lo que **realmente
> hace** en código. Sin nuevas features, solo robustez y transparencia.

### Added

- `SourceStatus` tipado con vocabulario estricto (`ok`, `empty_window`,
  `network_error`, `http_error`, `parse_error`, `not_executed`, `down`).
  Una fuente NUNCA falla silenciosa: cada `0` lleva motivo legible.
- Panel de diagnóstico en `discover.html.jinja` cuando `totalCandidates == 0`:
  desglose por fuente del por qué no aportó resultados.
- 6 tests nuevos (24/24 GREEN): typed status, exception → `down`, E2E del
  diagnóstico per-source.

### Fixed

- `discover.py`: el `except Exception` silencioso ya no oculta el motivo real
  por el que una fuente devuelve 0. Causa raíz documentada del bug
  `leadReconStats.lastTotal:0` observado en el primer run real.
- `borme.analyze_by_nif`: status legacy `"ok-no-index"` reemplazado por
  `"not_executed"` con razón explícita (BORME no expone índice por NIF).

### Removed

- Línea engañosa del CHANGELOG v0.1.0 que afirmaba que el anti-claim guard
  estaba implementado. Movida a "Known caveats" — pendiente para issue #5.

## [0.1.0] — 2026-04-29

### Added

- Skill orquestadora con 3 modos: `--discover`, `--analyze`, `--cross`.
- 9 adapters de fuentes oficiales españolas en `scripts/sources/`: BORME, Cartociudad (IGN), AEPD-DPO, OpenStreetMap/Overpass, DuckDuckGo HTML, PLACSP, Infosubvenciones (SNPSAP), DIRCE.
- `domain_resolver.py` con waterfall de 4 pasos (heurística → DDG → Wayback → unresolved).
- `mappings/cnae.json` con 20 sectores legibles → CNAE-2009 + 52 provincias INE.
- 2 plantillas HTML twin: `discover.html.jinja` (mapa Leaflet OSM + tabla) y `analyze.html.jinja` (timeline registral + ficha).
- 3 slash-commands: `/lead-discover`, `/lead-analyze`, `/lead-cross`.
- Cache TTL escalonado por capa (BORME indefinida, Cartociudad 90d, DDG 7d, OSM 7d).
- 18 tests unit GREEN.
- Auto-detección de runners hermanos del proyecto Mapeador (autodetect `apps/borme-parser/dist/` y `apps/worker-py/`).
- Configurable via env vars: `LEAD_RECON_PROJECT_ROOT`, `MISSION_CONTROL_API_URL`, `MISSION_CONTROL_API_KEY`, `MISSION_CONTROL_LEADS_PATH`, `BORME_PARSER_URL`, `WORKER_PY_URL`.

### Known caveats — sé honesto antes de mergear

Documentamos aquí lo que **NO** funciona en v0.1.0 — leer antes de basar
decisiones de negocio en outputs de esta versión.

| Componente | Estado real v0.1.0 | Issue / fix |
|---|---|---|
| `borme.discover_by_cnae_province` | Parcial — sólo sumarios, no XML de acto | [#1](https://github.com/Luispitik/norteia-lead-recon/issues/1) |
| `borme.analyze_by_nif` | **Stub** — devuelve timeline vacío con nota | Delegar a `apps/borme-parser` o `--premium` |
| `dirce.segment_size` | **Stub** — `totalCompanies: null` | [#2](https://github.com/Luispitik/norteia-lead-recon/issues/2) |
| `--premium` con Registradores.org | **No implementado** — sólo imprime WARN | [#3](https://github.com/Luispitik/norteia-lead-recon/issues/3) |
| Anti-claim guard `/lead-cross` | **Documentado pero no en código** | issue v0.1.1 (P0 audit) |
| `osm.PROVINCE_BBOX` | **Sólo 7/52 provincias mapeadas** | issue v0.1.1 |
| Fallback real a `apps/borme-parser` | `detect_project_runners()` existe pero ningún orquestador lo invoca | issue v0.1.1 |
| Evidence pack (`url + fetchedAt + sha256`) | Sólo `url`, falta timestamp y hash | issue v0.1.1 |
| Confirmación humana en `--premium` | No bloquea — sólo imprime WARN | fix v0.1.1 (P0 audit) |
| Discovery por sumario BORME | Baja recall por geografía (filtra por keyword en título) | [#1](https://github.com/Luispitik/norteia-lead-recon/issues/1) |

### Sources verificadas (uptime esperado)

| Fuente | Endpoint | Stability |
|---|---|---|
| BORME / BOE | boe.es/diario_borme | Alta — open data oficial |
| Cartociudad | cartociudad.es/geocoder | Alta — IGN público |
| AEPD-DPO | aepd.es/dpd/buscar | Media — formulario web |
| Overpass / OSM | overpass-api.de | Alta — rate-limited |
| DuckDuckGo HTML | html.duckduckgo.com | Media — sin API key, layout puede cambiar |
| PLACSP | contrataciondelestado.es/sindicacion | Alta — feeds Atom anuales |
| Infosubvenciones | infosubvenciones.es | Media — sin API JSON, parser HTML |

## [Unreleased] — Roadmap v0.2

- [ ] **BORME-A acto-XML parser**: extraer capital social, administradores, objeto social del XML individual (gratis, datos.gob.es). Habilita filtros por capital ≥ X €, sector real, etc.
- [ ] **DIRCE Tempus3 mapping**: actualizar tabla INE para devolver totalCompanies real por CNAE+provincia (cifra anual).
- [ ] **Registradores.org integration**: modo `--premium` con scraping autenticado + cobro por nota simple confirmado humano.
- [ ] **Cache compartido**: hoy cada operador tiene su propio cache local. Posible compartir BORME parsed entre miembros de la Forja.
- [ ] **Multi-país**: hoy España-only. CNAE-EU (NACE) + portales registrales por país (KBO Bélgica, RCS Francia, Companies House UK).
- [ ] **MCP server wrapper**: para consumir desde otros agents/clients fuera de Claude Code.
