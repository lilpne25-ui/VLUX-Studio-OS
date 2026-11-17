from __future__ import annotations
import argparse, csv, json, shutil, subprocess, sys, webbrowser
from pathlib import Path
from .db import connect, sha256_file, json_dumps
from .probe import probe
from .analyzer import analyze
from .ml import Baseline, load_rows, train, infer
from .creative import recommend, CONTRACT_VERSION
from .commercial import summarize
from .funnel import funnel
from .proposals import ep025_proposals, payload, CONTRACT_VERSION as PROPOSAL_CONTRACT_VERSION
from .attention import ANALYZER_VERSION, analyze_attention, latest_attention
from .ab import compare as ab_compare, record_evaluation, list_evaluations
from .learning import (
    dataset_registry, evaluation_report, gate_report, list_experiments, list_models,
    promote_model, rollback_model, run_gated_training, training_status,
)
from .production import (
    activate_version, history as production_history, list_versions, plan_version,
    render_version, rollback_version, summary as production_summary,
)
from .creative_loop import (
    CONTRACT_CREATIVE_REVIEW, CONTRACT_EPISODE_VERSION, CONTRACT_HUMAN_APPROVAL,
    CONTRACT_HUMAN_EVALUATION, CONTRACT_PERFORMANCE_COMPARISON, CONTRACT_PERFORMANCE_RECORD,
    CONTRACT_PRODUCTION_BRIEF, CONTRACT_RECOMMENDED_CHANGES, CONTRACT_VISUAL_DEFECTS,
    activate_episode_version, compare_episode_versions, create_production_brief,
    create_review, export_production_brief, export_review_bundle, get_episode_version,
    import_episode_version, import_version_contract, list_version_evaluations,
    loop_status, record_human_approval, record_performance, record_version_evaluation,
    recommended_changes_contract, rollback_episode_version, verify_version_integrity,
    visual_defects_contract,
)

