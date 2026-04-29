---
description: Ficha completa de UNA empresa cruzando BORME + Cartociudad + PLACSP + Infosubvenciones + AEPD-DPO + scraping web. Modo --premium añade Registro Mercantil (€10-30).
---

# /lead-analyze

Lanza el modo `--analyze` de la skill `norteia-lead-recon`.

**Uso esperado**: `/lead-analyze <NIF|razón-social> [--premium]`

Ejemplos:
- `/lead-analyze B12345678`
- `/lead-analyze "Asesores Pérez S.L."`
- `/lead-analyze B12345678 --premium`

## Qué hace

1. Detecta si la entrada es NIF o razón social.
2. En paralelo:
   - BORME timeline histórico (si NIF disponible — placeholder hasta que `apps/borme-parser` esté listo).
   - PLACSP — contratos públicos del adjudicatario.
   - Infosubvenciones — subvenciones recibidas.
   - AEPD — DPO designado sí/no.
3. Resuelve dominio web vía waterfall.
4. Si `--premium`: marca slot para Registradores.org (no implementado en este MVP — placeholder explícito con coste estimado).
5. Calcula recomendación de productos NorteIA (formacion-eu-ai-act, lidera-ia, auditoria-ia) según señales.
6. Escribe JSON snapshot + HTML twin con timeline visual.

## Comando real a ejecutar

```bash
python "$HOME/.claude/skills/_library/norteia-lead-recon/scripts/analyze.py" --input "$1" $([ "$2" = "--premium" ] && echo "--premium")
```

## Después

- Si la ficha es prometedora: lanzar `lead-research-brief` para narrativa deep + procesos AS-IS.
- Si hay reunión: `meeting-preaudit-brief` post-reunión.
- Para registrar el lead en CRM: `crm-automation-pipeline` o entrada manual en Mission Control.
