from __future__ import annotations

import json
import socket
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(args, cwd=ROOT):
    p = subprocess.run([sys.executable, "-m", "vlux_ci.cli", *args],
                       cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"{args}\nSTDOUT={p.stdout}\nSTDERR={p.stderr}")
    return p.stdout


def main():
    temp = Path(tempfile.mkdtemp(prefix="vlux-v03-", dir=ROOT / "data" / "synthetic"))
    db = temp / "workflow.sqlite"
    video = temp / "fixture.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x90:d=2.2",
                    "-an", "-pix_fmt", "yuv420p", str(video)],
                   check=True, capture_output=True)
    base = ["--db", str(db)]
    imported = json.loads(run(base + ["import", str(video), "--episode", "SYN-V03",
                                      "--source-kind", "synthetic", "--permission", "synthetic"]))
    video_id = imported["video_id"]
    analyzed = json.loads(run(base + ["analyze", str(video_id)]))
    assert analyzed["observations"] or analyzed["objective"]["sample_count"] > 0
    # A second imported fixture makes A/B persistence concrete.
    video2 = temp / "fixture-b.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=green:s=160x90:d=2.2",
                    "-an", "-pix_fmt", "yuv420p", str(video2)],
                   check=True, capture_output=True)
    imported2 = json.loads(run(base + ["import", str(video2), "--episode", "SYN-V03-B",
                                       "--source-kind", "synthetic", "--permission", "synthetic"]))
    run(base + ["analyze", str(imported2["video_id"])])
    run(base + ["feedback", "--a", str(video_id), "--b", str(imported2["video_id"]),
                "--winner", "A", "--criterion", "clarity", "--confidence", "0.8"])
    brief = ROOT / "examples" / "brief.json"
    bundle = temp / "bundle"
    run(base + ["export-bundle", "--brief", str(brief), "--output-dir", str(bundle)])
    required = ["creative_director.json", "video_brief.json", "qa_recommendations.json"]
    for name in required:
        data = json.loads((bundle / name).read_text(encoding="utf-8"))
        assert data.get("status") in {"PROPOSAL_ONLY", "REVIEW_REQUIRED"}
    # Restart persistence: new process reads the same database.
    status = json.loads(run(base + ["dataset-status"]))
    assert status["schema_version"] in ("0.5", "0.6")
    assert status["source_kinds"]
    publication = json.loads(run(base + ["publication", "--episode", "WEB-SYN",
                                          "--platform", "Instagram",
                                          "--provenance", "SYNTHETIC_E2E"]))
    run(base + ["platform-metric", str(publication["publication_id"]), "views",
                "--value", "10", "--provenance", "SYNTHETIC_E2E"])
    run(base + ["seed-ep025-proposals"])
    video3 = temp / "fixture-web.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=160x90:d=2.2",
                    "-an", "-pix_fmt", "yuv420p", str(video3)],
                   check=True, capture_output=True)
    # Product check: start the actual local dashboard and use its HTTP workflow.
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
        for _ in range(30):
            try:
                with urllib.request.urlopen(base_url + "/api/summary", timeout=1) as response:
                    summary = json.loads(response.read())
                    break
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                time.sleep(0.2)
        else:
            raise RuntimeError("dashboard_did_not_start")
        assert summary["schema_version"] in ("0.5", "0.6")
        with urllib.request.urlopen(base_url + "/api/publications", timeout=5) as response:
            assert json.loads(response.read())["publications"]
        with urllib.request.urlopen(base_url + "/api/proposals", timeout=5) as response:
            assert len(json.loads(response.read())["proposals"]) == 3
        req = urllib.request.Request(
            base_url + "/api/platform-metric", data=json.dumps({
                "publication_id": publication["publication_id"], "name": "profile_visits",
                "value": 2, "provenance": "SYNTHETIC_E2E",
            }).encode(), method="POST", headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            assert json.loads(response.read())["status"] == "PLATFORM_METRIC_RECORDED"
        body = video3.read_bytes()
        req = urllib.request.Request(
            base_url + "/api/upload?episode=WEB-SYN&source_kind=synthetic",
            data=body, method="POST",
            headers={"Content-Type": "video/mp4", "Content-Length": str(len(body)),
                     "X-Filename": "web-fixture.mp4"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            uploaded = json.loads(response.read())
        assert uploaded["status"] == "IMPORTED_COPY"
        req = urllib.request.Request(
            base_url + "/api/analyze", data=json.dumps({"video_id": uploaded["video_id"]}).encode(),
            method="POST", headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=90) as response:
            web_analysis = json.loads(response.read())
        assert web_analysis["status"] == "ANALYZED"
        req = urllib.request.Request(
            base_url + "/api/proposal-feedback", data=json.dumps({
                "a": 1, "b": 2, "winner": "A", "clarity": 4, "impact": 4,
                "credibility": 4, "retention": 3, "commercial": 4,
                "confidence": .8, "evaluator": "synthetic-e2e",
            }).encode(), method="POST", headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            assert json.loads(response.read())["status"] == "PROPOSAL_FEEDBACK_RECORDED"
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
    print(json.dumps({"status": "V03_E2E_PASS", "database": str(db),
                      "video_id": video_id, "bundle": str(bundle),
                      "restart_persistence": True, "dashboard_http_workflow": True,
                      "publication_and_proposal_ui": True}, indent=2))


if __name__ == "__main__":
    main()
