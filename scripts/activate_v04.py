from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vlux_ci.db import connect
from vlux_ci.funnel import funnel
from vlux_ci.proposals import ep025_proposals, payload, CONTRACT_VERSION


METRICS = {
    "views": 5468,
    "unique_viewers": 4389,
    "avg_watch_time_s": 10,
    "likes": 176,
    "comments": 25,
    "shares": 51,
    "saves": 125,
    "new_followers": 23,
    "profile_visits": 11,
}
PROVENANCE = "USER_PROVIDED_SCREENSHOT"


def main():
    db = ROOT / "data" / "vlux.sqlite"
    con = connect(db)
    existing = con.execute(
        "select id from publications where episode='EP011' and platform='Instagram' and provenance=?",
        (PROVENANCE,),
    ).fetchone()
    if existing:
        publication_id = existing["id"]
    else:
        asset = con.execute("select id from videos where episode='EP011' order by id limit 1").fetchone()
        con.execute(
            "insert into publications(video_id,episode,campaign,platform,publication_ref,measured_at,publication_status,provenance,notes) values(?,?,?,?,?,?,?,?,?)",
            (asset["id"] if asset else None, "EP011", "Autodesk Fusion / Ingeniería de producto",
             "Instagram", None, None, "published", PROVENANCE,
             "Datos proporcionados por el usuario; no verificados mediante API de Instagram."),
        )
        con.commit()
        publication_id = con.execute("select last_insert_rowid()").fetchone()[0]
    for name, value in METRICS.items():
        con.execute(
            "insert or replace into platform_metrics(publication_id,metric_name,metric_value,status,provenance,measured_at,notes) values(?,?,?,?,?,?,?)",
            (publication_id, name, value, "OBSERVED", PROVENANCE, None,
             "Captura de métricas de Instagram proporcionada por el usuario."),
        )
    for item in ep025_proposals():
        con.execute(
            "insert into creative_proposals(episode,proposal_key,title,payload_json,contract_version) values(?,?,?,?,?) on conflict(episode,proposal_key) do update set title=excluded.title,payload_json=excluded.payload_json,contract_version=excluded.contract_version",
            ("EP025", item["proposal_key"], item["title"], payload(item), CONTRACT_VERSION),
        )
    con.commit()
    report = funnel(con, publication_id)
    (ROOT / "reports" / "EP011_funnel.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    proposals = [dict(r) for r in con.execute(
        "select id,episode,proposal_key,title,payload_json,contract_version from creative_proposals where episode='EP025' order by id"
    )]
    (ROOT / "reports" / "EP025_PROPOSALS.json").write_text(json.dumps(proposals, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "V04_ACTIVATED", "publication_id": publication_id,
                      "provenance": PROVENANCE, "metrics_registered": len(METRICS),
                      "ep025_proposals": len(proposals)}, indent=2))


if __name__ == "__main__":
    main()
