# QA_REPORT_V05

## Estado

V0.5 implementa el Attention Lab, la comparación A/B por capas, el registro de evaluaciones humanas, el Dataset Registry, el Training Gate, el Model Registry, las versiones locales de producción y el dashboard ampliado. El entrenamiento sigue bloqueado.

## Evidencia de verificación

- `powershell -File verify.ps1`: **35 tests PASS**, `V03_E2E_PASS`, `V05_E2E_PASS`.
- Contratos públicos validados contra exportaciones locales: `attention-lab.v0.1`, `ab-comparison.v0.1`, `learning-gate.v0.1`, `production-manifest.v0.1`.
- Dashboard probado con peticiones HTTP paralelas; cada petición abre su propia conexión SQLite.
- Persistencia verificada tras reinicio.
- Rollback de versiones de producción verificado.
- Promoción de modelo rechazada sin gate aprobado, evidencia de mejora y aprobador humano nombrado.
- `real_media_used: false` y `gpu_used: false` en la verificación sintética.

## Piloto real

- EP011 (id 1) y EP021 (id 2) importados desde copias autorizadas; permiso `authorized_analysis_only`.
- Ambos analizados con FFprobe/OpenCV y Attention Lab.
- Contrato A/B generado con `automatic_winner: null` y `decision_status: HUMAN_REVIEW_AND_RESULTS_REQUIRED`.
- `human_preferences: NOT_AVAILABLE`; no se inventaron evaluaciones.
- `commercial_results: NOT_COMPARABLE`; no se convirtieron likes en leads.
- `eligible_videos: 0`; el Training Gate permanece `BLOCKED`.

## No realizado

- No se entrenó ningún modelo.
- No se descargaron pesos de modelos.
- No se usó GPU.
- No se usó ningún servicio externo pagado.
- No se publicaron videos, bases de datos, hojas de contacto, informes privados ni métricas privadas.
- No se ejecutó el experimento de retención propuesto; sigue siendo una propuesta.

## Limitaciones

No hay OCR/ASR. El texto en pantalla del piloto se leyó mediante revisión visual asistida por IA (`AI_ASSISTED_VISUAL_REVIEW`). Las métricas de EP011 provienen de una captura proporcionada por el usuario, con fecha desconocida y vínculo por episodio. Las estimaciones son heurísticas y no constituyen una predicción científica de viralidad.
