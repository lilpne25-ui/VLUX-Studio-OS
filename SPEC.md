# Specification

## Functional

1. Registrar videos locales con episodio, versión, permisos y hash.
2. Rechazar corruptos y duplicados; aceptar video sin audio.
3. Analizar duración, FPS, resolución, cortes aproximados, movimiento, brillo, contraste, negros, congelados y proxies de espacio de subtítulos.
4. Registrar comparación A/B y calificaciones humanas sin atribuirlas al algoritmo.
5. Ejecutar baseline; entrenar sólo con ejemplos etiquetados suficientes y holdout por episodio.
6. Registrar artefacto, hash, parámetros, métricas y estado candidato; no promover automáticamente.
7. Servir dashboard local y exportar JSON mediante la salida CLI.

## Non-functional

CPU-first, reproducible, offline, auditable, no credenciales, no datos no autorizados, no modificación automática de código o modelos promovidos.

## Acceptance

La suite `python -m unittest discover -s tests -v` debe pasar. La demo debe completar importación, análisis, feedback, baseline y estado explícito de entrenamiento.
