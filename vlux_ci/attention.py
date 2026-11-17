from __future__ import annotations

"""VLUX Attention Lab v0.1.

Deterministic, explainable estimates built on FFprobe/OpenCV facts plus optional
human-reviewed text. Nothing in this module predicts virality, sales, or a
platform outcome. Every score is an estimate with explicit evidence, coverage
and limitations.
"""

import json
import math
from datetime import datetime, timezone
from typing import Any

from .analyzer import analyze
from .db import json_dumps

CONTRACT_VERSION = "attention-lab.v0.1"
ANALYZER_VERSION = "0.5.0"

DIMENSION_WEIGHTS = {
    "hook": 0.30,
    "narrative": 0.25,
    "production": 0.25,
    "commercial": 0.20,
}

_TEXT_KEYS = ("hook", "business_problem", "solution_presented", "cta",
              "target_audience", "transcript_text", "human_notes", "script")

CONSEQUENCE_MARKERS = (
    "hora", "costo", "coste", "pierde", "pérdida", "perdida", "retraso",
    "error", "rehacer", "redibujar", "déficit", "deficit", "riesgo",
    "paro", "margen", "reproceso", "retrabajo",
)
EVIDENCE_MARKERS = (
    "evidencia", "historial", "reconstru", "demo", "resultado", "métrica",
    "metrica", "dato", "ejemplo", "antes", "después", "despues", "preview",
    "dashboard", "simulación", "simulacion", "captura",
)
PROBLEM_MARKERS = (
    "problema", "no puedes", "no puede", "difícil", "dificil", "riesgo",
    "error", "pérdida", "perdida", "falta", "capacidad",
)
SOLUTION_MARKERS = (
    "solución", "solucion", "flujo", "sistema", "automatiz", "capacidad",
    "planifica", "integra", "trazabilidad", "control",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _band(value: Any, ideal_low: float, ideal_high: float,
          hard_low: float, hard_high: float) -> float | None:
    """1.0 inside the preferred band, falling linearly to 0 outside hard limits."""
    number = _num(value)
    if number is None:
        return None
    if ideal_low <= number <= ideal_high:
        return 1.0
    if number < ideal_low:
        if number <= hard_low:
            return 0.0
        return _clamp((number - hard_low) / (ideal_low - hard_low))
    if number >= hard_high:
        return 0.0
    return _clamp((hard_high - number) / (hard_high - ideal_high))


def _component(key: str, label: str, value: Any, unit: str | None,
               score: float | None, weight: float, evidence: str,
               source: str = "ffmpeg+opencv") -> dict:
    return {
        "key": key, "label": label, "value": _round(_num(value)),
        "unit": unit, "score": None if score is None else round(score, 3),
        "weight": weight, "evidence": evidence, "source": source,
    }


def _estimate(components: list[dict], *, confidence: str | None = None,
              extra_limitations: list[str] | None = None) -> dict:
    available = [c for c in components if c["score"] is not None]
    weight = sum(c["weight"] for c in available)
    coverage = weight / sum(c["weight"] for c in components) if components else 0.0
    if not available or weight <= 0:
        return {
            "score": None, "band": "not_assessable", "confidence": "none",
            "coverage": 0.0, "components": components,
            "evidence": ["No hay suficientes hechos o texto revisado para estimar."],
            "limitations": ["Sin evidencia suficiente; no se imputa un valor."],
        }
    normalized = sum((c["score"] or 0.0) * c["weight"] for c in available) / weight
    # Deliberate compression: heuristic extremes are not scientific certainty.
    score = round(10 + 80 * normalized)
    band = "high_estimate" if score >= 75 else "mid_estimate" if score >= 55 else "low_estimate"
    inferred_confidence = confidence or ("low" if coverage < 0.75 else "medium")
    if inferred_confidence == "medium" and coverage < 0.85:
        inferred_confidence = "low"
    return {
        "score": score, "band": band, "confidence": inferred_confidence,
        "coverage": round(coverage, 3), "components": components,
        "evidence": [f"{c['label']}: {c['evidence']}" for c in available],
        "limitations": [
            "Estimación heurística; no es una predicción científica de viralidad.",
            "Los pesos son una política editorial explícita, no un modelo entrenado.",
        ] + (extra_limitations or []),
    }


def _has_marker(text: str, markers: tuple[str, ...]) -> str | None:
    lowered = text.lower()
    for marker in markers:
        if marker in lowered:
            return marker
    return None


def _element(status: str, source: str, evidence: str, text: str | None = None) -> dict:
    item = {"status": status, "source": source, "evidence": evidence}
    if text:
        compact = " ".join(str(text).split())
        item["excerpt"] = compact[:180]
    return item


def _text_source(video: dict, analysis: dict) -> dict:
    provenance = (video.get("text_provenance") or "").strip()
    text = " ".join(str(video.get(key) or "") for key in _TEXT_KEYS).strip()
    human_confirmed = provenance.upper().startswith("HUMAN") or provenance.upper() in {
        "USER_PROVIDED", "OWNER_REVIEWED", "MANUAL",
    }
    ai_assisted = "AI" in provenance.upper() or "ASSISTED" in provenance.upper()
    return {
        "text_provenance": provenance or "none",
        "available": bool(text),
        "human_confirmed": human_confirmed,
        "ai_assisted": ai_assisted,
        "verbatim_transcript": False if provenance else False,
        "text": text,
    }


def _hook(video: dict, facts: dict, text_source: dict) -> dict:
    first = facts.get("first_frame") or {}
    brightness = first.get("brightness")
    contrast = first.get("contrast")
    first_motion = facts.get("first_3s_motion")
    cadence = facts.get("first_3s_cut_count")
    if cadence is not None:
        cadence = int(cadence)
        cadence_score = 1.0 if 1 <= cadence <= 3 else 0.75 if cadence == 4 else 0.5 if cadence == 5 else 0.3
    else:
        cadence_score = None
    hook_text = str(video.get("hook") or "").strip()
    if hook_text:
        text_score = 0.65
        if "?" in hook_text or "¿" in hook_text:
            text_score += 0.2
        if 12 <= len(hook_text) <= 90:
            text_score += 0.15
        text_score = _clamp(text_score)
        text_evidence = f"hook declarado: «{hook_text[:120]}»"
        text_source_name = "video_metadata"
    else:
        text_score = 0.25 if text_source["available"] else None
        text_evidence = "Sin hook textual declarado; sólo se evalúan señales visuales."
        text_source_name = "missing"
    components = [
        _component("first_frame_brightness", "Luminosidad del primer fotograma",
                   brightness, "0-255", _band(brightness, 45, 160, 5, 235), 0.20,
                   f"{_round(brightness)} de luminosidad media en el primer muestreo"),
        _component("first_frame_contrast", "Contraste del primer fotograma",
                   contrast, "0-255", _band(contrast, 35, 110, 5, 180), 0.15,
                   f"{_round(contrast)} de desviación estándar en el primer muestreo"),
        _component("first_3s_motion", "Cambio visual en los primeros 3 s",
                   first_motion, "diff media", _band(first_motion, 2, 20, 0, 40), 0.20,
                   f"{_round(first_motion)} de diferencia media entre muestras"),
        _component("first_3s_cadence", "Cortes relevantes antes de 3 s",
                   cadence, "cortes", cadence_score, 0.20,
                   f"{cadence if cadence is not None else 'sin dato'} cortes detectados antes de 3 s"),
        _component("hook_text", "Claridad del hook textual",
                   len(hook_text) if hook_text else None, "caracteres", text_score, 0.25,
                   text_evidence, text_source_name),
    ]
    limitations = []
    if not text_source["human_confirmed"]:
        limitations.append(
            "El hook textual no está confirmado por una persona; si existe, proviene de metadata o notas asistidas."
        )
    return _estimate(components, extra_limitations=limitations)


def _narrative(video: dict, text_source: dict) -> dict:
    text = text_source["text"]
    problem_field = str(video.get("business_problem") or "").strip()
    solution_field = str(video.get("solution_presented") or "").strip()
    cta_field = str(video.get("cta") or "").strip()
    transcript = " ".join(str(video.get(key) or "") for key in ("transcript_text", "human_notes", "script")).strip()

    problem_marker = _has_marker(text, PROBLEM_MARKERS)
    consequence_marker = _has_marker(text, CONSEQUENCE_MARKERS)
    evidence_marker = _has_marker(transcript or text, EVIDENCE_MARKERS)

    elements = {
        "problem": _element(
            "PRESENT_IN_METADATA" if problem_field else "INFERRED_FROM_TEXT" if problem_marker else "NOT_AVAILABLE",
            "video_metadata" if problem_field else "reviewed_text" if problem_marker else "none",
            f"business_problem declarado: {problem_field[:140]}" if problem_field else (
                f"marcador textual: «{problem_marker}»" if problem_marker else "sin problema explícito"
            ),
            problem_field or None,
        ),
        "consequence": _element(
            "INFERRED_FROM_TEXT" if consequence_marker else "NOT_AVAILABLE",
            "reviewed_text" if consequence_marker else "none",
            f"marcador de consecuencia: «{consequence_marker}»" if consequence_marker else "sin consecuencia explícita",
        ),
        "solution": _element(
            "PRESENT_IN_METADATA" if solution_field else "INFERRED_FROM_TEXT" if _has_marker(text, SOLUTION_MARKERS) else "NOT_AVAILABLE",
            "video_metadata" if solution_field else "reviewed_text" if _has_marker(text, SOLUTION_MARKERS) else "none",
            f"solution_presented declarado: {solution_field[:140]}" if solution_field else (
                f"marcador de solución: «{_has_marker(text, SOLUTION_MARKERS)}»" if _has_marker(text, SOLUTION_MARKERS) else "sin solución explícita"
            ),
            solution_field or None,
        ),
        "evidence": _element(
            "INFERRED_FROM_TEXT" if evidence_marker else "NOT_AVAILABLE",
            "reviewed_text" if evidence_marker else "none",
            f"marcador de evidencia: «{evidence_marker}»" if evidence_marker else "sin evidencia textual verificable",
        ),
        "cta": _element(
            "PRESENT_IN_METADATA" if cta_field else "NOT_AVAILABLE",
            "video_metadata" if cta_field else "none",
            f"cta declarado: «{cta_field[:140]}»" if cta_field else "sin CTA explícito",
            cta_field or None,
        ),
    }
    present = sum(1 for item in elements.values() if item["status"] != "NOT_AVAILABLE")
    order = ["problem", "consequence", "solution", "evidence", "cta"]
    ordered = 0
    for name in order:
        if elements[name]["status"] == "NOT_AVAILABLE":
            break
        ordered += 1

    narrative_text = " ".join(str(video.get(key) or "") for key in
                               ("business_problem", "solution_presented", "cta",
                                "transcript_text", "human_notes", "script")).strip()
    if not narrative_text:
        score = None
    else:
        base = 10 + 80 * (present / 5)
        order_bonus = 6 if ordered == 5 else 0
        score = min(90, round(base + order_bonus))
    confidence = "medium" if text_source["human_confirmed"] else "low"
    result = {
        "score": score,
        "band": "not_assessable" if score is None else "high_estimate" if score >= 75 else "mid_estimate" if score >= 55 else "low_estimate",
        "confidence": confidence if score is not None else "none",
        "coverage": round(present / 5, 3),
        "elements": elements,
        "ordered_elements": ordered,
        "text_source": {
            "provenance": text_source["text_provenance"],
            "human_confirmed": text_source["human_confirmed"],
            "ai_assisted": text_source["ai_assisted"],
            "verbatim_transcript": False,
        },
        "evidence": [
            f"{name}: {item['status']}" for name, item in elements.items()
        ],
        "limitations": [
            "La estructura narrativa se infiere de metadata y texto revisado, no de OCR/ASR automático.",
            "Sin transcripción verificable, la presencia de un elemento no demuestra claridad ante la audiencia.",
        ],
    }
    if not text_source["human_confirmed"]:
        result["limitations"].append(
            "El texto disponible es metadata o notas asistidas por IA; una persona debe confirmarlo."
        )
    return result


def _production(video: dict, facts: dict) -> dict:
    avg_shot = facts.get("avg_shot_s")
    freeze = facts.get("freeze_ratio")
    contrast = facts.get("contrast_mean")
    silence = facts.get("silence_ratio")
    has_audio = 1.0 if facts.get("has_audio") else 0.4
    if _num(avg_shot) is None:
        rhythm_score = None
    else:
        rhythm_score = _band(avg_shot, 1.5, 5.0, 0.2, 14.0)
    if _num(freeze) is None:
        freeze_score = None
    else:
        freeze_value = _num(freeze) or 0.0
        freeze_score = 1.0 if freeze_value <= 0.05 else 0.7 if freeze_value <= 0.12 else 0.4 if freeze_value <= 0.25 else 0.15
    if _num(silence) is None:
        silence_score = None
    else:
        silence_value = _num(silence) or 0.0
        silence_score = 1.0 if silence_value <= 0.10 else 0.75 if silence_value <= 0.20 else 0.4 if silence_value <= 0.35 else 0.15
    components = [
        _component("rhythm", "Ritmo por duración media de plano", avg_shot, "s",
                   rhythm_score, 0.22,
                   f"{_round(avg_shot)} s de plano medio; los cortes se detectan por diferencia de frame"),
        _component("freeze", "Proporción de muestras casi estáticas", freeze, "ratio",
                   freeze_score, 0.22,
                   f"{_round(freeze)} de muestras con diferencia < 1.0"),
        _component("contrast", "Contraste global", contrast, "0-255",
                   _band(contrast, 35, 105, 5, 180), 0.18,
                   f"{_round(contrast)} de contraste medio"),
        _component("silence", "Silencio detectable", silence, "ratio",
                   silence_score, 0.18,
                   f"{_round(silence)} del video por debajo de -35 dB durante >= 1 s"),
        _component("audio", "Presencia de pista de audio", 1 if facts.get("has_audio") else 0,
                   "bool", has_audio, 0.10,
                   "pista de audio presente" if facts.get("has_audio") else "sin pista de audio"),
        _component("subtitle_readability", "Legibilidad de subtítulos", None, None,
                   None, 0.10,
                   "OCR no disponible; no se estima legibilidad de texto en pantalla.",
                   "unavailable"),
    ]
    return _estimate(components, extra_limitations=[
        "No se evalúa calidad estética, realismo 3D ni intención de cámara.",
        "La legibilidad de subtítulos requiere OCR o revisión humana y queda fuera de esta estimación.",
        "Un plano estático puede ser una decisión narrativa correcta; la métrica no prueba lo contrario.",
    ])


def _commercial(video: dict, text_source: dict, results: dict) -> dict:
    audience = str(video.get("target_audience") or "").strip()
    problem = str(video.get("business_problem") or "").strip()
    solution = str(video.get("solution_presented") or "").strip()
    cta = str(video.get("cta") or "").strip()
    fields = {
        "target_audience": audience,
        "business_pain": problem,
        "solution_relevance": solution,
        "cta": cta,
    }
    present = sum(1 for value in fields.values() if value)
    if present == 0:
        score = None
    else:
        score = round(10 + 80 * (present / 4))
    commercial_signal = results.get("commercial_signal", {})
    result = {
        "score": score,
        "band": "not_assessable" if score is None else "high_estimate" if score >= 75 else "mid_estimate" if score >= 55 else "low_estimate",
        "confidence": "medium" if text_source["human_confirmed"] else "low",
        "coverage": round(present / 4, 3),
        "dimensions": {
            name: {
                "status": "PRESENT_IN_METADATA" if value else "NOT_AVAILABLE",
                "value": value[:180] if value else None,
            }
            for name, value in fields.items()
        },
        "evidence": [
            f"{name}: {'declarado' if value else 'no disponible'}" for name, value in fields.items()
        ],
        "commercial_signal": commercial_signal,
        "limitations": [
            "La presencia de un campo no demuestra relevancia comercial ni demanda.",
            "No se infieren leads, reuniones, ventas ni ingresos a partir de likes o visualizaciones.",
            "La evaluación comercial humana es una preferencia, no un resultado de negocio.",
        ],
    }
    return result


def _results(con, video: dict) -> dict:
    rows = [dict(r) for r in con.execute(
        "select * from publications where video_id=? or episode=? order by id desc",
        (video["id"], video["episode"]),
    )]
    publications = []
    observed_metrics = 0
    commercial_records = 0
    commercial_names = ("leads", "qualified_leads", "meetings", "proposals", "closed_won", "conversations")
    for publication in rows:
        metrics = [dict(r) for r in con.execute(
            "select metric_name,metric_value,status,provenance,measured_at from platform_metrics where publication_id=? order by metric_name,id",
            (publication["id"],),
        )]
        # Historical imports can contain repeated measurements of the same metric.
        # Keep the latest row per metric name; never sum duplicates.
        unique_metrics = {metric["metric_name"]: metric for metric in metrics}
        item = {
            "publication_id": publication["id"],
            "episode": publication["episode"],
            "platform": publication["platform"],
            "provenance": publication["provenance"],
            "measured_at": publication["measured_at"],
            "publication_status": publication["publication_status"],
            "match_basis": "video_id" if publication["video_id"] == video["id"] else "episode",
            "match_note": (
                "Métricas vinculadas al video exacto."
                if publication["video_id"] == video["id"] else
                "Métricas del episodio, no necesariamente de esta copia o versión."
            ),
            "metrics": {},
        }
        for metric in unique_metrics.values():
            name = metric["metric_name"]
            value = _num(metric["metric_value"])
            status = metric["status"] if value is not None else "NOT_AVAILABLE"
            item["metrics"][name] = {
                "value": value, "status": status,
                "provenance": metric["provenance"],
                "measured_at": metric["measured_at"],
            }
            if value is not None:
                observed_metrics += 1
            if name in commercial_names and value is not None and status != "NOT_AVAILABLE":
                commercial_records += 1
        publications.append(item)
    likes = sum(
        p["metrics"].get("likes", {}).get("value") or 0 for p in publications
    )
    lead_values = [p["metrics"]["leads"]["value"] for p in publications
                   if "leads" in p["metrics"] and p["metrics"]["leads"]["value"] is not None]
    leads = sum(lead_values) if lead_values else None
    return {
        "status": "AVAILABLE_PARTIAL" if observed_metrics else "NOT_AVAILABLE",
        "publications": publications,
        "observed_metrics": observed_metrics,
        "commercial_records": commercial_records,
        "commercial_signal": {
            "leads": leads,
            "status": "OBSERVED" if commercial_records else "NOT_AVAILABLE",
            "note": "Likes, saves, shares and followers are not sales or qualified leads.",
        },
        "likes_observed": likes,
        "likes_are_not_sales": True,
        "guardrails": [
            "Resultados de plataforma y estimaciones creativas son capas distintas.",
            "Métricas ausentes permanecen NOT_AVAILABLE; no se imputan.",
            "No se declara causalidad a partir de una publicación.",
        ],
    }


def _recommendations(video: dict, facts: dict, hook: dict, narrative: dict,
                     production: dict, commercial: dict, results: dict) -> list[dict]:
    items: list[dict] = []
    first = facts.get("first_frame") or {}

    def add(priority: str, dimension: str, action: str, reason: str,
            evidence: list[str], test_metric: str = "retention_3s") -> None:
        items.append({
            "priority": priority, "dimension": dimension, "status": "PROPOSAL",
            "action": action, "reason": reason, "evidence": evidence,
            "test_metric": test_metric,
        })

    brightness = _num(first.get("brightness"))
    if brightness is not None and brightness < 45:
        add("medium", "hook",
            "Probar un primer fotograma más luminoso o con mayor contraste antes de publicar.",
            "El primer muestreo es oscuro; la legibilidad en un feed móvil puede ser baja.",
            [f"Luminosidad del primer fotograma: {_round(brightness)}/255"],
            "retention_3s")
    if _num(facts.get("first_3s_cut_count")) == 0 and (_num(facts.get("duration_s")) or 0) > 6:
        add("high", "hook",
            "Introducir un cambio visual deliberado antes de 2 s (corte, reveal o transición).",
            "No se detectaron cortes en los primeros 3 s; el inicio puede leerse como estático.",
            [f"first_3s_cut_count: {facts.get('first_3s_cut_count')}",
             f"duración: {_round(facts.get('duration_s'))} s"],
            "retention_3s")
    if not str(video.get("hook") or "").strip():
        add("high", "hook",
            "Escribir y declarar un hook de una frase con problema o consecuencia.",
            "No hay hook textual que permita evaluar claridad ni consistencia.",
            ["hook: NOT_AVAILABLE"], "retention_3s")
    freeze = _num(facts.get("freeze_ratio"))
    if freeze is not None and freeze > 0.12:
        add("medium", "production",
            "Reducir el tramo casi estático o justificarlo con una intención narrativa explícita.",
            "La proporción de muestras estáticas supera el umbral editorial.",
            [f"freeze_ratio: {_round(freeze)}"], "avg_watch_time_s")
    avg_shot = _num(facts.get("avg_shot_s"))
    if avg_shot is not None and avg_shot > 6:
        add("medium", "production",
            "Aumentar la cadencia con un corte o movimiento que explique el cambio, no por decoración.",
            "El plano medio es largo para el formato vertical corto.",
            [f"avg_shot_s: {_round(avg_shot)}"], "avg_watch_time_s")
    silence = _num(facts.get("silence_ratio"))
    if silence is not None and silence > 0.15:
        add("medium", "production",
            "Revisar silencios y sincronización de narración/CTA.",
            "El silencio detectable ocupa una parte relevante del video.",
            [f"silence_ratio: {_round(silence)}"], "avg_watch_time_s")

    missing = [name for name, item in narrative.get("elements", {}).items()
               if item.get("status") == "NOT_AVAILABLE"]
    if missing:
        add("high", "narrative",
            "Completar la estructura narrativa: " + ", ".join(missing) + ".",
            "Faltan elementos que permiten entender problema, consecuencia, solución, evidencia o acción.",
            [f"elementos ausentes: {', '.join(missing)}"], "saves")
    if not str(video.get("cta") or "").strip():
        add("high", "commercial",
            "Definir un CTA concreto y medible (palabra clave, conversación o diagnóstico).",
            "Sin CTA declarado no se puede separar interés de intención.",
            ["cta: NOT_AVAILABLE"], "qualified_leads")
    if results.get("commercial_signal", {}).get("status") != "OBSERVED":
        add("medium", "results",
            "Registrar leads calificados, reuniones o ventas con fecha y procedencia; no usar likes como ventas.",
            "No hay resultados comerciales verificables para este video o episodio.",
            ["commercial_signal: NOT_AVAILABLE"], "qualified_leads")
    add("medium", "experiment",
        "Diseñar un A/B de una sola variable y mantener el resto del video estable.",
        "La comparación A/B sólo es interpretable si se cambia una dimensión por prueba.",
        ["Este sistema no declara ganador sin preferencia humana o resultado comercial."],
        "retention_3s")
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda item: priority_order.get(item["priority"], 3))
    return items


