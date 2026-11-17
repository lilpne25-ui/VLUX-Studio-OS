from __future__ import annotations

"""Local production adapters and version registry.

No model weights, GPU, external service or AI generation is used. The only
renderer is a CPU FFmpeg animatic made of text/color cards, explicitly marked
as a placeholder. It demonstrates the contract and rollback path without
pretending to be a finished video.
"""

import hashlib
import json
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import json_dumps
from .probe import probe

CONTRACT_VERSION = "production-adapter.v0.1"
MANIFEST_CONTRACT = "production-manifest.v0.1"
ADAPTERS = ("manifest", "ffmpeg_animatic")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _key(brief: dict) -> str:
    digest = hashlib.sha256(json_dumps(brief).encode("utf-8")).hexdigest()[:8]
    return f"prod-{_stamp()}-{digest}"


def _find_font() -> str | None:
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def plan_version(con, brief: dict, adapter: str = "manifest",
                 video_id: int | None = None, parent_version_id: int | None = None,
                 provenance: str = "local_deterministic") -> dict:
    if not isinstance(brief, dict) or not brief:
        raise ValueError("brief_required")
    if adapter not in ADAPTERS:
        raise ValueError("adapter_not_supported")
    if video_id is not None and not con.execute("select 1 from videos where id=?", (video_id,)).fetchone():
        raise ValueError("video_not_found")
    if parent_version_id is not None and not con.execute(
        "select 1 from production_versions where id=?", (parent_version_id,)
    ).fetchone():
        raise ValueError("parent_version_not_found")
    version_key = _key(brief)
    con.execute(
        "insert into production_versions(version_key,video_id,parent_version_id,brief_json,adapter,status,contract_version,provenance) values(?,?,?,?,?,?,?,?)",
        (version_key, video_id, parent_version_id, json_dumps(brief), adapter,
         "candidate", CONTRACT_VERSION, provenance),
    )
    con.commit()
    return get_version(con, version_key) or {}


