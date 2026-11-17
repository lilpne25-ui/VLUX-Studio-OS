from __future__ import annotations

import json
from typing import Any

CONTRACT_VERSION = "creative-director.v0.2"


def _evidence(con) -> tuple[list[dict], int]:
    rows = [dict(r) for r in con.execute(
        "SELECT v.episode,v.topic,v.business_problem,v.cta,v.source_kind,"
        "m.metric_name,m.metric_value FROM videos v LEFT JOIN metrics m ON m.video_id=v.id "
        "WHERE v.source_kind IN ('published','review')"
    )]
    return rows, len(rows)


def recommend(brief: dict[str, Any], con) -> dict[str, Any]:
    """Deterministic B2B creative brief; it proposes, never generates or promotes."""
    evidence, n = _evidence(con)
    problem = brief.get("business_problem") or "un problema operativo que cuesta tiempo y dinero"
    audience = brief.get("target_audience") or "directores de operaciones e ingeniería"
    solution = brief.get("vlux_product") or "una solución VLUX integrada al proceso empresarial"
    topic = brief.get("topic") or problem
    hooks = [
        f"¿Cuánto cuesta a {audience} seguir operando mientras {problem} ocurre?",
        f"{topic.capitalize()} no termina en el plano: termina en el costo operativo.",
        f"Antes de comprar otra herramienta, elimina el punto ciego detrás de {problem}.",
    ]
    confidence = "low" if n < 8 else "medium"
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "PROPOSAL_ONLY",
        "brief": brief,
        "hooks": hooks,
        "recommended_hook": hooks[0],
        "justification": (
            "La propuesta empieza con una consecuencia económica/operativa y no con una "
            "lista de funcionalidades. No se afirma causalidad."
        ),
        "short_script": [
            f"Problema: {problem}.",
            "Consecuencia: tiempo perdido, retrabajo o decisiones con información incompleta.",
            f"Solución: {solution}, presentada como sistema y no como herramienta aislada.",
            "Beneficio: más trazabilidad para decidir con menos fricción.",
        ],
        "visual_structure": [
            "0-3s: consecuencia concreta con texto legible y una señal visual inequívoca.",
            "3-8s: transición del estado problemático al flujo controlado.",
            "8-15s: animación 3D funcional que explica el cambio, no decoración.",
            "15s-final: beneficio empresarial y CTA.",
        ],
        "recommended_3d": [
            "Contraste entre estado desordenado y estado trazable.",
            "Movimiento de cámara con intención: revelar causa, transición y resultado.",
            "Detalles industriales sólo donde mejoren credibilidad o comprensión.",
        ],
        "cta_primary": "Agenda una conversación para revisar dónde se está perdiendo tiempo o margen.",
        "cta_alternative": "Solicita un diagnóstico inicial del flujo de ingeniería/operaciones.",
        "retention_risks": [
            "Abrir con una explicación técnica antes de mostrar la consecuencia.",
            "Usar movimiento sin relación con el problema.",
            "Prometer resultados de clientes sin evidencia autorizada.",
        ],
        "evaluation_indicators": [
            "retention_3s", "completion_rate", "qualified_leads",
            "conversations", "meetings", "business_value_human_score",
        ],
        "evidence": {
            "records_available": n,
            "source_kinds": sorted({r["source_kind"] for r in evidence}),
            "confidence": confidence,
            "limitations": "No se usan datos sintéticos ni se declara mejora comercial sin métricas verificadas.",
        },
        "recommended_experiment": {
            "design": "A/B por episodio o campaña; mantener el resto de variables estable.",
            "success_metric": "qualified_leads; secundarias retention_3s y completion_rate.",
            "approval_required": True,
        },
    }