def _overall(hook: dict, narrative: dict, production: dict, commercial: dict) -> dict:
    dimensions = {
        "hook": hook.get("score"),
        "narrative": narrative.get("score"),
        "production": production.get("score"),
        "commercial": commercial.get("score"),
    }
    available = {k: v for k, v in dimensions.items() if v is not None}
    weight = sum(DIMENSION_WEIGHTS[k] for k in available)
    if not available or weight <= 0:
        return {
            "score": None, "band": "not_assessable", "confidence": "none",
            "coverage": 0.0, "dimensions": dimensions,
            "status": "ESTIMATE_NOT_VALIDATED",
            "explanation": "No hay dimensiones suficientes para una estimación conjunta.",
        }
    score = round(sum(v * DIMENSION_WEIGHTS[k] for k, v in available.items()) / weight)
    return {
        "score": score,
        "band": "high_estimate" if score >= 75 else "mid_estimate" if score >= 55 else "low_estimate",
        "confidence": "low",
        "coverage": round(weight, 3),
        "dimensions": dimensions,
        "status": "ESTIMATE_NOT_VALIDATED",
        "explanation": (
            "Índice editorial ponderado de señales observables y texto revisado. "
            "No es una predicción de viralidad, ventas ni retención real."
        ),
    }


def ensure_analysis(con, video_id: int) -> dict:
    row = con.execute("select * from videos where id=?", (video_id,)).fetchone()
    if not row:
        raise ValueError("video_not_found")
    analysis = con.execute(
        "select * from analyses where video_id=? order by id desc limit 1", (video_id,)
    ).fetchone()
    if analysis:
        return dict(analysis)
    objective, estimated, observations = analyze(row["file_path"])
    con.execute(
        "insert into analyses(video_id,analyzer_version,objective_json,aesthetic_json) values(?,?,?,?)",
        (video_id, ANALYZER_VERSION, json_dumps(objective), json_dumps(estimated)),
    )
    for item in observations:
        con.execute(
            "insert into observations(video_id,start_s,end_s,severity,category,message,recommendation,evidence_json) values(?,?,?,?,?,?,?,?)",
            (video_id, item["start_s"], item["end_s"], item["severity"], item["category"],
             item["message"], item["recommendation"], json_dumps(objective)),
        )
    con.commit()
    return dict(con.execute(
        "select * from analyses where video_id=? order by id desc limit 1", (video_id,)
    ).fetchone())


