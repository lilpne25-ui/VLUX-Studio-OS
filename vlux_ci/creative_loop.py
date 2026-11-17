from __future__ import annotations

"""VLUX Studio OS V0.6 — Creative Feedback Loop.

This module adds a version-aware creative loop on top of V0.5 without changing
the V0.5 contracts or the training gate. It deliberately separates:

* observed audiovisual facts;
* heuristic interpretations and estimated impact;
* human evaluations and approvals;
* commercial metrics tied to an exact episode version.

Nothing here renders with a GPU, calls an external service, writes into a
Claude Code/Codex workspace, publishes a video, or promotes a model.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .attention import analyze_attention, latest_attention
from .db import json_dumps, sha256_file
from .probe import probe

CONTRACT_CREATIVE_REVIEW = "creative-review.v0.1"
CONTRACT_VISUAL_DEFECTS = "visual-defects.v0.1"
CONTRACT_RECOMMENDED_CHANGES = "recommended-changes.v0.1"
CONTRACT_PRODUCTION_BRIEF = "production-brief.v0.1"
CONTRACT_EPISODE_VERSION = "episode-version.v0.1"
CONTRACT_HUMAN_APPROVAL = "human-approval.v0.1"
CONTRACT_HUMAN_EVALUATION = "human-evaluation.v0.1"
CONTRACT_PERFORMANCE_RECORD = "performance-record.v0.1"
CONTRACT_PERFORMANCE_COMPARISON = "performance-comparison.v0.1"

LOOP_VERSION = "0.6.0"
CREATIVE_DIMENSIONS = (
    "visual_impact", "realism", "clarity", "hook", "narrative",
    "business_value", "cta",
)
APPROVAL_DECISIONS = ("APPROVED", "REJECTED", "CHANGES_REQUESTED", "PENDING")
APPROVAL_SUBJECTS = ("creative_review", "recommended_change", "production_brief",
                     "episode_version", "performance_comparison")
PERFORMANCE_METRICS = {
    "views": "engagement",
    "viewers": "engagement",
    "likes": "engagement",
    "comments": "engagement",
    "shares": "engagement",
    "saves": "engagement",
    "followers_gained": "engagement",
    "profile_visits": "engagement",
    "avg_watch_time_s": "engagement",
    "retention_3s": "engagement",
    "completion_rate": "engagement",
    "conversations": "commercial",
    "qualified_leads": "commercial",
    "meetings": "commercial",
    "proposals": "commercial",
    "closed_won": "commercial",
    "sales_verified": "commercial",
}
LEAD_METRICS = {
    "conversations", "qualified_leads", "meetings", "proposals",
    "closed_won", "sales_verified",
}
LEAD_PROVENANCE = {
    "VERIFIED_CRM", "OWNER_CONFIRMED", "USER_PROVIDED_SCREENSHOT",
    "USER_PROVIDED", "OWNER_REPORTED",
}
LEAD_VERIFICATION = {"VERIFIED", "OWNER_CONFIRMED", "USER_REPORTED", "UNVERIFIED"}
PERFORMANCE_STATUSES = {"OBSERVED", "USER_REPORTED", "ESTIMATED", "NOT_AVAILABLE"}

IMPORT_PERMISSIONS = {
    "authorized", "owned", "public_domain", "synthetic", "authorized_analysis_only",
}
PERMISSION_POLICY = {
    "authorized": {"comparison": True, "training": True, "label": "AUTHORIZED"},
    "owned": {"comparison": True, "training": True, "label": "OWNED"},
    "public_domain": {"comparison": True, "training": True, "label": "PUBLIC_DOMAIN"},
    "synthetic": {"comparison": True, "training": True, "label": "SYNTHETIC"},
    "authorized_analysis_only": {
        "comparison": True, "training": False,
        "label": "AUTHORIZED_ANALYSIS_ONLY",
    },
}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}

DEFECT_LABELS = {
    "HOOK_NO_CHANGE_BEFORE_3S": "Sin cambio visual deliberado antes de 3 s",
    "HOOK_DARK_OPEN": "Primer fotograma oscuro",
    "HOOK_TEXT_MISSING": "Hook textual ausente",
    "STATIC_PASSAGE": "Proporción alta de muestras casi estáticas",
    "LONG_AVERAGE_SHOT": "Plano medio largo para formato vertical",
    "AUDIO_SILENCE_GAP": "Silencio relevante en la pista de audio",
    "NARRATIVE_ELEMENT_MISSING": "Elementos narrativos ausentes",
    "CTA_MISSING": "CTA declarado ausente",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 3) -> float | None:
    number = _num(value)
    return None if number is None else round(number, digits)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _key(prefix: str, payload: Any) -> str:
    return f"{prefix}-{_hash(json_dumps(payload))[:16]}"


def _event(con, event_type: str, subject_type: str, subject_key: str,
           payload: dict | None = None) -> str:
    event_key = _key("evt", {
        "type": event_type, "subject_type": subject_type,
        "subject_key": subject_key, "payload": payload or {},
        "at": _now(),
    })
    con.execute(
        "insert into feedback_loop_events(event_key,event_type,subject_type,subject_key,payload_json) values(?,?,?,?,?)",
        (event_key, event_type, subject_type, subject_key, json_dumps(payload or {})),
    )
    return event_key


def _video(con, video_id: int) -> dict:
    row = con.execute("select * from videos where id=?", (video_id,)).fetchone()
    if not row:
        raise ValueError("video_not_found")
    return dict(row)


def _video_version(con, version_key: str) -> dict:
    row = con.execute("select * from episode_versions where version_key=?", (version_key,)).fetchone()
    if not row:
        raise ValueError("episode_version_not_found")
    item = dict(row)
    item["contract"] = json.loads(item.pop("import_contract_json"))
    return item


def _review_row(con, review_key: str) -> dict:
    row = con.execute("select * from creative_reviews where review_key=?", (review_key,)).fetchone()
    if not row:
        raise ValueError("review_not_found")
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    item["defects"] = json.loads(item.pop("defects_json"))
    item["changes"] = json.loads(item.pop("recommendations_json"))
    return item


def _change_row(con, change_key: str) -> dict:
    row = con.execute("select * from recommended_changes where change_key=?", (change_key,)).fetchone()
    if not row:
        raise ValueError("change_not_found")
    item = dict(row)
    item["evidence"] = json.loads(item.pop("evidence_json"))
    item["estimated_impact"] = json.loads(item.pop("estimated_impact_json"))
    review = con.execute(
        "select review_key,recommendations_json from creative_reviews where id=?",
        (item["review_id"],),
    ).fetchone()
    item["review_key"] = review["review_key"] if review else None
    item["suggested_tool_detail"] = {
        "name": item["suggested_tool"], "mode": "HUMAN_SUPERVISED",
    }
    if review:
        for change in json.loads(review["recommendations_json"]):
            if change.get("change_key") == change_key:
                item["suggested_tool_detail"] = change.get("suggested_tool") or item["suggested_tool_detail"]
                break
    return item


def _brief_row(con, brief_key: str) -> dict:
    row = con.execute("select * from production_briefs where brief_key=?", (brief_key,)).fetchone()
    if not row:
        raise ValueError("brief_not_found")
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    return item


def _commercial_layer(con, video: dict) -> dict:
    """Version-exact commercial context. Episode-linked data never becomes exact."""
    exact_rows = [dict(r) for r in con.execute(
        "select id,platform,provenance,measured_at,publication_status from publications "
        "where video_id=? order by id desc", (video["id"],),
    )]
    episode_rows = [dict(r) for r in con.execute(
        "select id,episode,platform,provenance,measured_at,publication_status from publications "
        "where episode=? and (video_id is null or video_id!=?) order by id desc",
        (video["episode"], video["id"]),
    )]
    exact_metrics: dict[str, dict] = {}
    for publication in exact_rows:
        for row in con.execute(
            "select metric_name,metric_value,status,provenance,measured_at from platform_metrics "
            "where publication_id=? order by metric_name,id", (publication["id"],),
        ):
            exact_metrics[row["metric_name"]] = {
                "value": _num(row["metric_value"]),
                "status": row["status"] if row["metric_value"] is not None else "NOT_AVAILABLE",
                "provenance": row["provenance"],
                "measured_at": row["measured_at"],
            }
    lead_metrics = {
        name: entry for name, entry in exact_metrics.items()
        if name in LEAD_METRICS and entry["value"] is not None
    }
    if exact_rows:
        status = "EXACT_VERSION"
        note = "Métricas vinculadas al video_id exacto."
    elif episode_rows:
        status = "EPISODE_LINKED_ONLY"
        note = (
            "Hay métricas del episodio, no de esta versión exacta. "
            "No se usan como resultado de la versión."
        )
    else:
        status = "NOT_AVAILABLE"
        note = "No hay métricas comerciales ni de plataforma para esta versión o episodio."
    return {
        "status": status,
        "exact_version_match": bool(exact_rows),
        "publication_ids": [item["id"] for item in exact_rows],
        "episode_linked_publication_ids": [item["id"] for item in episode_rows],
        "exact_metrics": exact_metrics,
        "commercial_leads": lead_metrics,
        "observed_metric_count": sum(
            1 for item in exact_metrics.values() if item["value"] is not None
        ),
        "note": note,
        "likes_are_not_leads": True,
    }


def _human_layer(con, video: dict) -> dict:
    rows = [dict(r) for r in con.execute(
        "select id,evaluator_id,provenance,evaluated_at from video_evaluations "
        "where video_id=? order by id desc", (video["id"],),
    )]
    gate_rows = [
        item for item in rows
        if item["provenance"] == "human"
        and item["evaluator_id"] not in ("", "anonymous", None)
    ]
    version_rows = [dict(r) for r in con.execute(
        "select ve.* from version_evaluations ve join episode_versions ev on ev.version_key=ve.version_key "
        "where ev.source_video_id=? order by ve.id desc", (video["id"],),
    )]
    return {
        "status": "AVAILABLE" if gate_rows or version_rows else "NOT_AVAILABLE",
        "video_evaluations": len(rows),
        "gate_eligible_video_evaluations": len(gate_rows),
        "version_evaluations": len(version_rows),
        "gate_eligible_version_evaluations": sum(
            1 for item in version_rows if item.get("gate_eligible")
        ),
        "provenance_counts": {
            key: sum(1 for item in rows if item["provenance"] == key)
            for key in sorted({item["provenance"] for item in rows})
        },
        "note": (
            "Sólo evaluaciones humanas identificadas cuentan como evidencia humana. "
            "AI-assisted, demo y anónimas se conservan pero se excluyen."
        ),
    }


def _defect_specs(video: dict, attention: dict) -> list[dict]:
    facts = attention.get("facts") or {}
    first_frame = facts.get("first_frame") or {}
    duration = _num(facts.get("duration_s")) or _num(video.get("duration_s")) or 0.0
    hook_text = str(video.get("hook") or "").strip()
    cta_text = str(video.get("cta") or "").strip()
    observed_at = attention.get("evaluated_at") or _now()
    specs: list[dict] = []

    def add(code: str, category: str, severity: str, start: float, end: float,
            problem: str, interpretation: str, metrics: list[dict],
            confidence: str = "medium", label: str | None = None) -> None:
        specs.append({
            "code": code,
            "category": category,
            "severity": severity,
            "start_s": round(max(0.0, start), 3),
            "end_s": round(max(start, end), 3),
            "timestamp_label": label or f"{round(max(0.0, start), 1)}–{round(max(start, end), 1)} s",
            "detected_problem": problem,
            "interpretation": interpretation,
            "observed_evidence": [
                {
                    "metric": item["metric"],
                    "value": item.get("value"),
                    "unit": item.get("unit"),
                    "source": item.get("source", "ffprobe+opencv"),
                    "observed_at": observed_at,
                }
                for item in metrics
            ],
            "evidence_class": "OBSERVED_FACT_TRIGGER",
            "assessment_class": "HEURISTIC_INTERPRETATION",
            "confidence": confidence,
            "limitations": [
                "La señal se calcula con FFprobe/OpenCV; no es una medición de retención real.",
                "La severidad es una regla editorial, no un resultado de plataforma.",
            ],
        })

    first_3s_cuts = _num(facts.get("first_3s_cut_count"))
    if first_3s_cuts == 0 and duration > 6:
        add(
            "HOOK_NO_CHANGE_BEFORE_3S", "hook", "high", 0.0, min(3.0, duration),
            "Poco cambio visual durante el gancho.",
            "El inicio puede leerse como estático en un feed móvil; no se observó un corte deliberado antes de 3 s.",
            [
                {"metric": "first_3s_cut_count", "value": first_3s_cuts, "unit": "cuts"},
                {"metric": "duration_s", "value": _round(duration), "unit": "s"},
            ],
            "high",
        )
    brightness = _num(first_frame.get("brightness"))
    if brightness is not None and brightness < 45:
        add(
            "HOOK_DARK_OPEN", "hook", "medium", 0.0, min(2.0, duration),
            "El primer fotograma es oscuro.",
            "La legibilidad inicial en pantalla móvil puede ser baja; se requiere revisión humana.",
            [{"metric": "first_frame_brightness", "value": _round(brightness), "unit": "0-255"}],
        )
    if not hook_text:
        add(
            "HOOK_TEXT_MISSING", "hook", "high", 0.0, min(3.0, duration),
            "No hay hook textual declarado.",
            "Sin una frase de gancho no se puede evaluar claridad ni consistencia editorial.",
            [{"metric": "hook", "value": None, "unit": "text"}],
        )
    freeze = _num(facts.get("freeze_ratio"))
    if freeze is not None and freeze > 0.12:
        add(
            "STATIC_PASSAGE", "production", "medium", 0.0, duration,
            "La proporción de muestras casi estáticas supera el umbral editorial.",
            "Puede reducir la sensación de movimiento, pero la intención narrativa debe revisarse.",
            [{"metric": "freeze_ratio", "value": _round(freeze), "unit": "ratio"}],
            label="video completo (muestreo)",
        )
    avg_shot = _num(facts.get("avg_shot_s"))
    if avg_shot is not None and avg_shot > 6:
        add(
            "LONG_AVERAGE_SHOT", "production", "medium", 0.0, duration,
            "El plano medio es largo para un formato vertical corto.",
            "La cadencia puede sentirse lenta; un corte debe explicar un cambio, no decorar.",
            [{"metric": "avg_shot_s", "value": _round(avg_shot), "unit": "s"}],
            label="video completo (promedio)",
        )
    silence = _num(facts.get("silence_ratio"))
    if silence is not None and silence > 0.15:
        add(
            "AUDIO_SILENCE_GAP", "production", "medium", 0.0, duration,
            "El silencio detectable ocupa una parte relevante del video.",
            "Puede afectar la sincronización de narración y CTA; revisar el audio real.",
            [{"metric": "silence_ratio", "value": _round(silence), "unit": "ratio"}],
        )
    narrative = attention.get("narrative") or {}
    missing = [
        name for name, item in (narrative.get("elements") or {}).items()
        if item.get("status") == "NOT_AVAILABLE"
    ]
    if missing:
        add(
            "NARRATIVE_ELEMENT_MISSING", "narrative", "high", 0.0, duration,
            "Faltan elementos de la estructura narrativa: " + ", ".join(missing) + ".",
            "Sin problema, consecuencia, solución, evidencia o acción, el mensaje puede quedar incompleto.",
            [{"metric": f"narrative.{name}", "value": "NOT_AVAILABLE", "unit": "element"} for name in missing],
            "high",
            label="video completo (estructura)",
        )
    if not cta_text:
        add(
            "CTA_MISSING", "commercial", "high", 0.0, duration,
            "No hay CTA declarado.",
            "Sin una acción concreta no se puede separar interés de intención comercial.",
            [{"metric": "cta", "value": None, "unit": "text"}],
            "high",
            label="video completo (cierre)",
        )
    return specs


def _solution_for(code: str, video: dict) -> dict:
    episode = video.get("episode") or "EPISODE"
    mapping = {
        "HOOK_NO_CHANGE_BEFORE_3S": {
            "solution": (
                "Añadir un cambio visual deliberado antes de 2 s: acercamiento cinematográfico "
                "a la pieza o detalle industrial, reveal de producto o transición motivada. "
                "Mantener el resto del video sin cambios."
            ),
            "impact": {
                "metric": "retention_3s", "direction": "increase", "band": "medium",
                "rationale": "Un cambio temprano puede reducir la incertidumbre del primer segundo; no existe medición real de retención para esta versión.",
            },
            "tool": {
                "name": "human_video_editor",
                "alternatives": ["claude_code", "codex"],
                "mode": "HUMAN_SUPERVISED",
                "reason": "La decisión de encuadre y ritmo requiere criterio humano; los agentes pueden proponer o ejecutar un plan aprobado.",
            },
            "acceptance": (
                "Un revisor humano confirma que hay un cambio visual perceptible antes de 2 s, "
                "que el mensaje sigue siendo legible en móvil y que no se alteró el problema, la solución ni el CTA."
            ),
            "priority": "high",
            "risks": [
                "Un movimiento decorativo puede distraer del mensaje.",
                "El zoom no debe recortar texto o elementos clave.",
            ],
        },
        "HOOK_DARK_OPEN": {
            "solution": "Aumentar la luminosidad o el contraste del primer fotograma sin cambiar el significado del plano.",
            "impact": {
                "metric": "retention_3s", "direction": "increase", "band": "low",
                "rationale": "La legibilidad inicial es una condición de entrada, no una predicción de retención.",
            },
            "tool": {
                "name": "human_video_editor", "alternatives": ["ffmpeg"],
                "mode": "HUMAN_SUPERVISED",
                "reason": "El ajuste de color debe preservar la intención visual y la marca.",
            },
            "acceptance": "Un revisor humano confirma que el primer fotograma se lee con claridad en un teléfono y que el color no parece artificial.",
            "priority": "medium",
            "risks": ["Sobreexponer el primer plano.", "Alterar la continuidad con el resto del video."],
        },
        "HOOK_TEXT_MISSING": {
            "solution": "Escribir un hook de una frase con problema o consecuencia y declararlo en los metadatos de la versión.",
            "impact": {
                "metric": "hook_clarity", "direction": "increase", "band": "medium",
                "rationale": "La claridad del hook se puede revisar humanamente; no se estima una tasa de retención.",
            },
            "tool": {
                "name": "copywriting", "alternatives": ["claude_code", "codex"],
                "mode": "HUMAN_SUPERVISED",
                "reason": "El texto debe ser aprobado por el responsable de marca.",
            },
            "acceptance": "Un revisor humano identifica el problema y la audiencia en una sola lectura del hook.",
            "priority": "high",
            "risks": ["Prometer un resultado no verificado.", "Usar un hook genérico sin relación con el video."],
        },
        "STATIC_PASSAGE": {
            "solution": "Reducir el tramo casi estático o justificarlo con una intención narrativa explícita.",
            "impact": {
                "metric": "avg_watch_time_s", "direction": "increase", "band": "medium",
                "rationale": "La cadencia puede influir en la atención, pero no hay una medición causal.",
            },
            "tool": {
                "name": "human_video_editor", "alternatives": ["claude_code", "codex"],
                "mode": "HUMAN_SUPERVISED",
                "reason": "El corte debe estar motivado por el contenido, no por una regla automática.",
            },
            "acceptance": "Un revisor humano puede explicar por qué cada tramo estático permanece o qué cambio narrativo lo reemplaza.",
            "priority": "medium",
            "risks": ["Cortar una explicación necesaria.", "Acelerar el video hasta perder claridad."],
        },
        "LONG_AVERAGE_SHOT": {
            "solution": "Aumentar la cadencia con un corte o movimiento que explique el cambio, no por decoración.",
            "impact": {
                "metric": "avg_watch_time_s", "direction": "increase", "band": "medium",
                "rationale": "Un plano largo no es un defecto por sí mismo; la prueba requiere revisión humana.",
            },
            "tool": {
                "name": "human_video_editor", "alternatives": ["claude_code", "codex"],
                "mode": "HUMAN_SUPERVISED",
                "reason": "La estructura narrativa manda sobre la duración del plano.",
            },
            "acceptance": "Un revisor humano confirma que el nuevo corte mejora el ritmo sin romper la explicación.",
            "priority": "medium",
            "risks": ["Fragmentar una demostración técnica.", "Perder continuidad visual."],
        },
        "AUDIO_SILENCE_GAP": {
            "solution": "Revisar silencios y sincronización de narración/CTA; conservar pausas sólo si son intencionales.",
            "impact": {
                "metric": "avg_watch_time_s", "direction": "increase", "band": "low",
                "rationale": "El silencio puede ser editorial; no se asume que sea un defecto.",
            },
            "tool": {
                "name": "human_audio_editor", "alternatives": ["ffmpeg"],
                "mode": "HUMAN_SUPERVISED",
                "reason": "La voz y la música requieren revisión de mezcla.",
            },
            "acceptance": "Un revisor humano confirma que no hay silencios accidentales y que el CTA se escucha completo.",
            "priority": "medium",
            "risks": ["Eliminar una pausa expresiva.", "Desincronizar voz y labios."],
        },
        "NARRATIVE_ELEMENT_MISSING": {
            "solution": "Completar la estructura narrativa con los elementos ausentes, sin inventar evidencia ni resultados.",
            "impact": {
                "metric": "human_clarity", "direction": "increase", "band": "medium",
                "rationale": "La claridad narrativa se evalúa humanamente; no es una predicción comercial.",
            },
            "tool": {
                "name": "copywriting", "alternatives": ["claude_code", "codex"],
                "mode": "HUMAN_SUPERVISED",
                "reason": "Los elementos faltantes deben provenir del negocio, no de una suposición del modelo.",
            },
            "acceptance": "Un revisor humano identifica problema, consecuencia, solución, evidencia y acción en el guion o en el video.",
            "priority": "high",
            "risks": ["Rellenar con datos ficticios.", "Alargar el video sin claridad."],
        },
        "CTA_MISSING": {
            "solution": "Definir un CTA concreto y medible (palabra clave, conversación o diagnóstico) y añadirlo al cierre.",
            "impact": {
                "metric": "qualified_leads", "direction": "increase", "band": "medium",
                "rationale": "El CTA puede mejorar la claridad de la acción, pero no se estima una tasa de leads ni una venta.",
                "not_a_result": True,
            },
            "tool": {
                "name": "copywriting", "alternatives": ["claude_code", "codex"],
                "mode": "HUMAN_SUPERVISED",
                "reason": "El CTA debe alinearse con el proceso comercial real.",
            },
            "acceptance": "Un revisor humano entiende exactamente qué acción tomar y el negocio puede registrar esa acción por separado de likes y guardados.",
            "priority": "high",
            "risks": ["Usar likes como sustituto de leads.", "Prometer una respuesta que el equipo no puede sostener."],
        },
    }
    item = mapping[code]
    return {
        "episode": episode,
        "proposed_solution": item["solution"],
        "estimated_impact": {
            "status": "ESTIMATE_ONLY",
            "not_a_result": True,
            "metric": item["impact"]["metric"],
            "direction": item["impact"]["direction"],
            "band": item["impact"]["band"],
            "rationale": item["impact"]["rationale"],
            "disclaimer": "Estimación heurística de impacto. No es una medición, una garantía ni un resultado comercial.",
        },
        "suggested_tool": item["tool"],
        "acceptance_criterion": item["acceptance"],
        "priority": item["priority"],
        "risks": item["risks"],
    }


def _build_defects(video: dict, attention: dict) -> list[dict]:
    specs = _defect_specs(video, attention)
    result = []
    for spec in specs:
        base = {
            "episode": video["episode"],
            "version": video.get("version"),
            "code": spec["code"],
            "label": DEFECT_LABELS.get(spec["code"], spec["code"]),
            "timestamp": {
                "start_s": spec["start_s"], "end_s": spec["end_s"],
                "label": spec["timestamp_label"],
            },
            "category": spec["category"],
            "severity": spec["severity"],
            "detected_problem": spec["detected_problem"],
            "interpretation": spec["interpretation"],
            "observed_evidence": spec["observed_evidence"],
            "evidence_class": spec["evidence_class"],
            "assessment_class": spec["assessment_class"],
            "confidence": spec["confidence"],
            "limitations": spec["limitations"],
            "status": "OPEN",
        }
        base["defect_key"] = _key("def", {
            "episode": video["episode"], "file_hash": video.get("file_hash"),
            "code": spec["code"], "start": spec["start_s"], "end": spec["end_s"],
        })
        result.append(base)
    return result


def _build_changes(video: dict, defects: list[dict]) -> list[dict]:
    result = []
    for defect in defects:
        solution = _solution_for(defect["code"], video)
        change = {
            "episode": video["episode"],
            "version": video.get("version"),
            "defect_key": defect["defect_key"],
            "timestamp": defect["timestamp"],
            "detected_problem": defect["detected_problem"],
            "evidence": defect["observed_evidence"],
            "evidence_class": defect["evidence_class"],
            "assessment_class": defect["assessment_class"],
            "estimated_impact": solution["estimated_impact"],
            "proposed_solution": solution["proposed_solution"],
            "priority": solution["priority"],
            "suggested_tool": solution["suggested_tool"],
            "acceptance_criterion": solution["acceptance_criterion"],
            "risks": solution["risks"],
            "status": "PROPOSAL",
            "requires_human_approval": True,
            "automatic_execution": False,
        }
        change["change_key"] = _key("chg", {
            "defect_key": defect["defect_key"],
            "solution": solution["proposed_solution"],
        })
        result.append(change)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    result.sort(key=lambda item: (priority_order.get(item["priority"], 3), item["timestamp"]["start_s"]))
    return result


def create_review(con, video_id: int, force: bool = False) -> dict:
    """Create or return a deterministic creative review for one video."""
    video = _video(con, video_id)
    attention = latest_attention(con, video_id)
    if force or not attention:
        attention = analyze_attention(con, video_id)
    attention_id = attention.get("attention_id")
    review_key = _key("review", {
        "episode": video["episode"], "file_hash": video.get("file_hash"),
        "attention_id": attention_id,
    })
    existing = con.execute("select * from creative_reviews where review_key=?", (review_key,)).fetchone()
    if existing and not force:
        row = _review_row(con, review_key)
        return {
            "review": row["payload"], "defects": row["defects"],
            "changes": row["changes"], "review_id": row["id"],
        }

    defects = _build_defects(video, attention)
    changes = _build_changes(video, defects)
    commercial = _commercial_layer(con, video)
    human = _human_layer(con, video)
    overall = attention.get("overall") or {}
    facts = attention.get("facts") or {}
    review = {
        "contract_version": CONTRACT_CREATIVE_REVIEW,
        "review_key": review_key,
        "status": "REVIEW_ESTIMATE_ONLY",
        "created_at": _now(),
        "video": {
            "id": video["id"], "episode": video["episode"], "version": video.get("version"),
            "duration_s": _round(video.get("duration_s")),
            "resolution": f"{video.get('width')}x{video.get('height')}",
            "file_hash": video.get("file_hash"),
            "permission_status": video.get("permission_status"),
            "source_kind": video.get("source_kind"),
            "attention_id": attention_id,
        },
        "evidence_layers": {
            "observed_facts": {
                "status": "AVAILABLE",
                "source": "ffprobe+opencv",
                "duration_s": facts.get("duration_s"),
                "cut_count": facts.get("cut_count"),
                "first_3s_cut_count": facts.get("first_3s_cut_count"),
                "avg_shot_s": facts.get("avg_shot_s"),
                "brightness_mean": facts.get("brightness_mean"),
                "contrast_mean": facts.get("contrast_mean"),
                "freeze_ratio": facts.get("freeze_ratio"),
                "silence_ratio": facts.get("silence_ratio"),
                "first_frame": facts.get("first_frame"),
                "limitations": facts.get("limitations") or [],
            },
            "heuristic_estimates": {
                "status": "ESTIMATE_ONLY_NOT_VALIDATED",
                "source": attention.get("contract_version"),
                "overall": overall.get("score"),
                "band": overall.get("band"),
                "confidence": overall.get("confidence"),
                "coverage": overall.get("coverage"),
                "dimensions": overall.get("dimensions"),
                "disclaimer": (
                    "Índice editorial heurístico. No es una predicción de viralidad, "
                    "retención, leads ni ventas."
                ),
            },
            "human_evaluations": human,
            "commercial_metrics": commercial,
        },
        "defects": defects,
        "recommended_changes": changes,
        "approval": {
            "status": "PENDING",
            "required": True,
            "note": "Ninguna recomendación se ejecuta ni se publica sin aprobación humana explícita.",
        },
        "guardrails": [
            "Hechos observados, estimaciones, evaluaciones humanas y métricas comerciales no se fusionan.",
            "Las estimaciones de impacto nunca se presentan como resultados.",
            "No se usan salidas o evaluaciones derivadas de Higgsfield para entrenar modelos propios.",
            "No se escribe en proyectos de Claude Code o Codex; sólo se exportan propuestas.",
        ],
    }
    con.execute(
        "insert into creative_reviews(review_key,video_id,episode,version_label,contract_version,status,payload_json,defects_json,recommendations_json) values(?,?,?,?,?,?,?,?,?)",
        (review_key, video["id"], video["episode"], video.get("version"),
         CONTRACT_CREATIVE_REVIEW, review["status"], json_dumps(review),
         json_dumps(defects), json_dumps(changes)),
    )
    review_id = int(con.execute("select last_insert_rowid()").fetchone()[0])
    for change in changes:
        con.execute(
            "insert into recommended_changes(change_key,review_id,video_id,episode,start_s,end_s,problem,evidence_json,estimated_impact_json,proposed_solution,priority,suggested_tool,acceptance_criterion,status) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (change["change_key"], review_id, video["id"], video["episode"],
             change["timestamp"]["start_s"], change["timestamp"]["end_s"],
             change["detected_problem"], json_dumps(change["evidence"]),
             json_dumps(change["estimated_impact"]), change["proposed_solution"],
             change["priority"], change["suggested_tool"]["name"],
             change["acceptance_criterion"], change["status"]),
        )
    _event(con, "CREATIVE_REVIEW_CREATED", "creative_review", review_key, {
        "episode": video["episode"], "video_id": video["id"],
        "defects": len(defects), "changes": len(changes),
    })
    con.commit()
    return {"review": review, "defects": defects, "changes": changes, "review_id": review_id}


def get_review(con, review_key: str) -> dict:
    row = _review_row(con, review_key)
    return {"review": row["payload"], "defects": row["defects"], "changes": row["changes"],
            "review_id": row["id"]}


def visual_defects_contract(review_bundle: dict) -> dict:
    review = review_bundle["review"]
    return {
        "contract_version": CONTRACT_VISUAL_DEFECTS,
        "review_key": review["review_key"],
        "episode": review["video"]["episode"],
        "version": review["video"].get("version"),
        "generated_at": review["created_at"],
        "status": review["status"],
        "source": {
            "analysis": "attention-lab.v0.1",
            "facts": "ffprobe+opencv",
            "human_text_provenance": "preserved_in_videos_table",
        },
        "defects": review_bundle["defects"],
        "limitations": [
            "Los defectos son señales heurísticas derivadas de muestreo de frames y metadatos.",
            "No sustituyen una revisión humana de legibilidad, narrativa o calidad final.",
            "La severidad es editorial y no un resultado de plataforma.",
        ],
    }


def recommended_changes_contract(review_bundle: dict) -> dict:
    review = review_bundle["review"]
    return {
        "contract_version": CONTRACT_RECOMMENDED_CHANGES,
        "review_key": review["review_key"],
        "episode": review["video"]["episode"],
        "version": review["video"].get("version"),
        "generated_at": review["created_at"],
        "status": "PROPOSAL_ONLY",
        "changes": review_bundle["changes"],
        "guardrails": [
            "Cada cambio incluye episodio, timestamp, problema, evidencia, impacto estimado, solución, prioridad, herramienta y criterio de aceptación.",
            "El impacto estimado está marcado ESTIMATE_ONLY y no es un resultado.",
            "Ningún cambio se ejecuta automáticamente.",
            "La aprobación humana es obligatoria antes de producción o publicación.",
        ],
    }


def _write_json(path: Path, value: Any) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False)
    path.write_bytes(text.encode("utf-8"))
    return {
        "path": str(path),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "bytes": len(text.encode("utf-8")),
    }


def _handoff_readme(episode: str, brief_key: str, target_label: str) -> str:
    return f"""# VLUX Production Handoff — {episode}

