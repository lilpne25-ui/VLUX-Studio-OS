from __future__ import annotations

"""A/B comparator that keeps four evidence layers separate:

1. observed audiovisual facts;
2. heuristic estimates;
3. human preferences;
4. real commercial results.

The comparator does not elect a winner from heuristic scores.
"""

import json
from datetime import datetime, timezone
from typing import Any

from .attention import analyze_attention, results_for_video
from .db import json_dumps

CONTRACT_VERSION = "ab-comparison.v0.1"
HUMAN_DIMENSIONS = ("hook", "narrative", "production", "commercial", "cta", "clarity")
VALID_PROVENANCE = ("human", "ai_assisted", "synthetic", "demo")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def record_evaluation(con, video_id: int, evaluator_id: str = "anonymous",
                      provenance: str = "human", hook: float | None = None,
                      narrative: float | None = None, production: float | None = None,
                      commercial: float | None = None, cta: float | None = None,
                      clarity: float | None = None, confidence: float | None = None,
                      notes: str = "", evaluated_at: str | None = None) -> int:
    if not con.execute("select 1 from videos where id=?", (video_id,)).fetchone():
        raise ValueError("video_not_found")
    if provenance not in VALID_PROVENANCE:
        raise ValueError("invalid_provenance")
    scores = {"hook": hook, "narrative": narrative, "production": production,
              "commercial": commercial, "cta": cta, "clarity": clarity}
    clean = {}
    for name, value in scores.items():
        if value is None:
            clean[name] = None
            continue
        number = _num(value)
        if number is None or not 1 <= number <= 5:
            raise ValueError(f"invalid_{name}_score_must_be_1_to_5")
        clean[name] = number
    if all(value is None for value in clean.values()):
        raise ValueError("at_least_one_score_required")
    if confidence is not None:
        confidence = _num(confidence)
        if confidence is None or not 0 <= confidence <= 1:
            raise ValueError("invalid_confidence")
    if provenance == "human" and not str(evaluator_id).strip():
        evaluator_id = "anonymous"
    con.execute(
        "insert into video_evaluations(video_id,hook,narrative,production,commercial,cta,clarity,confidence,evaluator_id,provenance,evaluated_at,notes) values(?,?,?,?,?,?,?,?,?,?,?,?)",
        (video_id, clean["hook"], clean["narrative"], clean["production"],
         clean["commercial"], clean["cta"], clean["clarity"], confidence,
         evaluator_id or "anonymous", provenance, evaluated_at or _now(), notes),
    )
    con.commit()
    return int(con.execute("select last_insert_rowid()").fetchone()[0])


def _human_profile(con, video_id: int) -> dict:
    rows = [dict(r) for r in con.execute(
        "select * from video_evaluations where video_id=? and provenance='human' and evaluator_id!='anonymous' order by id",
        (video_id,),
    )]
    dimensions: dict[str, list[float]] = {name: [] for name in HUMAN_DIMENSIONS}
    evaluators = set()
    evaluated_at = []
    for row in rows:
        evaluators.add(row["evaluator_id"])
        if row.get("evaluated_at"):
            evaluated_at.append(row["evaluated_at"])
        for name in HUMAN_DIMENSIONS:
            value = _num(row.get(name))
            if value is not None:
                dimensions[name].append(value)
    means = {
        name: round(sum(values) / len(values), 3) for name, values in dimensions.items() if values
    }
    return {
        "status": "AVAILABLE" if rows else "NOT_AVAILABLE",
        "evaluations": len(rows),
        "anonymous_evaluations": sum(1 for r in rows if r["evaluator_id"] == "anonymous"),
        "evaluators": len(evaluators),
        "dimension_means_1_to_5": means,
        "evaluated_at": sorted(set(evaluated_at)),
        "provenance": "human",
        "note": "Preferencias humanas declaradas; no son resultados comerciales ni verdad objetiva.",
    }


def _excluded_ai(con, video_id: int) -> dict:
    rows = [dict(r) for r in con.execute(
        "select provenance,count(*) as n from video_evaluations where video_id=? and provenance!='human' group by provenance",
        (video_id,),
    )]
    anonymous = con.execute(
        "select count(*) from video_evaluations where video_id=? and provenance='human' and evaluator_id='anonymous'",
        (video_id,),
    ).fetchone()[0]
    return {
        "excluded_from_human_gate": sum(r["n"] for r in rows) + anonymous,
        "excluded_non_human": sum(r["n"] for r in rows),
        "excluded_anonymous": anonymous,
        "by_provenance": rows,
    }


def _pairwise_feedback(con, a_id: int, b_id: int) -> dict:
    rows = [dict(r) for r in con.execute(
        "select * from feedback where (variant_a_id=? and variant_b_id=?) or (variant_a_id=? and variant_b_id=?) order by id",
        (a_id, b_id, b_id, a_id),
    )]
    counts = {"A": 0, "B": 0, "tie": 0, "non_human_excluded": 0}
    for row in rows:
        if row.get("origin") != "human":
            counts["non_human_excluded"] += 1
            continue
        winner = row["winner"]
        if row["variant_a_id"] == b_id and row["variant_b_id"] == a_id:
            winner = {"A": "B", "B": "A", "tie": "tie"}[winner]
        counts[winner] += 1
    total = counts["A"] + counts["B"] + counts["tie"]
    return {
        "status": "AVAILABLE" if total else "NOT_AVAILABLE",
        "counts": counts,
        "total": total,
        "note": "Preferencia pareada humana; no se extrapola a resultados de negocio.",
    }