def analyze_attention(con, video_id: int, persist: bool = True) -> dict:
    video_row = con.execute("select * from videos where id=?", (video_id,)).fetchone()
    if not video_row:
        raise ValueError("video_not_found")
    video = dict(video_row)
    analysis = ensure_analysis(con, video_id)
    facts = json.loads(analysis["objective_json"])
    text_source = _text_source(video, analysis)
    hook = _hook(video, facts, text_source)
    narrative = _narrative(video, text_source)
    production = _production(video, facts)
    results = _results(con, video)
    commercial = _commercial(video, text_source, results)
    recommendations = _recommendations(video, facts, hook, narrative, production, commercial, results)
    overall = _overall(hook, narrative, production, commercial)
    first_change = next((r for r in recommendations if r["dimension"] != "experiment"), recommendations[-1])
    contract = {
        "contract_version": CONTRACT_VERSION,
        "analyzer_version": ANALYZER_VERSION,
        "status": "ESTIMATE_ONLY_NOT_VALIDATED",
        "evaluated_at": _now(),
        "video": {
            "id": video["id"], "episode": video["episode"], "version": video["version"],
            "duration_s": _round(video.get("duration_s")),
            "resolution": f"{video.get('width')}x{video.get('height')}",
            "source_kind": video.get("source_kind"),
            "permission_status": video.get("permission_status"),
            "file_hash": video.get("file_hash"),
        },
        "facts": {
            "source": "ffprobe+opencv",
            "analysis_id": analysis["id"],
            "duration_s": _round(facts.get("duration_s")),
            "fps": _round(facts.get("fps")),
            "width": facts.get("width"), "height": facts.get("height"),
            "has_audio": facts.get("has_audio"),
            "cut_count": facts.get("cut_count"),
            "cut_times": facts.get("cut_times") or [],
            "first_3s_cut_count": facts.get("first_3s_cut_count"),
            "avg_shot_s": _round(facts.get("avg_shot_s")),
            "motion_mean": _round(facts.get("motion_mean")),
            "motion_mean_full": _round(facts.get("motion_mean_full")),
            "first_3s_motion": _round(facts.get("first_3s_motion")),
            "first_second_motion": _round(facts.get("first_second_motion")),
            "first_second_brightness": _round(facts.get("first_second_brightness")),
            "sample_count": facts.get("sample_count"),
            "brightness_mean": _round(facts.get("brightness_mean")),
            "contrast_mean": _round(facts.get("contrast_mean")),
            "edge_density_mean": _round(facts.get("edge_density_mean")),
            "edge_density_first3s": _round(facts.get("edge_density_first3s")),
            "lower_third_edge_density_mean": _round(facts.get("lower_third_edge_density_mean")),
            "freeze_ratio": _round(facts.get("freeze_ratio")),
            "black_ratio": _round(facts.get("black_ratio")),
            "silence_ratio": _round(facts.get("silence_ratio")),
            "silence_total_s": _round(facts.get("silence_total_s")),
            "first_frame": facts.get("first_frame"),
            "timeline": facts.get("timeline") or [],
            "limitations": [
                "Los cortes son diferencias de frame muestreadas; no son un shot detector semántico.",
                "La densidad de bordes es un proxy de complejidad visual, no de claridad.",
                "OCR/ASR no están disponibles; no se simula texto en pantalla.",
            ],
        },
        "text_source": {
            "provenance": text_source["text_provenance"],
            "available": text_source["available"],
            "human_confirmed": text_source["human_confirmed"],
            "ai_assisted": text_source["ai_assisted"],
            "verbatim_transcript": False,
        },
        "hook": hook,
        "narrative": narrative,
        "production": production,
        "commercial_value": commercial,
        "results": results,
        "overall": overall,
        "recommendations": recommendations,
        "first_change": first_change,
        "limitations": [
            "Attention Lab V0.1 es heurístico y determinista; no hay modelo predictivo entrenado.",
            "Las estimaciones no sustituyen preferencia humana, resultados de plataforma ni resultados comerciales.",
            "No se usan pesos, prompts ni salidas derivadas de Higgsfield.",
            "La evidencia visual se calcula en CPU; no se usó GPU.",
        ],
    }
    if persist:
        con.execute(
            "insert into attention_analyses(video_id,analyzer_version,contract_version,facts_json,hook_json,narrative_json,production_json,commercial_json,results_json,recommendations_json,overall_json) values(?,?,?,?,?,?,?,?,?,?,?)",
            (video_id, ANALYZER_VERSION, CONTRACT_VERSION, json_dumps(contract["facts"]),
             json_dumps(hook), json_dumps(narrative), json_dumps(production),
             json_dumps(commercial), json_dumps(results), json_dumps(recommendations),
             json_dumps(overall)),
        )
        con.commit()
        contract["attention_id"] = con.execute("select last_insert_rowid()").fetchone()[0]
    return contract


