from __future__ import annotations

import json

CONTRACT_VERSION = "ep025-proposals.v0.4"


def ep025_proposals() -> list[dict]:
    return [
        {
            "proposal_key": "cad-erp",
            "title": "Del CAD al ERP sin copiar a mano",
            "business_problem": "Datos de ingeniería se copian manualmente hacia ERP/MRP.",
            "operational_pain": "Retrabajo, errores de captura y retrasos en cotizaciones o producción.",
            "hook": "¿Cuánto margen se pierde copiando datos de diseño a mano?",
            "solution": "Diseñar un flujo trazable entre ingeniería y ERP/MRP.",
            "storyboard": ["0-3s: dato duplicado y costo operativo", "3-8s: quiebre entre CAD y ERP", "8-18s: puente 3D de información", "18-25s: beneficio y CTA"],
            "animation_3d": "Dos sistemas industriales separados por una barrera de datos que se transforma en un flujo único.",
            "cta": "Escribe DISEÑO para revisar tu flujo de ingeniería.",
            "experiment": "A/B: costo del error vs. velocidad de decisión.",
            "primary_metric": "qualified_leads",
        },
        {
            "proposal_key": "quality-traceability",
            "title": "El defecto que no puedes rastrear",
            "business_problem": "Calidad detecta defectos sin una trazabilidad completa de causa y lote.",
            "operational_pain": "Paros, investigación lenta y riesgo de repetir el defecto.",
            "hook": "Un defecto sin trazabilidad vuelve a aparecer.",
            "solution": "Conectar información de calidad, proceso y producto para investigar más rápido.",
            "storyboard": ["0-3s: defecto visible", "3-8s: búsqueda fragmentada", "8-18s: mapa 3D de trazabilidad", "18-25s: diagnóstico y CTA"],
            "animation_3d": "Una pieza industrial iluminada conecta defecto, lote y operación con líneas cyan sobrias.",
            "cta": "Escribe CALIDAD para identificar tus puntos ciegos.",
            "experiment": "A/B: costo de repetición vs. velocidad de diagnóstico.",
            "primary_metric": "conversations",
        },
        {
            "proposal_key": "cad-automation",
            "title": "La ingeniería que no se puede reutilizar",
            "business_problem": "Diseños CAD valiosos quedan aislados y difíciles de reutilizar.",
            "operational_pain": "Cada nuevo proyecto reinicia trabajo y aumenta el tiempo de entrega.",
            "hook": "Tu mejor diseño no debería empezar de cero cada vez.",
            "solution": "Estructurar automatización y reutilización de ingeniería de producto.",
            "storyboard": ["0-3s: diseño repetido", "3-8s: horas duplicadas", "8-18s: componentes 3D se convierten en sistema reutilizable", "18-25s: beneficio y CTA"],
            "animation_3d": "Módulos CAD se ordenan en una biblioteca industrial visualmente creíble.",
            "cta": "Escribe INGENIERÍA para conversar sobre reutilización.",
            "experiment": "A/B: horas repetidas vs. capacidad de reutilización.",
            "primary_metric": "qualified_leads",
        },
    ]


def payload(proposal: dict) -> str:
    return json.dumps(proposal, ensure_ascii=False, sort_keys=True)
