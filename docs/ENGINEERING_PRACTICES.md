# Engineering Practices

## Evidence before claims

Objective media facts, human judgments, hypotheses, and commercial observations are stored separately. Missing values remain missing.

## Reproducibility

- SQLite schema version is recorded.
- Files receive SHA-256 hashes.
- Duplicate assets are rejected.
- Model candidates use deterministic seeds.
- Episode/campaign grouping protects holdout evaluation.

## Safety

Only an explicitly selected local copy is imported. The dashboard writes to `data/review`; it does not overwrite the source. Credentials and platform API tokens are not part of the product.

## Quality

The project uses unit tests, corrupted-media tests, migration checks, dashboard HTTP checks, persistence checks, contract checks, and a complete synthetic workflow.

## Governance

Human feedback can inform a candidate model but cannot promote it automatically. Recommendations are proposals. Production repositories remain outside this project's write boundary.
