# Results

## V0.6 engineering verification

- 47 automated tests passing (35 V0.5 preserved plus 12 new V0.6 creative-loop tests).
- Synthetic V0.6 end-to-end workflow verified, including creative review, exports, imports, human evaluation, performance records and version comparison, plus the dashboard HTTP workflow.
- V0.3/V0.4/V0.5 compatibility workflow still verified.
- V0.6 contracts validate against their published schemas.
- Layered comparison keeps `automatic_winner: null`.
- Human evaluations persist; anonymous, AI-assisted and demo inputs are excluded from the training gate.
- Training remains blocked and creates no model.
- Production handoff exports stay proposal-only.

## V0.6 creative feedback loop demo — EP011 vs EP021

The V0.6 loop was executed on authorized local copies of EP011 and EP021.

- EP021 defect (high priority): no deliberate visual change before 3 s in the hook.
- EP021 proposal: add a deliberate visual change before 2 s (cinematic close-up / reveal / motivated transition), keeping the rest stable.
- Estimated impact: `ESTIMATE_ONLY` on `retention_3s`; not a measurement and not a commercial result.
- Acceptance: human review of legibility and clarity on mobile.
- Versions compared: EP011 vs EP021 with explicit version keys and SHA-256 integrity checks.
- Human evaluation: recorded during the local demo as `demo`, excluded from the training gate.
- Performance: missing metrics remained missing; no commercial improvement was claimed.

The public-safe summary is [`V06_PILOT.md`](V06_PILOT.md).

## V0.5 pilot — EP011 vs EP021

| Observed fact | EP011 | EP021 |
| --- | ---: | ---: |
| Duration | 22.67 s | 22.87 s |
| Cuts detected | 11 | 4 |
| Cuts before 3 s | 1 | 0 |
| Average shot | 1.89 s | 4.57 s |
| Motion, full video | 12.12 | 5.95 |
| Mean brightness (0–255) | 81.76 | 50.06 |
| Mean contrast (0–255) | 66.01 | 40.75 |
| Near-static samples | 5.2 % | 15.5 % |

| Heuristic estimate (0–100) | EP011 | EP021 | Confidence |
| --- | ---: | ---: | --- |
| Hook | 90 | 69 | medium |
| Narrative | 90 | 90 | low |
| Production | 84 | 78 | medium |
| Commercial value (message completeness) | 90 | 90 | low |
| Overall | 88 | 81 | low |

The A/B contract reports:

```text
decision_status: HUMAN_REVIEW_AND_RESULTS_REQUIRED
human_preferences: NOT_AVAILABLE
commercial_results: NOT_COMPARABLE
automatic_winner: null
```

The only estimate gap above the reporting threshold favors EP011’s hook by 21 points. That is not a verdict: no human preference or comparable commercial result exists. The episodes have different topics and treatments, so causal attribution is impossible.

The first proposed test is a single change in EP021: add a deliberate visual change before 2 s and measure 3-second retention when real measurement exists. This test has not been run.

Full public-safe report: [`V05_PILOT.md`](V05_PILOT.md).

## EP011 reference

EP011 / Instagram is recorded from `USER_PROVIDED_SCREENSHOT`. It has 5,468 views, 4,389 viewers, 10 seconds average watch time, 176 likes, 25 comments, 51 shares, 125 saves, 23 new followers and 11 profile visits.

The measurement date, leads and revenue are unavailable. The metric rows are linked to the episode, not a specific file version (`match_basis: episode`). No causal conclusion is made.
