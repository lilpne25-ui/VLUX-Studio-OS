# LEARNING_STATUS V0.5

## Datos actuales

- EP011: publicación de Instagram con métricas proporcionadas por el usuario (`USER_PROVIDED_SCREENSHOT`); fecha de medición desconocida.
- EP011 y EP021: copias locales autorizadas para análisis, permiso `authorized_analysis_only`.
- Las copias del piloto son inelegibles para entrenamiento por diseño.
- Texto leído mediante revisión visual asistida por IA (`AI_ASSISTED_VISUAL_REVIEW`); sin OCR/ASR.
- Evaluaciones humanas identificadas: 0.
- Registros comerciales verificados: 0.

## Estado ML

```text
NO_TRAINING_INSUFFICIENT_DATA
```

El Training Gate está `BLOCKED`. El registro contiene dos videos de piloto pero `eligible_videos: 0`; no hay etiquetas humanas ni resultados comerciales que permitan validar un modelo. Las recomendaciones heurísticas siguen disponibles y se presentan como propuestas.

## Próximo umbral

La política `learning-gate.v0.1` exige 12 videos elegibles, 4 episodios independientes, 12 evaluaciones humanas identificadas, 4 videos evaluados, 5 registros comerciales legítimos, 2 clases de etiqueta, 2 episodios etiquetados y holdout por episodio completo.

Antes de entrenar también se requiere una persona nombrada que apruebe la promoción; el sistema rechaza aprobadores anónimos o automáticos.