This folder is a **proposal**, not a command. It was generated by VLUX Studio OS
V0.6 and is safe to read from Claude Code or Codex only when the project owner
authorizes it.

- Brief: `{brief_key}`
- Target label: `{target_label}`
- Expected return contract: `{CONTRACT_EPISODE_VERSION}`
- Expected return file: `import-template.json` completed by the producer.

Rules:

1. Do not modify the source episode or its original file.
2. Do not interrupt an active render.
3. Do not publish automatically.
4. Produce the new version in your own workspace.
5. Return the completed `import-template.json` plus the rendered file path.
6. Studio OS must import the result explicitly; it will never write into your workspace.
7. No Higgsfield-derived outputs or evaluations may be used to train models.
"""


def export_review_bundle(con, review_key: str, output_dir: str | Path) -> dict:
    bundle = get_review(con, review_key)
    out = Path(output_dir).expanduser().resolve() / review_key
    out.mkdir(parents=True, exist_ok=True)
    review_doc = bundle["review"]
    defects_doc = visual_defects_contract(bundle)
    changes_doc = recommended_changes_contract(bundle)
    files = {
        "creative-review.json": _write_json(out / "creative-review.json", review_doc),
        "visual-defects.json": _write_json(out / "visual-defects.json", defects_doc),
        "recommended-changes.json": _write_json(out / "recommended-changes.json", changes_doc),
    }
    manifest = {
        "contract_version": "creative-loop-export.v0.1",
        "status": "PROPOSAL_ONLY",
        "exported_at": _now(),
        "review_key": review_key,
        "episode": review_doc["video"]["episode"],
        "files": files,
        "consumers": ["claude_code", "codex", "human_reviewer"],
        "auto_apply": False,
        "write_into_agent_workspace": False,
        "note": "Sólo propuestas exportadas. La importación de resultados es explícita.",
    }
    manifest_path = _write_json(out / "manifest.json", manifest)
    _event(con, "REVIEW_EXPORTED", "creative_review", review_key, {
        "output_dir": str(out), "files": list(files),
    })
    con.commit()
    return {
        "status": "EXPORTED", "review_key": review_key, "output_dir": str(out),
        "files": files, "manifest": manifest_path,
    }


def create_production_brief(con, change_key: str, target_version_label: str | None = None) -> dict:
    change = _change_row(con, change_key)
    video = _video(con, change["video_id"])
    target = target_version_label or f"{change['episode']}-rev-{change['change_key'][-8:]}"
    existing = con.execute(
        "select brief_key from production_briefs where change_id=? and target_version_label=? "
        "order by id desc limit 1", (change["id"], target),
    ).fetchone()
    if existing:
        return _brief_row(con, existing["brief_key"])

    episode_version = con.execute(
        "select version_key,file_hash,permission_status from episode_versions "
        "where source_video_id=? order by id desc limit 1", (video["id"],),
    ).fetchone()
    brief_key = _key("brief", {
        "change_key": change_key, "target": target,
        "file_hash": video.get("file_hash"),
    })
    instruction = {
        "order": 1,
        "start_s": change["start_s"],
        "end_s": change["end_s"],
        "operation": "VISUAL_CHANGE_PROPOSAL",
        "description": change["proposed_solution"],
        "priority": change["priority"],
        "suggested_tool": change["suggested_tool_detail"],
        "preserve": [
            "mensaje de negocio", "problema", "solución", "CTA",
            "relación de aspecto", "audio original si existe",
        ],
        "acceptance_criterion": change["acceptance_criterion"],
    }
    brief = {
        "contract_version": CONTRACT_PRODUCTION_BRIEF,
        "brief_key": brief_key,
        "status": "PROPOSAL_ONLY",
        "created_at": _now(),
        "episode": change["episode"],
        "source_version": {
            "video_id": video["id"],
            "version": video.get("version"),
            "file_hash": video.get("file_hash"),
            "permission_status": video.get("permission_status"),
            "episode_version_key": episode_version["version_key"] if episode_version else None,
        },
        "target_version_label": target,
        "objective": change["problem"],
        "change_refs": [change_key],
        "edit_instructions": [instruction],
        "preserve": [
            "La estructura problema → consecuencia → solución → beneficio → CTA.",
            "La duración y el formato vertical, salvo que la instrucción indique lo contrario.",
            "El archivo fuente original: nunca se modifica ni se sobrescribe.",
        ],
        "do_not_change": [
            "No inventar datos, clientes, resultados ni métricas.",
            "No usar likes, guardados o compartidos como leads o ventas.",
            "No publicar ni programar publicación automáticamente.",
            "No escribir en el proyecto activo de Claude Code o Codex.",
        ],
        "acceptance_criteria": [
            change["acceptance_criterion"],
            "El resultado sigue siendo reconocible como el mismo episodio y conserva el mensaje de negocio.",
            "Un revisor humano confirma legibilidad en móvil antes de publicar.",
        ],
        "source_permission": {
            "status": video.get("permission_status"),
            "allowed_use": "analysis_and_comparison_only",
            "derivative_allowed": False,
            "note": (
                "El permiso del archivo fuente no autoriza automáticamente un derivado. "
                "El productor debe confirmar permiso antes de crear o publicar una versión."
            ),
        },
        "handoff": {
            "consumers": ["claude_code", "codex"],
            "mode": "EXPLICIT_IMPORT_ONLY",
            "auto_apply": False,
            "write_into_agent_workspace": False,
            "expected_return_contract": CONTRACT_EPISODE_VERSION,
            "expected_return_file": "import-template.json",
            "instructions": (
                "El agente puede leer esta propuesta sólo si su responsable lo autoriza. "
                "Debe producir la nueva versión en su propio espacio y devolver la ruta y el hash. "
                "Studio OS no escribe en el espacio del agente."
            ),
        },
        "data_policy": {
            "no_higgsfield_derived_training": True,
            "no_automatic_training": True,
            "no_commercial_improvement_claim": True,
        },
        "guardrails": [
            "Propuesta exportable; no es una orden de producción.",
            "No se modifican trabajos activos ni se interrumpen renders.",
            "No se sobrescriben episodios anteriores.",
            "La aprobación humana es obligatoria antes de publicar.",
        ],
    }
    con.execute(
        "insert into production_briefs(brief_key,change_id,episode,source_video_id,target_version_label,payload_json,status) values(?,?,?,?,?,?,?)",
        (brief_key, change["id"], change["episode"], video["id"], target,
         json_dumps(brief), "EXPORT_READY"),
    )
    _event(con, "PRODUCTION_BRIEF_CREATED", "production_brief", brief_key, {
        "change_key": change_key, "target_version_label": target,
    })
    con.commit()
    return brief


def request_human_approval(con, subject_type: str, subject_key: str,
                           evaluator_id: str = "anonymous", notes: str = "") -> dict:
    if subject_type not in APPROVAL_SUBJECTS:
        raise ValueError("subject_type_not_supported")
    if not evaluator_id or evaluator_id == "anonymous":
        raise ValueError("identified_evaluator_required")
    approval_key = _key("approval", {
        "subject_type": subject_type, "subject_key": subject_key,
        "at": _now(),
    })
    contract = {
        "contract_version": CONTRACT_HUMAN_APPROVAL,
        "approval_key": approval_key,
        "subject_type": subject_type,
        "subject_key": subject_key,
        "decision": "PENDING",
        "evaluator_id": evaluator_id,
        "provenance": "human",
        "notes": notes,
        "conditions": [],
        "created_at": _now(),
        "gate_eligible": False,
        "no_automatic_promotion": True,
    }
    con.execute(
        "insert into human_approvals(approval_key,subject_type,subject_key,decision,evaluator_id,provenance,notes,contract_version,payload_json) values(?,?,?,?,?,?,?,?,?)",
        (approval_key, subject_type, subject_key, "PENDING", evaluator_id,
         "human", notes, CONTRACT_HUMAN_APPROVAL, json_dumps(contract)),
    )
    _event(con, "APPROVAL_REQUESTED", subject_type, subject_key, {"approval_key": approval_key})
    con.commit()
    return contract


def record_human_approval(con, subject_type: str, subject_key: str, decision: str,
                          evaluator_id: str, notes: str = "",
                          conditions: list[str] | None = None,
                          provenance: str = "human") -> dict:
    if subject_type not in APPROVAL_SUBJECTS:
        raise ValueError("subject_type_not_supported")
    if decision not in APPROVAL_DECISIONS:
        raise ValueError("decision_not_supported")
    if not evaluator_id or evaluator_id == "anonymous":
        raise ValueError("identified_evaluator_required")
    if decision == "APPROVED" and provenance != "human":
        raise ValueError("approved_requires_human_provenance")
    gate_eligible = provenance == "human" and evaluator_id not in ("", "anonymous")
    approval_key = _key("approval", {
        "subject_type": subject_type, "subject_key": subject_key,
        "decision": decision, "evaluator": evaluator_id, "at": _now(),
    })
    contract = {
        "contract_version": CONTRACT_HUMAN_APPROVAL,
        "approval_key": approval_key,
        "subject_type": subject_type,
        "subject_key": subject_key,
        "decision": decision,
        "evaluator_id": evaluator_id,
        "provenance": provenance,
        "notes": notes,
        "conditions": conditions or [],
        "created_at": _now(),
        "gate_eligible": gate_eligible,
        "no_automatic_promotion": True,
        "scope": (
            "Aprobación de una propuesta creativa. No autoriza publicación, "
            "entrenamiento de modelos ni promoción automática."
        ),
    }
    con.execute(
        "insert into human_approvals(approval_key,subject_type,subject_key,decision,evaluator_id,provenance,notes,contract_version,payload_json) values(?,?,?,?,?,?,?,?,?)",
        (approval_key, subject_type, subject_key, decision, evaluator_id, provenance,
         notes, CONTRACT_HUMAN_APPROVAL, json_dumps(contract)),
    )
    if subject_type == "recommended_change":
        status = {
            "APPROVED": "APPROVED_FOR_PRODUCTION",
            "REJECTED": "REJECTED",
            "CHANGES_REQUESTED": "CHANGES_REQUESTED",
            "PENDING": "PROPOSAL",
        }[decision]
        con.execute("update recommended_changes set status=? where change_key=?",
                    (status, subject_key))
    elif subject_type == "production_brief":
        status = "APPROVED" if decision == "APPROVED" else decision
        con.execute("update production_briefs set status=? where brief_key=?",
                    (status, subject_key))
    _event(con, "HUMAN_APPROVAL_RECORDED", subject_type, subject_key, {
        "decision": decision, "evaluator_id": evaluator_id,
    })
    con.commit()
    return contract


def export_production_brief(con, brief_key: str, output_dir: str | Path) -> dict:
    brief = _brief_row(con, brief_key)
    change_row = con.execute(
        "select change_key from recommended_changes where id=?", (brief["change_id"],)
    ).fetchone()
    if not change_row:
        raise ValueError("change_not_found")
    change = _change_row(con, change_row["change_key"])
    out = Path(output_dir).expanduser().resolve() / brief_key
    out.mkdir(parents=True, exist_ok=True)
    import_template = {
        "contract_version": CONTRACT_EPISODE_VERSION,
        "status": "TO_BE_COMPLETED_BY_PRODUCER",
        "episode": brief["episode"],
        "parent_version_key": brief["payload"]["source_version"].get("episode_version_key"),
        "brief_key": brief_key,
        "version_label": brief["target_version_label"],
        "file_path": None,
        "file_sha256": None,
        "permission_status": None,
        "provenance": "PRODUCER_DECLARED",
        "notes": "Completar ruta, hash y permiso. Studio OS verificará el hash antes de importar.",
    }
    files = {
        "production-brief.json": _write_json(out / "production-brief.json", brief["payload"]),
        "recommended-change.json": _write_json(out / "recommended-change.json", {
            "contract_version": CONTRACT_RECOMMENDED_CHANGES,
            "review_key": change.get("review_key"),
            "episode": change["episode"],
            "version": None,
            "generated_at": brief["created_at"],
            "status": "PROPOSAL_ONLY",
            "changes": [{
                "change_key": change["change_key"],
                "episode": change["episode"],
                "version": None,
                "defect_key": None,
                "timestamp": {"start_s": change["start_s"], "end_s": change["end_s"],
                              "label": f"{change['start_s']}–{change['end_s']} s"},
                "detected_problem": change["problem"],
                "evidence": change["evidence"],
                "evidence_class": "OBSERVED_FACT_TRIGGER",
                "assessment_class": "HEURISTIC_INTERPRETATION",
                "estimated_impact": change["estimated_impact"],
                "proposed_solution": change["proposed_solution"],
                "priority": change["priority"],
                "suggested_tool": change["suggested_tool_detail"],
                "acceptance_criterion": change["acceptance_criterion"],
                "risks": [],
                "requires_human_approval": True,
                "automatic_execution": False,
                "status": change["status"],
            }],
            "guardrails": [
                "Propuesta exportada; no es una orden de producción.",
                "El impacto estimado no es un resultado.",
                "La aprobación humana es obligatoria.",
            ],
        }),
        "import-template.json": _write_json(out / "import-template.json", import_template),
    }
    (out / "README.md").write_text(
        _handoff_readme(brief["episode"], brief_key, brief["target_version_label"]),
        encoding="utf-8",
    )
    manifest = {
        "contract_version": "production-handoff.v0.1",
        "status": "PROPOSAL_ONLY",
        "exported_at": _now(),
        "brief_key": brief_key,
        "episode": brief["episode"],
        "target_version_label": brief["target_version_label"],
        "files": files,
        "readme": str(out / "README.md"),
        "consumers": ["claude_code", "codex"],
        "explicit_import_required": True,
        "auto_apply": False,
        "write_into_agent_workspace": False,
        "expected_return_contract": CONTRACT_EPISODE_VERSION,
    }
    manifest_doc = _write_json(out / "manifest.json", manifest)
    con.execute(
        "update production_briefs set status='EXPORTED',exported_path=?,exported_sha256=? where brief_key=?",
        (str(out), files["production-brief.json"]["sha256"], brief_key),
    )
    _event(con, "PRODUCTION_BRIEF_EXPORTED", "production_brief", brief_key, {
        "output_dir": str(out),
    })
    con.commit()
    return {
        "status": "EXPORTED", "brief_key": brief_key, "output_dir": str(out),
        "files": files, "manifest": manifest_doc, "brief": brief["payload"],
    }


def _allowed_roots(allowed_roots: list[str | Path] | None) -> list[Path]:
    roots = allowed_roots or [Path("data")]
    result = []
    for root in roots:
        result.append(Path(root).expanduser().resolve())
    return result


def _within(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def import_episode_version(con, episode: str, file_path: str | Path,
                           permission_status: str, *,
                           parent_version_key: str | None = None,
                           brief_key: str | None = None,
                           source_video_id: int | None = None,
                           provenance: str = "EXPLICIT_IMPORT",
                           allowed_roots: list[str | Path] | None = None,
                           version_label: str | None = None) -> dict:
    """Import an already-produced file read-only. Never moves or modifies it."""
    if not episode or not str(episode).strip():
        raise ValueError("episode_required")
    if permission_status not in IMPORT_PERMISSIONS:
        raise ValueError("explicit_permission_required")
    source = Path(file_path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise ValueError("file_not_found")
    if source.suffix.lower() not in VIDEO_SUFFIXES:
        raise ValueError("video_suffix_required")
    roots = _allowed_roots(allowed_roots)
    if not _within(source, roots):
        raise ValueError("path_not_allowed_by_explicit_root")
    file_hash = sha256_file(source)
    existing = con.execute(
        "select version_key,episode,file_path from episode_versions where file_hash=?",
        (file_hash,),
    ).fetchone()
    if existing:
        return {
            "status": "DUPLICATE", "version_key": existing["version_key"],
            "episode": existing["episode"], "file_path": existing["file_path"],
            "note": "El hash ya está registrado; no se sobrescribe ni se duplica.",
        }
    if brief_key and not con.execute(
        "select 1 from production_briefs where brief_key=?", (brief_key,)
    ).fetchone():
        raise ValueError("brief_not_found")
    if parent_version_key and not con.execute(
        "select 1 from episode_versions where version_key=?", (parent_version_key,)
    ).fetchone():
        raise ValueError("parent_version_not_found")
    meta = probe(source)
    label = version_label or f"{episode}-import-{_stamp()}"
    video_row = con.execute("select * from videos where file_hash=?", (file_hash,)).fetchone()
    video_created = False
    if video_row:
        if video_row["episode"] != episode:
            raise ValueError("file_already_registered_to_other_episode")
        video_id = int(video_row["id"])
    else:
        video_id = source_video_id
        if video_id is not None and not con.execute("select 1 from videos where id=?", (video_id,)).fetchone():
            raise ValueError("source_video_not_found")
        con.execute(
            "insert into videos(episode,version,file_path,file_hash,duration_s,fps,width,height,"
            "permission_status,source_kind,source_type,provenance,creative_version,approval_status) "
            "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (episode, label, str(source), file_hash, meta.get("duration_s"),
             meta.get("fps"), meta.get("width"), meta.get("height"), permission_status,
             "review", "local", provenance, label, "unknown"),
        )
        video_id = int(con.execute("select last_insert_rowid()").fetchone()[0])
        video_created = True
    version_key = _key("ver", {
        "episode": episode, "file_hash": file_hash,
    })
    policy = PERMISSION_POLICY[permission_status]
    contract = {
        "contract_version": CONTRACT_EPISODE_VERSION,
        "version_key": version_key,
        "episode": episode,
        "imported_at": _now(),
        "status": "IMPORTED",
        "video_id": video_id,
        "parent_version_key": parent_version_key,
        "brief_key": brief_key,
        "file": {
            "path": str(source),
            "sha256": file_hash,
            "size_bytes": source.stat().st_size,
            "duration_s": _round(meta.get("duration_s")),
            "fps": _round(meta.get("fps")),
            "width": meta.get("width"),
            "height": meta.get("height"),
        },
        "permission": {
            "status": permission_status,
            "label": policy["label"],
            "comparison_allowed": policy["comparison"],
            "training_allowed": policy["training"],
            "derivative_allowed": False,
            "note": "El archivo se registra en su ruta original y nunca se mueve, modifica ni sobrescribe.",
        },
        "provenance": {
            "producer": provenance,
            "source_kind": "review",
            "video_created": video_created,
            "brief_key": brief_key,
        },
        "overwrite_policy": "NEVER_OVERWRITE",
        "intended_use": "comparison_only" if not policy["training"] else "comparison_and_possible_training",
        "training_eligible": bool(policy["training"]),
        "constraints": [
            "No se sobrescribe ninguna versión anterior.",
            "No se interrumpen renders ni trabajos activos.",
            "No se publica automáticamente.",
            "El hash se verificará de nuevo antes de una comparación.",
        ],
    }
    con.execute(
        "insert into episode_versions(version_key,episode,source_video_id,parent_version_key,brief_key,file_path,file_hash,duration_s,width,height,permission_status,provenance,status,import_contract_json) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (version_key, episode, video_id, parent_version_key, brief_key, str(source),
         file_hash, meta.get("duration_s"), meta.get("width"), meta.get("height"),
         permission_status, provenance, "IMPORTED", json_dumps(contract)),
    )
    _event(con, "EPISODE_VERSION_IMPORTED", "episode_version", version_key, {
        "episode": episode, "file_hash": file_hash, "video_id": video_id,
        "permission_status": permission_status,
    })
    con.commit()
    return contract


def import_version_contract(con, contract_path: str | Path, *,
                            allowed_roots: list[str | Path] | None = None) -> dict:
    path = Path(contract_path).expanduser().resolve()
    if not path.exists():
        raise ValueError("contract_file_not_found")
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != CONTRACT_EPISODE_VERSION:
        raise ValueError("episode_version_contract_required")
    if contract.get("status") == "TO_BE_COMPLETED_BY_PRODUCER":
        raise ValueError("contract_not_completed")
    file_path = contract.get("file_path") or (contract.get("file") or {}).get("path")
    if not file_path:
        raise ValueError("file_path_required")
    expected_hash = contract.get("file_sha256") or (contract.get("file") or {}).get("sha256")
    actual_hash = sha256_file(Path(file_path).expanduser().resolve())
    if expected_hash and actual_hash != expected_hash:
        raise ValueError("file_hash_mismatch")
    return import_episode_version(
        con, contract["episode"], file_path,
        contract.get("permission_status") or (contract.get("permission") or {}).get("status"),
        parent_version_key=contract.get("parent_version_key"),
        brief_key=contract.get("brief_key"),
        source_video_id=contract.get("video_id"),
        provenance=contract.get("provenance", "EXPLICIT_CONTRACT_IMPORT")
        if isinstance(contract.get("provenance"), str)
        else "EXPLICIT_CONTRACT_IMPORT",
        allowed_roots=allowed_roots,
        version_label=contract.get("version_label"),
    )


def verify_version_integrity(con, version_key: str) -> dict:
    version = _video_version(con, version_key)
    path = Path(version["file_path"])
    if not path.exists():
        return {"status": "MISSING", "version_key": version_key, "file_path": str(path)}
    actual = sha256_file(path)
    if actual != version["file_hash"]:
        return {
            "status": "HASH_MISMATCH", "version_key": version_key,
            "expected": version["file_hash"], "actual": actual,
        }
    return {"status": "MATCH", "version_key": version_key, "sha256": actual}


def get_episode_version(con, version_key: str) -> dict:
    version = _video_version(con, version_key)
    integrity = verify_version_integrity(con, version_key)
    return {
        "contract": version["contract"],
        "db": {
            "id": version["id"], "version_key": version["version_key"],
            "episode": version["episode"], "status": version["status"],
            "video_id": version["source_video_id"],
            "parent_version_key": version["parent_version_key"],
            "brief_key": version["brief_key"], "created_at": version["created_at"],
            "activated_at": version["activated_at"],
        },
        "integrity": integrity,
    }


def list_episode_versions(con, episode: str | None = None) -> list[dict]:
    if episode:
        rows = con.execute(
            "select * from episode_versions where episode=? order by id desc", (episode,)
        )
    else:
        rows = con.execute("select * from episode_versions order by id desc")
    result = []
    for row in rows:
        item = dict(row)
        item["contract"] = json.loads(item.pop("import_contract_json"))
        result.append(item)
    return result


def activate_episode_version(con, version_key: str) -> dict:
    version = _video_version(con, version_key)
    current = con.execute(
        "select version_key from episode_versions where episode=? and status='ACTIVE_FOR_COMPARISON'",
        (version["episode"],),
    ).fetchone()
    if current and current["version_key"] != version_key:
        con.execute(
            "update episode_versions set status='SUPERSEDED' where version_key=?",
            (current["version_key"],),
        )
    con.execute(
        "update episode_versions set status='ACTIVE_FOR_COMPARISON',activated_at=? where version_key=?",
        (_now(), version_key),
    )
    _event(con, "EPISODE_VERSION_ACTIVATED", "episode_version", version_key, {
        "episode": version["episode"],
        "previous": current["version_key"] if current else None,
    })
    con.commit()
    return {
        "status": "ACTIVE_FOR_COMPARISON", "version_key": version_key,
        "episode": version["episode"],
        "previous_version": current["version_key"] if current else None,
        "note": "Estado interno de comparación; no significa publicación.",
    }


def rollback_episode_version(con, version_key: str) -> dict:
    target = _video_version(con, version_key)
    current = con.execute(
        "select version_key from episode_versions where episode=? and status='ACTIVE_FOR_COMPARISON'",
        (target["episode"],),
    ).fetchone()
    if current and current["version_key"] != version_key:
        con.execute(
            "update episode_versions set status='ROLLED_BACK' where version_key=?",
            (current["version_key"],),
        )
    con.execute(
        "update episode_versions set status='ACTIVE_FOR_COMPARISON',activated_at=? where version_key=?",
        (_now(), version_key),
    )
    _event(con, "EPISODE_VERSION_ROLLED_BACK", "episode_version", version_key, {
        "episode": target["episode"],
        "rolled_back_from": current["version_key"] if current else None,
    })
    con.commit()
    return {
        "status": "ROLLED_BACK", "active_version": version_key,
        "rolled_back_from": current["version_key"] if current else None,
        "episode": target["episode"],
        "note": "Rollback de estado de comparación; no modifica archivos ni publicaciones.",
    }


def _score(value: Any, name: str) -> float | None:
    number = _num(value)
    if number is None:
        return None
    if number < 1 or number > 5:
        raise ValueError(f"{name}_must_be_1_to_5")
    return round(number, 2)


def record_version_evaluation(con, version_key: str, evaluator_id: str, *,
                              visual_impact: Any = None, realism: Any = None,
                              clarity: Any = None, hook: Any = None,
                              narrative: Any = None, business_value: Any = None,
                              cta: Any = None, preference: str | None = None,
                              compared_version_key: str | None = None,
                              confidence: Any = None, notes: str = "",
                              provenance: str = "human",
                              evaluated_at: str | None = None) -> dict:
    if not evaluator_id or not str(evaluator_id).strip():
        raise ValueError("identified_evaluator_required")
    version = _video_version(con, version_key)
    scores = {
        "visual_impact": _score(visual_impact, "visual_impact"),
        "realism": _score(realism, "realism"),
        "clarity": _score(clarity, "clarity"),
        "hook": _score(hook, "hook"),
        "narrative": _score(narrative, "narrative"),
        "business_value": _score(business_value, "business_value"),
        "cta": _score(cta, "cta"),
    }
    if all(value is None for value in scores.values()) and not preference:
        raise ValueError("at_least_one_score_or_preference_required")
    if preference is not None and preference not in ("A", "B", "tie", "no_preference"):
        raise ValueError("preference_not_supported")
    if preference in ("A", "B") and not compared_version_key:
        raise ValueError("compared_version_key_required_for_preference")
    if compared_version_key:
        _video_version(con, compared_version_key)
    gate_eligible = (
        provenance == "human"
        and evaluator_id not in ("", "anonymous")
        and any(value is not None for value in scores.values())
    )
    evaluation_key = _key("eval", {
        "version_key": version_key, "evaluator_id": evaluator_id,
        "scores": scores, "preference": preference, "at": _now(),
    })
    contract = {
        "contract_version": CONTRACT_HUMAN_EVALUATION,
        "evaluation_key": evaluation_key,
        "version_key": version_key,
        "episode": version["episode"],
        "evaluator_id": evaluator_id,
        "provenance": provenance,
        "scores": scores,
        "scale": "1-5",
        "preference": {
            "choice": preference,
            "compared_version_key": compared_version_key,
            "basis": "A/B" if compared_version_key else "single_version",
        },
        "confidence": _num(confidence),
        "notes": notes,
        "evaluated_at": evaluated_at or _now(),
        "gate_eligible": gate_eligible,
        "counts_for_training_gate": False,
        "note": (
            "La evaluación se conserva para el aprendizaje futuro, pero no modifica "
            "automáticamente el Training Gate V0.5 ni promociona modelos."
        ),
    }
    con.execute(
        "insert into version_evaluations(evaluation_key,version_key,episode,evaluator_id,provenance,"
        "visual_impact,realism,clarity,hook,narrative,business_value,cta,preference,"
        "compared_version_key,confidence,notes,gate_eligible,contract_version,payload_json,evaluated_at) "
        "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (evaluation_key, version_key, version["episode"], evaluator_id, provenance,
         scores["visual_impact"], scores["realism"], scores["clarity"], scores["hook"],
         scores["narrative"], scores["business_value"], scores["cta"], preference,
         compared_version_key, _num(confidence), notes, int(gate_eligible),
         CONTRACT_HUMAN_EVALUATION, json_dumps(contract), contract["evaluated_at"]),
    )
    _event(con, "VERSION_EVALUATION_RECORDED", "episode_version", version_key, {
        "evaluation_key": evaluation_key, "gate_eligible": gate_eligible,
        "provenance": provenance,
    })
    con.commit()
    return contract


def list_version_evaluations(con, version_key: str | None = None) -> list[dict]:
    if version_key:
        rows = con.execute(
            "select * from version_evaluations where version_key=? order by id desc",
            (version_key,),
        )
    else:
        rows = con.execute("select * from version_evaluations order by id desc")
    result = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        result.append(item)
    return result


def _metric_input(name: str, raw: Any, record_provenance: str,
                  measured_at: str | None) -> dict:
    if name not in PERFORMANCE_METRICS:
        raise ValueError(f"unknown_metric:{name}")
    if isinstance(raw, dict):
        value = raw.get("value")
        status = raw.get("status") or ("NOT_AVAILABLE" if value is None else "OBSERVED")
        provenance = raw.get("provenance") or record_provenance
        item_measured = raw.get("measured_at") or measured_at
        definition = raw.get("definition")
        verification = raw.get("verification")
        currency = raw.get("currency")
        note = raw.get("note")
    else:
        value = raw
        status = "NOT_AVAILABLE" if value is None else "OBSERVED"
        provenance = record_provenance
        item_measured = measured_at
        definition = None
        verification = None
        currency = None
        note = None
    if status not in PERFORMANCE_STATUSES:
        raise ValueError(f"metric_status_not_supported:{name}")
    if value is None:
        status = "NOT_AVAILABLE"
        numeric = None
    else:
        numeric = _num(value)
        if numeric is None:
            raise ValueError(f"metric_value_must_be_number_or_null:{name}")
        if status == "NOT_AVAILABLE":
            raise ValueError(f"not_available_must_be_null:{name}")
    if PERFORMANCE_METRICS[name] == "commercial":
        if provenance.upper().find("LIKE") >= 0 or "ENGAGEMENT" in provenance.upper():
            raise ValueError("likes_are_not_leads")
        if name in LEAD_METRICS and provenance.upper() not in LEAD_PROVENANCE:
            if numeric is not None:
                raise ValueError(f"commercial_metric_requires_legitimate_provenance:{name}")
        if verification is not None and verification not in LEAD_VERIFICATION:
            raise ValueError(f"verification_not_supported:{name}")
    return {
        "value": numeric,
        "status": status,
        "provenance": provenance,
        "measured_at": item_measured,
        "definition": definition or f"{name} as reported by {provenance}",
        "verification": verification or ("UNVERIFIED" if PERFORMANCE_METRICS[name] == "commercial" else None),
        "currency": currency,
        "note": note,
        "is_zero": numeric == 0 if numeric is not None else False,
        "is_missing": numeric is None,
    }


def record_performance(con, version_key: str, platform: str, measured_at: str | None,
                       metrics: dict, *, campaign: str | None = None,
                       published_at: str | None = None,
                       hook_used: str | None = None, cta_used: str | None = None,
                       provenance: str = "USER_PROVIDED",
                       notes: str = "") -> dict:
    """Record platform/commercial metrics for an exact episode version.

    ``None`` means missing and is preserved as ``NOT_AVAILABLE``. ``0`` is an
    observed zero. A like count can never be recorded as a lead.
    """
    if not platform or not str(platform).strip():
        raise ValueError("platform_required")
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError("metrics_required")
    version = _video_version(con, version_key)
    clean = {
        name: _metric_input(name, raw, provenance, measured_at)
        for name, raw in metrics.items()
    }
    observed = [item for item in clean.values() if item["value"] is not None]
    if not observed:
        status = "ALL_MISSING"
    elif len(observed) < len(clean):
        status = "PARTIAL"
    else:
        status = "OBSERVED_VERSION_EXACT"
    record_key = _key("perf", {
        "version_key": version_key, "platform": platform, "measured_at": measured_at,
        "metrics": clean, "provenance": provenance,
    })
    contract = {
        "contract_version": CONTRACT_PERFORMANCE_RECORD,
        "record_key": record_key,
        "version_key": version_key,
        "episode": version["episode"],
        "platform": platform,
        "campaign": campaign,
        "published_at": published_at,
        "measured_at": measured_at,
        "hook_used": hook_used,
        "cta_used": cta_used,
        "metrics": clean,
        "status": status,
        "provenance": provenance,
        "notes": notes,
        "created_at": _now(),
        "version_match": "EXACT_VERSION_KEY",
        "likes_are_not_leads": True,
        "guardrails": [
            "Métrica ausente (null / NOT_AVAILABLE) no es cero.",
            "Cero observado se conserva como cero y no se imputa.",
            "Likes, guardados y compartidos no son leads ni ventas.",
            "El registro está vinculado a la versión exacta, no sólo al episodio.",
        ],
    }
    con.execute(
        "insert into performance_records(record_key,version_key,episode,platform,campaign,published_at,"
        "measured_at,hook_used,cta_used,metrics_json,provenance,status,notes,contract_version,payload_json) "
        "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (record_key, version_key, version["episode"], platform, campaign, published_at,
         measured_at, hook_used, cta_used, json_dumps(clean), provenance, status,
         notes, CONTRACT_PERFORMANCE_RECORD, json_dumps(contract)),
    )
    _event(con, "PERFORMANCE_RECORDED", "episode_version", version_key, {
        "record_key": record_key, "platform": platform, "status": status,
    })
    con.commit()
    return contract


def list_performance_records(con, version_key: str | None = None) -> list[dict]:
    if version_key:
        rows = con.execute(
            "select * from performance_records where version_key=? order by id desc",
            (version_key,),
        )
    else:
        rows = con.execute("select * from performance_records order by id desc")
    result = []
    for row in rows:
        item = dict(row)
        item["performance"] = json.loads(item.pop("payload_json"))
        result.append(item)
    return result


def _latest_performance(con, version_key: str, platform: str) -> dict | None:
    row = con.execute(
        "select * from performance_records where version_key=? and platform=? "
        "order by id desc limit 1", (version_key, platform),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["metrics"] = json.loads(item.pop("metrics_json"))
    item["payload"] = json.loads(item.pop("payload_json"))
    return item


def _version_facts(con, version_key: str) -> dict:
    version = _video_version(con, version_key)
    video_id = version["source_video_id"]
    attention = latest_attention(con, video_id) if video_id else None
    if not attention and video_id:
        attention = analyze_attention(con, video_id)
    facts = (attention or {}).get("facts") or {}
    return {
        "version_key": version_key,
        "episode": version["episode"],
        "video_id": video_id,
        "status": "AVAILABLE" if facts else "NOT_AVAILABLE",
        "duration_s": facts.get("duration_s"),
        "cut_count": facts.get("cut_count"),
        "first_3s_cut_count": facts.get("first_3s_cut_count"),
        "avg_shot_s": facts.get("avg_shot_s"),
        "freeze_ratio": facts.get("freeze_ratio"),
        "brightness_mean": facts.get("brightness_mean"),
        "contrast_mean": facts.get("contrast_mean"),
        "estimate_overall": (attention or {}).get("overall", {}).get("score"),
        "estimate_status": "ESTIMATE_ONLY_NOT_VALIDATED",
    }


def _evaluation_summary(con, version_key: str) -> dict:
    rows = [dict(r) for r in con.execute(
        "select * from version_evaluations where version_key=? order by id desc",
        (version_key,),
    )]
    human = [row for row in rows if row["provenance"] == "human" and row["gate_eligible"]]
    means = {}
    for name in CREATIVE_DIMENSIONS:
        values = [row[name] for row in human if row[name] is not None]
        if values:
            means[name] = round(sum(values) / len(values), 2)
    return {
        "status": "AVAILABLE" if human else "NOT_AVAILABLE",
        "evaluations": len(rows),
        "gate_eligible_human_evaluations": len(human),
        "dimension_means_1_to_5": means,
        "provenance_counts": {
            key: sum(1 for row in rows if row["provenance"] == key)
            for key in sorted({row["provenance"] for row in rows})
        },
    }


def _pairwise_preference(con, version_a: str, version_b: str) -> dict:
    rows = [dict(r) for r in con.execute(
        "select * from version_evaluations where compared_version_key in (?,?) "
        "and version_key in (?,?) and preference is not null order by id",
        (version_a, version_b, version_a, version_b),
    )]
    counts = {"A": 0, "B": 0, "tie": 0, "no_preference": 0}
    for row in rows:
        if row["preference"] in counts:
            counts[row["preference"]] += 1
    return {
        "status": "AVAILABLE" if rows else "NOT_AVAILABLE",
        "counts": counts,
        "total": len(rows),
        "note": "La preferencia humana no se deduce de las estimaciones.",
    }


def compare_episode_versions(con, version_a: str, version_b: str,
                             platform: str | None = None,
                             persist: bool = True) -> dict:
    if version_a == version_b:
        raise ValueError("a_and_b_must_differ")
    a = _video_version(con, version_a)
    b = _video_version(con, version_b)
    if a["episode"] != b["episode"]:
        # A cross-episode comparison is allowed as a benchmark, never as a
        # controlled experiment. The contract states this explicitly.
        scope = "CROSS_EPISODE_BENCHMARK"
    else:
        scope = "SAME_EPISODE_VERSION_COMPARISON"
    integrity = {
        "a": verify_version_integrity(con, version_a),
        "b": verify_version_integrity(con, version_b),
    }
    platforms_a = sorted({row[0] for row in con.execute(
        "select distinct platform from performance_records where version_key=?", (version_a,)
    )})
    platforms_b = sorted({row[0] for row in con.execute(
        "select distinct platform from performance_records where version_key=?", (version_b,)
    )})
    chosen_platform = platform
    platform_status = "EXPLICIT" if platform else "INFERRED"
    if not chosen_platform:
        common = sorted(set(platforms_a) & set(platforms_b))
        if len(common) == 1:
            chosen_platform = common[0]
        elif len(common) > 1:
            chosen_platform = common[0]
            platform_status = "MULTIPLE_COMMON_PLATFORMS_FIRST_USED"
        else:
            chosen_platform = None
            platform_status = "NO_COMMON_PLATFORM"
    record_a = _latest_performance(con, version_a, chosen_platform) if chosen_platform else None
    record_b = _latest_performance(con, version_b, chosen_platform) if chosen_platform else None
    metrics = []
    if chosen_platform:
        names = sorted(set((record_a or {}).get("metrics", {})) | set((record_b or {}).get("metrics", {})))
        for name in names:
            entry_a = (record_a or {}).get("metrics", {}).get(name)
            entry_b = (record_b or {}).get("metrics", {}).get(name)
            missing_a = entry_a is None or entry_a.get("value") is None
            missing_b = entry_b is None or entry_b.get("value") is None
            if missing_a and missing_b:
                comparability = "BOTH_MISSING"
            elif missing_a:
                comparability = "MISSING_A"
            elif missing_b:
                comparability = "MISSING_B"
            elif entry_a.get("status") == "ESTIMATED" or entry_b.get("status") == "ESTIMATED":
                comparability = "ESTIMATE_ONLY"
            elif PERFORMANCE_METRICS.get(name) == "commercial" and (
                (entry_a.get("verification") or "UNVERIFIED") not in ("VERIFIED", "OWNER_CONFIRMED")
                or (entry_b.get("verification") or "UNVERIFIED") not in ("VERIFIED", "OWNER_CONFIRMED")
            ):
                comparability = "UNVERIFIED_COMMERCIAL"
            elif entry_a.get("measured_at") != entry_b.get("measured_at") and (
                entry_a.get("measured_at") and entry_b.get("measured_at")
            ):
                comparability = "DIFFERENT_MEASUREMENT_DATE"
            else:
                comparability = "COMPARABLE"
            delta = None
            if not missing_a and not missing_b:
                delta = round(float(entry_b["value"]) - float(entry_a["value"]), 4)
            metrics.append({
                "name": name,
                "family": PERFORMANCE_METRICS.get(name, "unknown"),
                "a": entry_a or {"value": None, "status": "NOT_AVAILABLE", "is_missing": True, "is_zero": False},
                "b": entry_b or {"value": None, "status": "NOT_AVAILABLE", "is_missing": True, "is_zero": False},
                "delta_b_minus_a": delta,
                "comparability": comparability,
                "note": (
                    "Valor ausente; no es cero." if comparability in ("MISSING_A", "MISSING_B", "BOTH_MISSING")
                    else "Comparación descriptiva; no prueba causalidad."
                ),
            })
    comparable = [item for item in metrics if item["comparability"] == "COMPARABLE"]
    missing = [item for item in metrics if item["comparability"] in
               ("MISSING_A", "MISSING_B", "BOTH_MISSING")]
    human = {
        "a": _evaluation_summary(con, version_a),
        "b": _evaluation_summary(con, version_b),
        "pairwise": _pairwise_preference(con, version_a, version_b),
    }
    if not chosen_platform:
        summary_status = "NO_COMMON_PLATFORM"
    elif not record_a and not record_b:
        summary_status = "NO_PERFORMANCE_DATA"
    elif not comparable:
        summary_status = "DESCRIPTIVE_ONLY_INSUFFICIENT_MATCH"
    elif human["a"]["status"] == "AVAILABLE" or human["b"]["status"] == "AVAILABLE":
        summary_status = "HUMAN_AND_PERFORMANCE_EVIDENCE_AVAILABLE"
    else:
        summary_status = "PERFORMANCE_EVIDENCE_ONLY_HUMAN_REVIEW_MISSING"
    contract = {
        "contract_version": CONTRACT_PERFORMANCE_COMPARISON,
        "comparison_key": _key("cmp", {
            "a": version_a, "b": version_b, "platform": chosen_platform,
        }),
        "created_at": _now(),
        "status": "COMPARISON_DESCRIPTIVE_ONLY",
        "scope": scope,
        "a": {
            "version_key": version_a, "episode": a["episode"],
            "file_hash": a["file_hash"], "label": "A",
            "permission_status": a["permission_status"],
            "facts": _version_facts(con, version_a),
            "performance_record_key": (record_a or {}).get("record_key"),
        },
        "b": {
            "version_key": version_b, "episode": b["episode"],
            "file_hash": b["file_hash"], "label": "B",
            "permission_status": b["permission_status"],
            "facts": _version_facts(con, version_b),
            "performance_record_key": (record_b or {}).get("record_key"),
        },
        "match": {
            "platform": chosen_platform,
            "platform_status": platform_status,
            "platforms_a": platforms_a,
            "platforms_b": platforms_b,
            "exact_version_keys": True,
            "integrity": integrity,
            "measurement_basis": "exact episode version; episode-linked data is not used",
        },
        "metrics": metrics,
        "human_evaluations": human,
        "summary": {
            "status": summary_status,
            "comparable_metrics": len(comparable),
            "missing_metrics": len(missing),
            "automatic_winner": None,
            "winner_policy": "Ningún ganador se declara con estimaciones o métricas descriptivas.",
            "commercial_improvement_claimed": False,
            "requires_real_measurement": True,
            "likes_are_not_leads": True,
        },
        "limitations": [
            "Una comparación entre versiones distintas no es un experimento controlado.",
            "Las métricas de plataforma son observacionales y pueden tener fechas o definiciones distintas.",
            "Los ausentes se conservan como NOT_AVAILABLE; no se imputan como cero.",
            "No se declara mejora comercial sin medición real y verificable.",
        ],
    }
    if persist:
        existing = con.execute(
            "select id from version_comparisons where comparison_key=?",
            (contract["comparison_key"],),
        ).fetchone()
        if not existing:
            con.execute(
                "insert into version_comparisons(comparison_key,version_a_key,version_b_key,contract_version,payload_json) values(?,?,?,?,?)",
                (contract["comparison_key"], version_a, version_b,
                 CONTRACT_PERFORMANCE_COMPARISON, json_dumps(contract)),
            )
            contract["comparison_id"] = int(
                con.execute("select last_insert_rowid()").fetchone()[0]
            )
        _event(con, "VERSION_COMPARISON_CREATED", "performance_comparison",
               contract["comparison_key"], {
                   "a": version_a, "b": version_b, "status": summary_status,
               })
        con.commit()
    return contract


def loop_status(con) -> dict:
    from .learning import gate_report

    gate = gate_report(con)
    counts = {
        "creative_reviews": con.execute("select count(*) from creative_reviews").fetchone()[0],
        "recommended_changes": con.execute("select count(*) from recommended_changes").fetchone()[0],
        "production_briefs": con.execute("select count(*) from production_briefs").fetchone()[0],
        "episode_versions": con.execute("select count(*) from episode_versions").fetchone()[0],
        "human_approvals": con.execute("select count(*) from human_approvals").fetchone()[0],
        "version_evaluations": con.execute("select count(*) from version_evaluations").fetchone()[0],
        "gate_eligible_version_evaluations": con.execute(
            "select count(*) from version_evaluations where gate_eligible=1"
        ).fetchone()[0],
        "performance_records": con.execute("select count(*) from performance_records").fetchone()[0],
        "version_comparisons": con.execute("select count(*) from version_comparisons").fetchone()[0],
    }
    recent_reviews = [
        {
            "review_key": row["review_key"], "episode": row["episode"],
            "version": row["version_label"], "created_at": row["created_at"],
            "status": row["status"],
        }
        for row in con.execute("select * from creative_reviews order by id desc limit 10")
    ]
    recent_versions = [
        {
            "version_key": row["version_key"], "episode": row["episode"],
            "status": row["status"], "permission_status": row["permission_status"],
            "created_at": row["created_at"], "file_path": row["file_path"],
        }
        for row in con.execute("select * from episode_versions order by id desc limit 10")
    ]
    return {
        "loop_version": LOOP_VERSION,
        "schema_version": con.execute(
            "select value from schema_meta where key='schema_version'"
        ).fetchone()[0],
        "contract_versions": {
            "creative_review": CONTRACT_CREATIVE_REVIEW,
            "visual_defects": CONTRACT_VISUAL_DEFECTS,
            "recommended_changes": CONTRACT_RECOMMENDED_CHANGES,
            "production_brief": CONTRACT_PRODUCTION_BRIEF,
            "episode_version": CONTRACT_EPISODE_VERSION,
            "human_approval": CONTRACT_HUMAN_APPROVAL,
            "human_evaluation": CONTRACT_HUMAN_EVALUATION,
            "performance_record": CONTRACT_PERFORMANCE_RECORD,
            "performance_comparison": CONTRACT_PERFORMANCE_COMPARISON,
        },
        "counts": counts,
        "recent_reviews": recent_reviews,
        "recent_versions": recent_versions,
        "training_state": gate["training_state"],
        "gate_status": gate["status"],
        "learning_readiness": {
            "version_evaluations_gate_eligible": counts["gate_eligible_version_evaluations"],
            "note": (
                "Las evaluaciones V0.6 se conservan para aprendizaje futuro, pero "
                "no cambian automáticamente el Training Gate V0.5."
            ),
        },
        "next_actions": [
            "Crear un Creative Review para una versión autorizada.",
            "Exportar el Production Brief y entregarlo sólo con autorización explícita.",
            "Importar la versión producida con ruta, hash y permiso explícitos.",
            "Comparar versiones y registrar evaluación humana identificada.",
            "Registrar métricas de plataforma y comerciales por versión exacta; no imputar ausentes.",
        ],
        "guardrails": [
            "No se escribe en proyectos de Claude Code o Codex.",
            "No se interrumpen renders ni se sobrescriben episodios.",
            "No se declara mejora comercial sin medición real.",
            "No se promociona ningún modelo automáticamente.",
        ],
    }
