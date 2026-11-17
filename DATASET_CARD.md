# Dataset Card

**Nombre:** VLUX Creative Intelligence Dataset
**Versión de esquema:** `0.5`
**Propósito:** evaluar señales audiovisuales, estimaciones heurísticas, preferencias humanas y resultados comerciales observados; no inferir clientes potenciales ni ventas a partir de likes.

## Composición

- videos autorizados con hash SHA-256, permiso, procedencia y tipo de fuente;
- análisis FFprobe/OpenCV y observaciones con timestamp;
- contratos Attention Lab (`attention-lab.v0.1`);
- evaluaciones humanas 1–5 con evaluador identificado;
- comparaciones A/B por capas (`ab-comparison.v0.1`);
- publicaciones, métricas de plataforma y registros comerciales separados;
- versiones de producción locales y su historial.

## Etiquetas

Las etiquetas válidas provienen de personas identificadas. Evaluaciones anónimas y asistidas por IA se almacenan, pero se excluyen de la capa humana y del Training Gate. No se generan etiquetas automáticas a partir de las estimaciones.

## Elegibilidad para entrenamiento

Sólo videos con permiso `authorized`, `owned`, `synthetic` o `public_domain`. Las copias de piloto usan `authorized_analysis_only` y son inelegibles por diseño. Los datos sintéticos o demo nunca se mezclan con decisiones reales de entrenamiento.

## Riesgos y mitigaciones

- **Sesgo de evaluador:** evaluadores identificados y dimensiones explícitas.
- **Proxies visuales imperfectos:** se declaran como estimaciones con cobertura y limitaciones.
- **Fuga por versiones relacionadas:** holdout por episodio completo.
- **Métricas duplicadas:** deduplicación por métrica y publicación.
- **Causalidad espuria:** resultados observacionales nunca se presentan como efecto causal.

## Privacidad

No cargar material sin autorización. No publicar la base, los medios, las hojas de contacto, los informes privados ni credenciales. El repositorio público sólo contiene código, esquemas y documentación sanitizada.
