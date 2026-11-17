from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factory import add_analysis, add_publication, add_video
from vlux_ci.attention import (
    CONTRACT_VERSION, analyze_attention, attention_summary, latest_attention,
)
from vlux_ci.db import connect


class TestAttentionLab(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.con = connect(Path(self.t.name) / "attention.sqlite")

    def tearDown(self):
        self.con.close()
        self.t.cleanup()

    def _video(self, **fields):
        episode = fields.pop("episode", "EP021")
        defaults = {
            "hook": "PROMESA DE ENTREGA ¿TIENES CAPACIDAD?",
            "business_problem": "La promesa de entrega no coincide con la capacidad real.",
            "solution_presented": "Planificación de capacidad con pedidos, recursos y fechas.",
            "cta": "Comenta CAPACIDAD para revisar tu flujo.",
            "target_audience": "directores de operaciones",
            "text_provenance": "AI_ASSISTED_VISUAL_REVIEW",
            "human_notes": "El video muestra un déficit de capacidad y una simulación; evidencia visual con datos simulados.",
        }
        defaults.update(fields)
        video_id = add_video(self.con, episode, **defaults)
        add_analysis(self.con, video_id)
        return video_id

    def test_contract_persists_and_is_estimate_only(self):
        video_id = self._video()
        result = analyze_attention(self.con, video_id)
        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(result["status"], "ESTIMATE_ONLY_NOT_VALIDATED")
        self.assertIsNotNone(result["overall"]["score"])
        self.assertEqual(result["overall"]["status"], "ESTIMATE_NOT_VALIDATED")
        self.assertEqual(result["overall"]["confidence"], "low")
        self.assertTrue(result["recommendations"])
        self.assertIn("first_change", result)
        self.assertGreater(self.con.execute("select count(*) from attention_analyses").fetchone()[0], 0)
        reloaded = latest_attention(self.con, video_id)
        self.assertEqual(reloaded["video"]["episode"], "EP021")
        self.assertEqual(reloaded["overall"]["score"], result["overall"]["score"])
        summary = attention_summary(reloaded)
        self.assertEqual(summary["overall"], result["overall"]["score"])
        self.assertEqual(summary["status"], result["status"])

    def test_ai_assisted_text_is_labeled_not_human(self):
        video_id = self._video()
        result = analyze_attention(self.con, video_id)
        self.assertFalse(result["text_source"]["human_confirmed"])
        self.assertTrue(result["text_source"]["ai_assisted"])
        self.assertFalse(result["narrative"]["text_source"]["human_confirmed"])
        self.assertTrue(any("asistidas" in item for item in result["narrative"]["limitations"]))

    def test_missing_text_does_not_fabricate_narrative_or_commercial(self):
        video_id = add_video(self.con, "EP-EMPTY", source_kind="review", permission="authorized")
        add_analysis(self.con, video_id)
        result = analyze_attention(self.con, video_id)
        self.assertIsNone(result["narrative"]["score"])
        self.assertEqual(result["narrative"]["band"], "not_assessable")
        self.assertIsNone(result["commercial_value"]["score"])
        self.assertEqual(result["commercial_value"]["coverage"], 0.0)
        self.assertIsNotNone(result["production"]["score"])
        self.assertTrue(any("hook" == item["dimension"] for item in result["recommendations"]))

    def test_likes_are_not_leads_or_sales(self):
        video_id = self._video()
        add_publication(self.con, "EP021", video_id=video_id, metrics=[
            ("views", 1000, "OBSERVED"),
            ("likes", 80, "OBSERVED"),
            ("saves", 20, "OBSERVED"),
            ("shares", 10, "OBSERVED"),
        ])
        result = analyze_attention(self.con, video_id)
        self.assertTrue(result["results"]["likes_are_not_sales"])
        self.assertIsNone(result["results"]["commercial_signal"]["leads"])
        self.assertEqual(result["results"]["commercial_signal"]["status"], "NOT_AVAILABLE")
        self.assertEqual(result["results"]["observed_metrics"], 4)

    def test_duplicate_metric_rows_are_not_summed(self):
        video_id = self._video()
        add_publication(self.con, "EP021", video_id=video_id, metrics=[
            ("views", 1000, "OBSERVED"),
            ("likes", 80, "OBSERVED"),
            ("likes", 80, "OBSERVED"),
            ("likes", 80, "OBSERVED"),
        ])
        result = analyze_attention(self.con, video_id)
        self.assertEqual(result["results"]["likes_observed"], 80)
        self.assertEqual(result["results"]["observed_metrics"], 2)

    def test_observed_facts_are_preserved(self):
        video_id = self._video()
        result = analyze_attention(self.con, video_id)
        self.assertEqual(result["facts"]["cut_count"], 4)
        self.assertEqual(result["facts"]["first_3s_cut_count"], 0)
        self.assertEqual(result["facts"]["first_frame"]["brightness"], 21.06)
        self.assertEqual(len(result["facts"]["timeline"]), 20)
        self.assertEqual(result["hook"]["components"][0]["source"], "ffmpeg+opencv")

    def test_scores_are_deterministic(self):
        video_id = self._video()
        first = analyze_attention(self.con, video_id, persist=False)
        second = analyze_attention(self.con, video_id, persist=False)
        for dimension in ("hook", "narrative", "production", "commercial_value", "overall"):
            self.assertEqual(first[dimension]["score"], second[dimension]["score"])


if __name__ == "__main__":
    unittest.main()
