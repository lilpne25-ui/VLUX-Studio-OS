# Integration

La integración inicial es read-only y por CLI. Importa un MP4 explícito, lee metadatos por FFprobe y devuelve JSON en stdout. Un bridge futuro puede leer manifiestos de episodios y guiones mediante adaptadores de ruta, sin importar automáticamente archivos productivos.

Recomendación exportable: conservar el JSON de `baseline`/`train` y adjuntarlo a la revisión humana de Video OS. No existe todavía un escritor ni un hook sobre el pipeline.

## V0.6 production handoff

El loop V0.6 exporta propuestas versionadas:

- `creative-review.v0.1`
- `visual-defects.v0.1`
- `recommended-changes.v0.1`
- `production-brief.v0.1`
- `episode-version.v0.1`
- `human-approval.v0.1`
- `human-evaluation.v0.1`
- `performance-record.v0.1`
- `performance-comparison.v0.1`

Los handoffs incluyen guardrails (`auto_apply: false`, `write_into_agent_workspace: false`) y un contrato de importación con ruta, SHA-256 y permiso explícitos. Studio OS no escribe en los proyectos de Claude Code o Codex; los agentes producen versiones en sus propios espacios y Studio OS importa los resultados devueltos.
