# Architecture

## Current state

VLUX Studio OS V0.6 implements the **Creative Feedback Loop** on top of the V0.5 Attention Lab.

```text
authorized media
   -> Creative Review (V0.6)
   -> Visual Defects (V0.6)
   -> Recommended Changes (V0.6)
   -> Production Brief (V0.6) + Production Handoff
   -> Episode Version Import (V0.6, explicit path + hash + permission)
   -> Version Comparison (V0.6)
   -> Human Evaluation (V0.6)
   -> Performance Records (V0.6)
   -> Learning Governance (V0.5, unchanged)
```

Layer separation is preserved:

1. Observed audiovisual facts (FFprobe/OpenCV).
2. Heuristic estimates and estimated impact (`ESTIMATE_ONLY`).
3. Human evaluations, preferences and approvals (named human evaluators only).
4. Commercial metrics tied to the exact episode version (missing stays missing, zero stays zero).

The learning branch remains separate: Dataset Registry -> Training Gate -> Experiment -> Evaluation -> Model Registry -> Manual promotion, and it stays blocked with `NO_TRAINING_INSUFFICIENT_DATA`.

## V0.6 modules

- `vlux_ci/creative_loop.py`: loop orchestration, contracts, exports, imports, comparisons, performance records, evaluations, approvals, status.
- Contracts: `creative-review.v0.1`, `visual-defects.v0.1`, `recommended-changes.v0.1`, `production-brief.v0.1`, `episode-version.v0.1`, `human-approval.v0.1`, `human-evaluation.v0.1`, `performance-record.v0.1`, `performance-comparison.v0.1`.
- SQLite schema: additive V0.6 tables under schema `0.6`; V0.5 tables remain valid.
- CLI: `creative-review`, `creative-defects`, `creative-changes`, `review-export`, `brief-create`, `brief-export`, `version-import`, `version-import-contract`, `version-approve`, `version-evaluate`, `performance-record`, `version-compare`, `version-integrity`, `versions-list`, `loop-status`.
- Dashboard: `/api/loop/status`, `/api/loop/review`, `/api/loop/review-export`, `/api/loop/brief`, `/api/loop/brief-export`, `/api/loop/version-import`, `/api/loop/version-evaluate`, `/api/loop/approval`, `/api/loop/performance`, `/api/loop/compare`, plus the V0.6 loop view.

## Non-regression

V0.5 Attention Lab, V0.5 A/B, V0.5 learning gate and V0.5 production adapters keep their V0.1/V0.2/V0.5 behavior. V0.6 only adds.
