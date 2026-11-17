from __future__ import annotations

import json
import uuid


def add_video(con, episode="EP-TEST", *, file_hash=None, source_kind="review",
              permission="authorized", version="v0.1", **fields):
    file_hash = file_hash or uuid.uuid4().hex
    keys = ["episode", "version", "file_path", "file_hash", "permission_status", "source_kind"]
    values = [episode, version, f"data/review/{file_hash}.mp4", file_hash, permission, source_kind]
    for key, value in fields.items():
        keys.append(key)
        values.append(value)
    con.execute(
        f"insert into videos({','.join(keys)}) values({','.join('?' for _ in keys)})",
        values,
    )
    video_id = int(con.execute("select last_insert_rowid()").fetchone()[0])
    con.commit()
    return video_id


def add_analysis(con, video_id, **overrides):
    objective = {
        "duration_s": 22.666667, "fps": 30.0, "width": 540, "height": 960,
        "has_audio": True, "codec": "h264",
        "cut_count": 4, "cut_times": [4.4, 8.6, 16.3, 20.1],
        "first_3s_cut_count": 0, "avg_shot_s": 4.57,
        "motion_mean": 8.15, "motion_mean_full": 5.95,
        "first_3s_motion": 8.15, "first_second_motion": 4.36,
        "brightness_mean": 50.06, "contrast_mean": 40.75,
        "edge_density_mean": 0.0238, "edge_density_first3s": 0.0275,
        "lower_third_edge_density_mean": 0.0089,
        "freeze_ratio": 0.1546, "black_ratio": 0.0,
        "silence_total_s": 0.0, "silence_ratio": 0.0,
        "first_frame": {"time_s": 0.233, "brightness": 21.06, "contrast": 39.57,
                        "motion": None, "edge_density": 0.0209,
                        "lower_third_edge_density": 0.0116},
        "timeline": [
            {"time_s": round(i * 0.5, 1), "brightness": 45 + i, "contrast": 40,
             "motion": 2 + i * 0.7, "edge_density": 0.02,
             "lower_third_edge_density": 0.01}
            for i in range(20)
        ],
        "sample_count": 98,
    }
    objective.update(overrides)
    con.execute(
        "insert into analyses(video_id,analyzer_version,objective_json,aesthetic_json) values(?,?,?,?)",
        (video_id, "0.5.0", json.dumps(objective), json.dumps({"test": True})),
    )
    con.commit()
    return objective


def add_publication(con, episode, *, video_id=None, platform="Instagram",
                    provenance="USER_PROVIDED_SCREENSHOT", measured_at=None,
                    metrics=()):
    con.execute(
        "insert into publications(video_id,episode,platform,measured_at,provenance) values(?,?,?,?,?)",
        (video_id, episode, platform, measured_at, provenance),
    )
    publication_id = int(con.execute("select last_insert_rowid()").fetchone()[0])
    for name, value, status in metrics:
        con.execute(
            "insert into platform_metrics(publication_id,metric_name,metric_value,status,provenance,measured_at) values(?,?,?,?,?,?)",
            (publication_id, name, value, status, provenance, measured_at),
        )
    con.commit()
    return publication_id


def make_eligible_dataset(con, *, video_count=12, episodes=4):
    """Synthetic fixture used only to test the gate and rollback machinery."""
    video_ids = []
    for index in range(video_count):
        episode = f"SYN-{index % episodes}"
        video_id = add_video(
            con, episode, source_kind="synthetic", permission="synthetic",
            file_hash=f"fixture-{index:02d}",
        )
        add_analysis(con, video_id, cut_count=index, avg_shot_s=2 + index * 0.2,
                     first_3s_cut_count=index % 4, freeze_ratio=0.02 * (index % 5))
        video_ids.append(video_id)
    # A balanced human label set: half strong, half weak, spread across episodes.
    from vlux_ci.ab import record_evaluation
    for index, video_id in enumerate(video_ids):
        score = 5 if (index // episodes) % 2 == 0 else 2
        record_evaluation(
            con, video_id, evaluator_id=f"reviewer-{index % 3}",
            provenance="human", hook=score, narrative=score, production=score,
            commercial=score, cta=score, clarity=score, confidence=0.9,
            evaluated_at="2026-11-17T12:00:00+00:00",
        )
    for index in range(5):
        publication_id = con.execute(
            "insert into publications(episode,platform,measured_at,provenance) values(?,?,?,?)",
            (f"SYN-{index % episodes}", "Synthetic", "2026-11-17", "USER_PROVIDED_SCREENSHOT"),
        ).lastrowid
        con.execute(
            "insert into platform_metrics(publication_id,metric_name,metric_value,status,provenance,measured_at) values(?,?,?,?,?,?)",
            (publication_id, "qualified_leads", index + 1, "OBSERVED", "USER_PROVIDED_SCREENSHOT", "2026-11-17"),
        )
    con.commit()
    return video_ids
