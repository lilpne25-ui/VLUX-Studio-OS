from __future__ import annotations

import json
import re
import shutil
import uuid
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .ab import compare as ab_compare
from .ab import list_evaluations, record_evaluation
from .analyzer import analyze
from .attention import ANALYZER_VERSION, analyze_attention, attention_summary, latest_attention
from .creative import recommend
from .creative_loop import (
    compare_episode_versions, create_production_brief, create_review, export_production_brief,
    export_review_bundle, get_episode_version, import_episode_version, list_version_evaluations,
    loop_status, record_human_approval, record_performance, record_version_evaluation, verify_version_integrity,
)
from .db import connect, json_dumps, sha256_file
from .funnel import funnel
from .learning import dataset_registry, gate_report, list_experiments, list_models, training_status
from .probe import probe
from .production import (
    activate_version, list_versions, plan_version, render_version,
    rollback_version, summary as production_summary,
)

MAX_UPLOAD_BYTES = 512 * 1024 * 1024


def _page() -> str:
    return """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VLUX Studio OS · Attention Lab V0.1</title>
<style>
:root{
  --bg:#080c11;--panel:#0f1721;--panel2:#131e2a;--line:#223244;--text:#e8eef6;
  --muted:#91a0b3;--cyan:#6fe3ff;--blue:#5b8cff;--green:#8ce8b0;--amber:#ffd27a;
  --red:#ff8f9b;--violet:#b7a4ff;--radius:14px
}
*{box-sizing:border-box}
body{margin:0;background:
  radial-gradient(900px 600px at 8% -10%,#12324a 0%,transparent 55%),
  radial-gradient(700px 500px at 95% 0%,#231c46 0%,transparent 50%),var(--bg);
  color:var(--text);font:14px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;min-height:100vh}
.wrap{max-width:1380px;margin:0 auto;padding:28px 28px 60px}
header{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:22px}
.brand{display:flex;align-items:center;gap:14px}
.mark{width:46px;height:46px;border-radius:13px;display:grid;place-items:center;font-weight:800;font-size:22px;
  background:linear-gradient(145deg,#7cecff,#5b8cff 55%,#b7a4ff);color:#071018;box-shadow:0 10px 30px #5b8cff33}
h1{margin:0;font-size:20px;letter-spacing:.16em;font-weight:800}
.sub{margin:2px 0 0;color:var(--muted);font-size:12px;letter-spacing:.04em}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:#0c141d;color:var(--muted);padding:7px 11px;border-radius:999px;
  font-size:11px;letter-spacing:.08em;text-transform:uppercase}
.chip.ok{color:var(--green);border-color:#2c5c42;background:#0b1a13}
.chip.warn{color:var(--amber);border-color:#5a4822;background:#1c1609}
.chip.info{color:var(--cyan);border-color:#1f4d5c;background:#08171d}
.hero{display:grid;grid-template-columns:1.55fr .9fr;gap:16px;margin-bottom:18px}
.card{background:linear-gradient(180deg,#111b26,#0d151e);border:1px solid var(--line);border-radius:var(--radius);padding:18px}
.hero-main{position:relative;overflow:hidden}
.hero-main:after{content:"";position:absolute;width:280px;height:280px;border-radius:50%;right:-90px;top:-110px;
  background:radial-gradient(circle,#6fe3ff22,transparent 65%)}
.eyebrow{margin:0 0 10px;color:var(--cyan);font-size:11px;letter-spacing:.22em;text-transform:uppercase;font-weight:700}
h2{margin:0 0 8px;font-size:27px;line-height:1.15;letter-spacing:-.02em;max-width:760px}
.lead{color:var(--muted);margin:0;max-width:760px}
.layers{display:flex;gap:8px;flex-wrap:wrap;margin-top:22px}
.layers span{border:1px solid #244257;background:#0a1720;color:#bcd2e4;padding:8px 11px;border-radius:8px;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase}
.layers b{color:var(--cyan);margin-right:5px}
.hero-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.metric{background:#0b131c;border:1px solid var(--line);border-radius:11px;padding:12px}
.metric .k{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.12em}
.metric .v{font-size:20px;font-weight:750;margin-top:3px}
nav{display:flex;gap:6px;flex-wrap:wrap;margin:20px 0 16px;border-bottom:1px solid var(--line);padding-bottom:10px}
nav button{background:transparent;border:1px solid transparent;color:var(--muted);padding:8px 13px;border-radius:8px;cursor:pointer;font-weight:600}
nav button:hover{color:var(--text);background:#101b26}
nav button.active{color:#081018;background:linear-gradient(135deg,#7cecff,#8cb6ff);border-color:#7cecff}
.view{display:none}.view.active{display:block}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px}
.col-4{grid-column:span 4}.col-5{grid-column:span 5}.col-6{grid-column:span 6}.col-7{grid-column:span 7}.col-8{grid-column:span 8}.col-12{grid-column:span 12}
@media(max-width:980px){.hero{grid-template-columns:1fr}.col-4,.col-5,.col-6,.col-7,.col-8{grid-column:span 12}}
h3{margin:0 0 12px;font-size:14px;letter-spacing:.08em;text-transform:uppercase;color:#c8d5e4}
.muted{color:var(--muted)}.small{font-size:12px}.tiny{font-size:11px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;color:var(--muted);font-weight:600;font-size:10.5px;text-transform:uppercase;letter-spacing:.09em;padding:8px 9px;border-bottom:1px solid var(--line)}
td{padding:9px;border-bottom:1px solid #182635;vertical-align:top}
tr:hover td{background:#101b26}
button{font:inherit}
.btn{background:#122536;color:#dff6ff;border:1px solid #2b4a60;border-radius:8px;padding:7px 11px;cursor:pointer}
.btn:hover{background:#173248;border-color:#4e819e}
.btn.primary{background:linear-gradient(135deg,#7cecff,#7ea7ff);color:#071018;border:0;font-weight:750}
.btn.good{background:#10301f;border-color:#2d6b47;color:#a9f5c4}
.btn.warn{background:#2a1d0a;border-color:#6b4e1c;color:#ffd98a}
.btn.ghost{background:transparent;border-color:var(--line);color:var(--muted)}
input,select,textarea{background:#081018;color:var(--text);border:1px solid #2a3b4d;border-radius:8px;padding:9px 10px;font:inherit}
textarea{width:100%;min-height:92px;resize:vertical}
label{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin:8px 0 4px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.score{display:flex;align-items:baseline;gap:8px}
.score .num{font-size:34px;font-weight:800;letter-spacing:-.03em}
.score .den{color:var(--muted);font-size:11px}
.bar{height:9px;background:#0a121a;border-radius:999px;overflow:hidden;border:1px solid #1d2c3b}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#6fe3ff,#8cb6ff);border-radius:999px}
.bar.amber i{background:linear-gradient(90deg,#ffd27a,#ff9d66)}
.bar.green i{background:linear-gradient(90deg,#8ce8b0,#6fe3ff)}
.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;font-size:10.5px;color:var(--muted);background:#0a121a}
.pill.ok{color:var(--green);border-color:#2c5c42}.pill.warn{color:var(--amber);border-color:#5a4822}.pill.bad{color:var(--red);border-color:#5c2b32}.pill.info{color:var(--cyan);border-color:#1f4d5c}
.timeline{display:flex;gap:2px;height:54px;align-items:flex-end;margin:10px 0 4px}
.timeline span{flex:1;min-width:2px;background:linear-gradient(180deg,#6fe3ff,#2b5c88);border-radius:2px 2px 0 0;opacity:.85}
.timeline span:hover{opacity:1;background:#b7a4ff}
.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.fact{background:#0a121a;border:1px solid #1b2a39;border-radius:9px;padding:9px}
.fact .k{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em}
.fact .v{font-weight:700;margin-top:2px}
.list{margin:0;padding-left:18px}.list li{margin:6px 0;color:#c6d3e2}
.kv{display:grid;grid-template-columns:1fr auto;gap:6px;padding:6px 0;border-bottom:1px dashed #1c2b3a}
.kv:last-child{border:0}
.banner{border:1px solid #5a4822;background:linear-gradient(90deg,#231a09,#15130d);color:#ffd98a;padding:12px 14px;border-radius:10px;margin-bottom:12px}
.banner.ok{border-color:#2c5c42;background:linear-gradient(90deg,#0c2418,#0d1711);color:#a9f5c4}
.banner.bad{border-color:#5c2b32;background:linear-gradient(90deg,#261013,#160d0f);color:#ffb3bc}
pre{white-space:pre-wrap;word-break:break-word;background:#081018;border:1px solid #1b2a39;border-radius:10px;padding:12px;max-height:420px;overflow:auto;font-size:12px;color:#c7d6e6}
details{border:1px solid #1b2a39;border-radius:10px;padding:10px;background:#0a121a}
summary{cursor:pointer;color:#c8d5e4;font-weight:650}
footer{margin-top:30px;color:#6f8094;font-size:11.5px;border-top:1px solid var(--line);padding-top:14px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.hr{height:1px;background:var(--line);margin:14px 0}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:800px){.two{grid-template-columns:1fr}}
.slider{display:grid;grid-template-columns:110px 1fr 34px;gap:8px;align-items:center;margin:5px 0}
.slider input{padding:0}.slider b{text-align:right;color:var(--cyan)}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="brand"><div class="mark">V</div><div><h1>VLUX STUDIO OS</h1><p class="sub">VLUX ATTENTION LAB · V0.6 · CREATIVE FEEDBACK LOOP · INDEPENDENT CREATIVE ENGINE</p></div></div>
  <div class="chips">
    <span class="chip info">LOCAL</span><span class="chip info">CPU</span>
    <span class="chip" id="schemaChip">SCHEMA 0.6</span>
    <span class="chip warn" id="trainChip">NO_TRAINING_INSUFFICIENT_DATA</span>
  </div>
</header>

<div class="hero">
  <div class="card hero-main">
    <p class="eyebrow">V0.6 · CREATIVE FEEDBACK LOOP</p>
    <h2>De señales observables a decisiones creativas defendibles.</h2>
    <p class="lead">Hechos audiovisuales, estimaciones heurísticas, preferencias humanas y resultados comerciales permanecen en capas separadas. Sin predicciones de viralidad, sin datos inventados.</p>
    <div class="layers">
      <span><b>01</b> Hechos</span><span><b>02</b> Estimaciones</span><span><b>03</b> Preferencia humana</span><span><b>04</b> Resultados</span>
    </div>
  </div>
  <div class="card">
    <h3>Estado del sistema</h3>
    <div class="hero-grid" id="heroStats"><div class="metric"><div class="k">Cargando</div><div class="v">…</div></div></div>
  </div>
</div>

<nav id="nav">
  <button class="active" data-view="overview">Overview</button>
  <button data-view="hook">Gancho y timeline</button>
  <button data-view="ab">Comparador A/B</button>
  <button data-view="learning">Aprendizaje</button>
  <button data-view="commercial">Resultados</button>
  <button data-view="production">Producción</button>
  <button data-view="loop">Loop de retroalimentación</button>
</nav>

<main>
<section class="view active" id="view-overview">
  <div class="grid">
    <div class="col-8 card">
      <h3>Biblioteca de videos</h3>
      <div class="row" style="margin-bottom:10px">
        <input id="search" placeholder="Filtrar por episodio o fuente" oninput="renderVideos()" style="flex:1">
        <button class="btn ghost" onclick="refreshAll()">Actualizar</button>
      </div>
      <div id="videos" class="muted">Cargando…</div>
    </div>
    <div class="col-4 card">
      <h3>Pipeline</h3>
      <div class="kv"><span>Importación</span><span class="pill ok">LOCAL</span></div>
      <div class="kv"><span>Análisis</span><span class="pill ok">FFPROBE + OPENCV</span></div>
      <div class="kv"><span>Estimación</span><span class="pill info">HEURÍSTICA</span></div>
      <div class="kv"><span>Preferencia humana</span><span class="pill warn" id="humanPill">SIN DATOS</span></div>
      <div class="kv"><span>Resultados comerciales</span><span class="pill warn" id="commercialPill">NO DISPONIBLES</span></div>
      <div class="kv"><span>Entrenamiento</span><span class="pill bad" id="trainingPill">BLOQUEADO</span></div>
      <div class="hr"></div>
      <p class="small muted" style="margin:0">El sistema no declara un ganador con estimaciones. Un cambio por experimento; una decisión por evidencia.</p>
    </div>
    <div class="col-6 card">
      <h3>Recomendaciones recientes</h3>
      <div id="recentRecommendations" class="muted">Selecciona un video y ejecuta Attention Lab.</div>
    </div>
    <div class="col-6 card">
      <h3>Estado de aprendizaje</h3>
      <div id="learningMini" class="muted">Cargando…</div>
    </div>
  </div>
</section>

<section class="view" id="view-loop">
  <div class="grid">
    <div class="col-12 card">
      <div class="row" style="justify-content:space-between"><h3 style="margin:0">Creative Feedback Loop · V0.6</h3><button class="btn ghost" onclick="refreshLoop()">Actualizar</button></div>
      <div id="loopPanel" class="muted" style="margin-top:10px">Cargando…</div>
      <pre id="loopResult" style="max-height:160px">Sin resultados todavía.</pre>
      <div class="row" style="margin-top:10px">
        <input id="loopVersionEpisode" placeholder="EP-TEST" style="flex:1">
        <input id="loopVersionPath" placeholder="data/review/pilot/EP021-pilot.mp4" style="flex:2">
        <select id="loopVersionPermission"><option value="authorized_analysis_only">authorized_analysis_only</option><option value="authorized">authorized</option><option value="owned">owned</option><option value="synthetic">synthetic</option><option value="public_domain">public_domain</option></select>
        <button class="btn" onclick="runLoopImport()">Importar versión</button>
      </div>
      <div class="row" style="margin-top:8px">
        <label>A</label>
        <select id="loopVersionA"></select>
        <label>B</label>
        <select id="loopVersionB"></select>
        <button class="btn" onclick="runLoopCompare()">Comparar versiones</button>
      </div>
      <div class="row" style="margin-top:8px">
        <input id="loopExportDir" value="reports/v06" style="flex:2">
        <button class="btn" onclick="runLoopExportReview()">Exportar review</button>
        <button class="btn" onclick="runLoopBrief()">Crear brief</button>
        <button class="btn" onclick="runLoopExportBrief()">Exportar handoff</button>
      </div>
    </div>
  </div>
</section>

<section class="view" id="view-hook">
  <div class="card" style="margin-bottom:14px">
    <div class="row">
      <div style="flex:1"><label>Video</label><select id="hookVideo" onchange="loadAttention()" style="width:100%"></select></div>
      <button class="btn primary" onclick="runAttention()">Ejecutar Attention Lab</button>
      <button class="btn ghost" onclick="loadAttention()">Ver último</button>
    </div>
    <p class="small muted" style="margin:10px 0 0">Heurístico, determinista y no validado. Los resultados son estimaciones, no predicciones científicas de viralidad.</p>
  </div>
  <div id="attentionPanel" class="muted">Selecciona un video para empezar.</div>
</section>

<section class="view" id="view-ab">
  <div class="card" style="margin-bottom:14px">
    <h3>Comparador A/B</h3>
    <div class="row">
      <div style="flex:1"><label>A</label><select id="abA" style="width:100%"></select></div>
      <div style="flex:1"><label>B</label><select id="abB" style="width:100%"></select></div>
      <button class="btn primary" onclick="runAB()">Comparar</button>
      <button class="btn ghost" onclick="downloadAB()">Descargar JSON</button>
    </div>
    <p class="small muted" style="margin:10px 0 0">Observado ≠ estimado ≠ preferencia humana ≠ resultado comercial. El comparador no elige ganador automáticamente.</p>
  </div>
  <div id="abPanel" class="muted">Elige dos videos analizados.</div>
</section>

<section class="view" id="view-learning">
  <div class="grid">
    <div class="col-8 card">
      <div class="row" style="justify-content:space-between"><h3 style="margin:0">Training Gate</h3><button class="btn ghost" onclick="refreshLearning()">Actualizar</button></div>
      <div id="learningPanel" class="muted" style="margin-top:12px">Cargando…</div>
    </div>
    <div class="col-4 card">
      <h3>Registro</h3>
      <div id="registryPanel" class="muted">Sin dataset registrado en esta sesión.</div>
      <div class="hr"></div>
      <button class="btn" onclick="registerDataset()">Registrar dataset</button>
      <p class="tiny muted">El entrenamiento sólo se ejecuta por CLI (`python -m vlux_ci.cli train`). El dashboard nunca entrena ni promueve modelos.</p>
    </div>
    <div class="col-12 card">
      <h3>Experimentos y modelos</h3>
      <div id="modelsPanel" class="muted">Cargando…</div>
    </div>
  </div>
</section>

<section class="view" id="view-commercial">
  <div class="grid">
    <div class="col-12 card">
      <h3>Resultados comerciales reales</h3>
      <div class="banner">Likes, guardados, compartidos y seguidores no son ventas ni leads calificados. Las métricas ausentes permanecen NOT_AVAILABLE.</div>
      <div id="publications" class="muted">Cargando…</div>
    </div>
    <div class="col-6 card">
      <h3>Creative Director</h3>
      <textarea id="brief" placeholder='{"business_problem":"errores de trazabilidad","target_audience":"directores de operaciones","vlux_product":"automatización del flujo","episode":"EP025"}'></textarea>
      <div class="row" style="margin-top:8px"><button class="btn primary" onclick="recommendBrief()">Generar propuesta</button><button class="btn ghost" onclick="downloadBrief()">Descargar JSON</button></div>
      <pre id="creativeResult" style="margin-top:10px">Propuesta pendiente.</pre>
    </div>
    <div class="col-6 card">
      <h3>Propuestas registradas</h3>
      <div id="proposals" class="muted">Cargando…</div>
    </div>
  </div>
</section>

<section class="view" id="view-production">
  <div class="grid">
    <div class="col-6 card">
      <h3>Visual Production Adapter</h3>
      <label>Brief JSON</label>
      <textarea id="prodBrief">{
  "contract_version": "creative-director.v0.2",
  "episode": "EP-DEMO",
  "topic": "trazabilidad de ingeniería",
  "business_problem": "Los datos se copian a mano y se pierden horas.",
  "target_audience": "directores de operaciones",
  "recommended_hook": "¿Cuántas horas pierdes copiando datos?",
  "cta_primary": "Solicita un diagnóstico del flujo."
}</textarea>
      <div class="row" style="margin-top:8px">
        <select id="prodAdapter"><option value="manifest">manifest</option><option value="ffmpeg_animatic">ffmpeg_animatic (placeholder CPU)</option></select>
        <button class="btn primary" onclick="planProduction()">Crear versión</button>
      </div>
      <p class="tiny muted">Sin GPU, sin pesos, sin servicios pagados. `ffmpeg_animatic` produce tarjetas de texto, no un render generativo.</p>
      <pre id="prodResult">Sin versión creada.</pre>
    </div>
    <div class="col-6 card">
      <h3>Version Registry</h3>
      <div id="versions" class="muted">Cargando…</div>
    </div>
    <div class="col-12 card">
      <h3>Importar copia autorizada</h3>
      <div class="row">
        <input id="file" type="file" accept="video/*">
        <input id="episode" placeholder="EP020">
        <select id="kind"><option value="review">review</option><option value="published">published</option><option value="synthetic">synthetic</option></select>
        <input id="permission" value="unknown" placeholder="permission">
        <button class="btn" onclick="upload()">Copiar e importar</button>
      </div>
      <pre id="importResult">La copia se guarda en data/review y nunca se publica.</pre>
    </div>
  </div>
</section>
</main>

<footer>
  <span>VLUX Studio OS · Attention Lab V0.1 · local-first · CPU-first</span>
  <span>Hechos → estimaciones → preferencias → resultados. Sin atajos.</span>
</footer>
</div>

<script>
const $=id=>document.getElementById(id);
const state={videos:[],summary:{},learning:{},publications:[],ab:null,attention:null,recent:{},loop:{}};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url,opt){const r=await fetch(url,opt);let x;try{x=await r.json()}catch(e){throw Error('Respuesta no JSON')}if(!r.ok)throw Error(x.error||JSON.stringify(x));return x}
function pct(v){return v==null?'—':Math.round(v*100)+'%'}
function score(v){return v==null?'—':v}
function pill(v,kind=''){return `<span class="pill ${kind}">${esc(v)}</span>`}
function bandPill(v){if(v==null)return pill('NO ASSESSABLE','warn');return pill(v, v==='high_estimate'?'ok':v==='mid_estimate'?'info':'warn')}
function bar(v,cls=''){return `<div class="bar ${cls}"><i style="width:${Math.max(0,Math.min(100,v||0))}%"></i></div>`}
function scoreCard(label,value,band,extra=''){return `<div class="card col-4" style="padding:14px"><div class="tiny muted">${esc(label)}</div><div class="score"><span class="num">${score(value)}</span><span class="den">/100 estimado</span></div>${bar(value||0)}<div style="margin-top:8px">${bandPill(band)} ${extra}</div></div>`}

const VIEWS=['overview','hook','ab','learning','commercial','production','loop'];
function currentView(){const h=location.hash.replace('#','');return VIEWS.includes(h)?h:'overview'}
function showView(name){
  if(!VIEWS.includes(name))name='overview';
  document.querySelectorAll('#nav button').forEach(x=>x.classList.toggle('active',x.dataset.view===name));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id==='view-'+name));
  if(location.hash!=='#'+name)history.replaceState(null,'','#'+name);
}
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>showView(b.dataset.view));
window.addEventListener('hashchange',()=>showView(currentView()));
let viewBooted=false;
function bootView(){
  if(viewBooted)return;viewBooted=true;
  const view=currentView();showView(view);
  if(view==='hook'&&state.videos.length){
    const analyzed=state.videos.filter(v=>v.attention).sort((a,b)=>(b.attention.overall??0)-(a.attention.overall??0));
    const video=analyzed[0]||state.videos[0];
    $('hookVideo').value=video.id;loadAttention();
  }
}

async function refreshAll(){
  try{
    const [s,v,l,p,pr,rec,loop]=await Promise.all([api('/api/summary'),api('/api/videos'),api('/api/learning'),api('/api/publications'),api('/api/production'),api('/api/recommendations'),api('/api/loop/status')]);
    state.summary=s;state.videos=v.videos;state.learning=l;state.publications=p.publications||[];state.recent=rec||{};state.loop=loop||{};
    $('schemaChip').textContent='SCHEMA '+s.schema_version;
    $('trainChip').textContent=s.training_state;
    $('trainChip').className='chip '+(s.training_state==='NO_TRAINING_INSUFFICIENT_DATA'?'warn':'ok');
    $('heroStats').innerHTML=[
      ['Videos',s.videos],['Analizados',s.analyzed],['Con Attention',s.attention_videos],
      ['Evaluaciones humanas',s.human_evaluations],['A/B',s.ab_comparisons],['Versiones',s.production_versions]
    ].map(([k,v])=>`<div class="metric"><div class="k">${esc(k)}</div><div class="v">${v??0}</div></div>`).join('');
    $('humanPill').textContent=s.human_evaluations?`${s.human_evaluations} REGISTRADAS`:'SIN DATOS';
    $('humanPill').className='pill '+(s.human_evaluations?'ok':'warn');
    $('commercialPill').textContent=s.commercial_records?`${s.commercial_records} REGISTROS`:'NO DISPONIBLES';
    $('commercialPill').className='pill '+(s.commercial_records?'ok':'warn');
    $('trainingPill').textContent=s.training_state==='NO_TRAINING_INSUFFICIENT_DATA'?'BLOQUEADO':'HABILITADO';
    $('trainingPill').className='pill '+(s.training_state==='NO_TRAINING_INSUFFICIENT_DATA'?'bad':'ok');
    renderVideos();fillSelects();renderLearning();renderPublications();renderVersions(pr);renderLearningMini();renderRecentRecommendations();bootView();
  }catch(e){$('videos').textContent='Error: '+e.message}
}

function renderRecentRecommendations(){
  const el=$('recentRecommendations');if(!el)return;
  const recs=state.recent?.recommendations||[];
  if(!recs.length){el.innerHTML='<p class="muted">Sin recomendaciones todavía. Ejecuta Attention Lab sobre un video.</p>';return}
  el.innerHTML=`<div class="row" style="justify-content:space-between;margin-bottom:4px"><span class="pill info">${esc(state.recent.episode||'')}</span><span class="tiny muted">${esc(state.recent.evaluated_at||'')} · índice ${esc(state.recent.overall?.score??'—')}/100 estimado</span></div>`+
    recs.map(r=>`<div style="padding:8px 0;border-bottom:1px solid #1b2a39"><div class="row">${pill(r.priority,r.priority==='high'?'bad':'warn')}${pill(r.dimension,'info')}</div><div class="small" style="margin-top:3px"><b>${esc(r.action)}</b></div><div class="tiny muted">${esc(r.reason)}</div></div>`).join('')+
    `<div class="tiny muted" style="margin-top:9px">Primer cambio sugerido: <b>${esc(state.recent.first_change?.action||'—')}</b></div>`;
}

async function refreshLoop(){try{const x=await api('/api/loop/status');state.loop=x;renderLoop()}catch(e){$('loopPanel').textContent='Error: '+e.message}}
function renderLoop(){
  const st=state.loop||{};
  const el=$('loopPanel');if(!el)return;
  el.innerHTML=`<div class="grid"><div class="col-6 card" style="padding:12px"><h3>Creative Feedback Loop</h3><div class="kv"><span>Estado loop</span><span class="pill">${esc(st.loop_version||'0.6')}</span></div><div class="kv"><span>Creative reviews</span><span>${esc((st.counts||{}).creative_reviews??0)}</span></div><div class="kv"><span>Recomendaciones</span><span>${esc((st.counts||{}).recommended_changes??0)}</span></div><div class="kv"><span>Briefs</span><span>${esc((st.counts||{}).production_briefs??0)}</span></div><div class="kv"><span>Versiones</span><span>${esc((st.counts||{}).episode_versions??0)}</span></div><div class="kv"><span>Comparaciones</span><span>${esc((st.counts||{}).version_comparisons??0)}</span></div><div class="kv"><span>Evaluaciones V0.6</span><span>${esc((st.counts||{}).version_evaluations??0)}</span></div></div><div class="col-6 card" style="padding:12px"><h3>Capas separadas</h3><ul class="list"><li>Hechos observados.</li><li>Estimaciones heurísticas.</li><li>Preferencia humana.</li><li>Métricas comerciales por versión exacta.</li></ul><div class="hr"></div><h3>Guardrails</h3><ul class="list">${(st.guardrails||[]).map(g=>`<li>${esc(g)}</li>`).join('')}</ul><div class="hr"></div><div class="kv"><span>Entrenamiento</span><span class="pill bad">${esc(st.training_state||'NO_TRAINING_INSUFFICIENT_DATA')}</span></div></div></div>`;
}
async function runLoopReview(){
  const id=+$('hookVideo').value;if(!id)return;
  $('loopResult').textContent='Creando creative review…';
  try{const x=await api('/api/loop/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:id})});$('loopResult').textContent=JSON.stringify(x,null,2);await refreshAll();await refreshLoop()}catch(e){$('loopResult').textContent='Error: '+e.message}
}
async function runLoopExportReview(){const r=JSON.parse($('loopResult').textContent);if(!r?.result?.review?.review_key)return;$('loopResult').textContent=JSON.stringify(await api('/api/loop/review-export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({review_key:r.result.review.review_key,output_dir:$('loopExportDir').value||'reports/v06'})}),null,2)}
async function runLoopBrief(){const r=JSON.parse($('loopResult').textContent);if(!r?.result?.changes?.[0]?.change_key)return;$('loopResult').textContent=JSON.stringify(await api('/api/loop/brief',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({change_key:r.result.changes[0].change_key,target_version_label:'EP-REV-01'})}),null,2)}
async function runLoopExportBrief(){const r=JSON.parse($('loopResult').textContent);if(!r?.result?.brief_key)return;$('loopResult').textContent=JSON.stringify(await api('/api/loop/brief-export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({brief_key:r.result.brief_key,output_dir:$('loopExportDir').value||'reports/v06'})}),null,2)}
async function runLoopImport(){const body={episode:$('loopVersionEpisode').value||'EP-TEST',file_path:$('loopVersionPath').value,permission_status:$('loopVersionPermission').value||'synthetic'};if($('loopVersionParent').value)body.parent_version_key=$('loopVersionParent').value;if($('loopVersionBrief').value)body.brief_key=$('loopVersionBrief').value;$('loopResult').textContent=JSON.stringify(await api('/api/loop/version-import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),null,2;await refreshAll();await refreshLoop()}
async function runLoopCompare(){const body={a:+$('loopVersionA').value,b:+$('loopVersionB').value};if(!body.a||!body.b)return;$('loopResult').textContent=JSON.stringify(await api('/api/loop/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),null,2;await refreshAll();await refreshLoop()}

  const q=($('search').value||'').toLowerCase();
  const rows=state.videos.filter(v=>!q||(v.episode+' '+v.source_kind+' '+v.permission_status).toLowerCase().includes(q));
  if(!rows.length){$('videos').innerHTML='<p class="muted">Sin videos. Importa una copia autorizada en Producción.</p>';return}
  $('videos').innerHTML=`<table><thead><tr><th>ID</th><th>Episodio</th><th>Fuente</th><th>Permiso</th><th>Técnico</th><th>Attention</th><th>Acciones</th></tr></thead><tbody>${rows.map(v=>`<tr>
    <td>#${v.id}</td><td><b>${esc(v.episode)}</b><div class="tiny muted">${esc(v.version)}</div></td>
    <td>${pill(v.source_kind,'info')}</td><td class="tiny">${esc(v.permission_status)}</td>
    <td class="tiny">${esc(v.width)}×${esc(v.height)} · ${v.duration_s?Number(v.duration_s).toFixed(1):'—'}s</td>
    <td>${v.attention?`<b>${v.attention.overall??'—'}</b><div class="tiny muted">${esc(v.attention.confidence||'')}</div>`:pill('PENDIENTE','warn')}</td>
    <td><button class="btn" onclick="openAttention(${v.id})">Gancho</button> <button class="btn ghost" onclick="attentionFor(${v.id})">${v.attention?'Ver':'Analizar'}</button></td>
  </tr>`).join('')}</tbody></table>`;
}
function fillSelects(){
  const opts=state.videos.map(v=>`<option value="${v.id}">#${v.id} · ${esc(v.episode)} · ${esc(v.source_kind)}</option>`).join('');
  for(const id of ['hookVideo','abA','abB']){const el=$(id);const old=el.value;el.innerHTML=opts;if(old)el.value=old}
  if(state.videos.length>1&&!$('abB').value){$('abA').value=state.videos[0].id;$('abB').value=state.videos[1].id}
}
function openAttention(id){document.querySelector('#nav button[data-view="hook"]').click();$('hookVideo').value=id;loadAttention()}
async function attentionFor(id){$('hookVideo').value=id;document.querySelector('#nav button[data-view="hook"]').click();await runAttention()}

async function loadAttention(){
  const id=+$('hookVideo').value;if(!id){$('attentionPanel').textContent='Selecciona un video.';return}
  $('attentionPanel').innerHTML='<div class="card muted">Cargando análisis…</div>';
  try{const x=await api('/api/attention?id='+id);if(!x.attention){$('attentionPanel').innerHTML=`<div class="card"><p>Sin análisis de Attention Lab.</p><button class="btn primary" onclick="runAttention()">Ejecutar ahora</button></div>`;return}state.attention=x.attention;renderAttention(x.attention)}catch(e){$('attentionPanel').textContent='Error: '+e.message}
}
async function runAttention(){
  const id=+$('hookVideo').value;if(!id)return;
  $('attentionPanel').innerHTML='<div class="card muted">Analizando en CPU. FFprobe + OpenCV…</div>';
  try{const x=await api('/api/attention',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:id})});state.attention=x.attention;renderAttention(x.attention);await refreshAll()}catch(e){$('attentionPanel').textContent='Error: '+e.message}
}
function renderAttention(a){
  const f=a.facts||{},h=a.hook||{},n=a.narrative||{},p=a.production||{},c=a.commercial_value||{},o=a.overall||{};
  const maxMotion=Math.max(...(f.timeline||[]).map(x=>x.motion||0),1);
  $('attentionPanel').innerHTML=`
  <div class="grid">
    <div class="col-12 card">
      <div class="row" style="justify-content:space-between"><div><h3 style="margin:0">${esc(a.video?.episode||'')} · Attention Lab</h3><p class="small muted" style="margin:4px 0 0">${esc(a.status)} · ${esc(a.evaluated_at)} · contrato ${esc(a.contract_version)}</p></div><button class="btn ghost" onclick="downloadAttention()">Descargar JSON</button></div>
    </div>
    ${scoreCard('Índice conjunto',o.score,o.band,`<span class="tiny muted">cobertura ${pct(o.coverage)}</span>`)}
    ${scoreCard('Gancho',h.score,h.band,`<span class="tiny muted">cobertura ${pct(h.coverage)}</span>`)}
    ${scoreCard('Narrativa',n.score,n.band,`<span class="tiny muted">${esc(n.text_source?.provenance||'')}</span>`)}
    ${scoreCard('Producción',p.score,p.band,`<span class="tiny muted">cobertura ${pct(p.coverage)}</span>`)}
    ${scoreCard('Valor comercial',c.score,c.band,`<span class="tiny muted">estimación, no ventas</span>`)}
    <div class="col-7 card">
      <h3>Hechos observados</h3>
      <div class="facts">
        ${[['Cortes',f.cut_count],['Cortes <3s',f.first_3s_cut_count],['Plano medio',(f.avg_shot_s??'—')+' s'],['Casi estático',pct(f.freeze_ratio)],['Luminosidad',f.brightness_mean],['Contraste',f.contrast_mean],['Silencio',pct(f.silence_ratio)],['Bordes',f.edge_density_mean],['Audio',f.has_audio?'Sí':'No']].map(([k,v])=>`<div class="fact"><div class="k">${esc(k)}</div><div class="v">${v??'—'}</div></div>`).join('')}
      </div>
      <div class="hr"></div>
      <h3>Timeline de movimiento</h3>
      <div class="timeline">${(f.timeline||[]).map(x=>`<span style="height:${Math.max(4,Math.round((x.motion||0)/maxMotion*100))}%" title="${x.time_s}s · motion ${x.motion??'—'} · edge ${x.edge_density??'—'}"></span>`).join('')}</div>
      <div class="row tiny muted"><span>0 s</span><span style="flex:1"></span><span>${f.duration_s??'—'} s</span></div>
    </div>
    <div class="col-5 card">
      <h3>Evidencia del gancho</h3>
      <ul class="list">${(h.evidence||[]).map(x=>`<li>${esc(x)}</li>`).join('')||'<li>Sin evidencia suficiente.</li>'}</ul>
      <div class="hr"></div>
      <h3>Narrativa</h3>
      ${Object.entries(n.elements||{}).map(([k,v])=>`<div class="kv"><span>${esc(k)}</span>${pill(v.status,v.status==='NOT_AVAILABLE'?'warn':'ok')}</div>`).join('')}
      <p class="tiny muted">${esc(n.limitations?.[0]||'')}</p>
    </div>
    <div class="col-7 card">
      <h3>Recomendaciones</h3>
      ${(a.recommendations||[]).map(r=>`<div style="padding:9px 0;border-bottom:1px solid #1b2a39"><div class="row">${pill(r.priority,r.priority==='high'?'bad':'warn')}${pill(r.dimension,'info')}<b>${esc(r.action)}</b></div><div class="small muted">${esc(r.reason)}</div><div class="tiny muted">Métrica de prueba: ${esc(r.test_metric)} · ${esc(r.status)}</div></div>`).join('')}
    </div>
    <div class="col-5 card">
      <h3>Primer cambio a probar</h3>
      <p><b>${esc(a.first_change?.action||'—')}</b></p>
      <p class="small muted">${esc(a.first_change?.reason||'')}</p>
      <div class="kv"><span>Prioridad</span>${pill(a.first_change?.priority||'—',a.first_change?.priority==='high'?'bad':'warn')}</div>
      <div class="kv"><span>Métrica</span><span>${esc(a.first_change?.test_metric||'—')}</span></div>
      <div class="hr"></div>
      <h3>Resultados</h3>
      <div class="kv"><span>Estado</span>${pill(a.results?.status||'NOT_AVAILABLE',a.results?.status==='AVAILABLE_PARTIAL'?'info':'warn')}</div>
      <div class="kv"><span>Likes observados</span><span>${a.results?.likes_observed??'—'}</span></div>
      <div class="kv"><span>Leads</span><span>${a.results?.commercial_signal?.leads??'NOT_AVAILABLE'}</span></div>
      <p class="tiny muted">${esc(a.results?.commercial_signal?.note||'')}</p>
    </div>
    <div class="col-12 card">
      <h3>Evaluación humana (1–5)</h3>
      <div class="two">
        <div>
          ${[['hook','Gancho'],['narrative','Narrativa'],['production','Producción'],['commercial','Valor comercial'],['cta','CTA'],['clarity','Claridad']].map(([k,l])=>`<div class="slider"><span class="small">${l}</span><input id="ev_${k}" type="range" min="1" max="5" step="1" value="3" oninput="$('evv_${k}').textContent=this.value"><b id="evv_${k}">3</b></div>`).join('')}
          <div class="row" style="margin-top:8px"><input id="ev_evaluator" placeholder="evaluador identificado" style="flex:1"><select id="ev_provenance"><option value="human">human</option><option value="ai_assisted">ai_assisted</option></select><button class="btn good" onclick="saveEvaluation()">Guardar evaluación</button></div>
          <pre id="evResult" style="max-height:120px">Sin guardar.</pre>
        </div>
        <div><h3>Evaluaciones registradas</h3><div id="evalList" class="muted">Cargando…</div></div>
      </div>
    </div>
    <div class="col-12 card"><details><summary>Contrato completo (JSON)</summary><pre>${esc(JSON.stringify(a,null,2))}</pre></details></div>
  </div>`;
  loadEvaluations();
}
function downloadAttention(){if(state.attention)download('attention-lab.json',state.attention)}
function download(name,data){const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click()}
async function saveEvaluation(){
  const id=+$('hookVideo').value;const body={video_id:id,evaluator_id:$('ev_evaluator').value||'anonymous',provenance:$('ev_provenance').value};
  for(const k of ['hook','narrative','production','commercial','cta','clarity'])body[k]=+$('ev_'+k).value;
  try{const x=await api('/api/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});$('evResult').textContent=JSON.stringify(x,null,2);loadEvaluations();refreshAll()}catch(e){$('evResult').textContent='Error: '+e.message}
}
async function loadEvaluations(){
  if(!$('evalList'))return;try{const x=await api('/api/evaluations');$('evalList').innerHTML=x.evaluations.length?x.evaluations.map(e=>`<div class="kv"><span>#${e.id} · ${esc(e.episode)} · ${esc(e.provenance)} · ${esc(e.evaluator_id)}</span><span class="tiny">${esc(e.evaluated_at||'')}</span></div>`).join(''):'<span class="muted">Sin evaluaciones. Una evaluación AI asistida no cuenta para el gate humano.</span>'}catch(e){$('evalList').textContent=e.message}
}

async function runAB(){
  const a=+$('abA').value,b=+$('abB').value;if(!a||!b||a===b){$('abPanel').textContent='Elige dos videos distintos.';return}
  $('abPanel').innerHTML='<div class="card muted">Comparando hechos, estimaciones y evidencia disponible…</div>';
  try{const x=await api('/api/ab',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({a,b})});state.ab=x;renderAB(x)}catch(e){$('abPanel').textContent='Error: '+e.message}
}
function renderAB(x){
  const s=x.summary||{};
  $('abPanel').innerHTML=`
  <div class="grid">
    <div class="col-12"><div class="banner ${s.human_evidence?'ok':''}"><b>${esc(s.decision_status)}</b> · Ganador automático: <b>NINGUNO</b>. ${esc(s.winner_policy)}</div></div>
    <div class="col-7 card"><h3>Hechos observados</h3><table><thead><tr><th>Dimensión</th><th>A</th><th>B</th><th>Δ B−A</th><th>Lectura</th></tr></thead><tbody>${(x.observed_facts||[]).map(f=>`<tr><td>${esc(f.label)}</td><td>${f.a??'—'}</td><td>${f.b??'—'}</td><td>${f.delta_b_minus_a??'—'}</td><td class="tiny muted">${esc(f.interpretation)}</td></tr>`).join('')}</tbody></table></div>
    <div class="col-5 card"><h3>Estimaciones</h3><table><thead><tr><th>Dimensión</th><th>A</th><th>B</th><th>Δ</th></tr></thead><tbody>${(x.estimates||[]).map(f=>`<tr><td>${esc(f.label)}</td><td>${f.a_estimate??'—'}</td><td>${f.b_estimate??'—'}</td><td>${f.delta_b_minus_a??'—'}</td></tr>`).join('')}</tbody></table><p class="tiny muted">Estimaciones heurísticas; no son preferencias humanas.</p></div>
    <div class="col-6 card"><h3>Preferencias humanas</h3><div class="kv"><span>Estado</span>${pill(x.human_preferences?.status||'NOT_AVAILABLE',x.human_preferences?.status==='AVAILABLE'?'ok':'warn')}</div>${Object.entries(x.human_preferences?.a?.dimension_means_1_to_5||{}).map(([k,v])=>`<div class="kv"><span>A · ${esc(k)}</span><span>${v}/5</span></div>`).join('')}${Object.entries(x.human_preferences?.b?.dimension_means_1_to_5||{}).map(([k,v])=>`<div class="kv"><span>B · ${esc(k)}</span><span>${v}/5</span></div>`).join('')}<p class="tiny muted">${esc(x.human_preferences?.note||'')}</p></div>
    <div class="col-6 card"><h3>Resultados comerciales</h3><div class="kv"><span>Estado</span>${pill(x.commercial_results?.status||'NOT_COMPARABLE',x.commercial_results?.status==='COMPARABLE'?'ok':'warn')}</div><p class="small muted">${esc(x.commercial_results?.reason||'')}</p><div class="kv"><span>A · likes</span><span>${x.commercial_results?.a?.likes_observed??'—'}</span></div><div class="kv"><span>B · likes</span><span>${x.commercial_results?.b?.likes_observed??'—'}</span></div><p class="tiny muted">Likes ≠ ventas. La capa comercial sólo es comparable con leads/reuniones/ventas verificables en ambos lados.</p></div>
    <div class="col-12 card"><h3>Recomendaciones</h3>${(x.recommendations||[]).map(r=>`<div class="kv"><span>${esc(r.action)}</span>${pill(r.priority,r.priority==='high'?'bad':'warn')}</div>`).join('')}</div>
    <div class="col-12 card"><details><summary>Contrato completo (JSON)</summary><pre>${esc(JSON.stringify(x,null,2))}</pre></details></div>
  </div>`;
}
function downloadAB(){if(state.ab)download('ab-comparison.json',state.ab)}

async function refreshLearning(){try{const x=await api('/api/learning');state.learning=x;renderLearning();renderLearningMini()}catch(e){$('learningPanel').textContent='Error: '+e.message}}
function renderLearning(){
  const g=state.learning.gate||{};
  $('learningPanel').innerHTML=`<div class="banner ${g.status==='ELIGIBLE'?'ok':'bad'}"><b>${esc(g.training_state||'NO_TRAINING_INSUFFICIENT_DATA')}</b> · Gate: ${esc(g.status||'BLOCKED')} · ${esc(g.policy||'')}</div>
  <table><thead><tr><th>Requisito</th><th>Actual</th><th>Mínimo</th><th>Estado</th></tr></thead><tbody>${(g.checks||[]).map(c=>`<tr><td>${esc(c.label)}<div class="tiny muted">${esc(c.note)}</div></td><td><b>${c.have}</b></td><td>${c.required}</td><td>${pill(c.ok?'PASS':'BLOCKED',c.ok?'ok':'bad')}</td></tr>`).join('')}</tbody></table>
  <div class="hr"></div><div class="two"><div><h3>Bloqueos</h3>${(g.blocking_reasons||[]).length?`<ul class="list">${g.blocking_reasons.map(r=>`<li>${esc(r.message)}</li>`).join('')}</ul>`:'<p class="muted">Ninguno.</p>'}</div><div><h3>Advertencias</h3>${(g.warnings||[]).length?`<ul class="list">${g.warnings.map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`:'<p class="muted">Ninguna.</p>'}</div></div>`;
}
function renderLearningMini(){
  const g=state.learning.gate||{};if(!$('learningMini'))return;
  $('learningMini').innerHTML=`<div class="row" style="justify-content:space-between"><span class="pill bad">${esc(g.training_state||'NO_TRAINING_INSUFFICIENT_DATA')}</span><span class="tiny muted">${g.counts?.eligible_videos??0} videos · ${g.counts?.human_evaluations??0} evaluaciones humanas</span></div>
  <div style="margin-top:10px">${(g.checks||[]).slice(0,4).map(c=>`<div class="kv"><span>${esc(c.label)}</span><span class="tiny">${c.have}/${c.required}</span></div>`).join('')}</div>
  <button class="btn ghost" style="margin-top:10px" onclick="document.querySelector('#nav button[data-view=learning]').click()">Ver gate completo</button>`;
  $('modelsPanel').innerHTML=(state.learning.models||[]).length?`<table><thead><tr><th>Modelo</th><th>Estado</th><th>Holdout</th><th>Baseline</th></tr></thead><tbody>${state.learning.models.map(m=>`<tr><td>${esc(m.model_version)}</td><td>${pill(m.approval_status,m.approval_status==='active'?'ok':'warn')}</td><td>${m.metrics?.accuracy??'—'}</td><td>${m.metrics?.baseline_accuracy??'—'}</td></tr>`).join('')}</tbody></table>`:'<p class="muted">No hay modelos. Esto es intencional: el gate está bloqueado.</p>';
}
async function registerDataset(){try{const x=await api('/api/dataset-register',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});$('registryPanel').innerHTML=`<div class="kv"><span>Dataset</span><span class="tiny">${esc(x.dataset_key)}</span></div><div class="kv"><span>Estado</span>${pill(x.status,x.status==='REGISTERED_ELIGIBLE'?'ok':'warn')}</div><div class="kv"><span>Videos</span><span>${x.counts.videos}</span></div><div class="kv"><span>Evaluaciones</span><span>${x.counts.evaluations}</span></div><div class="kv"><span>Comerciales</span><span>${x.counts.commercial_records}</span></div>`}catch(e){$('registryPanel').textContent='Error: '+e.message}}

function renderPublications(){
  const pubs=state.publications;
  $('publications').innerHTML=pubs.length?pubs.map(p=>`<div style="margin-bottom:14px"><div class="row" style="justify-content:space-between"><b>${esc(p.episode)} · ${esc(p.platform)}</b>${pill(p.provenance,'info')}</div><table><thead><tr><th>Etapa</th><th>Métrica</th><th>Valor</th><th>Estado</th></tr></thead><tbody>${Object.entries(p.funnel?.stages||{}).flatMap(([stage,metrics])=>Object.entries(metrics).map(([name,m])=>`<tr><td>${esc(stage)}</td><td>${esc(name)}</td><td>${m.value??'—'}</td><td>${pill(m.status,m.status==='OBSERVED'?'ok':'warn')}</td></tr>`)).join('')}</tbody></table><p class="tiny muted">${esc(p.funnel?.guardrails?.join(' '))}</p></div>`).join(''):'<p class="muted">Sin publicaciones registradas.</p>';
  if($('proposals'))api('/api/proposals').then(x=>{$('proposals').innerHTML=x.proposals.length?x.proposals.map(p=>`<div class="kv"><span>#${p.id} · ${esc(p.episode)} · ${esc(p.title)}</span>${pill(p.contract_version,'info')}</div>`).join(''):'<p class="muted">Sin propuestas. Usa Creative Director o el CLI.</p>'}).catch(()=>{});
}
async function recommendBrief(){try{const b=JSON.parse($('brief').value);$('creativeResult').textContent=JSON.stringify(await api('/api/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}),null,2)}catch(e){$('creativeResult').textContent='Error: '+e.message}}
function downloadBrief(){const blob=new Blob([$('creativeResult').textContent],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='creative_director.json';a.click()}

async function planProduction(){
  try{const brief=JSON.parse($('prodBrief').value);const x=await api('/api/production/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({brief,adapter:$('prodAdapter').value})});$('prodResult').textContent=JSON.stringify(x,null,2);refreshProduction()}catch(e){$('prodResult').textContent='Error: '+e.message}
}
async function refreshProduction(){try{const x=await api('/api/production');renderVersions(x)}catch(e){$('versions').textContent=e.message}}
function renderVersions(x){
  const rows=x.versions||[];
  if(!$('versions'))return;
  $('versions').innerHTML=rows.length?`<table><thead><tr><th>Versión</th><th>Adapter</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>${rows.map(v=>`<tr><td class="tiny">${esc(v.version_key)}</td><td>${esc(v.adapter)}</td><td>${pill(v.status,v.status==='active'?'ok':v.status==='failed'?'bad':'warn')}</td><td><button class="btn ghost" onclick="renderProd('${esc(v.version_key)}')">Render</button> <button class="btn ghost" onclick="activateProd('${esc(v.version_key)}')">Activar</button> <button class="btn ghost" onclick="rollbackProd('${esc(v.version_key)}')">Rollback</button></td></tr>`).join('')}</tbody></table><p class="tiny muted">${esc((x.summary?.guardrails||[]).join(' '))}</p>`:'<p class="muted">Sin versiones de producción.</p>';
}
async function renderProd(k){try{const x=await api('/api/production/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({version_key:k})});$('prodResult').textContent=JSON.stringify(x,null,2);refreshProduction()}catch(e){$('prodResult').textContent='Error: '+e.message}}
async function activateProd(k){try{const x=await api('/api/production/activate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({version_key:k})});$('prodResult').textContent=JSON.stringify(x,null,2);refreshProduction()}catch(e){$('prodResult').textContent='Error: '+e.message}}
async function rollbackProd(k){try{const x=await api('/api/production/rollback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({version_key:k})});$('prodResult').textContent=JSON.stringify(x,null,2);refreshProduction()}catch(e){$('prodResult').textContent='Error: '+e.message}}

async function upload(){
  const f=$('file').files[0];if(!f){$('importResult').textContent='Selecciona un video.';return}
  $('importResult').textContent='Copiando y validando…';
  try{const q=new URLSearchParams({episode:$('episode').value||'UNKNOWN',source_kind:$('kind').value||'review',permission:$('permission').value||'unknown'});const x=await api('/api/upload?'+q,{method:'POST',headers:{'X-Filename':f.name,'Content-Length':f.size},body:f});$('importResult').textContent=JSON.stringify(x,null,2);refreshAll()}catch(e){$('importResult').textContent='Error: '+e.message}
}

refreshAll();
</script>
</body></html>"""


