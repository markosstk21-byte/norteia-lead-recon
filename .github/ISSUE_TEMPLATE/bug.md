---
name: Bug report
about: Report something that broke or returned wrong data
title: "bug: "
labels: bug
assignees: ""
---

## What broke?

<!-- One sentence. -->

## Reproduce

```bash
# Exact command(s) you ran
/lead-discover "..." "..."
```

## Expected vs actual

- **Expected**:
- **Actual** (paste relevant slice of `~/.claude/.cache/lead-recon/<date>/<mode>-<HHMMSS>.json` if possible):

## Source diagnosis (if it's a 0-result issue)

What did the `sourcesAvailability` panel of the HTML twin / JSON report?
Include the per-source status (`empty_window`, `not_executed`, `network_error`, etc).

## Environment

- OS: <!-- e.g. macOS 14.4, Windows 11, Ubuntu 22.04 -->
- Python: <!-- e.g. 3.11.8 -->
- Skill commit / version: <!-- git rev-parse --short HEAD -->
- BORME / PLACSP feeds reachable from your network? (`curl -I https://www.boe.es/diario_borme/`)

## Anything else?

<!-- Logs, screenshots, related issues. -->