def _facts_comparison(a_facts: dict, b_facts: dict) -> list[dict]:
    fields = [
        ("duration_s", "Duración", "s"),
        ("fps", "FPS", None),
        ("cut_count", "Cortes detectados", "cortes"),
        ("first_3s_cut_count", "Cortes antes de 3 s", "cortes"),
        ("avg_shot_s", "Plano medio", "s"),
        ("motion_mean_full", "Movimiento medio global", "diff"),
        ("first_3s_motion", "Movimiento en primeros 3 s", "diff"),
        ("brightness_mean", "Luminosidad media", "0-255"),
        ("contrast_mean", "Contraste medio", "0-255"),
        ("edge_density_mean", "Densidad de bordes", "ratio"),
        ("freeze_ratio", "Proporción casi estática", "ratio"),
        ("silence_ratio", "Proporción de silencio", "ratio"),
    ]
    items = []
    for key, label, unit in fields:
        a_value = _num(a_facts.get(key))
        b_value = _num(b_facts.get(key))
        if a_value is None and b_value is None:
            continue
        delta = None if a_value is None or b_value is None else round(b_value - a_value, 3)
        if delta is None:
            direction = "unknown"
        elif delta > 0:
            direction = "B_higher"
        elif delta < 0:
            direction = "A_higher"
        else:
            direction = "equal"
        items.append({
            "key": key, "label": label, "unit": unit,
            "a": _round(a_value), "b": _round(b_value), "delta_b_minus_a": delta,
            "direction": direction,
            "interpretation": "Diferencia observada; no implica mejor calidad.",
        })
    return items


def _estimate_comparison(a: dict, b: dict) -> list[dict]:
    layers = [
        ("hook", "Gancho", a.get("hook", {}), b.get("hook", {})),
        ("narrative", "Narrativa", a.get("narrative", {}), b.get("narrative", {})),
        ("production", "Producción", a.get("production", {}), b.get("production", {})),
        ("commercial", "Valor comercial", a.get("commercial_value", {}), b.get("commercial_value", {})),
        ("overall", "Índice conjunto", a.get("overall", {}), b.get("overall", {})),
    ]
    items = []
    for key, label, a_item, b_item in layers:
        a_score = _num(a_item.get("score"))
        b_score = _num(b_item.get("score"))
        delta = None if a_score is None or b_score is None else round(b_score - a_score)
        items.append({
            "key": key, "label": label,
            "a_estimate": _round(a_score), "b_estimate": _round(b_score),
            "delta_b_minus_a": delta,
            "a_confidence": a_item.get("confidence"),
            "b_confidence": b_item.get("confidence"),
            "direction": "unknown" if delta is None else "B_higher" if delta > 0 else "A_higher" if delta < 0 else "equal",
            "interpretation": "Estimación heurística; no es preferencia humana ni resultado.",
        })
    return items


def _commercial_comparison(con, a_video: dict, b_video: dict) -> dict:
    a_results = results_for_video(con, a_video)
    b_results = results_for_video(con, b_video)
    a_signal = a_results.get("commercial_signal", {})
    b_signal = b_results.get("commercial_signal", {})
    comparable = a_signal.get("status") == "OBSERVED" and b_signal.get("status") == "OBSERVED"
    return {
        "status": "COMPARABLE" if comparable else "NOT_COMPARABLE",
        "a": a_results,
        "b": b_results,
        "reason": (
            "Ambos lados tienen algún registro comercial observado."
            if comparable else
            "Falta un registro comercial verificable en al menos un lado; likes y visualizaciones no son ventas."
        ),
        "guardrails": [
            "No se comparan likes como si fueran leads o ventas.",
            "Las fechas de medición y la procedencia deben coincidir para una comparación válida.",
        ],
    }


