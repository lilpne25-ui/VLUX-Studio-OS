from __future__ import annotations

from typing import Any


def _metrics(con, publication_id: int) -> dict[str, float | None]:
    return {r["metric_name"]: r["metric_value"] for r in con.execute(
        "select metric_name,metric_value from platform_metrics where publication_id=?",
        (publication_id,),
    )}


def _item(value, status, evidence, note=""):
    return {"value": value, "status": status, "evidence": evidence, "note": note}


def funnel(con, publication_id: int) -> dict[str, Any]:
    row = con.execute("select * from publications where id=?", (publication_id,)).fetchone()
    if not row:
        raise ValueError("publication_not_found")
    m = _metrics(con, publication_id)
    views = m.get("views")
    interactions = sum(m.get(k, 0) or 0 for k in ("likes", "comments", "shares", "saves"))
    result = {
        "publication_id": publication_id, "episode": row["episode"], "platform": row["platform"],
        "provenance": row["provenance"], "measured_at": row["measured_at"],
        "stages": {
            "attention": {
                "views": _item(views, "OBSERVED" if views is not None else "NOT_AVAILABLE", "platform_metrics"),
                "unique_viewers": _item(m.get("unique_viewers"), "OBSERVED" if m.get("unique_viewers") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "avg_watch_time_s": _item(m.get("avg_watch_time_s"), "OBSERVED" if m.get("avg_watch_time_s") is not None else "NOT_AVAILABLE", "platform_metrics"),
            },
            "interaction": {
                "likes": _item(m.get("likes"), "OBSERVED" if m.get("likes") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "comments": _item(m.get("comments"), "OBSERVED" if m.get("comments") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "shares": _item(m.get("shares"), "OBSERVED" if m.get("shares") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "saves": _item(m.get("saves"), "OBSERVED" if m.get("saves") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "interaction_rate": _item(round(interactions / views, 6) if views else None, "DERIVED" if views else "NOT_AVAILABLE", "likes+comments+shares+saves divided by views"),
            },
            "commercial_interest": {
                "new_followers": _item(m.get("new_followers"), "OBSERVED" if m.get("new_followers") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "profile_visits": _item(m.get("profile_visits"), "OBSERVED" if m.get("profile_visits") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "profile_visit_rate": _item(round(m["profile_visits"] / views, 6) if views and m.get("profile_visits") is not None else None, "DERIVED" if views and m.get("profile_visits") is not None else "NOT_AVAILABLE", "profile_visits divided by views"),
                "link_clicks": _item(m.get("link_clicks"), "OBSERVED" if m.get("link_clicks") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "conversations": _item(m.get("conversations"), "OBSERVED" if m.get("conversations") is not None else "NOT_AVAILABLE", "platform_metrics"),
            },
            "prospects": {
                "leads": _item(m.get("leads"), "OBSERVED" if m.get("leads") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "qualified_leads": _item(m.get("qualified_leads"), "OBSERVED" if m.get("qualified_leads") is not None else "NOT_AVAILABLE", "platform_metrics"),
            },
            "sales": {
                "meetings": _item(m.get("meetings"), "OBSERVED" if m.get("meetings") is not None else "NOT_AVAILABLE", "platform_metrics"),
                "closed_won": _item(m.get("closed_won"), "OBSERVED" if m.get("closed_won") is not None else "NOT_AVAILABLE", "platform_metrics"),
            },
        },
        "guardrails": [
            "Likes, shares and followers are not leads.",
            "No causal claim is made from one publication.",
            "Missing metrics remain NOT_AVAILABLE.",
        ],
    }
    return result
