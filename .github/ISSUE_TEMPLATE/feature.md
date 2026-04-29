---
name: Feature request
about: Propose a new capability or adapter
title: "feat: "
labels: enhancement
assignees: ""
---

## What problem does this solve?

<!-- Be specific. "Make BORME faster" is too vague. -->

## Proposed behaviour

<!-- Include input/output shape if relevant. -->

```bash
/lead-... <args>
```

## Source / API to integrate (if it's a new adapter)

- Name:
- URL of the official endpoint:
- Auth required? (Free / API key / OAuth / scraping)
- Rate limits known?
- License / terms of use:

> If the source requires payment or scraping behind auth, it likely belongs in
> `--premium` and needs the human cost gate. See `analyze.py:confirm_premium_cost`.

## Doctrine fit

Quick checklist — a feature that fails any of these is unlikely to land:

- [ ] No new dependency on Google/Apollo/Apify/SerpAPI/Hunter/n8n/proprietary brokers.
- [ ] All fetched data is public or covered by GDPR Art. 6.1.f legitimate interest.
- [ ] Adapter respects rate limits and identifies itself with the User-Agent
      `norteia-lead-recon/<version>`.
- [ ] No regression in the source-status diagnostic (every 0-result must be
      attributable to a typed reason).

## Tests

How would you validate this? (fixture VCR? mock server? real endpoint smoke
test in CI?)
