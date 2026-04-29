# Contribuir a `norteia-lead-recon`

Esta skill nació en NorteIA y se libera para la **Forja de Camaleones** y cualquier operador o consultor que quiera hacer discovery B2B en España **sin depender de Google Maps, Apollo o Apify**.

## Filosofía

1. **Cero dependencia de fuentes propietarias**. Solo open data oficial + scraping ético de fuentes públicas.
2. **Coste base 0€**. Cualquier capacidad pagada se aísla detrás de un flag opt-in (ej. `--premium`).
3. **Determinismo > magia**. Los scripts deben ser auditables, parseables y reusables fuera de Claude Code.
4. **Honestidad sobre limitaciones**. Si una fuente no devuelve lo que pide, decirlo en el output con `source_unavailable` antes que inventar.
5. **Cumplimiento legal por defecto**. La skill ni envía emails ni hace outreach. Eso es responsabilidad de otra skill o del operador con LIA + ROPA + opt-out.

## Cómo contribuir

### Sugerir mejoras

Abre un [issue](https://github.com/Luispitik/norteia-lead-recon/issues) describiendo:
- Caso de uso concreto que no cubre la skill.
- Fuente oficial española que la skill debería integrar.
- Bug reproducible (qué comando lanzaste, qué esperabas, qué obtuviste).

### Proponer un nuevo adapter de fuente

Cualquier nueva fuente debe cumplir:
- Ser oficial española o internacional con licencia abierta documentada.
- Tener endpoint estable (no scraping de página que cambie cada semana).
- Cero coste (o coste solo en modo `--premium`).
- Adapter en `scripts/<source>.py` siguiendo el patrón:
  - Función `discover(...)`, `by_nif(...)` o equivalente.
  - Cache propio con `CacheConfig(namespace="<source>", ttl_seconds=...)`.
  - Marca `SourceStatus.mark("<Source>", "ok|down|http-N")` siempre.
  - Emite `emit_observation("source_unavailable", ...)` si falla.
  - Tests en `tests/test_<source>.py` con fixtures sintéticos.

### Pull requests

1. Fork → branch `feat/<descripcion-corta>` o `fix/<descripcion-corta>`.
2. Tests verdes localmente: `python -m unittest tests.test_smoke`.
3. Sin paths personales hardcoded (sólo env vars y auto-detect portable).
4. Commit en inglés con [conventional commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.
5. Actualiza `CHANGELOG.md` bajo `## [Unreleased]`.
6. PR con descripción del problema + cómo lo resuelve + impacto en cumplimiento legal si aplica.

## Roadmap colaborativo

El roadmap v0.2 está documentado en `CHANGELOG.md` bajo `## [Unreleased]`. Si vas a trabajar en uno de esos puntos, comenta primero en el issue correspondiente para evitar duplicar trabajo.

Prioridades de la Forja:

1. **BORME-A acto-XML parser** — el bottleneck más doloroso del MVP. Habilitará filtros por capital social y datos vivos.
2. **DIRCE Tempus3 mapping** — segment sizing real, hoy es stub.
3. **Registradores.org** — flow de pago + scraping autenticado.
4. **MCP server wrapper** — para usar la skill fuera de Claude Code.

## Código de conducta

- Crítica al código, no a la persona.
- Cero contribuciones que faciliten spam masivo, scraping abusivo o bypass de ToS de fuentes oficiales.
- Documenta cualquier decisión legal/compliance que afecte a usuarios.

## Soporte

- **Bugs y features**: GitHub issues.
- **Discusión de la Forja**: canal interno (separado del repo público).
- **Compliance/legal**: marcar el issue con label `legal` para revisión cuidadosa antes de merge.