def latest_attention(con, video_id: int) -> dict | None:
    row = con.execute(
        "select * from attention_analyses where video_id=? order by id desc limit 1", (video_id,)
    ).fetchone()
    if not row:
        return None
    video_row = con.execute("select * from videos where id=?", (video_id,)).fetchone()
    video = dict(video_row) if video_row else {}
    recommendations = json.loads(row["recommendations_json"])
    first_change = next(
        (item for item in recommendations if item.get("dimension") != "experiment"),
        recommendations[-1] if recommendations else None,
    )
    return {
        "attention_id": row["id"],
        "contract_version": row["contract_version"],
        "analyzer_version": row["analyzer_version"],
        "status": "ESTIMATE_ONLY_NOT_VALIDATED",
        "evaluated_at": row["created_at"],
        "created_at": row["created_at"],
        "video": {
            "id": video.get("id"), "episode": video.get("episode"),
            "version": video.get("version"),
            "duration_s": _round(video.get("duration_s")),
            "resolution": f"{video.get('width')}x{video.get('height')}",
            "source_kind": video.get("source_kind"),
            "permission_status": video.get("permission_status"),
            "file_hash": video.get("file_hash"),
        },
        "facts": json.loads(row["facts_json"]),
        "hook": json.loads(row["hook_json"]),
        "narrative": json.loads(row["narrative_json"]),
        "production": json.loads(row["production_json"]),
        "commercial_value": json.loads(row["commercial_json"]),
        "results": json.loads(row["results_json"]),
        "recommendations": recommendations,
        "first_change": first_change,
        "overall": json.loads(row["overall_json"]),
    }


def results_for_video(con, video: dict) -> dict:
    """Public accessor for the results layer, used by the A/B comparator."""
    return _results(con, video)


def attention_summary(contract: dict) -> dict:
    """Compact, dashboard-safe projection of an attention contract."""
    facts = contract.get("facts", {})
    return {
        "attention_id": contract.get("attention_id"),
        "contract_version": contract.get("contract_version"),
        "evaluated_at": contract.get("evaluated_at"),
        "overall": contract.get("overall", {}).get("score"),
        "hook": contract.get("hook", {}).get("score"),
        "narrative": contract.get("narrative", {}).get("score"),
        "production": contract.get("production", {}).get("score"),
        "commercial": contract.get("commercial_value", {}).get("score"),
        "confidence": contract.get("overall", {}).get("confidence"),
        "cut_count": facts.get("cut_count"),
        "first_3s_cut_count": facts.get("first_3s_cut_count"),
        "avg_shot_s": facts.get("avg_shot_s"),
        "freeze_ratio": facts.get("freeze_ratio"),
        "status": contract.get("status"),
    }
