# Public Contracts

Versioned JSON contracts decouple the local dashboard, CLI, verification scripts and any future VLUX Video OS adapter. The schemas are published in this directory; runtime contracts remain local and git-ignored.

| File | Contract version | Produced by | Purpose |
| --- | --- | --- | --- |
| `creative-director.v0.2.schema.json` | `creative-director.v0.2` | Creative Director | Reviewable proposal with hooks, evidence and a recommended experiment. |
| `attention-lab.v0.1.schema.json` | `attention-lab.v0.1` | Attention Lab | Estimate-only hook, narrative, production, commercial-value and results layers. |
| `ab-comparison.v0.1.schema.json` | `ab-comparison.v0.1` | A/B comparator | Separates observed facts, heuristic estimates, human preferences and commercial results. |
| `learning-gate.v0.1.schema.json` | `learning-gate.v0.1` | Training Gate / Dataset Registry | Reports eligibility, thresholds, blocking reasons and registry state. The Training Gate is the policy that emits this contract. |
| `production-manifest.v0.1.schema.json` | `production-manifest.v0.1` | Production adapters | Scene manifest or CPU animatic output. The adapter interface is recorded as `production-adapter.v0.1` in the version registry. |

## Validation

```powershell
# Validate local exports and production manifests
python scripts\validate_contracts.py --defaults

# Validate one document against one schema
python scripts\validate_contracts.py contracts\attention-lab.v0.1.schema.json report.json
```

The validator implements the small JSON Schema subset used by these contracts and requires no extra dependency. The V0.5 end-to-end verification validates every generated contract before reporting success.

## Invariants

- No contract declares a winner from estimates alone.
- Missing values remain `null` or `NOT_AVAILABLE`; they are never imputed.
- Likes, saves and views are not leads, sales or revenue.
- Anonymous and AI-assisted evaluations are excluded from the human gate.
- Production manifests state `ai_generated: false`, `gpu_used: false`, `external_service_used: false` and `model_weights: none`.
- Training contracts remain `NO_TRAINING_INSUFFICIENT_DATA` until the gate passes.
