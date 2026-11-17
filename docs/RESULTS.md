# Results

## V0.5 engineering verification

- 35 automated tests passing.
- Synthetic V0.5 end-to-end workflow verified, including parallel dashboard requests.
- V0.3/V0.4 compatibility workflow still verified against schema 0.5.
- Attention Lab contracts persist and reload.
- Layered A/B returns `automatic_winner: null`.
- Human evaluations persist; anonymous and AI-assisted inputs are excluded from the human gate.
- Training remains blocked and creates no model.
- Production manifest and CPU animatic render, activate and roll back.
- Public contract schemas validate against exported local contracts.

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
