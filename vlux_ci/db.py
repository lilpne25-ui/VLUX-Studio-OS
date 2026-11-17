from __future__ import annotations
import hashlib, json, sqlite3
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.5"
FEATURE_NAMES = ["duration_s","fps","width","height","cut_count","avg_shot_s","motion_mean","brightness_mean","contrast_mean","black_ratio","freeze_ratio","subtitle_space_ratio","first_second_motion","first_second_brightness"]

def sha256_file(path: str | Path) -> str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def connect(db: str | Path, check_same_thread: bool = True) -> sqlite3.Connection:
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(str(db), check_same_thread=check_same_thread); con.row_factory=sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript('''
    CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS videos (
      id INTEGER PRIMARY KEY, episode TEXT NOT NULL, version TEXT NOT NULL, file_path TEXT NOT NULL,
      file_hash TEXT NOT NULL UNIQUE, duration_s REAL, fps REAL, width INTEGER, height INTEGER,
      production_date TEXT, campaign TEXT, platform TEXT, topic TEXT, target_audience TEXT,
      business_problem TEXT, solution_presented TEXT, script TEXT, hook TEXT, cta TEXT, category TEXT, visual_style TEXT,
      narration_type TEXT, asset_origin TEXT, approval_status TEXT, permission_status TEXT NOT NULL DEFAULT 'unknown',
      publication_status TEXT, creative_version TEXT, provenance TEXT, source_kind TEXT NOT NULL DEFAULT 'unknown',
      source_type TEXT NOT NULL DEFAULT 'local', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS analyses (
      id INTEGER PRIMARY KEY, video_id INTEGER NOT NULL REFERENCES videos(id), analyzer_version TEXT NOT NULL,
      objective_json TEXT NOT NULL, aesthetic_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS feedback (
      id INTEGER PRIMARY KEY, variant_a_id INTEGER NOT NULL REFERENCES videos(id), variant_b_id INTEGER NOT NULL REFERENCES videos(id),
      winner TEXT NOT NULL CHECK(winner IN ('A','B','tie')), clarity REAL, lighting REAL, composition REAL,
      realism REAL, movement REAL, commercial_quality REAL, retention REAL, visual_impact REAL,
      credibility REAL, business_value REAL, commercial_potential REAL, criterion TEXT,
      comparison_type TEXT NOT NULL DEFAULT 'full_video', confidence REAL, observations TEXT,
      evaluator_id TEXT NOT NULL DEFAULT 'anonymous', origin TEXT NOT NULL DEFAULT 'human',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS metrics (
      id INTEGER PRIMARY KEY, video_id INTEGER NOT NULL REFERENCES videos(id), metric_name TEXT NOT NULL,
      metric_value REAL, source TEXT NOT NULL, observed_at TEXT, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS models (
      id INTEGER PRIMARY KEY, model_version TEXT NOT NULL UNIQUE, model_type TEXT NOT NULL, dataset_hash TEXT NOT NULL,
      parameters_json TEXT NOT NULL, metrics_json TEXT NOT NULL, artifact_path TEXT NOT NULL, artifact_hash TEXT NOT NULL,
      baseline_metrics_json TEXT NOT NULL, approval_status TEXT NOT NULL DEFAULT 'candidate', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS experiments (
      id INTEGER PRIMARY KEY, experiment_id TEXT NOT NULL UNIQUE, dataset_hash TEXT NOT NULL, results_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS observations (
      id INTEGER PRIMARY KEY, video_id INTEGER NOT NULL REFERENCES videos(id),
      start_s REAL NOT NULL, end_s REAL NOT NULL, severity TEXT NOT NULL,
      category TEXT NOT NULL, message TEXT NOT NULL, recommendation TEXT NOT NULL,
      evidence_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS publications (
      id INTEGER PRIMARY KEY, video_id INTEGER REFERENCES videos(id), episode TEXT NOT NULL,
      campaign TEXT, platform TEXT NOT NULL, publication_ref TEXT, published_at TEXT,
      measured_at TEXT, publication_status TEXT NOT NULL DEFAULT 'published',
      provenance TEXT NOT NULL, notes TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS platform_metrics (
      id INTEGER PRIMARY KEY, publication_id INTEGER NOT NULL REFERENCES publications(id),
      metric_name TEXT NOT NULL, metric_value REAL, status TEXT NOT NULL DEFAULT 'OBSERVED',
      provenance TEXT NOT NULL, measured_at TEXT, notes TEXT,
      UNIQUE(publication_id, metric_name, measured_at)
    );
    CREATE TABLE IF NOT EXISTS creative_proposals (
      id INTEGER PRIMARY KEY, episode TEXT NOT NULL, proposal_key TEXT NOT NULL,
      title TEXT NOT NULL, payload_json TEXT NOT NULL, contract_version TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(episode, proposal_key)
    );
    CREATE TABLE IF NOT EXISTS proposal_feedback (
      id INTEGER PRIMARY KEY, proposal_a_id INTEGER NOT NULL REFERENCES creative_proposals(id),
      proposal_b_id INTEGER NOT NULL REFERENCES creative_proposals(id),
      winner TEXT NOT NULL CHECK(winner IN ('A','B','tie')), clarity REAL, impact REAL,
      credibility REAL, retention_potential REAL, commercial_potential REAL,
      confidence REAL, observations TEXT, evaluator_id TEXT NOT NULL DEFAULT 'anonymous',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS attention_analyses (
      id INTEGER PRIMARY KEY, video_id INTEGER NOT NULL REFERENCES videos(id),
      analyzer_version TEXT NOT NULL, contract_version TEXT NOT NULL,
      facts_json TEXT NOT NULL, hook_json TEXT NOT NULL, narrative_json TEXT NOT NULL,
      production_json TEXT NOT NULL, commercial_json TEXT NOT NULL, results_json TEXT NOT NULL,
      recommendations_json TEXT NOT NULL, overall_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS video_evaluations (
      id INTEGER PRIMARY KEY, video_id INTEGER NOT NULL REFERENCES videos(id),
      hook REAL, narrative REAL, production REAL, commercial REAL, cta REAL, clarity REAL,
      confidence REAL, evaluator_id TEXT NOT NULL, provenance TEXT NOT NULL,
      evaluated_at TEXT, notes TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS ab_comparisons (
      id INTEGER PRIMARY KEY, a_video_id INTEGER NOT NULL REFERENCES videos(id),
      b_video_id INTEGER NOT NULL REFERENCES videos(id), contract_version TEXT NOT NULL,
      payload_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS production_versions (
      id INTEGER PRIMARY KEY, version_key TEXT NOT NULL UNIQUE,
      video_id INTEGER REFERENCES videos(id),
      parent_version_id INTEGER REFERENCES production_versions(id),
      brief_json TEXT NOT NULL, adapter TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'candidate', output_path TEXT,
      contract_version TEXT NOT NULL, provenance TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, activated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS production_jobs (
      id INTEGER PRIMARY KEY, job_key TEXT NOT NULL UNIQUE,
      video_id INTEGER REFERENCES videos(id), adapter TEXT NOT NULL, status TEXT NOT NULL,
      brief_json TEXT NOT NULL, output_json TEXT, output_path TEXT, error TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS dataset_registry (
      id INTEGER PRIMARY KEY, dataset_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
      dataset_hash TEXT NOT NULL, videos_count INTEGER NOT NULL, episodes_count INTEGER NOT NULL,
      evaluations_count INTEGER NOT NULL, commercial_records INTEGER NOT NULL,
      authorization_status TEXT NOT NULL, payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS model_registry_state (
      key TEXT PRIMARY KEY, value TEXT NOT NULL
    );
    ''')
    migrations = {
      "campaign":"TEXT", "platform":"TEXT", "topic":"TEXT", "target_audience":"TEXT",
      "business_problem":"TEXT", "solution_presented":"TEXT", "publication_status":"TEXT",
      "creative_version":"TEXT", "provenance":"TEXT", "source_kind":"TEXT NOT NULL DEFAULT 'unknown'",
      "transcript_text":"TEXT", "text_provenance":"TEXT", "human_notes":"TEXT",
      "animation_style":"TEXT", "target_duration_s":"REAL",
    }
    feedback_migrations = {
      "retention":"REAL", "visual_impact":"REAL", "credibility":"REAL",
      "business_value":"REAL", "commercial_potential":"REAL", "criterion":"TEXT",
      "comparison_type":"TEXT NOT NULL DEFAULT 'full_video'", "confidence":"REAL",
      "hook":"REAL", "narrative":"REAL", "production":"REAL", "cta":"REAL",
      "pace":"REAL", "visual_quality":"REAL", "provenance":"TEXT NOT NULL DEFAULT 'human'",
      "evaluated_at":"TEXT",
    }
    for name, typ in migrations.items():
        if name not in {r[1] for r in con.execute("PRAGMA table_info(videos)")}:
            con.execute(f"ALTER TABLE videos ADD COLUMN {name} {typ}")
    for name, typ in feedback_migrations.items():
        if name not in {r[1] for r in con.execute("PRAGMA table_info(feedback)")}:
            con.execute(f"ALTER TABLE feedback ADD COLUMN {name} {typ}")
    con.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version',?)",(SCHEMA_VERSION,)); con.commit(); return con

def json_dumps(value: Any) -> str: return json.dumps(value, ensure_ascii=False, sort_keys=True)
