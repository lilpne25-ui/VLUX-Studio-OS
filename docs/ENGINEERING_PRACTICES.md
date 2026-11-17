# Engineering Practices

## Evidence before claims

Objective media facts, heuristic estimates, human judgments and commercial observations are stored in separate tables and reported in separate layers. Missing values remain missing. Estimates are labeled as estimates.

## Reproducibility

- SQLite schema version is recorded (`0.5`).
- Files receive SHA-256 hashes.
- Duplicate assets are rejected.
- Model candidates use deterministic seeds.
- Dataset Registry records a content hash.
- Episode/campaign grouping protects holdout evaluation.
- Production versions retain their brief, adapter, status and output path.

## Contracts

Public JSON contracts are versioned and checked:

- `attention-lab.v0.1`;
- `ab-comparison.v0.1`;
- `learning-gate.v0.1`;
- `production-manifest.v0.1`;
- `creative-director.v0.2`.

`scripts/validate_contracts.py` validates local exports without adding a runtime dependency. The V0.5 end-to-end verification validates every generated contract before reporting success.

## Safety

Only an explicitly selected local copy is imported. The dashboard writes to `data/review`; it does not overwrite the source. Credentials and platform API tokens are not part of the product.

Anonymous and AI-assisted evaluations are stored with provenance but excluded from the human layer and the Training Gate. Promotion requires a named human approver. The dashboard opens one SQLite connection per HTTP request and uses a busy timeout, avoiding cross-thread connection sharing.

## Quality

The project uses unit tests, corrupted-media tests, migration checks, dashboard HTTP checks (including parallel requests), persistence checks, contract checks and a complete synthetic workflow. `verify.ps1` runs unit tests, the V0.3 compatibility E2E and the V0.5 E2E.

## Governance

Human feedback can inform a candidate model but cannot promote it automatically. Recommendations are proposals. Production repositories remain outside this project's write boundary.
