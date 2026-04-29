# norteia-lead-recon

> Discovery + investigación de leads B2B en España **sin Google Maps, sin Apollo, sin Apify**.
> Coste base 0€. Cero dependencia de variables externas. Encadenamiento de fuentes oficiales abiertas.

[![tests](https://img.shields.io/badge/tests-18%2F18%20GREEN-brightgreen)](./tests) [![license](https://img.shields.io/badge/license-MIT-blue)](./LICENSE) [![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)

## Instalación (Claude Code)

```bash
# 1. Clonar el repo en la library de skills
git clone https://github.com/Luispitik/norteia-lead-recon.git \
  ~/.claude/skills/_library/norteia-lead-recon

# 2. Copiar los slash commands (vienen incluidos en commands/)
mkdir -p ~/.claude/commands
cp ~/.claude/skills/_library/norteia-lead-recon/commands/*.md \
   ~/.claude/commands/

# 3. (opcional) Configurar paths de tu proyecto
cp ~/.claude/skills/_library/norteia-lead-recon/.env.example \
   ~/.claude/skills/_library/norteia-lead-recon/.env
# editar .env con tus paths

# 4. Verificar (debe imprimir "Ran 18 tests in ... OK")
cd ~/.claude/skills/_library/norteia-lead-recon
python -m unittest tests.test_smoke
```

Reinicia Claude Code y los comandos `/lead-discover`, `/lead-analyze`, `/lead-cross` aparecerán activos.

## Adaptación para otros operadores

Si NO eres NorteIA, edita `mappings/cnae.json` para cambiar los productos por defecto:

```json
"asesoría fiscal": {
  "cnae": ["6920"],
  "norteiaProducts": ["TU-PRODUCTO-1", "TU-PRODUCTO-2"]
}
```

La lógica de la skill es agnóstica al operador. Los productos solo aparecen en el campo `recommendation.qualifiedFor` del output.

## Quick start

```bash
# Modo discovery: leads sectoriales por geografía
/lead-discover Sevilla "asesoría fiscal"

# Modo analyze: ficha completa de UNA empresa
/lead-analyze B12345678
/lead-analyze "Asesores Pérez S.L." --premium

# Modo cross: cruza con tu sistema (Mission Control + briefs previos)
/lead-cross B12345678
```

## Por qué

El plan F1 del proyecto **Mapeador de Leads** contemplaba un spider sobre Google Maps. Esta skill lo **reemplaza** con una orquestación de fuentes oficiales españolas que cumple la premisa innegociable del operador: cero variables externas. Resultado:

- 0€ base por lead.
- 100% datos públicos (BORME, PLACSP, Cartociudad, OSM, AEPD…).
- GDPR + LSSI-CE compliant por construcción.
- Output reusable: JSON estructurado + HTML twin + Mission Control + ingest opcional al Postgres del Mapeador.

## Las 3 capacidades

| Modo | Comando | Caso de uso |
|---|---|---|
| `--discover` | `/lead-discover <geo> <sector>` | "Necesito 50 asesorías fiscales en Sevilla con web propia." |
| `--analyze` | `/lead-analyze <NIF\|razón-social>` | "Cuéntame todo de Asesores Pérez S.L. antes de la reunión." |
| `--cross` | `/lead-cross <NIF\|nombre>` | "¿Qué tenemos ya de esta empresa en NorteIA?" |

## Las 12 fuentes oficiales que orquesta

**Free-tier core (siempre activadas)**:
- BORME (datos.gob.es) — eventos registrales 2009→hoy.
- Cámara de Comercio España — listados sectoriales.
- Cartociudad (IGN) — geocoding nacional.
- OpenStreetMap / Overpass — POIs alternativos a Maps.
- DuckDuckGo HTML — resolución de dominio sin Google.
- datos.gob.es — agregador subvenciones / contratos.
- PLACSP — Plataforma Contratación Pública.
- Infosubvenciones (SNPSAP) — subvencionados.
- BOE / DOGC / DOG / BOPV — anuncios y adjudicaciones.
- AEPD — registro de DPOs (señal de madurez compliance).

**Solo dimensiona segmento (NO listado nominal)**:
- DIRCE (INE) — estadísticas agregadas por CNAE × provincia.

**Premium on-demand (€10-30, requiere confirmación humana)**:
- Registradores.org — nota simple, cuentas anuales.

## Outputs

Para cada modo, la skill escribe:

```
~/.claude/.cache/lead-recon/<YYYY-MM-DD>/
├── <mode>-<HHMMSS>.json    # snapshot completo
└── <mode>-<HHMMSS>.html    # HTML twin (mapa Leaflet o timeline visual)
```

Y opcionalmente:
- Merge en `~/.claude/skills/_operator-state.json::leadReconStats`.
- Observation `tool_lead_recon` en `~/.claude/observations.jsonl` (Sinapsis aprende patrones).
- Push a Mission Control (solo con `--push` y OK humano).
- Ingest al Postgres del Mapeador (solo con `--ingest` y proyecto activo).

## Anti-claim guard

Si en la conversación afirmas "esta empresa es ya cliente" / "tengo email del decisor" y `/lead-cross` no encuentra evidencia, la skill emite observation `assertion_mismatch` y warn explícito. **Nunca** escribe a Mission Control sin confirmación humana.

## Standalone vs delegate

La skill incluye **mini-parsers internos** suficientes para correr **HOY**, sin esperar a que `apps/borme-parser` o `apps/worker-py` del proyecto Mapeador estén listos.

Cuando esos packages estén implementados (F1-F3 del Mapeador), la skill detecta automáticamente su presencia (`apps/borme-parser/dist/`, `apps/worker-py/`) y delega a ellos para mayor robustez. Sin cambios en la API externa.

## Tests

```bash
cd ~/.claude/skills/_library/norteia-lead-recon
python -m unittest tests.test_smoke -v
```

18/18 tests GREEN al implementar v0.1.

## Pipeline comercial recomendado

```
/lead-discover Sevilla "asesoría fiscal"     ← Esta skill
   ↓
[selecciona top-N candidatos cualificados]
   ↓
/lead-analyze <NIF>                          ← Esta skill (por cada candidato)
   ↓
lead-research-brief                          ← Skill existente (deep-dive narrativo)
   ↓
[reunión 1 con el lead]
   ↓
meeting-preaudit-brief                       ← Skill existente (post-reunión 2)
   ↓
norteia-contracts                            ← Skill existente (pack contractual)
```

## Legal

- Output `--discover`: solo datos públicos (razón social, NIF, CNAE, dirección registral, dominio, estado registral). Cero datos personales.
- Output `--analyze`: puede incluir nombres de administradores (públicos por ley en BORME).
- Antes de cualquier outreach: el proyecto Mapeador de Leads debe tener LIA + ROPA + opt-out generados con `packages/legal-pack`. Esta skill enlaza al pack legal pero **no lo sustituye**.
- LSSI-CE Art. 21 más restrictivo que GDPR para outreach B2B → consentimiento previo expreso.

## Lo que NO hace

- ❌ Google / Apollo / Hunter / SerpAPI / Apify / Bright Data.
- ❌ Páginas Amarillas / QDQ / LinkedIn (ToS).
- ❌ Automatización LinkedIn (ban + ToS).
- ❌ Envío de emails (eso es `salgadoia-sales-engine`).
- ❌ Generar ficha narrativa deep — eso es `lead-research-brief`.
- ❌ Sustituir al pack legal — lo enlaza.
- ❌ Listar empresas desde DIRCE (DIRCE es agregado, no nominal).

## Versión

- **0.1.0** (2026-04-29) — MVP: 3 modos, 10 fuentes core, 18 tests GREEN, 2 templates HTML.
- Pendiente: integración real Registradores.org (`--premium`), parser BORME por NIF (delegado a `apps/borme-parser`), ingest Postgres.

---

Builded by **NorteIA / Forja de Camaleones** — [github.com/Luispitik/norteia-lead-recon](https://github.com/Luispitik/norteia-lead-recon) · MIT License