def get_version(con, version_key: str) -> dict | None:
    row = con.execute("select * from production_versions where version_key=?", (version_key,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["brief"] = json.loads(item.pop("brief_json"))
    return item


def list_versions(con, video_id: int | None = None) -> list[dict]:
    if video_id is None:
        rows = con.execute("select * from production_versions order by id desc")
    else:
        rows = con.execute(
            "select * from production_versions where video_id=? order by id desc", (video_id,)
        )
    result = []
    for row in rows:
        item = dict(row)
        item["brief"] = json.loads(item.pop("brief_json"))
        result.append(item)
    return result


def _scene_plan(brief: dict) -> list[dict]:
    total = float(brief.get("target_duration_s") or brief.get("duration_s") or 15.0)
    raw = brief.get("visual_structure") or brief.get("scenes") or [
        "0-3s: problema concreto",
        "3-8s: consecuencia operativa",
        "8-15s: solución VLUX",
        "15s-final: beneficio y CTA",
    ]
    if not isinstance(raw, list) or not raw:
        raw = ["0-final: propuesta sin escenas detalladas"]
    scenes = []
    per = max(1.0, total / len(raw))
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("description") or "")
            start = float(item.get("start_s", index * per))
            end = float(item.get("end_s", min(total, (index + 1) * per)))
        else:
            text = str(item)
            start = index * per
            end = min(total, (index + 1) * per)
        scenes.append({
            "index": index + 1, "start_s": round(start, 3), "end_s": round(end, 3),
            "duration_s": round(max(0.1, end - start), 3),
            "text": text, "asset_refs": [], "asset_status": "UNBOUND_ASSET",
        })
    return scenes


def _write_manifest(version: dict, output_dir: Path) -> tuple[Path, dict]:
    brief = version["brief"]
    scenes = _scene_plan(brief)
    manifest = {
        "contract_version": MANIFEST_CONTRACT,
        "version_key": version["version_key"],
        "adapter": "manifest",
        "status": "PLACEHOLDER_NO_RENDER",
        "source_brief_contract": brief.get("contract_version") or "video-brief.v0.3",
        "episode": brief.get("episode"),
        "scenes": scenes,
        "audio": {"status": "NOT_BOUND", "voice": "NOT_BOUND", "music": "NOT_BOUND"},
        "generation": {
            "engine": "none", "ai_generated": False, "gpu_used": False,
            "external_service_used": False, "model_weights": "none",
        },
        "guardrails": [
            "No se generó video con IA.",
            "No se usaron pesos, prompts ni salidas derivadas de Higgsfield.",
            "Los assets visuales y la voz requieren incorporación y revisión humana.",
            "El manifiesto es un contrato de producción, no un render final.",
        ],
    }
    target = output_dir / f"{version['version_key']}.json"
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return target, manifest


def _animatic_cards(brief: dict) -> list[str]:
    problem = brief.get("business_problem") or brief.get("topic") or "PROBLEMA OPERATIVO"
    hook = brief.get("recommended_hook") or brief.get("hook") or problem
    cta = brief.get("cta_primary") or brief.get("cta") or "SIGUIENTE PASO"
    episode = brief.get("episode") or "VLUX"
    return [
        f"{episode}\n\nVLUX STUDIO OS\nANIMATIC PLACEHOLDER",
        f"GANCHO\n\n{str(hook)[:180]}",
        f"ACCIÓN\n\n{str(cta)[:180]}\n\nNO ES UN RENDER FINAL",
    ]


def _render_animatic(version: dict, output_dir: Path) -> tuple[Path, dict]:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg_not_available")
    font = _find_font()
    if not font:
        raise RuntimeError("font_not_available_for_animatic")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{version['version_key']}.mp4"
    cards = _animatic_cards(version["brief"])
    with tempfile.TemporaryDirectory(prefix="vlux-animatic-", dir=str(output_dir)) as tmp_name:
        tmp = Path(tmp_name)
        fontfile = font.replace("\\", "/").replace(":", "\\:")
        for index, text in enumerate(cards, start=1):
            text_path = tmp / f"card{index}.txt"
            text_path.write_text(text, encoding="utf-8")
            card_path = tmp / f"card{index}.mp4"
            drawtext = (
                f"drawtext=fontfile='{fontfile}':textfile='card{index}.txt':"
                "fontcolor=0xE9EEF5:fontsize=32:line_spacing=12:"
                "x=(w-text_w)/2:y=(h-text_h)/2"
            )
            cmd = [
                "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", "color=c=0x0E141B:s=540x960:d=2:r=25",
                "-vf", drawtext, "-an", "-pix_fmt", "yuv420p", str(card_path),
            ]
            subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, check=True, timeout=60)
        concat = tmp / "concat.txt"
        concat.write_text("".join(f"file 'card{i}.mp4'\n" for i in range(1, len(cards) + 1)), encoding="utf-8")
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
            "-i", "concat.txt", "-c", "copy", str(target),
        ]
        subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, check=True, timeout=90)
    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError("animatic_output_missing")
    meta = probe(target)
    manifest = {
        "contract_version": MANIFEST_CONTRACT,
        "version_key": version["version_key"],
        "adapter": "ffmpeg_animatic",
        "status": "PLACEHOLDER_RENDERED",
        "duration_s": meta.get("duration_s"),
        "resolution": f"{meta.get('width')}x{meta.get('height')}",
        "cards": len(cards),
        "audio": {"status": "SILENT", "voice": "NOT_BOUND"},
        "generation": {
            "engine": "ffmpeg_drawtext", "ai_generated": False, "gpu_used": False,
            "external_service_used": False, "model_weights": "none",
        },
        "guardrails": [
            "Animatic de tarjetas, no un video generado por IA.",
            "Sin voz, música, assets 3D ni aprobación de publicación.",
            "Uso local y demostrativo; requiere reemplazo por producción real.",
        ],
    }
    return target, manifest


def render_version(con, version_key: str, output_dir: str | Path = "data/production") -> dict:
    version = get_version(con, version_key)
    if not version:
        return {"status": "NOT_FOUND", "version_key": version_key}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    job_key = f"job-{uuid.uuid4().hex[:12]}"
    try:
        adapter = version["adapter"]
        if adapter == "manifest":
            target, manifest = _write_manifest(version, out)
        elif adapter == "ffmpeg_animatic":
            target, manifest = _render_animatic(version, out)
        else:
            raise RuntimeError("adapter_not_supported")
        con.execute(
            "insert into production_jobs(job_key,video_id,adapter,status,brief_json,output_json,output_path) values(?,?,?,?,?,?,?)",
            (job_key, version["video_id"], adapter, "SUCCEEDED",
             json_dumps(version["brief"]), json_dumps(manifest), str(target)),
        )
        new_status = "rendered" if version["status"] in ("candidate", "failed") else version["status"]
        con.execute(
            "update production_versions set status=?,output_path=? where version_key=?",
            (new_status, str(target), version_key),
        )
        con.commit()
        return {
            "status": "RENDERED", "version_key": version_key, "adapter": adapter,
            "output_path": str(target), "job_key": job_key, "manifest": manifest,
        }
    except Exception as exc:
        con.execute(
            "insert into production_jobs(job_key,video_id,adapter,status,brief_json,error) values(?,?,?,?,?,?)",
            (job_key, version["video_id"], version["adapter"], "FAILED",
             json_dumps(version["brief"]), f"{type(exc).__name__}: {exc}"),
        )
        con.execute("update production_versions set status='failed' where version_key=?", (version_key,))
        con.commit()
        return {"status": "FAILED", "version_key": version_key, "job_key": job_key,
                "error": f"{type(exc).__name__}: {exc}"}


