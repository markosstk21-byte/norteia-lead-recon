# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

**Please do NOT open a public issue for security vulnerabilities.**

This skill orchestrates official Spanish data sources (BORME, PLACSP, Cartociudad,
AEPD, Infosubvenciones, OSM, DDG) and reads from the operator's local Mission
Control / Sinapsis state. A vulnerability could leak operator state across
sessions or trick an adapter into running against unintended targets.

If you find one of these (the list is not exhaustive):

- An adapter that follows a malicious URL into an unintended host
- A path traversal in cache writes (`~/.claude/.cache/lead-recon/`)
- A way to make the skill exfiltrate `_operator-state.json` content
- A regex/parser DoS in `borme.py`, `placsp.py`, `infosubvenciones.py`, or
  `domain_resolver.py`
- A way to bypass the `--premium` cost gate (`confirm_premium_cost`)
- A way to bypass the `--assert` anti-claim guard in `cross.py`

…use one of these private channels:

1. **GitHub Private Vulnerability Reporting** (preferred):
   <https://github.com/Luispitik/norteia-lead-recon/security/advisories/new>
2. **Email**: `security@norteia.es` (PGP optional, ASCII fine).

## What to expect

- Acknowledgement within 5 working days.
- Triage and severity within 10 working days.
- Coordinated disclosure: we agree on a date, ship the fix, then publish the
  advisory. Default embargo is 30 days unless the fix is shipped sooner.

## What is out of scope

- The Spanish official sources themselves (report to BOE / INE / IGN / etc).
- Issues that require a malicious operator to attack their own machine
  (e.g. tampering with `~/.claude/skills/_operator-state.json` directly).
- Theoretical vulnerabilities without a reproducer.

## Disclosure hall of fame

We credit reporters in the release notes of the fix release unless they ask to
stay anonymous.
