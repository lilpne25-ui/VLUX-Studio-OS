from __future__ import annotations

import statistics


METRIC_NAMES = (
    "views", "avg_watch_time_s", "retention", "completion_rate", "comments",
    "likes", "saves", "shares", "profile_visits", "link_clicks",
    "conversations", "leads", "qualified_leads", "meetings", "proposals",
    "closed_won",
)


def summarize(con) -> dict:
    rows = [dict(r) for r in con.execute(
        "SELECT v.episode,v.topic,v.cta,v.campaign,v.source_kind,m.metric_name,m.metric_value "
        "FROM videos v JOIN metrics m ON m.video_id=v.id "
        "WHERE v.source_kind='published' AND m.metric_value IS NOT NULL"
    )]
    def group(key, metric):
        groups = {}
        for row in rows:
            if row["metric_name"] != metric or not row.get(key):
                continue
            groups.setdefault(row[key], []).append(row["metric_value"])
        return [{"group": k, "metric": metric, "n": len(v),
                 "mean": statistics.mean(v)} for k, v in sorted(groups.items())]
    return {
        "status": "DESCRIPTIVE_CORRELATION_ONLY",
        "records": len(rows),
        "by_topic_qualified_leads": group("topic", "qualified_leads"),
        "by_cta_conversations": group("cta", "conversations"),
        "by_campaign_meetings": group("campaign", "meetings"),
        "limitations": [
            "No causal claim from observational data.",
            "Missing metrics remain unknown and are excluded, not imputed.",
            "Synthetic and review-only videos are excluded from commercial summaries.",
        ],
    }
