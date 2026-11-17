# Release notes

## V0.6 — Creative Feedback Loop

- Added versioned V0.6 contracts: creative review, visual defects, recommended changes, production brief, episode version, human approval, human evaluation, performance record and performance comparison.
- Added the Creative Feedback Loop service: review -> defects -> actionable changes -> production brief -> episode-version import -> comparison -> human evaluation -> performance records.
- Actionable recommendations always carry: episode, timestamp, detected problem, evidence, estimated impact, proposed solution, priority, suggested tool and acceptance criterion. Estimates are marked `ESTIMATE_ONLY` and never presented as results.
- Production handoff exports are proposal-only (`auto_apply: false`, `write_into_agent_workspace: false`); Claude Code / Codex may read proposals when authorized, and Studio OS imports returned versions through explicit paths and hashes.
- Episode versions are immutable in practice (`NEVER_OVERWRITE` policy), integrity is verified by SHA-256 before comparisons, and activation/rollback only change comparison state, never files or publications.
- Performance records are tied to the exact episode version; missing metrics stay `NOT_AVAILABLE` and zeros stay `0`. Likes are never treated as leads.
- Human evaluations and approvals use named human evaluators; AI-assisted, demo and anonymous inputs stay excluded from the training gate.
- Training remains `NO_TRAINING_INSUFFICIENT_DATA`; no model promotion was performed and no commercial improvement was claimed.
- Added V0.6 synthetic end-to-end verification and the EP011/EP021 functional demo; public-safe summary in `docs/V06_PILOT.md`.

## V0.5 — Attention Lab V0.1

- Deterministic, CPU-only Attention Lab with hook, narrative, production, commercial-value and results layers.
- Evidence, confidence, coverage, limitations and a first proposed change in every analysis.
- Layered A/B comparison: observed facts, heuristic estimates, human preferences and commercial results stay separate.
- Human evaluation ledger with identified 1–5 evaluations; anonymous and AI-assisted inputs excluded from the human gate.
- Dataset Registry, Training Gate, experiments, Model Registry, named-human promotion and rollback.
- Local `manifest` and CPU `ffmpeg_animatic` production adapters with version activation and rollback.
- Expanded dashboard (library, hook/timeline, A/B, learning, commercial, production) with per-request SQLite connections.
- Public contract schemas and a dependency-free validator.
- Real pilot comparing authorized copies of EP011 and EP021; no automatic winner and no training.

## V0.4

Platform-separated commercial analytics, EP011 reference activation and EP025 proposal comparison.

## V0.3

Functional local dashboard, SQLite persistence and end-to-end workflow verification.

## V0.2

Creative Intelligence contracts and commercial data model.

## V0.1

Local dataset engine, FFprobe/OpenCV analysis, human A/B feedback, rules baseline, model registry and dashboard foundation.
