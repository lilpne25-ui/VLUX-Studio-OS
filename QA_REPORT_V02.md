# QA REPORT V0.2

## Auditoría

- MSA-VLUX local: 6.0.0; proyecto aislado; `EXTERNAL_WRITE_AUTHORIZED=NO`.
- Blender/Codex/Claude tenían procesos activos; no se usó GPU ni se tocaron sus proyectos.
- `specify` no instalado; se mantienen documentos Markdown equivalentes.
- Concord local detectado pero no modificado.

## Verificaciones V0.2

- Migración compatible desde schema 0.1.
- Dataset separado por `source_kind`.
- Análisis con observaciones temporales y silencios.
- Feedback humano con criterio y confianza.
- Métricas comerciales descriptivas sin imputación ni causalidad.
- Creative Director con contrato `creative-director.v0.2` y estado `PROPOSAL_ONLY`.
- Holdout por episodio/campaña y estado honesto de insuficiencia.
- `python -m unittest discover -s tests -v`: PASS, 9 tests.
- Demo sintética: PASS para importación, análisis, feedback, baseline y recomendación.

## Limitaciones

No hay videos reales autorizados ni datos comerciales verificables disponibles en el entorno. No se declara entrenamiento comercial ni mejora de negocio.
