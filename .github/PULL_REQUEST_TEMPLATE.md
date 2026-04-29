# Summary

<!-- One sentence of the change. -->

## What changed

<!-- Bullet list. -->

## Why

<!-- Reference an issue, a section of CHANGELOG, or a passage in CLAUDE.md / SKILL.md. -->

Fixes #

## Doctrine checklist

- [ ] No new external dependency on Google/Apollo/Apify/SerpAPI/Hunter/n8n.
- [ ] No silent `except Exception` in adapters (each failure path classifies
      itself via `SourceStatus`).
- [ ] Conventional commit messages (`feat`/`fix`/`docs`/`test`/`chore`/`refactor`).
- [ ] Branch name follows `feat/`, `fix/`, `chore/`, or `test/` prefix.
- [ ] No emojis in code or docs unless the user explicitly asked for them.

## Tests

- [ ] `python -m unittest tests.test_smoke` passes locally.
- [ ] If this PR touches an adapter, it adds a fixture under `fixtures/` (real
      response anonymised) and a unit test that does NOT hit the network.
- [ ] If this PR adds a new orchestrator path, it adds at least one E2E case
      that monkeypatches the adapters.
- [ ] Coverage does not regress (`coverage report --fail-under=<current>`).

## Honesty checklist

If your PR adds a feature that is partial/stubbed, add a row to the "Estado de
implementación" table in `SKILL.md` and to "Known caveats" in `CHANGELOG.md`.
**Don't ship prose-only features**.

- [ ] Did NOT promise something in docs that isn't in code.
- [ ] If `--premium` flow is touched, the cost gate (`confirm_premium_cost`)
      still blocks without `--yes` or `LEAD_RECON_PREMIUM_YES=1`.

## Screenshots / output

<!-- Paste a slice of the JSON snapshot or a screenshot of the HTML twin if UI changed. -->

## Risk

<!-- What could go wrong? Anything to babysit on first merge? -->
