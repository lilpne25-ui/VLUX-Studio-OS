# Architecture

`vlux_ci.db` define el esquema SQLite versionado 0.4: videos (activos), publications, platform_metrics, analyses, observations, feedback, creative_proposals, proposal_feedback, metrics, models y experiments.

`probe.py` obtiene metadatos objetivos con FFprobe. `analyzer.py` extrae métricas objetivas, timeline, silencios y observaciones con timestamps; separa estimaciones/proxies. `commercial.py` produce resúmenes descriptivos únicamente sobre datos publicados. `creative.py` implementa VLUX Creative Director sin generación de video. `dashboard.py` ofrece upload a copia interna, análisis, feedback y recomendación vía HTTP local. `ml.py` conserva baseline, dataset por hash y regresión logística NumPy. `cli.py` expone importación, análisis, feedback, métricas, recomendaciones y dashboard.

Flujo: `local file -> probe -> SQLite -> OpenCV features -> human feedback/metrics -> dataset hash -> baseline + holdout model -> model registry -> recommendation/export`.

No hay nube, microservicios, GPU, ejecución de Blender ni escritura en VLUX Video OS. La integración futura usa el contrato `contracts/creative-director.v0.2.schema.json`.
