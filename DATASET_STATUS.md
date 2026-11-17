# DATASET STATUS V0.5

El esquema `0.5` separa activos audiovisuales (`videos`), análisis (`analyses`, `observations`), estimaciones (`attention_analyses`), evaluaciones humanas (`video_evaluations`), publicaciones (`publications`), métricas por plataforma (`platform_metrics`), comparaciones (`ab_comparisons`), versiones de producción (`production_versions`) y estado de aprendizaje (`dataset_registry`, `experiments`, `models`).

## Estado del piloto real

- EP011 y EP021 tienen copias locales autorizadas y analizadas.
- Permiso registrado: `authorized_analysis_only`; elegibilidad de entrenamiento: **excluida**.
- Texto leído por revisión visual asistida por IA: `AI_ASSISTED_VISUAL_REVIEW`; sin OCR/ASR.
- EP011 tiene una publicación de Instagram registrada desde una captura proporcionada por el usuario, con fecha de medición desconocida y vínculo por episodio (`match_basis: episode`).
- No hay evaluaciones humanas identificadas.
- No hay leads, reuniones ni ventas verificadas.
- `eligible_videos: 0`; el Training Gate permanece `BLOCKED`.

## Reglas de higiene

No se mezclan métricas sintéticas con métricas observadas. Las plataformas y fechas se almacenan por separado; una fecha desconocida permanece `NULL`. Las métricas repetidas se deduplican en lectura y no se suman. Los datos ausentes permanecen `NOT_AVAILABLE`; no se imputan.
