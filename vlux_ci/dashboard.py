from __future__ import annotations

import json
import re
import shutil
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .analyzer import analyze
from .creative import recommend
from .db import connect, json_dumps, sha256_file
from .funnel import funnel
from .probe import probe

MAX_UPLOAD_BYTES = 512 * 1024 * 1024


def _page() -> str:
    return """<!doctype html><meta charset="utf-8">
<title>VLUX Creative Intelligence V0.4</title>
<style>
body{font:15px system-ui;max-width:1180px;margin:28px auto;background:#0e141b;color:#e9eef5}
section{background:#18232e;padding:18px;margin:12px 0;border-radius:10px}
button{background:#8be9fd;border:0;border-radius:5px;padding:8px 12px;cursor:pointer}
input,select,textarea{margin:4px;padding:7px;background:#101820;color:#e9eef5;border:1px solid #455565;border-radius:4px}
textarea{width:95%;min-height:55px}pre{white-space:pre-wrap;max-height:480px;overflow:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.muted{color:#a9b5c1}.ok{color:#9fe3b1}.warn{color:#ffd580}
</style>
<h1>VLUX Creative Intelligence <small>V0.4</small></h1>
<p class="muted">CPU-first · local-only · no render · propuestas separadas de evidencia.</p>
<div class="grid">
<section><h2>Estado</h2><pre id="summary">Cargando…</pre></section>
<section><h2>Registrar métrica de publicación</h2>
<input id="pubid" type="number" placeholder="ID publicación"><input id="metricname" placeholder="qualified_leads">
<input id="metricvalue" type="number" step=".01" placeholder="valor"><input id="metricprov" value="USER_PROVIDED_SCREENSHOT" placeholder="procedencia"><input id="metricdate" placeholder="fecha ISO"><br>
<button onclick="metric()">Guardar métrica</button><pre id="metricResult"></pre></section>
<section><h2>Importar copia de revisión</h2>
<input id="file" type="file" accept="video/*"><br>
<input id="episode" placeholder="EP020"><input id="kind" value="review" placeholder="published/review/synthetic">
<input id="campaign" placeholder="campaña"><br>
<button onclick="upload()">Copiar e importar</button><pre id="importResult"></pre></section>
</div>
<section><h2>Videos y publicaciones</h2><pre id="publications">Cargando…</pre><div id="videos">Cargando…</div></section>
<section><h2>Evaluación A/B</h2>
<input id="a" type="number" placeholder="ID A"><input id="b" type="number" placeholder="ID B">
<select id="winner"><option>A</option><option>B</option><option>tie</option></select>
<select id="criterion"><option>full_video</option><option>retention</option><option>clarity</option><option>visual_impact</option><option>realism_3d</option><option>credibility</option><option>business_value</option><option>commercial_potential</option></select>
<input id="confidence" type="number" min="0" max="1" step=".05" placeholder="confianza">
<input id="evaluator" placeholder="evaluador"><textarea id="observations" placeholder="observaciones"></textarea>
<button onclick="feedback()">Guardar preferencia humana</button><pre id="feedbackResult"></pre></section>
<section><h2>Creative Director</h2>
<textarea id="brief" placeholder='{"business_problem":"errores de trazabilidad","target_audience":"directores de operaciones","vlux_product":"automatización del flujo"}'></textarea><br>
<button onclick="recommendBrief()">Generar propuesta</button><button onclick="downloadBrief()">Descargar JSON</button><pre id="creativeResult"></pre></section>
<section><h2>EP025 — comparación de propuestas</h2>
<input id="pa" type="number" placeholder="propuesta A"><input id="pb" type="number" placeholder="propuesta B">
<select id="pw"><option>A</option><option>B</option><option>tie</option></select>
<input id="pcl" type="number" min="1" max="5" step=".5" placeholder="claridad"><input id="pi" type="number" min="1" max="5" step=".5" placeholder="impacto"><input id="pcr" type="number" min="1" max="5" step=".5" placeholder="credibilidad"><input id="prt" type="number" min="1" max="5" step=".5" placeholder="retención"><input id="pco" type="number" min="1" max="5" step=".5" placeholder="comercial"><br>
<input id="pc" type="number" min="0" max="1" step=".05" placeholder="confianza">
<input id="pe" placeholder="evaluador"><textarea id="po" placeholder="observaciones"></textarea>
<button onclick="proposalFeedback()">Guardar comparación</button><pre id="proposalResult"></pre><pre id="proposals"></pre></section>
<script>
const $=id=>document.getElementById(id);
async function api(url,opt){let r=await fetch(url,opt);let x=await r.json();if(!r.ok)throw Error(x.error||JSON.stringify(x));return x}
async function refresh(){try{$('summary').textContent=JSON.stringify(await api('/api/summary'),null,2);let x=await api('/api/videos');$('videos').innerHTML=x.videos.map(v=>`<article><b>#${v.id} ${v.episode}</b> · ${v.source_kind} · ${v.file_path}<br><button onclick="analyze(${v.id})">Analizar</button> <button onclick="show(${v.id})">Ver análisis</button><pre id="v${v.id}"></pre></article>`).join('')||'Sin videos';$('publications').textContent=JSON.stringify(await api('/api/publications'),null,2);$('proposals').textContent=JSON.stringify(await api('/api/proposals'),null,2)}catch(e){$('summary').textContent=e}}
async function upload(){let f=$('file').files[0];if(!f){$('importResult').textContent='Selecciona un video';return} $('importResult').textContent='Copiando y validando…';try{let q=new URLSearchParams({episode:$('episode').value||'UNKNOWN',source_kind:$('kind').value||'review',campaign:$('campaign').value||''});let x=await api('/api/upload?'+q,{method:'POST',headers:{'X-Filename':f.name,'Content-Length':f.size},body:f});$('importResult').textContent=JSON.stringify(x,null,2);refresh()}catch(e){$('importResult').textContent='Error: '+e}}
async function analyze(id){$('v'+id).textContent='Analizando CPU…';try{$('v'+id).textContent=JSON.stringify(await api('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:id})}),null,2)}catch(e){$('v'+id).textContent='Error: '+e}}
async function show(id){try{$('v'+id).textContent=JSON.stringify(await api('/api/analysis?id='+id),null,2)}catch(e){$('v'+id).textContent='Error: '+e}}
async function feedback(){try{$('feedbackResult').textContent=JSON.stringify(await api('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({a:+$('a').value,b:+$('b').value,winner:$('winner').value,criterion:$('criterion').value,confidence:+$('confidence').value,evaluator:$('evaluator').value,observations:$('observations').value})}),null,2);refresh()}catch(e){$('feedbackResult').textContent='Error: '+e}}
async function metric(){try{$('metricResult').textContent=JSON.stringify(await api('/api/platform-metric',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({publication_id:+$('pubid').value,name:$('metricname').value,value:+$('metricvalue').value,provenance:$('metricprov').value,measured_at:$('metricdate').value||null})}),null,2);refresh()}catch(e){$('metricResult').textContent='Error: '+e}}
async function recommendBrief(){try{let b=JSON.parse($('brief').value);$('creativeResult').textContent=JSON.stringify(await api('/api/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}),null,2)}catch(e){$('creativeResult').textContent='Error: '+e}}
async function proposalFeedback(){try{$('proposalResult').textContent=JSON.stringify(await api('/api/proposal-feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({a:+$('pa').value,b:+$('pb').value,winner:$('pw').value,clarity:+$('pcl').value,impact:+$('pi').value,credibility:+$('pcr').value,retention:+$('prt').value,commercial:+$('pco').value,confidence:+$('pc').value,evaluator:$('pe').value,observations:$('po').value})}),null,2);refresh()}catch(e){$('proposalResult').textContent='Error: '+e}}
function downloadBrief(){let blob=new Blob([$('creativeResult').textContent],{type:'application/json'});let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='creative_director.json';a.click()}
refresh();
</script>"""