def serve(db, host, port):
    db_path = str(db)
    data_dir = Path(db_path).resolve().parent
    copy_dir = data_dir / "review"
    production_dir = data_dir / "production"
    copy_dir.mkdir(parents=True, exist_ok=True)
    production_dir.mkdir(parents=True, exist_ok=True)

    class H(BaseHTTPRequestHandler):
        def send_json(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def body_json(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length > 2 * 1024 * 1024:
                raise ValueError("json_payload_too_large")
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            return json.loads(raw or "{}")

        def _publication_rows(self, con):
            rows = []
            for row in con.execute("select * from publications order by id desc"):
                item = dict(row)
                item["funnel"] = funnel(con, row["id"])
                rows.append(item)
            return rows

        def do_GET(self):
            with closing(connect(db_path)) as con:
                self._handle_get(con)

        def _handle_get(self, con):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/api/summary":
                gate = gate_report(con)
                self.send_json({
                    "schema_version": con.execute("select value from schema_meta where key='schema_version'").fetchone()[0],
                    "videos": con.execute("select count(*) from videos").fetchone()[0],
                    "analyzed": con.execute("select count(distinct video_id) from analyses").fetchone()[0],
                    "observations": con.execute("select count(*) from observations").fetchone()[0],
                    "attention_analyses": con.execute("select count(*) from attention_analyses").fetchone()[0],
                    "attention_videos": con.execute("select count(distinct video_id) from attention_analyses").fetchone()[0],
                    "feedback": con.execute("select count(*) from feedback").fetchone()[0],
                    "video_evaluations": con.execute("select count(*) from video_evaluations").fetchone()[0],
                    "human_evaluations": gate["counts"]["human_evaluations"],
                    "ab_comparisons": con.execute("select count(*) from ab_comparisons").fetchone()[0],
                    "metrics": con.execute("select count(*) from metrics").fetchone()[0],
                    "publications": con.execute("select count(*) from publications").fetchone()[0],
                    "platform_metrics": con.execute("select count(*) from platform_metrics").fetchone()[0],
                    "commercial_records": gate["counts"]["commercial_records"],
                    "creative_proposals": con.execute("select count(*) from creative_proposals").fetchone()[0],
                    "production_versions": con.execute("select count(*) from production_versions").fetchone()[0],
                    "creative_reviews": con.execute("select count(*) from creative_reviews").fetchone()[0],
                    "episode_versions": con.execute("select count(*) from episode_versions").fetchone()[0],
                    "performance_records": con.execute("select count(*) from performance_records").fetchone()[0],
                    "version_comparisons": con.execute("select count(*) from version_comparisons").fetchone()[0],
                    "loop": loop_status(con),
                    "models": con.execute("select count(*) from models").fetchone()[0],
                    "training_state": gate["training_state"],
                    "gate_status": gate["status"],
                })
            elif parsed.path == "/api/videos":
                videos = []
                for row in con.execute(
                    "select id,episode,version,file_path,source_kind,permission_status,campaign,duration_s,width,height from videos order by id desc"
                ):
                    item = dict(row)
                    attention = con.execute(
                        "select overall_json,created_at from attention_analyses where video_id=? order by id desc limit 1",
                        (row["id"],),
                    ).fetchone()
                    item["attention"] = None
                    if attention:
                        overall = json.loads(attention["overall_json"])
                        item["attention"] = {
                            "overall": overall.get("score"), "band": overall.get("band"),
                            "confidence": overall.get("confidence"), "created_at": attention["created_at"],
                        }
                    videos.append(item)
                self.send_json({"videos": videos})
            elif parsed.path == "/api/analysis":
                video_id = int(query.get("id", ["0"])[0])
                row = con.execute("select * from analyses where video_id=? order by id desc limit 1", (video_id,)).fetchone()
                obs = [dict(r) for r in con.execute("select * from observations where video_id=? order by start_s", (video_id,))]
                self.send_json({"analysis": dict(row) if row else None, "observations": obs})
            elif parsed.path == "/api/attention":
                video_id = int(query.get("id", ["0"])[0])
                payload = latest_attention(con, video_id)
                self.send_json({"attention": payload, "summary": attention_summary(payload) if payload else None})
            elif parsed.path == "/api/evaluations":
                video_id = query.get("video_id", [None])[0]
                self.send_json({"evaluations": list_evaluations(con, int(video_id) if video_id else None)})
            elif parsed.path == "/api/publications":
                self.send_json({"publications": self._publication_rows(con)})
            elif parsed.path == "/api/proposals":
                self.send_json({"proposals": [dict(r) for r in con.execute("select id,episode,proposal_key,title,contract_version from creative_proposals order by id")]})
            elif parsed.path == "/api/learning":
                self.send_json({
                    "status": training_status(con),
                    "gate": gate_report(con),
                    "models": list_models(con),
                    "experiments": list_experiments(con)[:10],
                })
            elif parsed.path == "/api/recommendations":
                latest = con.execute(
                    "select video_id,created_at from attention_analyses order by id desc limit 1"
                ).fetchone()
                if not latest:
                    self.send_json({"episode": None, "recommendations": [], "first_change": None})
                else:
                    payload = latest_attention(con, latest["video_id"]) or {}
                    video_row = con.execute(
                        "select episode from videos where id=?", (latest["video_id"],)
                    ).fetchone()
                    self.send_json({
                        "episode": video_row["episode"] if video_row else None,
                        "evaluated_at": latest["created_at"],
                        "overall": payload.get("overall", {}),
                        "first_change": payload.get("first_change"),
                        "recommendations": (payload.get("recommendations") or [])[:4],
                    })
            elif parsed.path == "/api/production":
                self.send_json({"versions": list_versions(con), "summary": production_summary(con)})
            elif parsed.path == "/api/loop/status":
                self.send_json(loop_status(con))
            elif parsed.path == "/api/loop/review":
                result = create_review(con, int(query.get("video_id", ["0"])[0]))
                self.send_json({"status": "REVIEW_CREATED", "result": result})
            elif parsed.path == "/api/loop/reviews":
                result = list_version_evaluations(con)
                self.send_json({"evaluations": result})
            elif parsed.path == "/api/loop/export-review":
                data = self.body_json()
                self.send_json(export_review_bundle(con, data["review_key"], data["output_dir"]))
            elif parsed.path == "/api/loop/brief":
                data = self.body_json()
                self.send_json(create_production_brief(con, data["change_key"], data.get("target_version_label")))
            elif parsed.path == "/api/loop/brief-export":
                data = self.body_json()
                self.send_json(export_production_brief(con, data["brief_key"], data["output_dir"]))
            elif parsed.path == "/api/loop/version-import":
                data = self.body_json()
                result = import_episode_version(
                    con, data["episode"], data["file_path"], data["permission_status"],
                    parent_version_key=data.get("parent_version_key"),
                    brief_key=data.get("brief_key"),
                    source_video_id=data.get("source_video_id"),
                    version_label=data.get("version_label"),
                    allowed_roots=data.get("allowed_roots") or [Path("data")],
                )
                self.send_json({"status": "VERSION_IMPORTED", "result": result})
            elif parsed.path == "/api/loop/version-evaluate":
                data = self.body_json()
                result = record_version_evaluation(
                    con, data["version_key"], data.get("evaluator_id", "anonymous"),
                    visual_impact=data.get("visual_impact"), realism=data.get("realism"),
                    clarity=data.get("clarity"), hook=data.get("hook"), narrative=data.get("narrative"),
                    business_value=data.get("business_value"), cta=data.get("cta"),
                    preference=data.get("preference"), compared_version_key=data.get("compared_version_key"),
                    confidence=data.get("confidence"), notes=data.get("notes", ""),
                    provenance=data.get("provenance", "human"), evaluated_at=data.get("evaluated_at"),
                )
                self.send_json({"status": "EVALUATION_RECORDED", "result": result})
            elif parsed.path == "/api/loop/approval":
                data = self.body_json()
                self.send_json(record_human_approval(
                    con, data["subject_type"], data["subject_key"], data["decision"],
                    data.get("evaluator_id", "anonymous"), data.get("notes", ""),
                ))
            elif parsed.path == "/api/loop/performance":
                data = self.body_json()
                result = record_performance(
                    con, data["version_key"], data["platform"], data.get("measured_at"), data["metrics"],
                    campaign=data.get("campaign"), published_at=data.get("published_at"),
                    hook_used=data.get("hook_used"), cta_used=data.get("cta_used"),
                    provenance=data.get("provenance", "USER_PROVIDED"), notes=data.get("notes", ""),
                )
                self.send_json({"status": "PERFORMANCE_RECORDED", "result": result})
            elif parsed.path == "/api/loop/compare":
                data = self.body_json()
                self.send_json(compare_episode_versions(con, data["a"], data["b"], data.get("platform")))
            else:
                body = _page().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def do_POST(self):
            with closing(connect(db_path)) as con:
                self._handle_post(con)

        def _handle_post(self, con):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
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
                    h = sha256_file(target)
                    if con.execute("select id from videos where file_hash=?", (h,)).fetchone():
                        target.unlink(missing_ok=True)
                        self.send_json({"status": "DUPLICATE"}, 409)
                        return
                    con.execute(
                        "insert into videos(episode,version,file_path,file_hash,duration_s,fps,width,height,campaign,"
                        "approval_status,permission_status,source_kind,source_type,provenance) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (query.get("episode", ["UNKNOWN"])[0], "v0.5", str(target), h, meta["duration_s"],
                         meta["fps"], meta["width"], meta["height"], query.get("campaign", [None])[0],
                         "unknown", query.get("permission", ["unknown"])[0],
                         query.get("source_kind", ["review"])[0], "dashboard-upload", "copied_by_vlux_ci_dashboard"),
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
                                (row["id"], ANALYZER_VERSION, json_dumps(objective), json_dumps(estimated)))
                    for item in observations:
                        con.execute("insert into observations(video_id,start_s,end_s,severity,category,message,recommendation,evidence_json) values(?,?,?,?,?,?,?,?)",
                                    (row["id"], item["start_s"], item["end_s"], item["severity"], item["category"], item["message"], item["recommendation"], json_dumps(objective)))
                    con.commit()
                    self.send_json({"status": "ANALYZED", "video_id": row["id"], "objective": objective, "estimated": estimated, "observations": observations})
                elif parsed.path in ("/api/attention", "/api/analyze-attention"):
                    data = self.body_json()
                    result = analyze_attention(con, int(data["video_id"]))
                    self.send_json({"status": "ATTENTION_ANALYZED", "attention": result, "summary": attention_summary(result)})
                elif parsed.path == "/api/ab":
                    data = self.body_json()
                    result = ab_compare(con, int(data["a"]), int(data["b"]))
                    self.send_json(result)
                elif parsed.path == "/api/evaluate":
                    data = self.body_json()
                    evaluation_id = record_evaluation(
                        con, int(data["video_id"]), data.get("evaluator_id", "anonymous"),
                        data.get("provenance", "human"), data.get("hook"), data.get("narrative"),
                        data.get("production"), data.get("commercial"), data.get("cta"),
                        data.get("clarity"), data.get("confidence"), data.get("notes", ""),
                        data.get("evaluated_at"),
                    )
                    self.send_json({"status": "EVALUATION_RECORDED", "evaluation_id": evaluation_id,
                                    "gate": gate_report(con)["counts"]})
                elif parsed.path == "/api/feedback":
                    data = self.body_json()
                    con.execute(
                        "insert into feedback(variant_a_id,variant_b_id,winner,criterion,comparison_type,confidence,observations,evaluator_id,origin,provenance,evaluated_at) values(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                        (int(data["a"]), int(data["b"]), data["winner"], data.get("criterion", "full_video"),
                         "dashboard", data.get("confidence"), data.get("observations", ""),
                         data.get("evaluator", "anonymous"), data.get("origin", "human"),
                         data.get("provenance", data.get("origin", "human"))),
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
                elif parsed.path == "/api/dataset-register":
                    self.send_json(dataset_registry(con))
                elif parsed.path == "/api/production/plan":
                    data = self.body_json()
                    result = plan_version(con, data["brief"], data.get("adapter", "manifest"),
                                          data.get("video_id"), data.get("parent_version_id"))
                    self.send_json(result)
                elif parsed.path == "/api/production/render":
                    data = self.body_json()
                    self.send_json(render_version(con, data["version_key"], production_dir))
                elif parsed.path == "/api/production/activate":
                    data = self.body_json()
                    self.send_json(activate_version(con, data["version_key"]))
                elif parsed.path == "/api/loop/status":
                    self.send_json(loop_status(con))
                elif parsed.path == "/api/loop/review":
                    result = create_review(con, int(self.body_json()["video_id"]))
                    self.send_json({"status": "REVIEW_CREATED", "result": result})
                elif parsed.path == "/api/loop/review-export":
                    data = self.body_json()
                    self.send_json(export_review_bundle(con, data["review_key"], data["output_dir"]))
                elif parsed.path == "/api/loop/brief":
                    data = self.body_json()
                    self.send_json(create_production_brief(con, data["change_key"], data.get("target_version_label")))
                elif parsed.path == "/api/loop/brief-export":
                    data = self.body_json()
                    self.send_json(export_production_brief(con, data["brief_key"], data["output_dir"]))
                elif parsed.path == "/api/loop/version-import":
                    data = self.body_json()
                    result = import_episode_version(
                        con, data["episode"], data["file_path"], data["permission_status"],
                        parent_version_key=data.get("parent_version_key"),
                        brief_key=data.get("brief_key"),
                        source_video_id=data.get("source_video_id"),
                        version_label=data.get("version_label"),
                        allowed_roots=data.get("allowed_roots") or [Path("data")],
                    )
                    self.send_json({"status": "VERSION_IMPORTED", "result": result})
                elif parsed.path == "/api/loop/version-evaluate":
                    data = self.body_json()
                    result = record_version_evaluation(
                        con, data["version_key"], data.get("evaluator_id", "anonymous"),
                        visual_impact=data.get("visual_impact"), realism=data.get("realism"),
                        clarity=data.get("clarity"), hook=data.get("hook"), narrative=data.get("narrative"),
                        business_value=data.get("business_value"), cta=data.get("cta"),
                        preference=data.get("preference"), compared_version_key=data.get("compared_version_key"),
                        confidence=data.get("confidence"), notes=data.get("notes", ""),
                        provenance=data.get("provenance", "human"), evaluated_at=data.get("evaluated_at"),
                    )
                    self.send_json({"status": "EVALUATION_RECORDED", "result": result})
                elif parsed.path == "/api/loop/approval":
                    data = self.body_json()
                    self.send_json(record_human_approval(
                        con, data["subject_type"], data["subject_key"], data["decision"],
                        data.get("evaluator_id", "anonymous"), data.get("notes", ""),
                    ))
                elif parsed.path == "/api/loop/performance":
                    data = self.body_json()
                    result = record_performance(
                        con, data["version_key"], data["platform"], data.get("measured_at"), data["metrics"],
                        campaign=data.get("campaign"), published_at=data.get("published_at"),
                        hook_used=data.get("hook_used"), cta_used=data.get("cta_used"),
                        provenance=data.get("provenance", "USER_PROVIDED"), notes=data.get("notes", ""),
                    )
                    self.send_json({"status": "PERFORMANCE_RECORDED", "result": result})
                elif parsed.path == "/api/loop/compare":
                    data = self.body_json()
                    self.send_json(compare_episode_versions(con, data["a"], data["b"], data.get("platform")))
                else:
                    self.send_json({"error": "not_found"}, 404)
            except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, 400)

        def log_message(self, *_args):
            pass

    print(f"http://{host}:{port}")
    ThreadingHTTPServer((host, port), H).serve_forever()
