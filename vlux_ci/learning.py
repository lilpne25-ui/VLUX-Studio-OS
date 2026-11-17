from __future__ import annotations

"""Learning governance for VLUX Attention Lab.

The gate is intentionally conservative: no training happens until independent
episodes, identified human evaluations, authorized data, legitimate commercial
records and a viable episode-level holdout exist. The state remains
NO_TRAINING_INSUFFICIENT_DATA while any requirement is missing.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .db import json_dumps
from .ml import Baseline, load_rows, train_rows

TRAINING_PERMISSIONS = {"authorized", "owned", "synthetic", "public_domain"}
TRAINING_SOURCE_KINDS = {"published", "review", "synthetic"}
COMMERCIAL_METRICS = ("leads", "qualified_leads", "meetings", "proposals", "closed_won", "conversations")
HUMAN_DIMENSIONS = ("hook", "narrative", "production", "commercial", "cta", "clarity")
ILLEGITIMATE_PROVENANCE = ("SYNTHETIC", "DEMO", "FIXTURE", "TEST", "AI_ASSISTED")

GATE_THRESHOLDS = {
    "eligible_videos": 12,
    "independent_episodes": 4,
    "human_evaluations": 12,
    "evaluated_videos": 4,
    "commercial_records": 5,
    "minimum_label_classes": 2,
    "minimum_episodes_with_labels": 2,
    "holdout_design": "complete_episode",
}

TRAINING_STATE_BLOCKED = "NO_TRAINING_INSUFFICIENT_DATA"
TRAINING_STATE_READY = "READY_FOR_GATED_TRAINING"
TRAINING_STATE_CANDIDATE = "CANDIDATE_TRAINED_AWAITING_HUMAN_APPROVAL"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _eligible_videos(con) -> list[dict]:
    rows = [dict(r) for r in con.execute(
        "select id,episode,version,file_hash,permission_status,source_kind,file_path from videos order by id"
    )]
    return [
        row for row in rows
        if row.get("permission_status") in TRAINING_PERMISSIONS
        and row.get("source_kind") in TRAINING_SOURCE_KINDS
    ]


def _human_evaluations(con, eligible_ids: set[int]) -> list[dict]:
    rows = [dict(r) for r in con.execute(
        "select e.*,v.episode from video_evaluations e join videos v on v.id=e.video_id "
        "where e.provenance='human' and e.evaluator_id!='anonymous' order by e.id"
    )]
    result = []
    for row in rows:
        if row["video_id"] not in eligible_ids:
            continue
        if not any(_num(row.get(name)) is not None for name in HUMAN_DIMENSIONS):
            continue
        result.append(row)
    return result


def _commercial_records(con) -> list[dict]:
    rows = [dict(r) for r in con.execute(
        "select pm.id,pm.publication_id,pm.metric_name,pm.metric_value,pm.status,pm.provenance,pm.measured_at,"
        "p.episode,p.video_id from platform_metrics pm join publications p on p.id=pm.publication_id "
        "where pm.metric_name in (%s) and pm.metric_value is not null and pm.status='OBSERVED' order by pm.id"
        % ",".join("?" for _ in COMMERCIAL_METRICS),
        COMMERCIAL_METRICS,
    )]
    legit = []
    latest: dict[tuple[int, str], dict] = {}
    for row in rows:
        # Repeated imports of the same metric are one commercial record, not several.
        latest[(row["publication_id"], row["metric_name"])] = row
    for row in latest.values():
        provenance = str(row.get("provenance") or "").upper()
        if any(token in provenance for token in ILLEGITIMATE_PROVENANCE):
            continue
        row["provenance_is_user_reported"] = provenance == "USER_PROVIDED_SCREENSHOT"
        legit.append(row)
    return legit


def labels_by_video(con, evaluations: list[dict] | None = None) -> dict[int, dict]:
    eligible = _eligible_videos(con)
    eligible_ids = {row["id"] for row in eligible}
    evaluations = evaluations if evaluations is not None else _human_evaluations(con, eligible_ids)
    grouped: dict[int, list[dict]] = {}
    for row in evaluations:
        grouped.setdefault(row["video_id"], []).append(row)
    result = {}
    for video_id, rows in grouped.items():
        values = []
        for row in rows:
            for name in HUMAN_DIMENSIONS:
                value = _num(row.get(name))
                if value is not None:
                    values.append(value)
        if not values:
            continue
        mean = sum(values) / len(values)
        result[video_id] = {
            "evaluations": len(rows),
            "mean_rating_1_to_5": round(mean, 3),
            "label": 1 if mean >= 3.5 else 0,
            "evaluators": sorted({row["evaluator_id"] for row in rows}),
        }
    return result


def gate_report(con) -> dict:
    eligible = _eligible_videos(con)
    eligible_ids = {row["id"] for row in eligible}
    evaluations = _human_evaluations(con, eligible_ids)
    commercial = _commercial_records(con)
    labels = labels_by_video(con, evaluations)
    episodes = sorted({row["episode"] for row in eligible})
    evaluated_videos = sorted({row["video_id"] for row in evaluations})
    label_episodes = sorted({row["episode"] for row in eligible if row["id"] in labels})
    label_classes = sorted({item["label"] for item in labels.values()})
    excluded_ai = con.execute(
        "select count(*) from video_evaluations where provenance!='human'"
    ).fetchone()[0]
    excluded_anonymous = con.execute(
        "select count(*) from video_evaluations where evaluator_id='anonymous'"
    ).fetchone()[0]
    all_videos = con.execute("select count(*) from videos").fetchone()[0]
    unknown_permission = con.execute(
        "select count(*) from videos where permission_status='unknown' or permission_status is null"
    ).fetchone()[0]

    checks = [
        {
            "name": "eligible_videos", "label": "Videos independientes autorizados",
            "have": len(eligible), "required": GATE_THRESHOLDS["eligible_videos"],
            "ok": len(eligible) >= GATE_THRESHOLDS["eligible_videos"],
            "note": "Sólo videos con permiso authorized/owned/synthetic/public_domain.",
        },
        {
            "name": "independent_episodes", "label": "Episodios independientes",
            "have": len(episodes), "required": GATE_THRESHOLDS["independent_episodes"],
            "ok": len(episodes) >= GATE_THRESHOLDS["independent_episodes"],
            "note": "El holdout se hace por episodio completo.",
        },
        {
            "name": "human_evaluations", "label": "Evaluaciones humanas identificadas",
            "have": len(evaluations), "required": GATE_THRESHOLDS["human_evaluations"],
            "ok": len(evaluations) >= GATE_THRESHOLDS["human_evaluations"],
            "note": "Excluye evaluaciones anónimas y cualquier provenance distinta de human.",
        },
        {
            "name": "evaluated_videos", "label": "Videos con evaluación humana",
            "have": len(evaluated_videos), "required": GATE_THRESHOLDS["evaluated_videos"],
            "ok": len(evaluated_videos) >= GATE_THRESHOLDS["evaluated_videos"],
            "note": "Evita que una sola pieza concentre todas las etiquetas.",
        },
        {
            "name": "commercial_records", "label": "Registros comerciales legítimos",
            "have": len(commercial), "required": GATE_THRESHOLDS["commercial_records"],
            "ok": len(commercial) >= GATE_THRESHOLDS["commercial_records"],
            "note": "Leads, reuniones, propuestas o ventas observadas; excluye datos sintéticos/demo.",
        },
        {
            "name": "label_classes", "label": "Clases de etiqueta",
            "have": len(label_classes), "required": GATE_THRESHOLDS["minimum_label_classes"],
            "ok": len(label_classes) >= GATE_THRESHOLDS["minimum_label_classes"],
            "note": "Se necesitan ejemplos favorables y desfavorables según la media humana 1-5.",
        },
        {
            "name": "episodes_with_labels", "label": "Episodios con etiquetas",
            "have": len(label_episodes), "required": GATE_THRESHOLDS["minimum_episodes_with_labels"],
            "ok": len(label_episodes) >= GATE_THRESHOLDS["minimum_episodes_with_labels"],
            "note": "El holdout necesita al menos dos episodios etiquetados.",
        },
    ]
    blocking = [
        {
            "name": check["name"], "have": check["have"], "required": check["required"],
            "message": f"{check['label']}: {check['have']}/{check['required']}",
        }
        for check in checks if not check["ok"]
    ]
    eligible_now = not blocking
    warnings = []
    if excluded_ai:
        warnings.append(f"{excluded_ai} evaluaciones no humanas excluidas del gate.")
    if excluded_anonymous:
        warnings.append(f"{excluded_anonymous} evaluaciones anónimas excluidas del gate.")
    if unknown_permission:
        warnings.append(
            f"{unknown_permission} videos con permiso unknown no se incluyen en el dataset de entrenamiento."
        )
    if any(row["provenance_is_user_reported"] for row in commercial):
        warnings.append(
            "Algunos registros comerciales son reportados por el usuario y no están verificados por API."
        )
    payload = {
        "status": "ELIGIBLE" if eligible_now else "BLOCKED",
        "training_state": TRAINING_STATE_READY if eligible_now else TRAINING_STATE_BLOCKED,
        "evaluated_at": _now(),
        "thresholds": GATE_THRESHOLDS,
        "checks": checks,
        "blocking_reasons": blocking,
        "warnings": warnings,
        "counts": {
            "all_videos": all_videos,
            "eligible_videos": len(eligible),
            "excluded_videos": all_videos - len(eligible),
            "episodes": len(episodes),
            "human_evaluations": len(evaluations),
            "evaluated_videos": len(evaluated_videos),
            "commercial_records": len(commercial),
            "label_classes": label_classes,
            "episodes_with_labels": len(label_episodes),
            "excluded_ai_evaluations": excluded_ai,
            "excluded_anonymous_evaluations": excluded_anonymous,
        },
        "authorization_status": (
            "ALL_ELIGIBLE_AUTHORIZED" if eligible else "NO_ELIGIBLE_AUTHORIZED_VIDEOS"
        ),
        "never_auto_train": True,
        "policy": "El entrenamiento sólo se ejecuta mediante run_gated_training y nunca por el dashboard.",
    }
    return payload


def dataset_registry(con) -> dict:
    eligible = _eligible_videos(con)
    eligible_ids = {row["id"] for row in eligible}
    evaluations = _human_evaluations(con, eligible_ids)
    commercial = _commercial_records(con)
    gate = gate_report(con)
    payload = {
        "videos": sorted([
            {"id": row["id"], "episode": row["episode"], "file_hash": row["file_hash"],
             "permission_status": row["permission_status"], "source_kind": row["source_kind"]}
            for row in eligible
        ], key=lambda item: item["id"]),
        "evaluations": sorted([
            {"id": row["id"], "video_id": row["video_id"], "episode": row["episode"],
             "evaluator_hash": _hash(row["evaluator_id"])[:16],
             "evaluated_at": row.get("evaluated_at"),
             "scores": {name: _num(row.get(name)) for name in HUMAN_DIMENSIONS}}
            for row in evaluations
        ], key=lambda item: item["id"]),
        "commercial_records": sorted([
            {"id": row["id"], "publication_id": row["publication_id"],
             "metric_name": row["metric_name"], "value": _num(row["metric_value"]),
             "measured_at": row.get("measured_at"), "provenance": row.get("provenance")}
            for row in commercial
        ], key=lambda item: item["id"]),
        "thresholds": GATE_THRESHOLDS,
        "gate_status": gate["status"],
    }
    digest = hashlib.sha256(json_dumps(payload).encode("utf-8")).hexdigest()
    key = f"vlux-attention-{digest[:12]}"
    status = "REGISTERED_ELIGIBLE" if gate["status"] == "ELIGIBLE" else "REGISTERED_BLOCKED"
    con.execute(
        "insert into dataset_registry(dataset_key,status,dataset_hash,videos_count,episodes_count,evaluations_count,commercial_records,authorization_status,payload_json) "
        "values(?,?,?,?,?,?,?,?,?) "
        "on conflict(dataset_key) do update set status=excluded.status,payload_json=excluded.payload_json",
        (key, status, digest, gate["counts"]["eligible_videos"], gate["counts"]["episodes"],
         gate["counts"]["human_evaluations"], gate["counts"]["commercial_records"],
         gate["authorization_status"], json_dumps(payload)),
    )
    con.commit()
    return {
        "dataset_key": key, "dataset_hash": digest, "status": status,
        "counts": {
            "videos": gate["counts"]["eligible_videos"],
            "episodes": gate["counts"]["episodes"],
            "evaluations": gate["counts"]["human_evaluations"],
            "commercial_records": gate["counts"]["commercial_records"],
        },
        "authorization_status": gate["authorization_status"],
        "gate": gate,
        "payload": payload,
    }


def _state(con) -> dict:
    rows = con.execute("select key,value from model_registry_state").fetchall()
    state = {row["key"]: row["value"] for row in rows}
    state.setdefault("active_model_version", "")
    state.setdefault("previous_model_version", "")
    state.setdefault("training_state", TRAINING_STATE_BLOCKED)
    return state


def _set_state(con, **values) -> None:
    for key, value in values.items():
        con.execute(
            "insert into model_registry_state(key,value) values(?,?) "
            "on conflict(key) do update set value=excluded.value",
            (key, str(value)),
        )
    con.commit()


def _labeled_rows(con, gate: dict) -> list[tuple[dict, float]]:
    eligible_ids = {row["id"] for row in _eligible_videos(con)}
    evaluations = _human_evaluations(con, eligible_ids)
    labels = labels_by_video(con, evaluations)
    rows = {row["id"]: row for row in load_rows(con)}
    result = []
    for video_id, data in labels.items():
        row = rows.get(video_id)
        if row:
            result.append((row, float(data["label"])))
    return result


def _experiment_id(dataset_hash: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"exp-{stamp}-{dataset_hash[:8]}"


def run_gated_training(con, artifact_dir="artifacts", seed: int = 17) -> dict:
    gate = gate_report(con)
    registry = dataset_registry(con)
    dataset_hash = registry["dataset_hash"]
    experiment_id = _experiment_id(dataset_hash)
    if gate["status"] != "ELIGIBLE":
        result = {
            "status": TRAINING_STATE_BLOCKED,
            "reason": "TRAINING_GATE_BLOCKED",
            "experiment_id": experiment_id,
            "dataset_hash": dataset_hash,
            "gate": gate,
            "model_created": False,
        }
        con.execute(
            "insert into experiments(experiment_id,dataset_hash,results_json) values(?,?,?)",
            (experiment_id, dataset_hash, json_dumps(result)),
        )
        con.commit()
        _set_state(con, training_state=TRAINING_STATE_BLOCKED, last_gate_json=json_dumps(gate),
                   last_experiment_id=experiment_id)
        return result

    rows = _labeled_rows(con, gate)
    training = train_rows(rows, artifact_dir, seed=seed, min_examples=GATE_THRESHOLDS["eligible_videos"])
    training["experiment_id"] = experiment_id
    training["gate_status"] = gate["status"]
    training["dataset_key"] = registry["dataset_key"]
    con.execute(
        "insert into experiments(experiment_id,dataset_hash,results_json) values(?,?,?)",
        (experiment_id, dataset_hash, json_dumps(training)),
    )
    con.commit()
    if training.get("status") == "TRAINED":
        model_version = f"candidate-{dataset_hash[:12]}"
        con.execute(
            "insert or ignore into models(model_version,model_type,dataset_hash,parameters_json,metrics_json,artifact_path,artifact_hash,baseline_metrics_json,approval_status) values(?,?,?,?,?,?,?,?,?)",
            (model_version, "logistic_numpy", dataset_hash, json_dumps({"seed": seed}),
             json_dumps(training), training["artifact_path"], training["artifact_hash"],
             json_dumps({"baseline_accuracy": training.get("baseline_accuracy")}), "candidate"),
        )
        con.commit()
        _set_state(con, training_state=TRAINING_STATE_CANDIDATE,
                   last_gate_json=json_dumps(gate), last_experiment_id=experiment_id)
        training["model_version"] = model_version
        training["model_created"] = True
    else:
        _set_state(con, training_state=TRAINING_STATE_BLOCKED,
                   last_gate_json=json_dumps(gate), last_experiment_id=experiment_id)
        training["model_created"] = False
    return training


def list_experiments(con) -> list[dict]:
    return [dict(row) for row in con.execute(
        "select experiment_id,dataset_hash,results_json,created_at from experiments order by id desc"
    )]


def training_status(con) -> dict:
    gate = gate_report(con)
    state = _state(con)
    return {
        "contract_version": "learning-gate.v0.1",
        "evaluated_at": _now(),
        "training_state": state["training_state"] if gate["status"] == "ELIGIBLE" else TRAINING_STATE_BLOCKED,
        "gate": gate,
        "active_model_version": state["active_model_version"] or None,
        "previous_model_version": state["previous_model_version"] or None,
        "experiments": len(list_experiments(con)),
        "models": list_models(con),
        "model_created": False,
    }


def list_models(con) -> list[dict]:
    rows = [dict(r) for r in con.execute(
        "select model_version,model_type,dataset_hash,metrics_json,artifact_path,approval_status,created_at from models order by id desc"
    )]
    for row in rows:
        try:
            row["metrics"] = json.loads(row.pop("metrics_json"))
        except (TypeError, json.JSONDecodeError):
            row["metrics"] = {}
    return rows


def promote_model(con, model_version: str, approved_by: str) -> dict:
    if not approved_by or approved_by.strip().lower() in {"anonymous", "ai", "automated", "system"}:
        return {"status": "REFUSED", "reason": "NAMED_HUMAN_APPROVER_REQUIRED"}
    gate = gate_report(con)
    if gate["status"] != "ELIGIBLE":
        return {"status": "REFUSED", "reason": "TRAINING_GATE_BLOCKED", "gate": gate}
    row = con.execute("select * from models where model_version=?", (model_version,)).fetchone()
    if not row:
        return {"status": "NOT_FOUND", "model_version": model_version}
    metrics = json.loads(row["metrics_json"])
    accuracy = _num(metrics.get("accuracy"))
    baseline = _num(metrics.get("baseline_accuracy"))
    if accuracy is None or baseline is None:
        return {"status": "REFUSED", "reason": "HOLDOUT_METRICS_MISSING"}
    if accuracy <= baseline:
        return {"status": "REFUSED", "reason": "NO_HOLDOUT_IMPROVEMENT",
                "accuracy": accuracy, "baseline_accuracy": baseline}
    state = _state(con)
    previous = state.get("active_model_version") or ""
    if previous and previous != model_version:
        con.execute("update models set approval_status='superseded' where model_version=?", (previous,))
    con.execute("update models set approval_status='active' where model_version=?", (model_version,))
    _set_state(con, active_model_version=model_version, previous_model_version=previous,
               training_state="MODEL_ACTIVE_HUMAN_APPROVED")
    con.commit()
    return {"status": "PROMOTED", "model_version": model_version,
            "previous_model_version": previous or None, "approved_by": approved_by,
            "accuracy": accuracy, "baseline_accuracy": baseline}


def rollback_model(con, target_version: str | None = None) -> dict:
    state = _state(con)
    current = state.get("active_model_version") or ""
    target = target_version or state.get("previous_model_version") or ""
    if not target:
        return {"status": "REFUSED", "reason": "NO_ROLLBACK_TARGET"}
    row = con.execute("select * from models where model_version=?", (target,)).fetchone()
    if not row:
        return {"status": "NOT_FOUND", "model_version": target}
    if current and current != target:
        con.execute("update models set approval_status='rolled_back' where model_version=?", (current,))
    con.execute("update models set approval_status='active' where model_version=?", (target,))
    _set_state(con, active_model_version=target, previous_model_version=current,
               training_state="MODEL_ROLLED_BACK")
    con.commit()
    return {"status": "ROLLED_BACK", "active_model_version": target,
            "previous_model_version": current or None,
            "rolled_back_from": current or None,
            "artifact_path": row["artifact_path"]}


def evaluation_report(con, model_version: str) -> dict:
    row = con.execute("select * from models where model_version=?", (model_version,)).fetchone()
    if not row:
        return {"status": "NOT_FOUND", "model_version": model_version}
    metrics = json.loads(row["metrics_json"])
    accuracy = _num(metrics.get("accuracy"))
    baseline = _num(metrics.get("baseline_accuracy"))
    return {
        "contract_version": "evaluation-pipeline.v0.1",
        "status": "HOLDOUT_REPORT_AVAILABLE" if accuracy is not None else "METRICS_NOT_AVAILABLE",
        "model_version": model_version,
        "dataset_hash": row["dataset_hash"],
        "holdout_design": metrics.get("holdout_design", "complete_episode"),
        "holdout_episode": metrics.get("holdout_episode"),
        "accuracy": accuracy,
        "baseline_accuracy": baseline,
        "delta_vs_baseline": None if accuracy is None or baseline is None else round(accuracy - baseline, 6),
        "approval_status": row["approval_status"],
        "limitations": [
            "La exactitud de holdout no demuestra mejora comercial.",
            "El modelo sólo puede promoverse con aprobación humana nombrada y mejora sobre la línea base.",
        ],
    }
