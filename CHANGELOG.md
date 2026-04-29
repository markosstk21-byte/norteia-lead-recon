# Changelog

Todos los cambios notables a `norteia-lead-recon` se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) y el versionado sigue [SemVer](https://semver.org/lang/es/).

## [0.1.0] — 2026-04-29

### Added

- Skill orquestadora con 3 modos: `--discover`, `--analyze`, `--cross`.
- 9 adapters de fuentes oficiales españolas en `scripts/sources/`: BORME, Cartociudad (IGN), AEPD-DPO, OpenStreetMap/Overpass, DuckDuckGo HTML, PLACSP, Infosubvenciones (SNPSAP), DIRCE.
- `domain_resolver.py` con waterfall de 4 pasos (heurística → DDG → Wayback → unresolved).
- `mappings/cnae.json` con 20 sectores legibles → CNAE-2009 + 52 provincias INE.
- 2 plantillas HTML twin: `discover.html.jinja` (mapa Leaflet OSM + tabla) y `analyze.html.jinja` (timeline registral + ficha).
- 3 slash-commands: `/lead-discover`, `/lead-analyze`, `/lead-cross`.
- Anti-claim guard: emite `assertion_mismatch` cuando una afirmación del operador no se valida contra Mission Control.
- Cache TTL escalonado por capa (BORME indefinida, Cartociudad 90d, DDG 7d, OSM 7d).
- 18 tests unit GREEN.
- Auto-detección de runners hermanos del proyecto Mapeador (autodetect `apps/borme-parser/dist/` y `apps/worker-py/`).
- Configurable via env vars: `LEAD_RECON_PROJECT_ROOT`, `MISSION_CONTROL_API_URL`, `MISSION_CONTROL_API_KEY`, `MISSION_CONTROL_LEADS_PATH`, `BORME_PARSER_URL`, `WORKER_PY_URL`.

### Known limitations

- BORME: solo procesa **sumarios** (títulos de actos), no extrae **capital social** del XML del acto individual. Esto es trabajo de v0.2.
- DIRCE: solo segment sizing — NO devuelve listado nominal (DIRCE es agregado estadístico por construcción; documentado).
- Registradores.org: modo `--premium` reservado, integración real pendiente (€10-30/empresa, requiere flow de pago + scraping autenticado).
- Discovery por sumario BORME tiene baja recall por geografía: títulos no siempre incluyen provincia. Mitigación v0.2: parser de actos individuales con filtro fiable.

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
