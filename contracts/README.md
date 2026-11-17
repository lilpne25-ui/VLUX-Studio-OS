# Public Contracts

Versioned JSON contracts decouple the local dashboard, CLI, verification scripts and any future VLUX Video OS adapter. The schemas are published in this directory; runtime contracts remain local and git-ignored.

| File | Contract version | Produced by | Purpose |
| --- | --- | --- | --- |
| `creative-director.v0.2.schema.json` | `creative-director.v0.2` | Creative Director | Reviewable proposal with hooks, evidence and a recommended experiment. |
| `attention-lab.v0.1.schema.json` | `attention-lab.v0.1` | Attention Lab | Estimate-only hook, narrative, production, commercial-value and results layers. |
| `ab-comparison.v0.1.schema.json` | `ab-comparison.v0.1` | A/B comparator | Separates observed facts, heuristic estimates, human preferences and commercial results. |
| `learning-gate.v0.1.schema.json` | `learning-gate.v0.1` | Training Gate / Dataset Registry | Reports eligibility, thresholds, blocking reasons and registry state. The Training Gate is the policy that emits this contract. |
| `production-manifest.v0.1.schema.json` | `production-manifest.v0.1` | Production adapters | Scene manifest or CPU animatic output. The adapter interface is recorded as `production-adapter.v0.1` in the version registry. |
| `creative-review.v0.1.schema.json` | `creative-review.v0.1` | Creative Feedback Loop | Review aggregation with observed facts, heuristic estimates, human evaluations and commercial metrics in separate layers. |
| `visual-defects.v0.1.schema.json` | `visual-defects.v0.1` | Creative Feedback Loop | Visual defects with observed evidence and heuristic assessment. |
| `recommended-changes.v0.1.schema.json` | `recommended-changes.v0.1` | Creative Feedback Loop | Actionable recommendation with episode, timestamp, problem, evidence, estimated impact, solution, priority, tool and acceptance criterion. |
| `production-brief.v0.1.schema.json` | `production-brief.v0.1` | Creative Feedback Loop | Proposal-only production brief with handoff and guardrails. |
| `episode-version.v0.1.schema.json` | `episode-version.v0.1` | Creative Feedback Loop | Imported episode version with explicit path, hash, permission and overwrite policy. |
| `human-approval.v0.1.schema.json` | `human-approval.v0.1` | Creative Feedback Loop | Human approval decisions, conditions and no-automatic-promotion flag. |
| `human-evaluation.v0.1.schema.json` | `human-evaluation.v0.1` | Creative Feedback Loop | Version-level human evaluation with named evaluators and preferences. |
| `performance-record.v0.1.schema.json` | `performance-record.v0.1` | Creative Feedback Loop / V0.5 performance layer | Metrics tied to an exact episode version; missing stays missing, zero stays zero, likes are not leads. |
| `performance-comparison.v0.1.schema.json` | `performance-comparison.v0.1` | Creative Feedback Loop | Version comparison without automatic winner and without commercial improvement claims. |

## Validation

```powershell
python scripts\validate_contracts.py --defaults
python scripts\validate_contracts.py contracts\creative-review.v0.1.schema.json report.json
```

The validator implements the small JSON Schema subset used by these contracts and requires no extra dependency. The V0.5 and V0.6 end-to-end verification scripts validate every generated contract before reporting success.

## Invariants

- No contract declares a winner from estimates alone.
- Missing values remain `null` or `NOT_AVAILABLE`; they are never imputed.
- Likes, saves and views are not leads, sales or revenue.
- Anonymous and AI-assisted evaluations are excluded from the human gate.
- Production contracts state `ai_generated: false`, `gpu_used: false`, `external_service_used: false` and `model_weights: none`.
- Training contracts remain `NO_TRAINING_INSUFFICIENT_DATA` until the gate passes.
- Creative proposals remain `PROPOSAL_ONLY` and production handoffs remain `auto_apply: false`.
