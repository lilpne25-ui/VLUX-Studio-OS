# Architecture

VLUX Studio OS V0.4 is a local-first Python application. The public repository contains the application and safe examples; runtime databases and media remain local.

```text
authorized copy
      ↓
FFprobe / OpenCV
      ↓
SQLite evidence store
      ├── assets
      ├── analyses + observations
      ├── publications + platform metrics
      ├── human feedback
      └── experiments + model registry
      ↓
baseline / Creative Director / JSON contracts
```

## Boundaries

- `vlux_ci/db.py`: schema, migrations, hashing and persistence.
- `vlux_ci/probe.py`: FFprobe metadata.
- `vlux_ci/analyzer.py`: CPU-first visual/audio proxies and timestamped observations.
- `vlux_ci/funnel.py`: observed/derived/unavailable funnel indicators.
- `vlux_ci/creative.py`: deterministic Creative Director proposal engine.
- `vlux_ci/proposals.py`: EP025 proposal catalog.
- `vlux_ci/ml.py`: rules baseline and lightweight candidate path.
- `vlux_ci/dashboard.py`: local HTTP workflow.
- `vlux_ci/cli.py`: automation and reproducible commands.

There is no cloud service, platform credential, Blender invocation, render queue, GPU dependency, or write integration with VLUX Video OS.