def dbpath(args): return args.db or str(Path("data")/"vlux.sqlite")
def cmd_import(a):
    con=connect(dbpath(a)); path=Path(a.file).resolve(); meta=probe(path); h=sha256_file(path)
    old=con.execute("SELECT id FROM videos WHERE file_hash=?",(h,)).fetchone()
    if old: print(json.dumps({"status":"DUPLICATE","video_id":old[0]})); return 2
    con.execute("INSERT INTO videos(episode,version,file_path,file_hash,duration_s,fps,width,height,campaign,platform,topic,target_audience,business_problem,solution_presented,publication_status,creative_version,provenance,approval_status,permission_status,source_kind,source_type) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(a.episode,a.version,str(path),h,meta["duration_s"],meta["fps"],meta["width"],meta["height"],a.campaign,a.platform,a.topic,a.audience,a.problem,a.solution,a.publication_status,a.version,a.provenance,a.approval,a.permission,a.source_kind,"local")); con.commit(); print(json.dumps({"status":"IMPORTED","video_id":con.execute("SELECT last_insert_rowid()").fetchone()[0],"probe":meta},indent=2)); return 0
def cmd_import_metadata(a):
    source=Path(a.file)
    if source.suffix.lower()==".csv":
        with source.open(newline="",encoding="utf-8-sig") as f: rows=list(csv.DictReader(f))
    else:
        rows=json.loads(source.read_text(encoding="utf-8"))
        if isinstance(rows,dict): rows=rows.get("videos",[])
    con=connect(dbpath(a)); imported=0; rejected=[]
    for i,row in enumerate(rows):
        raw_path = row.get("file") or row.get("file_path","")
        path=Path(raw_path).expanduser()
        if not path.is_absolute(): path = (source.parent / path).resolve()
        if not path.exists(): rejected.append({"row":i,"reason":"file_missing"}); continue
        try: meta=probe(path); h=sha256_file(path)
        except ValueError as e: rejected.append({"row":i,"reason":str(e)}); continue
        if con.execute("select 1 from videos where file_hash=?",(h,)).fetchone(): rejected.append({"row":i,"reason":"duplicate"}); continue
        con.execute("insert into videos(episode,version,file_path,file_hash,duration_s,fps,width,height,hook,cta,category,visual_style,narration_type,asset_origin,approval_status,permission_status,source_kind,source_type) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(row.get("episode","UNKNOWN"),row.get("version","v0.1"),str(path),h,meta["duration_s"],meta["fps"],meta["width"],meta["height"],row.get("hook"),row.get("cta"),row.get("category"),row.get("visual_style"),row.get("narration_type"),row.get("asset_origin"),row.get("approval_status","unknown"),row.get("permission_status","unknown"),row.get("source_kind","unknown"),"metadata-import")); imported+=1
    con.commit(); print(json.dumps({"status":"IMPORTED_METADATA","imported":imported,"rejected":rejected},indent=2)); return 0
def cmd_analyze(a):
    con=connect(dbpath(a)); row=con.execute("SELECT * FROM videos WHERE id=?",(a.video_id,)).fetchone();
    if not row: raise SystemExit("video_not_found")
    obj,est,observations=analyze(row["file_path"]); con.execute("INSERT INTO analyses(video_id,analyzer_version,objective_json,aesthetic_json) VALUES(?,?,?,?)",(a.video_id,ANALYZER_VERSION,json_dumps(obj),json_dumps(est)))
    for item in observations:
        con.execute("INSERT INTO observations(video_id,start_s,end_s,severity,category,message,recommendation,evidence_json) VALUES(?,?,?,?,?,?,?,?)",(a.video_id,item["start_s"],item["end_s"],item["severity"],item["category"],item["message"],item["recommendation"],json_dumps(obj)))
    con.commit(); print(json.dumps({"objective":obj,"estimated":est,"observations":observations},indent=2)); return 0
def cmd_feedback(a):
    con=connect(dbpath(a)); con.execute("INSERT INTO feedback(variant_a_id,variant_b_id,winner,clarity,lighting,composition,realism,movement,commercial_quality,retention,visual_impact,credibility,business_value,commercial_potential,criterion,comparison_type,confidence,observations,evaluator_id,origin) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(a.a,a.b,a.winner,a.clarity,a.lighting,a.composition,a.realism,a.movement,a.commercial_quality,a.retention,a.visual_impact,a.credibility,a.business_value,a.commercial_potential,a.criterion,a.comparison_type,a.confidence,a.observations,a.evaluator,a.origin)); con.commit(); print("FEEDBACK_RECORDED"); return 0
def cmd_metric(a):
    con=connect(dbpath(a)); con.execute("INSERT INTO metrics(video_id,metric_name,metric_value,source,observed_at,notes) VALUES(?,?,?,?,?,?)",(a.video_id,a.name,a.value,a.source,a.observed_at,a.notes)); con.commit(); print("METRIC_RECORDED"); return 0
def cmd_dataset_status(a):
    con=connect(dbpath(a)); rows=[dict(r) for r in con.execute("SELECT source_kind,COUNT(*) AS count FROM videos GROUP BY source_kind")]
    missing=[dict(r) for r in con.execute("SELECT metric_name,COUNT(*) AS records FROM metrics GROUP BY metric_name")]
    gate=gate_report(con)
    print(json.dumps({"schema_version":con.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0],"source_kinds":rows,"metrics_present":missing,"unknown_metrics_remain_unknown":True,"training_state":gate["training_state"],"gate_status":gate["status"],"gate_counts":gate["counts"],"blocking_reasons":gate["blocking_reasons"]},indent=2)); return 0
def cmd_recommend(a):
    brief=json.loads(Path(a.brief).read_text(encoding="utf-8")); con=connect(dbpath(a)); result=recommend(brief,con)
    text=json.dumps(result,indent=2,ensure_ascii=False); print(text)
    if a.output: Path(a.output).write_text(text,encoding="utf-8")
    return 0
def cmd_commercial_insights(a):
    con=connect(dbpath(a)); result=summarize(con); text=json.dumps(result,indent=2,ensure_ascii=False); print(text)
    if a.output: Path(a.output).write_text(text,encoding="utf-8")
    return 0
def cmd_export_bundle(a):
    con=connect(dbpath(a)); brief=json.loads(Path(a.brief).read_text(encoding="utf-8")); result=recommend(brief,con)
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    (out/"creative_director.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    video_brief={"contract_version":"video-brief.v0.3","status":"PROPOSAL_ONLY","episode":brief.get("episode"),"scenes":result["visual_structure"],"hooks":result["hooks"],"cta":result["cta_primary"],"measure":result["evaluation_indicators"]}
    qa={"contract_version":"qa-recommendations.v0.3","status":"REVIEW_REQUIRED","risks":result["retention_risks"],"observations":[],"evidence":result["evidence"]}
    (out/"video_brief.json").write_text(json.dumps(video_brief,indent=2,ensure_ascii=False),encoding="utf-8")
    (out/"qa_recommendations.json").write_text(json.dumps(qa,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"status":"EXPORTED_BUNDLE","output_dir":str(out),"files":["creative_director.json","video_brief.json","qa_recommendations.json"]},indent=2)); return 0
def cmd_publication(a):
    con=connect(dbpath(a))
    con.execute("insert into publications(video_id,episode,campaign,platform,publication_ref,published_at,measured_at,publication_status,provenance,notes) values(?,?,?,?,?,?,?,?,?,?)",
                (a.video_id,a.episode,a.campaign,a.platform,a.publication_ref,a.published_at,a.measured_at,a.status,a.provenance,a.notes))
    con.commit(); print(json.dumps({"status":"PUBLICATION_RECORDED","publication_id":con.execute("select last_insert_rowid()").fetchone()[0]},indent=2)); return 0
def cmd_platform_metric(a):
    con=connect(dbpath(a))
    con.execute("insert or replace into platform_metrics(publication_id,metric_name,metric_value,status,provenance,measured_at,notes) values(?,?,?,?,?,?,?)",
                (a.publication_id,a.name,a.value,a.status,a.provenance,a.measured_at,a.notes))
    con.commit(); print("PLATFORM_METRIC_RECORDED"); return 0
def cmd_funnel(a):
    con=connect(dbpath(a)); print(json.dumps(funnel(con,a.publication_id),indent=2,ensure_ascii=False)); return 0
def cmd_seed_proposals(a):
    con=connect(dbpath(a)); output=[]
    for item in ep025_proposals():
        con.execute("insert into creative_proposals(episode,proposal_key,title,payload_json,contract_version) values(?,?,?,?,?) on conflict(episode,proposal_key) do update set title=excluded.title,payload_json=excluded.payload_json,contract_version=excluded.contract_version",
                    ("EP025",item["proposal_key"],item["title"],payload(item),PROPOSAL_CONTRACT_VERSION))
        output.append(dict(con.execute("select id,episode,proposal_key,title,contract_version from creative_proposals where episode='EP025' and proposal_key=?",(item["proposal_key"],)).fetchone()))
    con.commit(); print(json.dumps({"status":"PROPOSALS_REGISTERED","proposals":output},indent=2,ensure_ascii=False)); return 0
def cmd_proposals(a):
    con=connect(dbpath(a)); print(json.dumps([dict(r) for r in con.execute("select id,episode,proposal_key,title,contract_version from creative_proposals order by id")],indent=2,ensure_ascii=False)); return 0
def cmd_proposal_feedback(a):
    con=connect(dbpath(a)); con.execute("insert into proposal_feedback(proposal_a_id,proposal_b_id,winner,clarity,impact,credibility,retention_potential,commercial_potential,confidence,observations,evaluator_id) values(?,?,?,?,?,?,?,?,?,?,?)",
                (a.a,a.b,a.winner,a.clarity,a.impact,a.credibility,a.retention,a.commercial,a.confidence,a.observations,a.evaluator))
    con.commit(); print("PROPOSAL_FEEDBACK_RECORDED"); return 0
def cmd_baseline(a):
    con=connect(dbpath(a)); out=[]
    for r in load_rows(con): out.append({"video_id":r["id"],"episode":r["episode"],"score":Baseline().score(r)})
    print(json.dumps({"model":"rules-v0.1","results":out},indent=2)); return 0
def cmd_train(a):
    con=connect(dbpath(a)); result=train(con,a.artifacts,a.seed,a.min_examples); print(json.dumps(result,indent=2));
    if result.get("status")=="TRAINED": con.execute("INSERT OR REPLACE INTO models(model_version,model_type,dataset_hash,parameters_json,metrics_json,artifact_path,artifact_hash,baseline_metrics_json,approval_status) VALUES(?,?,?,?,?,?,?,?,?)",(f"candidate-{result['dataset_hash'][:12]}","logistic_numpy",result["dataset_hash"],json_dumps({"seed":a.seed}),json_dumps(result),result["artifact_path"],result["artifact_hash"],json_dumps({"accuracy":result["baseline_accuracy"]}),"candidate")); con.commit()
    return 0
def dashboard(a):
    from .dashboard import serve; serve(dbpath(a),a.host,a.port)
def cmd_report(a):
    con=connect(dbpath(a)); videos=con.execute("select count(*) from videos").fetchone()[0]; analyses=con.execute("select count(*) from analyses").fetchone()[0]; feedback=con.execute("select count(*) from feedback").fetchone()[0]; models=[dict(x) for x in con.execute("select model_version,approval_status,metrics_json from models order by id desc")]
    gate=gate_report(con); attention=con.execute("select count(*) from attention_analyses").fetchone()[0]; evaluations=con.execute("select count(*) from video_evaluations").fetchone()[0]; comparisons=con.execute("select count(*) from ab_comparisons").fetchone()[0]
    result={"status":"READY_LOCAL","schema_version":con.execute("select value from schema_meta where key='schema_version'").fetchone()[0],"videos":videos,"analyses":analyses,"attention_analyses":attention,"evaluations":evaluations,"ab_comparisons":comparisons,"feedback":feedback,"models":models,"training_state":gate["training_state"],"gate":gate,"production":production_summary(con),"recommendations":["Collect independent human A/B feedback by episode","Do not infer commercial quality or leads from visual features alone","Promote a model only after holdout and named human review"]}
    text=json.dumps(result,indent=2,ensure_ascii=False); print(text)
    if a.output: Path(a.output).write_text(text,encoding='utf-8')
    return 0
def cmd_export(a):
    con=connect(dbpath(a)); rows=[]
    for r in load_rows(con): rows.append({"video_id":r["id"],"episode":r["episode"],"version":r["version"],"baseline_score":Baseline().score(r),"source":"VLUX-CI-local"})
    Path(a.output).write_text(json.dumps({"schema":"vlux-video-os-recommendations-0.1","read_only":True,"recommendations":rows},indent=2),encoding='utf-8'); print(a.output); return 0
def cmd_rollback(a):
    con=connect(dbpath(a)); row=con.execute("select * from models where model_version=?",(a.model_version,)).fetchone()
    if not row: print(json.dumps({"status":"NOT_FOUND","model_version":a.model_version})); return 2
    artifact=Path(row["artifact_path"])
    if not artifact.exists(): print(json.dumps({"status":"ARTIFACT_MISSING","model_version":a.model_version})); return 2
    print(json.dumps({"status":"RECOVERED_READ_ONLY","model_version":a.model_version,"artifact_path":str(artifact),"approval_status":row["approval_status"]},indent=2)); return 0
def _print(value, output=None):
    text=json.dumps(value,indent=2,ensure_ascii=False,sort_keys=False); print(text)
    if output: Path(output).write_text(text,encoding="utf-8")
    return 0


def cmd_annotate(a):
    con=connect(dbpath(a))
    if not con.execute("select 1 from videos where id=?",(a.video_id,)).fetchone(): raise SystemExit("video_not_found")
    fields={"hook":a.hook,"business_problem":a.problem,"solution_presented":a.solution,"cta":a.cta,"target_audience":a.audience,"topic":a.topic,"human_notes":a.notes,"text_provenance":a.text_provenance}
    if a.transcript_file:
        fields["transcript_text"]=Path(a.transcript_file).read_text(encoding="utf-8")
    updates={k:v for k,v in fields.items() if v is not None}
    if not updates: raise SystemExit("no_fields_to_update")
    con.execute("update videos set "+",".join(f"{k}=?" for k in updates)+" where id=?",(*updates.values(),a.video_id)); con.commit()
    row=dict(con.execute("select id,episode,version,hook,business_problem,solution_presented,cta,target_audience,topic,text_provenance,human_notes,transcript_text from videos where id=?",(a.video_id,)).fetchone())
    if row.get("transcript_text"): row["transcript_text"]=row["transcript_text"][:400]
    return _print({"status":"ANNOTATED","video":row})


def cmd_attention(a):
    con=connect(dbpath(a)); result=analyze_attention(con,a.video_id,persist=not a.no_persist)
    return _print(result,a.output)


def cmd_evaluate(a):
    con=connect(dbpath(a)); evaluation_id=record_evaluation(con,a.video_id,a.evaluator,a.provenance,a.hook,a.narrative,a.production,a.commercial,a.cta,a.clarity,a.confidence,a.notes,a.evaluated_at)
    row=dict(con.execute("select * from video_evaluations where id=?",(evaluation_id,)).fetchone())
    note="Evaluación humana registrada." if a.provenance=="human" and a.evaluator!="anonymous" else "Evaluación registrada pero NO cuenta para el gate humano (anónima o no humana)."
    return _print({"status":"EVALUATION_RECORDED","evaluation":row,"gate_note":note,"gate":gate_report(con)["counts"]})


def cmd_ab(a):
    con=connect(dbpath(a)); result=ab_compare(con,a.a,a.b,persist=not a.no_persist); return _print(result,a.output)


def cmd_learning_status(a):
    con=connect(dbpath(a)); result=training_status(con); result["experiments_detail"]=list_experiments(con)[:10]; return _print(result,a.output)


def cmd_dataset_register(a):
    con=connect(dbpath(a)); result=dataset_registry(con); return _print(result,a.output)


def cmd_train_gated(a):
    con=connect(dbpath(a)); result=run_gated_training(con,a.artifacts,a.seed); return _print(result,a.output)


def cmd_model_registry(a):
    con=connect(dbpath(a)); result={"status":training_status(con),"models":list_models(con),"experiments":list_experiments(con)}
    if a.model_version: result["evaluation"]=evaluation_report(con,a.model_version)
    return _print(result,a.output)


def cmd_model_promote(a):
    con=connect(dbpath(a)); return _print(promote_model(con,a.model_version,a.approved_by),a.output)


def cmd_model_rollback(a):
    con=connect(dbpath(a)); return _print(rollback_model(con,a.model_version),a.output)


def cmd_production_plan(a):
    con=connect(dbpath(a)); brief=json.loads(Path(a.brief).read_text(encoding="utf-8"))
    result=plan_version(con,brief,a.adapter,a.video_id,a.parent_version_id); return _print(result,a.output)


def cmd_production_render(a):
    con=connect(dbpath(a)); result=render_version(con,a.version_key,a.output_dir); return _print(result,a.output)


def cmd_production_activate(a):
    con=connect(dbpath(a)); return _print(activate_version(con,a.version_key),a.output)


def cmd_production_rollback(a):
    con=connect(dbpath(a)); return _print(rollback_version(con,a.version_key),a.output)


def cmd_production_versions(a):
    con=connect(dbpath(a)); result={"versions":list_versions(con,a.video_id),"summary":production_summary(con)}
    if a.version_key: result["history"]=production_history(con,a.version_key)
    return _print(result,a.output)
def cmd_creative_review(a):
    con=connect(dbpath(a)); result=create_review(con,a.video_id); return _print(result,a.output)
def cmd_creative_reviews(a):
    con=connect(dbpath(a)); result=[dict(r) for r in con.execute("select review_key,video_id,episode,version_label,contract_version,status,created_at from creative_reviews order by id desc")]; return _print(result,a.output)
def cmd_creative_defects(a):
    con=connect(dbpath(a)); result=visual_defects_contract(create_review(con,a.video_id)); return _print(result,a.output)
def cmd_creative_changes(a):
    con=connect(dbpath(a)); result=recommended_changes_contract(create_review(con,a.video_id)); return _print(result,a.output)
def cmd_review_export(a):
    con=connect(dbpath(a)); result=export_review_bundle(con,a.review_key,a.output_dir); return _print(result,a.output)
def cmd_brief_create(a):
    con=connect(dbpath(a)); result=create_production_brief(con,a.change_key,a.target_version_label); return _print(result,a.output)
def cmd_brief_export(a):
    con=connect(dbpath(a)); result=export_production_brief(con,a.brief_key,a.output_dir); return _print(result,a.output)
def cmd_version_import(a):
    con=connect(dbpath(a)); result=import_episode_version(con,a.episode,a.file,a.permission,allowed_roots=[Path(p) for p in (a.allowed_root or [])]); return _print(result,a.output)
def cmd_version_import_contract(a):
    con=connect(dbpath(a)); result=import_version_contract(con,a.file); return _print(result,a.output)
def cmd_version_approve(a):
    con=connect(dbpath(a)); result=record_human_approval(con,a.subject_type,a.subject_key,a.decision,a.evaluator,a.notes); return _print(result,a.output)
def cmd_version_evaluate(a):
    con=connect(dbpath(a)); result=record_version_evaluation(con,a.version_key,a.evaluator,a.visual_impact,a.realism,a.clarity,a.hook,a.narrative,a.business_value,a.cta,a.preference,a.compared_version_key,a.confidence,a.notes,a.provenance,a.evaluated_at); return _print(result,a.output)
def cmd_performance_record(a):
    con=connect(dbpath(a)); result=record_performance(con,a.version_key,a.platform,a.measured_at,json.loads(a.metrics),campaign=a.campaign,published_at=a.published_at,hook_used=a.hook_used,cta_used=a.cta_used,provenance=a.provenance,notes=a.notes); return _print(result,a.output)
def cmd_version_compare(a):
    con=connect(dbpath(a)); result=compare_episode_versions(con,a.a,a.b,platform=a.platform); return _print(result,a.output)
def cmd_version_integrity(a):
    con=connect(dbpath(a)); result=verify_version_integrity(con,a.version_key); return _print(result,a.output)
def cmd_versions_list(a):
    con=connect(dbpath(a)); result={"versions":list_episode_versions(con,a.episode)}; return _print(result,a.output)
def cmd_loop_status(a):
    con=connect(dbpath(a)); result=loop_status(con); return _print(result,a.output)


def parser():
    p=argparse.ArgumentParser(prog="vlux-ci"); p.add_argument("--db",default=None); s=p.add_subparsers(dest="command",required=True)
    q=s.add_parser("creative-review"); q.add_argument("video_id",type=int); q.add_argument("--output",default=None); q.add_argument("--no-persist",action="store_true"); q.set_defaults(fn=cmd_creative_review)
    q=s.add_parser("creative-reviews"); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_creative_reviews)
    q=s.add_parser("creative-defects"); q.add_argument("video_id",type=int); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_creative_defects)
    q=s.add_parser("creative-changes"); q.add_argument("video_id",type=int); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_creative_changes)
    q=s.add_parser("review-export"); q.add_argument("--review-key",required=True); q.add_argument("--output-dir",required=True); q.set_defaults(fn=cmd_review_export)
    q=s.add_parser("brief-create"); q.add_argument("--change-key",required=True); q.add_argument("--target-version-label",default=None); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_brief_create)
    q=s.add_parser("brief-export"); q.add_argument("--brief-key",required=True); q.add_argument("--output-dir",required=True); q.set_defaults(fn=cmd_brief_export)
    q=s.add_parser("version-import"); q.add_argument("file"); q.add_argument("--episode",required=True); q.add_argument("--permission",required=True); q.add_argument("--parent-version-key",default=None); q.add_argument("--brief-key",default=None); q.add_argument("--source-video-id",type=int,default=None); q.add_argument("--version-label",default=None); q.add_argument("--allowed-root",action="append",default=None); q.set_defaults(fn=cmd_version_import)
    q=s.add_parser("version-import-contract"); q.add_argument("file"); q.add_argument("--allowed-root",action="append",default=None); q.set_defaults(fn=cmd_version_import_contract)
    q=s.add_parser("version-approve"); q.add_argument("--subject-type",required=True); q.add_argument("--subject-key",required=True); q.add_argument("--decision",required=True); q.add_argument("--evaluator",required=True); q.add_argument("--notes",default=""); q.set_defaults(fn=cmd_version_approve)
    q=s.add_parser("version-evaluate"); q.add_argument("--version-key",required=True); q.add_argument("--evaluator",required=True); q.add_argument("--visual-impact",type=float); q.add_argument("--realism",type=float); q.add_argument("--clarity",type=float); q.add_argument("--hook",type=float); q.add_argument("--narrative",type=float); q.add_argument("--business-value",type=float); q.add_argument("--cta",type=float); q.add_argument("--preference",default="no_preference"); q.add_argument("--compared-version-key",default=None); q.add_argument("--confidence",type=float); q.add_argument("--notes",default=""); q.add_argument("--evaluated-at",default=None); q.add_argument("--provenance",default="human"); q.set_defaults(fn=cmd_version_evaluate)
    q=s.add_parser("performance-record"); q.add_argument("--version-key",required=True); q.add_argument("--platform",required=True); q.add_argument("--measured-at",default=None); q.add_argument("--metrics",required=True); q.add_argument("--campaign",default=None); q.add_argument("--published-at",default=None); q.add_argument("--hook-used",default=None); q.add_argument("--cta-used",default=None); q.add_argument("--provenance",default="USER_PROVIDED"); q.add_argument("--notes",default=""); q.set_defaults(fn=cmd_performance_record)
    q=s.add_parser("version-compare"); q.add_argument("--a",required=True); q.add_argument("--b",required=True); q.add_argument("--platform",default=None); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_version_compare)
    q=s.add_parser("version-integrity"); q.add_argument("--version-key",required=True); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_version_integrity)
    q=s.add_parser("versions-list"); q.add_argument("--episode",default=None); q.set_defaults(fn=cmd_versions_list)
    q=s.add_parser("loop-status"); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_loop_status)
    q=s.add_parser("import"); q.add_argument("file"); q.add_argument("--episode",required=True); q.add_argument("--version",default="v0.1"); q.add_argument("--campaign",default=None); q.add_argument("--platform",default=None); q.add_argument("--topic",default=None); q.add_argument("--audience",default=None); q.add_argument("--problem",default=None); q.add_argument("--solution",default=None); q.add_argument("--publication-status",default=None); q.add_argument("--provenance",default=None); q.add_argument("--source-kind",choices=["published","review","synthetic","unknown"],default="unknown"); q.add_argument("--approval",default="unknown"); q.add_argument("--permission",default="unknown"); q.set_defaults(fn=cmd_import)
    q=s.add_parser("import-metadata"); q.add_argument("file"); q.set_defaults(fn=cmd_import_metadata)
    q=s.add_parser("analyze"); q.add_argument("video_id",type=int); q.set_defaults(fn=cmd_analyze)
    q=s.add_parser("feedback"); q.add_argument("--a",type=int,required=True); q.add_argument("--b",type=int,required=True); q.add_argument("--winner",choices=["A","B","tie"],required=True); q.add_argument("--criterion",default="full_video",choices=["retention","clarity","visual_impact","realism_3d","credibility","business_value","commercial_potential","full_video"]); q.add_argument("--comparison-type",default="full_video"); q.add_argument("--confidence",type=float,default=None); q.add_argument("--clarity",type=float,default=None); q.add_argument("--lighting",type=float,default=None); q.add_argument("--composition",type=float,default=None); q.add_argument("--realism",type=float,default=None); q.add_argument("--movement",type=float,default=None); q.add_argument("--commercial-quality",type=float,default=None); q.add_argument("--retention",type=float,default=None); q.add_argument("--visual-impact",type=float,default=None); q.add_argument("--credibility",type=float,default=None); q.add_argument("--business-value",type=float,default=None); q.add_argument("--commercial-potential",type=float,default=None); q.add_argument("--observations",default=""); q.add_argument("--evaluator",default="anonymous"); q.add_argument("--origin",default="human"); q.set_defaults(fn=cmd_feedback)
    q=s.add_parser("baseline"); q.set_defaults(fn=cmd_baseline)
    q=s.add_parser("metric"); q.add_argument("video_id",type=int); q.add_argument("name",choices=["views","avg_watch_time_s","retention","completion_rate","comments","likes","saves","shares","profile_visits","link_clicks","conversations","leads","qualified_leads","meetings","proposals","closed_won"]); q.add_argument("--value",type=float,default=None); q.add_argument("--source",required=True); q.add_argument("--observed-at",default=None); q.add_argument("--notes",default=""); q.set_defaults(fn=cmd_metric)
    q=s.add_parser("dataset-status"); q.set_defaults(fn=cmd_dataset_status)
    q=s.add_parser("train"); q.add_argument("--artifacts",default="artifacts"); q.add_argument("--seed",type=int,default=17); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_train_gated)
    q=s.add_parser("train-gated"); q.add_argument("--artifacts",default="artifacts"); q.add_argument("--seed",type=int,default=17); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_train_gated)
    q=s.add_parser("annotate"); q.add_argument("video_id",type=int); q.add_argument("--hook"); q.add_argument("--problem"); q.add_argument("--solution"); q.add_argument("--cta"); q.add_argument("--audience"); q.add_argument("--topic"); q.add_argument("--notes"); q.add_argument("--transcript-file"); q.add_argument("--text-provenance"); q.set_defaults(fn=cmd_annotate)
    q=s.add_parser("attention"); q.add_argument("video_id",type=int); q.add_argument("--output",default=None); q.add_argument("--no-persist",action="store_true"); q.set_defaults(fn=cmd_attention)
    q=s.add_parser("evaluate"); q.add_argument("video_id",type=int); q.add_argument("--evaluator",default="anonymous"); q.add_argument("--provenance",choices=["human","ai_assisted","synthetic","demo"],default="human"); q.add_argument("--hook",type=float); q.add_argument("--narrative",type=float); q.add_argument("--production",type=float); q.add_argument("--commercial",type=float); q.add_argument("--cta",type=float); q.add_argument("--clarity",type=float); q.add_argument("--confidence",type=float); q.add_argument("--notes",default=""); q.add_argument("--evaluated-at",default=None); q.set_defaults(fn=cmd_evaluate)
    q=s.add_parser("ab"); q.add_argument("--a",type=int,required=True); q.add_argument("--b",type=int,required=True); q.add_argument("--output",default=None); q.add_argument("--no-persist",action="store_true"); q.set_defaults(fn=cmd_ab)
    q=s.add_parser("learning-status"); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_learning_status)
    q=s.add_parser("dataset-register"); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_dataset_register)
    q=s.add_parser("model-registry"); q.add_argument("--model-version",default=None); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_model_registry)
    q=s.add_parser("model-promote"); q.add_argument("model_version"); q.add_argument("--approved-by",required=True); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_model_promote)
    q=s.add_parser("model-rollback"); q.add_argument("--model-version",default=None); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_model_rollback)
    q=s.add_parser("production-plan"); q.add_argument("--brief",required=True); q.add_argument("--adapter",choices=["manifest","ffmpeg_animatic"],default="manifest"); q.add_argument("--video-id",type=int,default=None); q.add_argument("--parent-version-id",type=int,default=None); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_production_plan)
    q=s.add_parser("production-render"); q.add_argument("version_key"); q.add_argument("--output-dir",default="data/production"); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_production_render)
    q=s.add_parser("production-activate"); q.add_argument("version_key"); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_production_activate)
    q=s.add_parser("production-rollback"); q.add_argument("version_key"); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_production_rollback)
    q=s.add_parser("production-versions"); q.add_argument("--video-id",type=int,default=None); q.add_argument("--version-key",default=None); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_production_versions)
    q=s.add_parser("report"); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_report)
    q=s.add_parser("export"); q.add_argument("--output",required=True); q.set_defaults(fn=cmd_export)
    q=s.add_parser("rollback"); q.add_argument("model_version"); q.set_defaults(fn=cmd_rollback)
    q=s.add_parser("recommend"); q.add_argument("--brief",required=True); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_recommend)
    q=s.add_parser("commercial-insights"); q.add_argument("--output",default=None); q.set_defaults(fn=cmd_commercial_insights)
    q=s.add_parser("export-bundle"); q.add_argument("--brief",required=True); q.add_argument("--output-dir",required=True); q.set_defaults(fn=cmd_export_bundle)
    q=s.add_parser("publication"); q.add_argument("--episode",required=True); q.add_argument("--platform",required=True); q.add_argument("--video-id",type=int,default=None); q.add_argument("--campaign",default=None); q.add_argument("--publication-ref",default=None); q.add_argument("--published-at",default=None); q.add_argument("--measured-at",default=None); q.add_argument("--status",default="published"); q.add_argument("--provenance",required=True); q.add_argument("--notes",default=""); q.set_defaults(fn=cmd_publication)
    q=s.add_parser("platform-metric"); q.add_argument("publication_id",type=int); q.add_argument("name"); q.add_argument("--value",type=float,default=None); q.add_argument("--status",choices=["OBSERVED","ESTIMATED","NOT_AVAILABLE"],default="OBSERVED"); q.add_argument("--provenance",required=True); q.add_argument("--measured-at",default=None); q.add_argument("--notes",default=""); q.set_defaults(fn=cmd_platform_metric)
    q=s.add_parser("funnel"); q.add_argument("publication_id",type=int); q.set_defaults(fn=cmd_funnel)
    q=s.add_parser("seed-ep025-proposals"); q.set_defaults(fn=cmd_seed_proposals)
    q=s.add_parser("proposals"); q.set_defaults(fn=cmd_proposals)
    q=s.add_parser("proposal-feedback"); q.add_argument("--a",type=int,required=True); q.add_argument("--b",type=int,required=True); q.add_argument("--winner",choices=["A","B","tie"],required=True); q.add_argument("--clarity",type=float); q.add_argument("--impact",type=float); q.add_argument("--credibility",type=float); q.add_argument("--retention",type=float); q.add_argument("--commercial",type=float); q.add_argument("--confidence",type=float); q.add_argument("--observations",default=""); q.add_argument("--evaluator",default="anonymous"); q.set_defaults(fn=cmd_proposal_feedback)
    q=s.add_parser("dashboard"); q.add_argument("--host",default="127.0.0.1"); q.add_argument("--port",type=int,default=8765); q.set_defaults(fn=dashboard)
    return p
def main(argv=None):
    a=parser().parse_args(argv); return a.fn(a)
if __name__=="__main__": sys.exit(main())
