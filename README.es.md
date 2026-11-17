# VLUX Studio OS

**Inteligencia creativa local para tomar mejores decisiones audiovisuales de negocio.**

<p>
  <a href="README.md">Read in English</a> ·
  <a href="https://vlux.com.mx">VLUX — eTransformation Partner</a>
</p>

![VLUX Studio OS](docs/assets/vlux-studio-banner.svg)

VLUX Studio OS es un sistema local en Python para analizar video autorizado, separar hechos observables de estimaciones heurísticas, capturar juicio humano, comparar versiones creativas y convertir todo eso en decisiones de producción revisables.

V0.5 introduce **VLUX Attention Lab V0.1**: una capa de análisis creativo determinista y CPU-only que explica su evidencia, declara sus límites y se niega a tratar “me gusta” como leads, ventas o prueba científica de viralidad.

> **Estado actual de entrenamiento**
>
> ```text
> NO_TRAINING_INSUFFICIENT_DATA
> ```
>
> Es intencional. Ningún modelo ha sido entrenado, promovido ni validado comercialmente.

## Novedades de V0.5

- **Attention Lab** — capas de gancho, narrativa, producción, valor comercial y resultados con confianza, cobertura y limitaciones explícitas.
- **Comparación A/B de cuatro capas** — hechos observados, estimaciones heurísticas, preferencias humanas y resultados comerciales reales nunca se fusionan en un puntaje único.
- **Registro de evaluación humana** — evaluaciones 1–5 con evaluador identificado; entradas anónimas y asistidas por IA se guardan pero se excluyen de la capa humana y del gate de entrenamiento.
- **Dataset Registry y Training Gate** — el entrenamiento sigue bloqueado hasta tener videos legítimos, etiquetas, registros comerciales y holdout por episodio.
- **Model Registry y rollback** — experimentos, métricas candidatas, promoción por humano nombrado y activación reversible.
- **Adaptadores de producción** — `manifest` JSON local y `ffmpeg_animatic` como placeholder CPU; sin GPU, sin pesos de modelos y sin servicios externos pagados.
- **Dashboard local ampliado** — biblioteca, gancho/timeline, A/B, evaluaciones, estado de aprendizaje, resultados comerciales, versiones de producción y recomendaciones recientes.
- **Piloto real** — EP011 comparado con EP021 usando copias locales autorizadas. Informe público: [`docs/V05_PILOT.md`](docs/V05_PILOT.md).

## El problema

Las empresas publican contenido, pero muchas veces no pueden explicar por qué una pieza consigue atención, guardados, conversaciones o interés comercial y otra no. Las visualizaciones por sí solas no explican el valor de negocio.

```text
VIDEO AUTORIZADO
   → HECHOS OBSERVADOS
   → ESTIMACIONES HEURÍSTICAS
   → PREFERENCIA HUMANA
   → RESULTADOS COMERCIALES
   → UNA RECOMENDACIÓN REVISABLE
```

El producto **no** afirma generar videos completos automáticamente, predecir viralidad ni reemplazar la revisión humana.

## Vista del producto

Las capturas son reales del dashboard V0.5, ejecutado con **datos sintéticos de demostración** (`DEMO-01`, `DEMO-02`, `DEMO-03`). No muestran medios de clientes, métricas privadas ni la base de producción.

![Dashboard V0.5](docs/assets/dashboard-v05.png)

*Vista general: biblioteca, estado del pipeline, gate de entrenamiento, recomendaciones recientes y estado comercial.*

![Attention Lab V0.5](docs/assets/dashboard-v05-attention.png)

*Attention Lab: puntuaciones estimadas, hechos del timeline, evidencia, limitaciones y formulario de evaluación humana.*

## El piloto: EP011 vs EP021

Se analizaron dos copias locales autorizadas con FFprobe/OpenCV. La comparación es un **benchmark entre episodios distintos**, no un experimento controlado: cambian tema, gancho y tratamiento visual, así que no permite afirmar causalidad.

| Hecho observado | EP011 | EP021 |
| --- | ---: | ---: |
| Duración | 22,67 s | 22,87 s |
| Cortes detectados | 11 | 4 |
| Cortes antes de 3 s | 1 | 0 |
| Plano medio | 1,89 s | 4,57 s |
| Movimiento global | 12,12 | 5,95 |
| Luminosidad media (0–255) | 81,76 | 50,06 |
| Contraste medio (0–255) | 66,01 | 40,75 |
| Muestras casi estáticas | 5,2 % | 15,5 % |

| Estimación heurística (0–100) | EP011 | EP021 | Confianza |
| --- | ---: | ---: | --- |
| Gancho | 90 | 69 | media |
| Narrativa | 90 | 90 | baja |
| Producción | 84 | 78 | media |
| Valor comercial (completitud del mensaje) | 90 | 90 | baja |
| Índice conjunto | 88 | 81 | baja |

Son estimaciones editoriales, no un modelo entrenado ni una predicción de viralidad. “Valor comercial” sólo significa que la metadata contiene audiencia, problema, solución y CTA; no es ingreso.

El contrato A/B devuelve:

```text
decision_status: HUMAN_REVIEW_AND_RESULTS_REQUIRED
human_preferences: NOT_AVAILABLE
commercial_results: NOT_COMPARABLE
automatic_winner: null
```

**Todavía no existe preferencia humana registrada.** Las notas visuales asistidas por IA están marcadas como no humanas y se excluyen. El primer cambio propuesto es introducir un cambio visual deliberado antes de 2 s en EP021, mantener todo lo demás constante y medir retención a 3 segundos cuando exista una medición real. Es una propuesta, no un resultado.