def activate_version(con, version_key: str) -> dict:
    version = get_version(con, version_key)
    if not version:
        return {"status": "NOT_FOUND", "version_key": version_key}
    if not version.get("output_path") or not Path(version["output_path"]).exists():
        return {"status": "REFUSED", "reason": "RENDER_REQUIRED_BEFORE_ACTIVATION"}
    same_scope = "video_id is null" if version["video_id"] is None else "video_id=?"
    params: tuple = () if version["video_id"] is None else (version["video_id"],)
    con.execute(
        f"update production_versions set status='superseded' where status='active' and version_key!=? and {same_scope}",
        (version_key, *params),
    )
    con.execute(
        "update production_versions set status='active',activated_at=? where version_key=?",
        (_now(), version_key),
    )
    con.commit()
    return {"status": "ACTIVATED", "version_key": version_key,
            "previous_versions_superseded": True,
            "output_path": version["output_path"]}


def rollback_version(con, version_key: str) -> dict:
    target = get_version(con, version_key)
    if not target:
        return {"status": "NOT_FOUND", "version_key": version_key}
    if not target.get("output_path") or not Path(target["output_path"]).exists():
        return {"status": "REFUSED", "reason": "ROLLBACK_TARGET_OUTPUT_MISSING"}
    current = con.execute(
        "select version_key from production_versions where status='active' and "
        + ("video_id is null" if target["video_id"] is None else "video_id=?"),
        () if target["video_id"] is None else (target["video_id"],),
    ).fetchone()
    if current:
        con.execute(
            "update production_versions set status='rolled_back' where version_key=?",
            (current["version_key"],),
        )
    con.execute(
        "update production_versions set status='active',activated_at=? where version_key=?",
        (_now(), version_key),
    )
    con.commit()
    return {
        "status": "ROLLED_BACK", "active_version": version_key,
        "rolled_back_from": current["version_key"] if current else None,
        "output_path": target["output_path"],
    }


def history(con, version_key: str) -> dict:
    chain = []
    current = get_version(con, version_key)
    seen = set()
    while current and current["version_key"] not in seen:
        seen.add(current["version_key"])
        chain.append({
            "version_key": current["version_key"], "status": current["status"],
            "adapter": current["adapter"], "created_at": current["created_at"],
            "parent_version_id": current["parent_version_id"],
        })
        parent_id = current["parent_version_id"]
        current = get_version_by_id(con, parent_id) if parent_id else None
    return {"version_key": version_key, "chain": chain,
            "root_first": list(reversed(chain))}


def get_version_by_id(con, version_id: int) -> dict | None:
    row = con.execute("select version_key from production_versions where id=?", (version_id,)).fetchone()
    return get_version(con, row["version_key"]) if row else None


def summary(con) -> dict:
    return {
        "contract_version": CONTRACT_VERSION,
        "versions": len(list_versions(con)),
        "active": [
            {"version_key": row["version_key"], "video_id": row["video_id"],
             "adapter": row["adapter"], "output_path": row["output_path"]}
            for row in con.execute("select * from production_versions where status='active' order by id")
        ],
        "rendered": con.execute("select count(*) from production_versions where status in ('rendered','active','superseded','rolled_back')").fetchone()[0],
        "adapters": list(ADAPTERS),
        "guardrails": [
            "Sin GPU y sin pesos de modelos.",
            "ffmpeg_animatic es un placeholder de tarjetas, no un render generativo.",
            "Toda versión requiere revisión humana antes de producción.",
        ],
    }
