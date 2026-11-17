from __future__ import annotations

"""V0.6 end-to-end verification with synthetic media only.

Flow verified here:
    creative review -> export recommendations -> production brief -> handoff
    -> episode version import -> human approval + version evaluation
    -> performance records -> version comparison

It never touches real VLUX media, private databases, GPUs, model weights or
external services, and it never declares a winner or a commercial improvement.
"""

import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from validate_contracts import validate
from factory import add_analysis, add_video
from vlux_ci.creative_loop import (
    compare_episode_versions, create_production_brief, create_review,
    export_production_brief, export_review_bundle, import_episode_version,
    loop_status, record_human_approval, record_performance, record_version_evaluation,
    recommended_changes_contract, visual_defects_contract,
)
from vlux_ci.db import connect
from vlux_ci.learning import gate_report

V06_REPORTS = "reports/v06"


def run(args, cwd=ROOT):
    p = subprocess.run([sys.executable, "-m", "vlux_ci.cli", *args],
                       cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"{args}\nSTDOUT={p.stdout}\nSTDERR={p.stderr}")
    return p.stdout


def http_json(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read())


def validate_contract(schema_name: str, document: dict) -> None:
    schema = json.loads((ROOT / "contracts" / schema_name).read_text(encoding="utf-8"))
    validate(document, schema)