Los propios videos declaran su naturaleza: EP011 es una recreación 3D conceptual, no la interfaz de Autodesk; EP021 es un caso simulado con datos ficticios. Las copias usan `authorized_analysis_only` y son deliberadamente inelegibles para entrenamiento. Medios, hojas de contacto, bases de datos e informes privados permanecen locales y fuera de Git.

## Arquitectura y prácticas

![Arquitectura](docs/assets/architecture.svg)

![Flujo](docs/assets/workflow.svg)

```text
medio autorizado
   → hechos FFprobe / OpenCV
   → almacén de evidencia SQLite
   → estimaciones Attention Lab + evaluaciones humanas
   → comparación A/B por capas
   → recomendaciones
   → brief del Creative Director
   → adaptador de producción visual
   → análisis de calidad + registro de versiones
   → aprobación humana
```

La rama de entrenamiento está separada y bloqueada:

```text
Dataset Registry → Training Gate → Experimento → Evaluación → Model Registry → Promoción manual
```

No hay servicio cloud, credenciales de plataforma, dependencia de GPU, pesos de modelos, cola de render ni integración de escritura con VLUX Video OS.

Más información:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/ENGINEERING_PRACTICES.md`](docs/ENGINEERING_PRACTICES.md)
- [`docs/ML_METHODOLOGY.md`](docs/ML_METHODOLOGY.md)

## MSA-VLUX

El desarrollo utiliza MSA-VLUX 6.0.0 con átomos verificables, ownership, contratos, evidencia, validación, handoffs y ledger local. También aplica principios de coordinación inspirados en Concord. Concord no ejecutó directamente este repositorio.

## Estado de aprendizaje

```text
NO_TRAINING_INSUFFICIENT_DATA
```

Umbrales actuales del gate (`learning-gate.v0.1`):

| Requisito | Mínimo |
| --- | ---: |
| Videos autorizados elegibles | 12 |
| Episodios independientes | 4 |
| Evaluaciones humanas identificadas | 12 |
| Videos con evaluación humana | 4 |
| Registros comerciales legítimos | 5 |
| Clases de etiqueta | 2 |
| Episodios con etiquetas | 2 |
| Diseño de holdout | episodio completo |

El piloto real reporta `eligible_videos: 0` porque las copias son `authorized_analysis_only`. El entrenamiento sigue bloqueado; no se publican porcentajes de precisión ni mejoras comerciales inventadas.

## Referencia EP011

- **Tema:** Autodesk Fusion / Ingeniería de producto
- **Plataforma:** Instagram
- **Procedencia:** `USER_PROVIDED_SCREENSHOT`
- **Fecha de medición:** `UNKNOWN`
- **Verificación por API:** no realizada

| Métrica | Valor |
|---|---:|
| Visualizaciones | 5.468 |
| Espectadores | 4.389 |
| Reproducción promedio | 10 segundos |
| Me gusta | 176 |
| Comentarios | 25 |
| Compartidos | 51 |
| Guardados | 125 |
| Nuevos seguidores | 23 |
| Visitas al perfil | 11 |

Son observaciones de referencia, no prueba causal. Leads e ingresos: **no disponibles**. En V0.5 la publicación de EP011 se vincula al episodio, no a una versión exacta del archivo; el contrato A/B lo declara con `match_basis: episode`. La copia autorizada del piloto es una revisión tardía, así que las métricas de plataforma podrían no corresponder exactamente a ella.

## Inicio rápido en Windows

```powershell
git clone https://github.com/lilpne25-ui/VLUX-Studio-OS.git
cd VLUX-Studio-OS
.\start.ps1
```

Dashboard: <http://127.0.0.1:8765>

Verificación:

```powershell
.\verify.ps1
```

### Comandos V0.5 útiles

```powershell
python -m vlux_ci.cli attention 1
python -m vlux_ci.cli evaluate 1 --evaluator revisor --provenance human `
  --hook 4 --narrative 4 --production 4 --commercial 3 --cta 4 --clarity 4
python -m vlux_ci.cli ab --a 1 --b 2
python -m vlux_ci.cli learning-status
python -m vlux_ci.cli dataset-register
python -m vlux_ci.cli production-plan --brief brief.json --adapter manifest
```

Validar los esquemas públicos contra exportaciones locales:

```powershell
python scripts\validate_contracts.py --defaults
```

Las versiones, productores e invariantes están en [`contracts/README.md`](contracts/README.md).

## Estado y roadmap

Implementado: V0.1 dataset, V0.2 inteligencia creativa, V0.3 dashboard funcional, V0.4 analítica comercial separada por plataforma, V0.5 Attention Lab, A/B por capas, Dataset Registry, Training Gate, Model Registry y versiones locales de producción.

Planeado: registrar evaluaciones humanas reales, adjuntar resultados comerciales verificados, ejecutar experimentos de una sola variable, ampliar el dataset autorizado hasta pasar el gate, validar un modelo con holdout independiente e integrar recomendaciones con VLUX Video OS mediante contratos versionados.

El trabajo planeado no se presenta como capacidad implementada.

## Sobre VLUX

**VLUX — eTransformation Partner**

> “No adaptamos tu empresa al software. Adaptamos la tecnología a la forma en que realmente opera tu empresa.”

- Sitio oficial: <https://vlux.com.mx>
- GitHub: <https://github.com/lilpne25-ui>

No se listan otras redes porque no fueron confirmadas independientemente durante esta publicación.

## Licencia

No se ha asignado una licencia open source. Los derechos permanecen en VLUX y el propietario del proyecto. No asumas permiso de copia, redistribución o uso comercial.
