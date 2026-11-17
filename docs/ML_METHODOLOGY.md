# ML Methodology

VLUX Studio OS is human-in-the-loop and evidence-gated. The system separates:

1. **Observed facts** — file metadata and CPU visual/audio measurements;
2. **Heuristic estimates** — deterministic editorial policy, not a trained model;
3. **Human labels** — identified 1–5 evaluations and pairwise preferences;
4. **Commercial observations** — provenance-dated leads, meetings, proposals or sales.

## Learning path

1. Import authorized assets and record provenance and permission.
2. Extract objective features and clearly marked proxies.
3. Capture identified human evaluations; exclude anonymous and AI-assisted inputs from the human gate.
4. Attach verified platform and commercial observations.
5. Register the dataset with a content hash.
6. Evaluate the Training Gate.
7. Train a lightweight candidate only when the gate passes.
8. Hold out complete episodes or campaigns.
9. Compare baseline and candidate through the Evaluation Pipeline.
10. Review limitations and promote manually with a named human approver.
11. Keep rollback available.

## Training Gate v0.1

| Check | Minimum |
| --- | ---: |
| Eligible authorized videos | 12 |
| Independent episodes | 4 |
| Identified human evaluations | 12 |
| Videos with human evaluation | 4 |
| Legitimate commercial records | 5 |
| Label classes | 2 |
| Episodes with labels | 2 |
| Holdout design | complete episode |

Eligibility excludes permissions outside `authorized`, `owned`, `synthetic` and `public_domain`. Repeated imports of the same commercial metric count once. AI-assisted and anonymous evaluations are counted separately as exclusions, never as human evidence.

## Current state

```text
NO_TRAINING_INSUFFICIENT_DATA
```

The real pilot has two videos but `eligible_videos: 0`, because both copies are `authorized_analysis_only`. There are no identified human evaluations or legitimate commercial records attached to the pilot. Training is blocked by design, not by an error.

## Attention Lab is not ML

`attention-lab.v0.1` is a deterministic scoring policy over measurable signals plus optional human-reviewed text. Its outputs are labeled `ESTIMATE_ONLY_NOT_VALIDATED`, include confidence, coverage, evidence and limitations, and are never presented as scientific virality prediction.

The commercial-value estimate measures message completeness in metadata (audience, problem, solution, CTA). It is separate from the results layer and does not imply demand, leads or revenue.

## Evaluation rules

- No accuracy, uplift or business impact is claimed without a legitimate holdout evaluation.
- Missing values remain missing; they are not imputed.
- Synthetic and demo data never enter a real training or promotion decision.
- Promotion requires a named human approver; “anonymous”, “ai”, “automated” and “system” are refused.
- Model versions remain reproducible through dataset hash, metrics and artifact path.