def serve(db, host, port):
    db_path = str(db)
    con = connect(db_path, check_same_thread=False)
    root = Path(db_path).parent.parent
    copy_dir = root / "data" / "review"
    copy_dir.mkdir(parents=True, exist_ok=True)

    class H(BaseHTTPRequestHandler):
        def send_json(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def body_json(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length > 2 * 1024 * 1024:
                raise ValueError("json_payload_too_large")
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/summary":
                self.send_json({
                    "schema_version": con.execute("select value from schema_meta where key='schema_version'").fetchone()[0],
                    "videos": con.execute("select count(*) from videos").fetchone()[0],
                    "analyzed": con.execute("select count(distinct video_id) from analyses").fetchone()[0],
                    "observations": con.execute("select count(*) from observations").fetchone()[0],
                    "feedback": con.execute("select count(*) from feedback").fetchone()[0],
                    "metrics": con.execute("select count(*) from metrics").fetchone()[0],
                    "publications": con.execute("select count(*) from publications").fetchone()[0],
                    "platform_metrics": con.execute("select count(*) from platform_metrics").fetchone()[0],
                    "creative_proposals": con.execute("select count(*) from creative_proposals").fetchone()[0],
                    "models": con.execute("select count(*) from models").fetchone()[0],
                    "training_state": "NO_TRAINING_INSUFFICIENT_DATA_UNLESS_EVIDENCE_CHANGES",
                })
            elif parsed.path == "/api/videos":
                self.send_json({"videos": [dict(r) for r in con.execute(
                    "select id,episode,version,file_path,source_kind,campaign,duration_s,width,height from videos order by id desc"
                )]})
            elif parsed.path == "/api/analysis":
                video_id = int(parse_qs(parsed.query).get("id", ["0"])[0])
                row = con.execute("select * from analyses where video_id=? order by id desc limit 1", (video_id,)).fetchone()
                obs = [dict(r) for r in con.execute("select * from observations where video_id=? order by start_s", (video_id,))]
                self.send_json({"analysis": dict(row) if row else None, "observations": obs})
            elif parsed.path == "/api/publications":
                rows = []
                for row in con.execute("select * from publications order by id desc"):
                    item = dict(row)
                    item["funnel"] = funnel(con, row["id"])
                    rows.append(item)
                self.send_json({"publications": rows})
            elif parsed.path == "/api/proposals":
                self.send_json({"proposals": [dict(r) for r in con.execute("select id,episode,proposal_key,title,contract_version from creative_proposals order by id")]})
            else:
                body = _page().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def do_POST(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/upload":
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > MAX_UPLOAD_BYTES:
                        raise ValueError("upload_size_invalid_or_too_large")
                    name = re.sub(r"[^A-Za-z0-9_.-]", "_", self.headers.get("X-Filename", "upload.mp4"))
                    target = copy_dir / f"{uuid.uuid4().hex[:12]}-{name}"
                    remaining = length
                    with target.open("wb") as out:
                        while remaining:
                            block = self.rfile.read(min(1024 * 1024, remaining))
                            if not block:
                                break
                            out.write(block)
                            remaining -= len(block)
                    if remaining:
                        target.unlink(missing_ok=True)
                        raise ValueError("upload_incomplete")
                    meta = probe(target)
                    q = parse_qs(parsed.query)
                    h = sha256_file(target)
                    if con.execute("select id from videos where file_hash=?", (h,)).fetchone():
                        target.unlink(missing_ok=True)
                        self.send_json({"status": "DUPLICATE"}, 409)
                        return
                    con.execute(
                        "insert into videos(episode,version,file_path,file_hash,duration_s,fps,width,height,campaign,"
                        "approval_status,permission_status,source_kind,source_type,provenance) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (q.get("episode", ["UNKNOWN"])[0], "v0.3", str(target), h, meta["duration_s"],
                         meta["fps"], meta["width"], meta["height"], q.get("campaign", [None])[0],
                         "unknown", "user-selected-local-copy", q.get("source_kind", ["review"])[0],
                         "dashboard-upload", "copied_by_vlux_ci_dashboard"),
                    )
                    con.commit()
                    self.send_json({"status": "IMPORTED_COPY", "video_id": con.execute("select last_insert_rowid()").fetchone()[0], "probe": meta})
                elif parsed.path == "/api/analyze":
                    data = self.body_json()
                    row = con.execute("select * from videos where id=?", (int(data["video_id"]),)).fetchone()
                    if not row:
                        raise ValueError("video_not_found")
                    objective, estimated, observations = analyze(row["file_path"])
                    con.execute("insert into analyses(video_id,analyzer_version,objective_json,aesthetic_json) values(?,?,?,?)",
                                (row["id"], "0.3.0", json_dumps(objective), json_dumps(estimated)))
                    for item in observations:
                        con.execute("insert into observations(video_id,start_s,end_s,severity,category,message,recommendation,evidence_json) values(?,?,?,?,?,?,?,?)",
                                    (row["id"], item["start_s"], item["end_s"], item["severity"], item["category"], item["message"], item["recommendation"], json_dumps(objective)))
                    con.commit()
                    self.send_json({"status": "ANALYZED", "video_id": row["id"], "objective": objective, "estimated": estimated, "observations": observations})
                elif parsed.path == "/api/feedback":
                    data = self.body_json()
                    con.execute(
                        "insert into feedback(variant_a_id,variant_b_id,winner,criterion,comparison_type,confidence,observations,evaluator_id,origin) values(?,?,?,?,?,?,?,?,?)",
                        (int(data["a"]), int(data["b"]), data["winner"], data.get("criterion", "full_video"),
                         "dashboard", data.get("confidence"), data.get("observations", ""),
                         data.get("evaluator", "anonymous"), "human"),
                    )
                    con.commit()
                    self.send_json({"status": "FEEDBACK_RECORDED"})
                elif parsed.path == "/api/platform-metric":
                    data = self.body_json()
                    con.execute(
                        "insert or replace into platform_metrics(publication_id,metric_name,metric_value,status,provenance,measured_at) values(?,?,?,?,?,?)",
                        (int(data["publication_id"]), data["name"], data.get("value"),
                         data.get("status", "OBSERVED"), data["provenance"], data.get("measured_at")),
                    )
                    con.commit()
                    self.send_json({"status": "PLATFORM_METRIC_RECORDED"})
                elif parsed.path == "/api/recommend":
                    self.send_json(recommend(self.body_json(), con))
                elif parsed.path == "/api/proposal-feedback":
                    data = self.body_json()
                    con.execute(
                        "insert into proposal_feedback(proposal_a_id,proposal_b_id,winner,clarity,impact,credibility,retention_potential,commercial_potential,confidence,observations,evaluator_id) values(?,?,?,?,?,?,?,?,?,?,?)",
                        (int(data["a"]), int(data["b"]), data["winner"], data.get("clarity"), data.get("impact"), data.get("credibility"), data.get("retention"), data.get("commercial"), data.get("confidence"),
                         data.get("observations", ""), data.get("evaluator", "anonymous")),
                    )
                    con.commit()
                    self.send_json({"status": "PROPOSAL_FEEDBACK_RECORDED"})
                else:
                    self.send_json({"error": "not_found"}, 404)
            except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, 400)

        def log_message(self, *_args):
            pass

    print(f"http://{host}:{port}")
    ThreadingHTTPServer((host, port), H).serve_forever()
