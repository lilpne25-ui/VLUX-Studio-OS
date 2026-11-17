from __future__ import annotations

"""V0.5 end-to-end verification with synthetic media only.

This verifies Attention Lab, A/B layers, human evaluation persistence, the
training gate, local production versions/rollback and the dashboard HTTP API.
It never touches real VLUX media or private databases.
"""

import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validate_contracts import validate


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
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read())


def make_fixture(path: Path, source: str):
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", source,
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-shortest", "-pix_fmt", "yuv420p", str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def validate_contract(schema_name: str, document: dict):
    schema = json.loads((ROOT / "contracts" / schema_name).read_text(encoding="utf-8"))
    validate(document, schema)


def main():
    base_tmp = ROOT / "data" / "synthetic"
    base_tmp.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="vlux-v05-", dir=base_tmp))
    db = temp / "workflow.sqlite"
    a_path = temp / "fixture-a.mp4"
    b_path = temp / "fixture-b.mp4"
    make_fixture(a_path, "testsrc2=size=160x90:rate=30:duration=3")
    make_fixture(b_path, "color=c=0x101820:size=160x90:rate=30:duration=3")
    base = ["--db", str(db)]

    a = json.loads(run(base + ["import", str(a_path), "--episode", "SYN-V05-A",
                               "--source-kind", "synthetic", "--permission", "synthetic"]))
    b = json.loads(run(base + ["import", str(b_path), "--episode", "SYN-V05-B",
                               "--source-kind", "synthetic", "--permission", "synthetic"]))
    a_id, b_id = a["video_id"], b["video_id"]
    run(base + ["annotate", str(a_id), "--hook", "¿Cuánto cuesta copiar datos a mano?",
                "--problem", "Los datos se copian manualmente y se pierden horas.",
                "--solution", "Flujo trazable entre ingeniería y ERP.",
                "--cta", "Comenta FLUJO.", "--audience", "directores de operaciones",
                "--text-provenance", "SYNTHETIC_FIXTURE"])
    run(base + ["annotate", str(b_id), "--hook", "Una entrega sin capacidad es una promesa rota.",
                "--problem", "La promesa de entrega no coincide con la capacidad.",
                "--solution", "Planificación de capacidad.",
                "--cta", "Comenta CAPACIDAD.", "--audience", "directores de operaciones",
                "--text-provenance", "SYNTHETIC_FIXTURE"])

    attention_a = json.loads(run(base + ["attention", str(a_id)]))
    attention_b = json.loads(run(base + ["attention", str(b_id)]))
    assert attention_a["contract_version"] == "attention-lab.v0.1"
    assert attention_a["status"] == "ESTIMATE_ONLY_NOT_VALIDATED"
    assert attention_a["facts"]["sample_count"] > 0
    assert attention_b["overall"]["status"] == "ESTIMATE_NOT_VALIDATED"
    assert attention_a["results"]["likes_are_not_sales"] is True
    validate_contract("attention-lab.v0.1.schema.json", attention_a)
    validate_contract("attention-lab.v0.1.schema.json", attention_b)

    run(base + ["evaluate", str(a_id), "--evaluator", "synthetic-reviewer",
                "--provenance", "human", "--hook", "4", "--narrative", "4",
                "--production", "4", "--commercial", "3", "--cta", "4", "--clarity", "4",
                "--confidence", "0.8", "--evaluated-at", "2026-11-17T12:00:00+00:00"])
    run(base + ["evaluate", str(b_id), "--evaluator", "ai-assistant",
                "--provenance", "ai_assisted", "--hook", "5", "--clarity", "5"])

    ab = json.loads(run(base + ["ab", "--a", str(a_id), "--b", str(b_id)]))
    assert ab["contract_version"] == "ab-comparison.v0.1"
    assert ab["human_preferences"]["status"] == "AVAILABLE"
    assert ab["human_preferences"]["excluded_non_human"]["b"]["excluded_from_human_gate"] == 1
    assert ab["summary"]["automatic_winner"] is None
    assert ab["commercial_results"]["status"] == "NOT_COMPARABLE"
    assert ab["observed_facts"] and ab["estimates"]
    validate_contract("ab-comparison.v0.1.schema.json", ab)

    learning = json.loads(run(base + ["learning-status"]))
    assert learning["training_state"] == "NO_TRAINING_INSUFFICIENT_DATA"
    assert learning["gate"]["status"] == "BLOCKED"
    assert learning["gate"]["counts"]["excluded_ai_evaluations"] == 1
    blocked = json.loads(run(base + ["train-gated", "--artifacts", str(temp / "artifacts")]))
    assert blocked["status"] == "NO_TRAINING_INSUFFICIENT_DATA"
    assert blocked["model_created"] is False
    registry = json.loads(run(base + ["dataset-register"]))
    assert registry["status"] == "REGISTERED_BLOCKED"
    assert registry["counts"]["videos"] == 2
    validate_contract("learning-gate.v0.1.schema.json", learning)

    brief_a = {
        "contract_version": "creative-director.v0.2", "episode": "SYN-V05-A",
        "topic": "trazabilidad", "business_problem": "Copiar datos cuesta horas.",
        "target_audience": "directores de operaciones",
        "recommended_hook": "¿Cuánto cuesta copiar datos a mano?",
        "cta_primary": "Solicita un diagnóstico.", "target_duration_s": 6,
    }
    version_a = json.loads(run(base + ["production-plan", "--brief", str(_write(temp / "brief-a.json", brief_a)), "--adapter", "manifest"]))
    rendered_a = json.loads(run(base + ["production-render", version_a["version_key"], "--output-dir", str(temp / "production")]))
    assert rendered_a["status"] == "RENDERED"
    assert rendered_a["manifest"]["generation"]["ai_generated"] is False
    validate_contract("production-manifest.v0.1.schema.json", rendered_a["manifest"])
    activated_a = json.loads(run(base + ["production-activate", version_a["version_key"]]))
    assert activated_a["status"] == "ACTIVATED"
    brief_b = {**brief_a, "episode": "SYN-V05-B", "recommended_hook": "Una promesa sin capacidad se rompe."}
    version_b = json.loads(run(base + ["production-plan", "--brief", str(_write(temp / "brief-b.json", brief_b)), "--adapter", "ffmpeg_animatic", "--parent-version-id", str(version_a["id"])]))
    rendered_b = json.loads(run(base + ["production-render", version_b["version_key"], "--output-dir", str(temp / "production")]))
    assert rendered_b["status"] == "RENDERED", rendered_b
    validate_contract("production-manifest.v0.1.schema.json", rendered_b["manifest"])
    run(base + ["production-activate", version_b["version_key"]])
    rolled = json.loads(run(base + ["production-rollback", version_a["version_key"]]))
    assert rolled["status"] == "ROLLED_BACK"

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "vlux_ci.cli", "--db", str(db), "dashboard",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                summary = http_json(base_url + "/api/summary")
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                time.sleep(0.2)
        else:
            raise RuntimeError("dashboard_did_not_start")
        assert summary["schema_version"] == "0.5"
        assert summary["training_state"] == "NO_TRAINING_INSUFFICIENT_DATA"
        assert summary["attention_analyses"] >= 2
        assert summary["human_evaluations"] >= 1
        assert summary["production_versions"] >= 2
        # The browser loads these endpoints in parallel; each request must use
        # its own SQLite connection, never a shared one across threads.
        parallel_paths = [
            "/api/summary", "/api/videos", "/api/learning", "/api/publications",
            "/api/production", "/api/recommendations",
        ] * 2
        with ThreadPoolExecutor(max_workers=8) as pool:
            parallel = list(pool.map(lambda path: http_json(base_url + path), parallel_paths))
        assert all(isinstance(item, dict) for item in parallel)
        assert all(item.get("error") is None for item in parallel)
        videos = http_json(base_url + "/api/videos")["videos"]
        assert len(videos) == 2 and videos[0]["attention"]
        latest = http_json(base_url + f"/api/attention?id={a_id}")["attention"]
        assert latest["overall"]["status"] == "ESTIMATE_NOT_VALIDATED"
        assert latest["video"]["episode"] == "SYN-V05-A"
        web_attention = http_json(base_url + "/api/attention", {"video_id": b_id})
        assert web_attention["status"] == "ATTENTION_ANALYZED"
        web_ab = http_json(base_url + "/api/ab", {"a": a_id, "b": b_id})
        assert web_ab["summary"]["automatic_winner"] is None
        webpage = urllib.request.urlopen(base_url + "/", timeout=5).read().decode("utf-8")
        assert "VLUX STUDIO OS" in webpage and "ATTENTION LAB" in webpage.upper()
        web_eval = http_json(base_url + "/api/evaluate", {
            "video_id": a_id, "evaluator_id": "web-reviewer", "provenance": "human",
            "hook": 4, "narrative": 4, "clarity": 4,
        })
        assert web_eval["status"] == "EVALUATION_RECORDED"
        web_registry = http_json(base_url + "/api/dataset-register", {})
        assert web_registry["status"] == "REGISTERED_BLOCKED"
        web_learning = http_json(base_url + "/api/learning")
        assert web_learning["gate"]["status"] == "BLOCKED"
        web_plan = http_json(base_url + "/api/production/plan", {
            "brief": brief_a, "adapter": "manifest",
        })
        assert web_plan["status"] == "candidate"
        web_render = http_json(base_url + "/api/production/render", {
            "version_key": web_plan["version_key"],
        })
        assert web_render["status"] == "RENDERED"
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

    report = {
        "status": "V05_E2E_PASS",
        "database": str(db),
        "attention_contract": attention_a["contract_version"],
        "ab_contract": ab["contract_version"],
        "training_state": learning["training_state"],
        "gate_status": learning["gate"]["status"],
        "production_versions": 2,
        "dashboard_http_workflow": True,
        "contract_schemas_validated": True,
        "real_media_used": False,
        "gpu_used": False,
    }
    print(json.dumps(report, indent=2))


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    main()