def compare(con, a_id: int, b_id: int, persist: bool = True) -> dict:
    if a_id == b_id:
        raise ValueError("a_and_b_must_differ")
    rows = {r["id"]: dict(r) for r in con.execute(
        "select * from videos where id in (?,?)", (a_id, b_id)
    )}
    if a_id not in rows or b_id not in rows:
        raise ValueError("video_not_found")
    a_video, b_video = rows[a_id], rows[b_id]
    a_attention = analyze_attention(con, a_id)
    b_attention = analyze_attention(con, b_id)
    a_human = _human_profile(con, a_id)
    b_human = _human_profile(con, b_id)
    pairwise = _pairwise_feedback(con, a_id, b_id)
    human_available = (a_human["status"] == "AVAILABLE" or b_human["status"] == "AVAILABLE"
                       or pairwise["status"] == "AVAILABLE")
    commercial = _commercial_comparison(con, a_video, b_video)
    estimates = _estimate_comparison(a_attention, b_attention)
    estimated_advantages = [
        {"dimension": item["key"], "label": item["label"],
         "favored_side": "B" if item["direction"] == "B_higher" else "A",
         "delta": abs(item["delta_b_minus_a"]),
         "status": "ESTIMATE_ONLY"}
        for item in estimates
        if item["delta_b_minus_a"] is not None and abs(item["delta_b_minus_a"]) >= 8
    ]
    if human_available and commercial["status"] == "COMPARABLE":
        decision = "HUMAN_AND_COMMERCIAL_EVIDENCE_AVAILABLE"
    elif human_available:
        decision = "HUMAN_PREFERENCE_AVAILABLE_COMMERCIAL_RESULTS_MISSING"
    elif commercial["status"] == "COMPARABLE":
        decision = "COMMERCIAL_RESULTS_AVAILABLE_HUMAN_PREFERENCE_MISSING"
    else:
        decision = "HUMAN_REVIEW_AND_RESULTS_REQUIRED"
    recommendations = []
    if not human_available:
        recommendations.append({
            "priority": "high", "action": "Recoger evaluación humana por dimensión (1-5) con evaluador identificado.",
            "reason": "No hay preferencia humana verificable para este par.",
            "status": "PROPOSAL",
        })
    if commercial["status"] != "COMPARABLE":
        recommendations.append({
            "priority": "high", "action": "Registrar resultados comerciales con fecha y procedencia; no inferirlos de likes.",
            "reason": "La capa comercial no es comparable.",
            "status": "PROPOSAL",
        })
    if estimated_advantages:
        top = estimated_advantages[0]
        recommendations.append({
            "priority": "medium",
            "action": f"Probar una sola variable en {top['label'].lower()} y medir el resultado antes de cambiar otra.",
            "reason": "Hay una diferencia de estimación, no una prueba de calidad.",
            "status": "PROPOSAL",
        })
    contract = {
        "contract_version": CONTRACT_VERSION,
        "status": "COMPARISON_ESTIMATE_ONLY",
        "evaluated_at": _now(),
        "a": {
            "video_id": a_id, "episode": a_video["episode"], "label": "A",
            "attention_status": a_attention.get("status"),
            "overall_estimate": a_attention.get("overall", {}).get("score"),
            "first_change": a_attention.get("first_change"),
        },
        "b": {
            "video_id": b_id, "episode": b_video["episode"], "label": "B",
            "attention_status": b_attention.get("status"),
            "overall_estimate": b_attention.get("overall", {}).get("score"),
            "first_change": b_attention.get("first_change"),
        },
        "observed_facts": _facts_comparison(a_attention["facts"], b_attention["facts"]),
        "estimates": estimates,
        "human_preferences": {
            "status": "AVAILABLE" if human_available else "NOT_AVAILABLE",
            "a": a_human, "b": b_human, "pairwise": pairwise,
            "excluded_non_human": {"a": _excluded_ai(con, a_id), "b": _excluded_ai(con, b_id)},
            "note": "La preferencia humana no se deduce de las estimaciones.",
        },
        "commercial_results": commercial,
        "summary": {
            "decision_status": decision,
            "estimated_advantages": estimated_advantages,
            "automatic_winner": None,
            "winner_policy": "Ningún ganador se declara sólo con estimaciones heurísticas.",
            "human_evidence": human_available,
            "commercial_evidence": commercial["status"] == "COMPARABLE",
        },
        "recommendations": recommendations,
        "limitations": [
            "Este contrato compara hechos, estimaciones, preferencias y resultados sin fusionarlos.",
            "Las diferencias objetivas no prueban qué versión funciona mejor en una plataforma.",
            "La muestra es insuficiente para inferencia causal o entrenamiento.",
        ],
    }
    if persist:
        con.execute(
            "insert into ab_comparisons(a_video_id,b_video_id,contract_version,payload_json) values(?,?,?,?)",
            (a_id, b_id, CONTRACT_VERSION, json_dumps(contract)),
        )
        con.commit()
        contract["comparison_id"] = con.execute("select last_insert_rowid()").fetchone()[0]
    return contract


def latest_comparison(con, a_id: int, b_id: int) -> dict | None:
    row = con.execute(
        "select * from ab_comparisons where a_video_id=? and b_video_id=? order by id desc limit 1",
        (a_id, b_id),
    ).fetchone()
    if not row:
        return None
    payload = json.loads(row["payload_json"])
    payload["comparison_id"] = row["id"]
    return payload


def list_evaluations(con, video_id: int | None = None) -> list[dict]:
    if video_id is None:
        rows = con.execute(
            "select e.*,v.episode from video_evaluations e join videos v on v.id=e.video_id order by e.id desc"
        )
    else:
        rows = con.execute(
            "select e.*,v.episode from video_evaluations e join videos v on v.id=e.video_id where e.video_id=? order by e.id desc",
            (video_id,),
        )
    return [dict(row) for row in rows]
