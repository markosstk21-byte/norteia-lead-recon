---
description: Cruza un lead candidato (NIF / razón social) con todo el conocimiento existente en el sistema NorteIA - Mission Control, lead-research-brief previos, meeting-preaudit-brief, instincts Sinapsis y observations.
---

# /lead-cross

Lanza el modo `--cross` de la skill `norteia-lead-recon`.

**Uso esperado**: `/lead-cross <NIF|razón-social|id>`

Ejemplos:
- `/lead-cross B12345678`
- `/lead-cross "Asesores Pérez S.L."`
- `/lead-cross lead_4521`

## Qué hace

1. Busca en Mission Control (HTTP API si configurada vía `MISSION_CONTROL_API_URL` + `_API_KEY`, fallback a JSON local).
2. Busca en `~/.claude/.cache/lead-research-brief/` outputs previos.
3. Busca en `~/.claude/.cache/meeting-preaudit-brief/` post-reunión.
4. Busca en `~/.claude/observations.jsonl` por menciones de la empresa.
5. Busca en `_instincts-index.json` patrones aplicables.
6. Calcula "qué falta" y la siguiente skill recomendada.

## Comando real a ejecutar

```bash
python "$HOME/.claude/skills/_library/norteia-lead-recon/scripts/cross.py" --input "$1"
```

## Anti-claim guard

Si en la conversación afirmaste "esta empresa es ya cliente" / "tengo email del decisor" y `--cross` no lo encuentra, la skill emite observation `assertion_mismatch` y warn explícito. **Nunca** escribe a Mission Control sin OK humano.
