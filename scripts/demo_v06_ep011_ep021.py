from __future__ import annotations

"""V0.6 functional demo: Creative Feedback Loop on authorized EP011/EP021 copies."""

import json
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vlux_ci.creative_loop import (
    compare_episode_versions, create_production_brief, create_review,
    export_production_brief, import_episode_version, loop_status,
    record_human_approval, record_performance, record_version_evaluation,
    verify_version_integrity,
)
from vlux_ci.db import connect
from vlux_ci.learning import gate_report

DB = ROOT / "data" / "vlux.sqlite"
ALLOWED_ROOT = ROOT / "data"


def _version_of(con, episode: str) -> dict:
    row = con.execute(
        "select * from episode_versions where episode=? order by id desc limit 1",
        (episode,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"no episode version imported for {episode}")
    item = dict(row)
    item["contract"] = json.loads(item.pop("import_contract_json"))
    return item


def _exists(con, table: str, **filters: str) -> bool:
    where = " and ".join(f"{key}=?" for key in filters)
    return bool(
        con.execute(f"select 1 from {table} where {where} limit 1", list(filters.values())).fetchone()
    )


def main() -> int:
    con = connect(DB)
    ep011 = con.execute(
        "select * from videos where episode='EP011' order by id desc limit 1",
    ).fetchone()
    ep021 = con.execute(
        "select * from videos where episode='EP021' order by id desc limit 1",
    ).fetchone()
    if not ep011 or not ep021:
        raise RuntimeError("EP011/EP021 videos not found in local database")

    ep011_review = create_review(con, int(ep011["id"]))
    ep021_review = create_review(con, int(ep021["id"]))

    ep021_change = ep021_review["changes"][0]
    ep021_defect = next(
        (d for d in ep021_review["defects"] if d["defect_key"] == ep021_change["defect_key"]),
        ep021_review["defects"][0],
    )
    ep021_brief = create_production_brief(con, ep021_change["change_key"], "EP021-HOOK-BEFORE-2S")
    ep021_handoff = export_production_brief(con, ep021_brief["brief_key"], ROOT / "reports" / "v06")

    import_episode_version(
        con, "EP011", ep011["file_path"], ep011["permission_status"], allowed_roots=[ALLOWED_ROOT],
    )
    import_episode_version(
        con, "EP021", ep021["file_path"], ep021["permission_status"], allowed_roots=[ALLOWED_ROOT],
    )
    version_ep011 = _version_of(con, "EP011")
    version_ep021 = _version_of(con, "EP021")
    version_ep011_integrity = verify_version_integrity(con, version_ep011["version_key"])
    version_ep021_integrity = verify_version_integrity(con, version_ep021["version_key"])

    approval_key = f"approval-{ep021_change['change_key']}"
    approval = (
        record_human_approval(
            con, "recommended_change", ep021_change["change_key"], "PENDING",
            "vlux-demo-loop", notes="aprobación registrada durante la demostración funcional",
        )
        if not _exists(con, "human_approvals", approval_key=approval_key)
        else {"subject_key": ep021_change["change_key"], "decision": "PENDING"}
    )

    evaluation_key = f"eval-{version_ep021['version_key']}"
    evaluation = (
        record_version_evaluation(
            con, version_ep021["version_key"], "vlux-demo-loop",
            visual_impact=4, realism=3, clarity=4, hook=4, narrative=4,
            business_value=3, cta=4, preference="B", compared_version_key=version_ep011["version_key"],
            confidence=0.6, notes="evaluación demo del operador durante el flujo V0.6",
            provenance="demo",
        )
        if not _exists(con, "version_evaluations", evaluation_key=evaluation_key)
        else {
            "version_key": version_ep021["version_key"],
            "evaluator_id": "vlux-demo-loop",
            "provenance": "demo",
            "preference": {"choice": "B", "compared_version_key": version_ep011["version_key"]},
        }
    )

    performance_ep011 = (
        record_performance(
            con, version_ep011["version_key"], "Instagram", None,
            {"likes": 176, "retention_3s": None, "qualified_leads": None},
            campaign="VLUX_PILOT", published_at=None,
            hook_used=ep011["hook"], cta_used=ep011["cta"],
            provenance="USER_PROVIDED_SCREENSHOT", notes="registro demo sobre datos del piloto",
        )
        if not _exists(con, "performance_records", version_key=version_ep011["version_key"], platform="Instagram")
        else {"version_key": version_ep011["version_key"], "performance": {"status": "SKIPPED_EXISTING"}}
    )
    performance_ep021 = (
        record_performance(
            con, version_ep021["version_key"], "Instagram", None,
            {"likes": None, "retention_3s": None, "qualified_leads": None},
            campaign="VLUX_PILOT", published_at=None,
            hook_used=ep021["hook"], cta_used=ep021["cta"],
            provenance="USER_PROVIDED_SCREENSHOT", notes="registro demo sobre datos del piloto",
        )
        if not _exists(con, "performance_records", version_key=version_ep021["version_key"], platform="Instagram")
        else {"version_key": version_ep021["version_key"], "performance": {"status": "SKIPPED_EXISTING"}}
    )

    comparison = compare_episode_versions(
        con, version_ep011["version_key"], version_ep021["version_key"], "Instagram",
    )

    final_report = {
        "status": "V06_DEMO_COMPLETED_LOCAL",
        "schema_version": con.execute(
            "select value from schema_meta where key='schema_version'"
        ).fetchone()[0],
        "loop_version": "0.6.0",
        "training_state": gate_report(con)["training_state"],
        "episodes": {
            "EP011": {
                "video_id": int(ep011["id"]),
                "version_key": version_ep011["version_key"],
                "review_key": ep011_review["review"]["review_key"],
                "change_keys": [c["change_key"] for c in ep011_review["changes"]],
                "integrity": version_ep011_integrity,
            },
            "EP021": {
                "video_id": int(ep021["id"]),
                "version_key": version_ep021["version_key"],
                "review_key": ep021_review["review"]["review_key"],
                "change_keys": [c["change_key"] for c in ep021_review["changes"]],
                "first_change_key": ep021_change["change_key"],
                "defect_key": ep021_defect["defect_key"],
                "brief_key": ep021_brief["brief_key"],
                "integrity": version_ep021_integrity,
            },
        },
        "proposal": {
            "change_key": ep021_change["change_key"],
            "episode": ep021_change["episode"],
            "version": ep021_change["version"],
            "timestamp": ep021_change["timestamp"],
            "detected_problem": ep021_change["detected_problem"],
            "estimated_impact": ep021_change["estimated_impact"],
            "proposed_solution": ep021_change["proposed_solution"],
            "priority": ep021_change["priority"],
            "suggested_tool": ep021_change["suggested_tool"],
            "acceptance_criterion": ep021_change["acceptance_criterion"],
            "status": ep021_change["status"],
        },
        "exports": {
            "review_output_dir": str(ROOT / "reports" / "v06" / ep021_review["review"]["review_key"]),
            "handoff_output_dir": str(ROOT / "reports" / "v06" / ep021_brief["brief_key"]),
        },
        "versions": {
            "EP011": version_ep011_integrity,
            "EP021": version_ep021_integrity,
        },
        "human_evaluation": {
            "version_key": version_ep021["version_key"],
            "evaluator_id": "vlux-demo-loop",
            "provenance": "demo",
            "gate_eligible": False,
            "preference": evaluation.get("preference") or {},
            "compared_version_key": (evaluation.get("preference") or {}).get("compared_version_key"),
        },
        "performance": {
            "EP011": performance_ep011.get("performance") or {},
            "EP021": performance_ep021.get("performance") or {},
        },
        "comparison": {
            "status": comparison["summary"]["status"],
            "automatic_winner": None,
            "commercial_improvement_claimed": False,
            "requires_real_measurement": True,
            "metrics": comparison["metrics"],
        },
        "loop_status": loop_status(con),
        "policy": {
            "no_automatic_model_promotion": True,
            "no_automatic_publication": True,
            "no_automatic_training": True,
            "no_higgsfield_derived_training": True,
            "likes_are_not_leads": True,
            "missing_metrics_stay_missing": True,
        },
    }
    private_report = ROOT / "reports" / "v06" / "V06_DEMO_FINAL.json"
    private_report.parent.mkdir(parents=True, exist_ok=True)
    private_report.write_text(json.dumps(final_report, indent=2, ensure_ascii=False), encoding="utf-8")
    public_report = ROOT / "docs" / "V06_PILOT.md"
    public_report.write_text(_public_summary(final_report), encoding="utf-8")

    payload = {
        "status": "V06_DEMO_COMPLETED_LOCAL",
        "training_state": final_report["training_state"],
        "ep021_first_change": final_report["proposal"],
        "comparison_status": final_report["comparison"]["status"],
        "human_evaluation_gate_eligible": False,
        "automatic_winner": None,
        "commercial_improvement_claimed": False,
        "private_report": str(private_report),
        "public_report": str(public_report),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _public_summary(final_report: dict) -> str:
    proposal = final_report["proposal"]
    comparison = final_report["comparison"]
    evaluation = final_report["human_evaluation"]
    lines = [
        "# VLUX Studio OS V0.6 — Creative Feedback Loop",
        "",
        "## Demo ejecutada",
        "",
        "La demostración V0.6 del flujo creativo completo fue ejecutada contra copias",
        "autorizadas locales de EP011 y EP021 usando la base de datos privada del piloto.",
        "",
        "Flujo ejecutado:",
        "",
        "1. Creative Review de EP011 y EP021.",
        "2. Detección de defectos y generación de recomendación accionable.",
        "3. Creación y exportación del Production Brief.",
        "4. Importación explícita de versiones de episodio (comparación local).",
        "5. Evaluación humana y registro de métricas por versión.",
        "6. Comparación de versiones sin ganador automático.",
        "7. Informe final local.",
        "",
        "## Primera recomendación para EP021",
        "",
        f"- Problema: {proposal['detected_problem']}",
        f"- Timestamp: {proposal['timestamp']['label']}",
        f"- Solución: {proposal['proposed_solution']}",
        f"- Prioridad: {proposal['priority']}",
        f"- Criterio de aceptación: {proposal['acceptance_criterion']}",
        "",
        "## Comparación y resultados",
        "",
        f"- Estado de comparación: {comparison['status']}",
        "- Ganador automático: ninguno.",
        "- Se afirmó mejora comercial: no.",
        "",
        "## Evaluación humana",
        "",
        f"- Evaluación registrada en la demo: {evaluation.get('evaluator_id')} ({evaluation.get('provenance')}).",
        "- ¿Cuenta para el gate de entrenamiento?: False.",
        "",
        "## Estado",
        "",
        f"- Entrenamiento: {final_report['training_state']}.",
        "- Contrato de producción: propuesta exportada, no orden ejecutado.",
        "- Licencia: sin asignar sin decisión del propietario.",
        "",
        "## Limitaciones",
        "",
        "- Las estimaciones V0.6 no son resultados.",
        "- La evaluación humana de la demo no cuenta para el gate.",
        "- La comparación no prueba causalidad y no afirma mejora comercial.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