def make_fixture(path: Path, source: str):
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", source,
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-shortest", "-pix_fmt", "yuv420p", str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    base_tmp = ROOT / "data" / "synthetic"
    base_tmp.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="vlux-v06-", dir=base_tmp))
    db = temp / "workflow.sqlite"
    con = connect(db)
    a_path = temp / "fixture-a.mp4"
    b_path = temp / "fixture-b.mp4"
    make_fixture(a_path, "testsrc2=size=160x90:rate=30:duration=3")
    make_fixture(b_path, "color=c=0x101820:size=160x90:rate=30:duration=3")
    a_id = add_video(con, "SYN-V06-A", source_kind="synthetic", permission="synthetic")
    b_id = add_video(con, "SYN-V06-B", source_kind="synthetic", permission="synthetic")
    for video_id, path, hook, cta in (
        (a_id, a_path, "¿Cuánto cuesta copiar datos a mano?", "Comenta FLUJO."),
        (b_id, b_path, "Una promesa sin capacidad se rompe.", "Comenta CAPACIDAD."),
    ):
        add_analysis(con, video_id)
        con.execute("update videos set hook=?,cta=? where id=?", (hook, cta, video_id))
        con.commit()

    review = create_review(con, a_id)
    validate_contract("creative-review.v0.1.schema.json", review["review"])
    validate_contract("visual-defects.v0.1.schema.json", visual_defects_contract(review))
    validate_contract("recommended-changes.v0.1.schema.json", recommended_changes_contract(review))

    exported = export_review_bundle(con, review["review"]["review_key"], temp / "exports")
    for name, item in exported["files"].items():
        if not Path(item["path"]).exists():
            raise RuntimeError(f"exported file missing: {name}")
    exported_recommendations = json.loads(
        Path(exported["files"]["recommended-changes.json"]["path"]).read_text(encoding="utf-8")
    )
    if exported_recommendations["status"] != "PROPOSAL_ONLY":
        raise RuntimeError("exported recommendations must be PROPOSAL_ONLY")

    change_key = review["changes"][0]["change_key"]
    brief = create_production_brief(con, change_key, "SYN-V06-REV")
    brief_exported = export_production_brief(con, brief["brief_key"], temp / "handoff")
    if not Path(brief_exported["files"]["production-brief.json"]["path"]).exists():
        raise RuntimeError("production brief export failed")

    version_a = import_episode_version(
        con, "SYN-V06-A", a_path, "synthetic",
        allowed_roots=[temp], version_label="SYN-V06-A-ORIG",
    )
    version_b = import_episode_version(
        con, "SYN-V06-B", b_path, "synthetic",
        parent_version_key=version_a["version_key"], allowed_roots=[temp],
        version_label="SYN-V06-B-REV",
    )

    approval = record_human_approval(
        con, "recommended_change", change_key, "APPROVED",
        "synthetic-reviewer", notes="aprobación de verificación sintética",
    )
    validate_contract("human-approval.v0.1.schema.json", approval)

    evaluation = record_version_evaluation(
        con, version_b["version_key"], "synthetic-reviewer",
        visual_impact=4, realism=3, clarity=4, hook=4, narrative=4,
        business_value=3, cta=4, preference="B", compared_version_key=version_a["version_key"],
        confidence=0.8, provenance="human", notes="verificación sintética",
    )
    validate_contract("human-evaluation.v0.1.schema.json", evaluation)

    performance_a = record_performance(
        con, version_a["version_key"], "Synthetic", "2026-11-17",
        {"views": 100, "likes": 5, "qualified_leads": 1, "meetings": None},
        provenance="USER_PROVIDED",
    )
    performance_b = record_performance(
        con, version_b["version_key"], "Synthetic", "2026-11-17",
        {"views": 120, "likes": 7, "qualified_leads": 2, "meetings": None},
        provenance="USER_PROVIDED",
    )
    comparison = compare_episode_versions(con, version_a["version_key"], version_b["version_key"], "Synthetic")
    validate_contract("performance-comparison.v0.1.schema.json", comparison)
    validate_contract("performance-record.v0.1.schema.json", performance_a)
    validate_contract("performance-record.v0.1.schema.json", performance_b)
    if comparison["summary"]["automatic_winner"] is not None:
        raise RuntimeError("V0.6 must not declare an automatic winner")

    status = loop_status(con)
    gate = gate_report(con)
    if gate["training_state"] != "NO_TRAINING_INSUFFICIENT_DATA":
        raise RuntimeError("V0.6 must preserve the training gate block")

    server = subprocess.Popen(
        [sys.executable, "-m", "vlux_ci.cli", "--db", str(db), "dashboard",
         "--host", "127.0.0.1", "--port", "8899"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        base_url = "http://127.0.0.1:8899"
        for _ in range(60):
            try:
                summary = http_json(base_url + "/api/summary")
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
                time.sleep(0.2)
        else:
            raise RuntimeError("dashboard_did_not_start")
        if summary.get("loop", {}).get("schema_version") not in (None, "0.6"):
            raise RuntimeError("dashboard loop payload must report schema 0.6")
        loop_status_payload = http_json(base_url + "/api/loop/status")
        if loop_status_payload.get("schema_version") != "0.6":
            raise RuntimeError("loop status must report schema 0.6")
        created = http_json(base_url + "/api/loop/review", {"video_id": a_id})
        if created.get("status") != "REVIEW_CREATED":
            raise RuntimeError("loop review endpoint failed")
        web_compare = http_json(base_url + "/api/loop/compare", {
            "a": version_a["version_key"], "b": version_b["version_key"], "platform": "Synthetic",
        })
        if web_compare.get("summary", {}).get("automatic_winner") is not None:
            raise RuntimeError("dashboard comparison must not declare a winner")
        webpage = urllib.request.urlopen(base_url + "/", timeout=10).read().decode("utf-8")
        if "VLUX STUDIO OS" not in webpage or "CREATIVE FEEDBACK LOOP" not in webpage:
            raise RuntimeError("dashboard page must expose the V0.6 loop view")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        err_text = ""
        if server.stderr is not None:
            try:
                err_text = server.stderr.read() or ""
            except Exception:
                err_text = ""
        if err_text.strip():
            print("SERVER STDERR:", err_text, file=sys.stderr)

    report = {
        "status": "V06_E2E_PASS",
        "schema_version": "0.6",
        "contracts_validated": [
            "creative-review.v0.1", "visual-defects.v0.1",
            "recommended-changes.v0.1", "production-brief.v0.1",
            "human-approval.v0.1", "human-evaluation.v0.1",
            "performance-record.v0.1", "performance-comparison.v0.1",
        ],
        "synthetic_media_used": True,
        "real_media_used": False,
        "gpu_used": False,
        "training_state": gate["training_state"],
        "automatic_winner": None,
        "commercial_improvement_claimed": False,
        "dashboard_http_workflow": True,
        "temporary_directory": str(temp),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
