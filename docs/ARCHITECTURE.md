# Architecture

VLUX Studio OS V0.5 is a local-first Python application. The public repository contains the application, versioned contracts and public-safe documentation; runtime databases, media, reports and artifacts remain local and git-ignored.

## System flow

```text
authorized local copy
        ↓
FFprobe / OpenCV
        ↓
SQLite evidence store (schema 0.5)
  ├── videos + analyses + observations
  ├── publications + platform metrics + commercial records
  ├── attention_analyses
  ├── video_evaluations + feedback
  ├── ab_comparisons
  ├── dataset_registry
  ├── production_versions + production_jobs
  └── experiments + models
        ↓
Attention Lab / layered A/B / Creative Director
        ↓
JSON contracts → dashboard, CLI, future Video OS adapter
```

## Evidence layers

V0.5 keeps four layers separate by construction:

| Layer | Source | May it decide a winner? |
| --- | --- | --- |
| Observed facts | FFprobe/OpenCV on the file | No |
| Heuristic estimates | Deterministic Attention Lab policy | No |
| Human preference | Identified 1–5 evaluations and pairwise choices | Only as stated human evidence |
| Commercial results | Provenance-dated platform and business records | Only when comparable |

`ab.py` returns `automatic_winner: null` unless legitimate human and commercial evidence support a decision. Likes, saves and views are never converted into leads or revenue.

## Boundaries

- `vlux_ci/db.py` — schema 0.5, migrations, hashing and persistence helpers.
- `vlux_ci/probe.py` — FFprobe metadata.
- `vlux_ci/analyzer.py` — CPU-first visual/audio facts and timestamped observations.
- `vlux_ci/attention.py` — Attention Lab contract, evidence, estimates, results layer, recommendations and `first_change`.
- `vlux_ci/ab.py` — layered A/B comparison and human evaluation persistence.
- `vlux_ci/learning.py` — Dataset Registry, Training Gate, experiments, Model Registry, promotion guard and rollback.
- `vlux_ci/production.py` — local `manifest` and CPU `ffmpeg_animatic` adapters, version registry, activation and rollback.
- `vlux_ci/funnel.py` — observed/derived/unavailable funnel indicators.
- `vlux_ci/creative.py` — deterministic Creative Director proposal engine.
- `vlux_ci/proposals.py` — EP025 proposal catalog.
- `vlux_ci/ml.py` — rules baseline and gated lightweight candidate path.
- `vlux_ci/dashboard.py` — local HTTP workflow with per-request SQLite connections.
- `vlux_ci/cli.py` — automation and reproducible commands.

## Training boundary

```text
Dataset Registry
  → eligibility check (permission, provenance, deduplication)
  → Training Gate (videos, episodes, human labels, commercial records, classes)
  → experiment with episode-level holdout
  → Evaluation Pipeline
  → Model Registry candidate
  → named-human promotion
  → activation or rollback
```

The default and current state is:

```text
NO_TRAINING_INSUFFICIENT_DATA
```

Anonymous evaluations, AI-assisted evaluations and videos with permissions outside `authorized`, `owned`, `synthetic` or `public_domain` are excluded. Pilot copies use `authorized_analysis_only` and therefore cannot train anything.

## Production boundary

The V0.5 adapters are intentionally modest:

- `manifest` writes a scene-level JSON production contract with unbound assets;
- `ffmpeg_animatic` renders text cards locally with FFmpeg, without voice, music, 3D assets or AI generation.

Both record `gpu_used: false`, `model_weights: none` and `external_service_used: false`. A version must be rendered before activation. Rollback re-activates a previously rendered version without rewriting history.

## Non-goals

There is no cloud service, platform credential, Blender invocation, render queue, GPU dependency, model-weight bundle, or write integration with VLUX Video OS. Recommendations are proposals; human approval remains mandatory.
