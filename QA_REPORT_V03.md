# QA REPORT V0.3

## Resultado

`V0.3 FUNCTIONAL` para workflow local con datos sintéticos o copias autorizadas.

## Evidencia ejecutada

- `python -m unittest discover -s tests -v`: **9 PASS, 0 FAIL**.
- `python scripts/verify_v03.py`: **V03_E2E_PASS**.
- Flujo E2E: fixture MP4 → importación/hash → análisis OpenCV/FFprobe → timestamps → feedback A/B → bundle Creative Director → nueva conexión SQLite.
- Dashboard HTTP real iniciado en localhost; upload de copia → análisis → respuesta JSON.
- Detección de duplicado verificada por el endpoint HTTP (`409 DUPLICATE` en el primer intento).
- MSA ledger verificado; proyecto aislado.

## Probado

- MP4 válido.
- MP4 corrupto.
- MP4 sin audio.
- Duplicados.
- Datos faltantes.
- Separación sintética.
- Observaciones temporales.
- Feedback A/B.
- Contratos `creative_director`, `video_brief`, `qa_recommendations`.
- Persistencia tras reinicio lógico del proceso.

## No probado

- Videos VLUX reales: no hay copias autorizadas disponibles en el dataset.
- Métricas comerciales reales.
- Entrenamiento ML comercial: permanece `NO_TRAINING_INSUFFICIENT_DATA`.
- GPU, Blender, renders y repositorios de otros agentes: deliberadamente no ejecutados.
