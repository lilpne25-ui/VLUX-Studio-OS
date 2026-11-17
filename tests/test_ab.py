from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factory import add_analysis, add_publication, add_video
from vlux_ci.ab import compare, latest_comparison, list_evaluations, record_evaluation
from vlux_ci.db import connect


class TestABComparator(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.con = connect(Path(self.t.name) / "ab.sqlite")
        self.a = add_video(
            self.con, "EP-A", source_kind="review", permission="authorized",
            hook="¿NO PUEDES EDITARLO?", business_problem="Redibujar cuesta horas.",
            solution_presented="Historial editable y reconstrucción.", cta="Comenta CAD.",
            target_audience="ingenieros de producto", text_provenance="AI_ASSISTED_VISUAL_REVIEW",
        )
        add_analysis(self.con, self.a, cut_count=11, first_3s_cut_count=1, avg_shot_s=1.89,
                     brightness_mean=81.76, contrast_mean=66.01, freeze_ratio=0.052,
                     first_frame={"time_s": 0.233, "brightness": 90.99, "contrast": 68.21,
                                  "motion": None, "edge_density": 0.021,
                                  "lower_third_edge_density": 0.029})
        self.b = add_video(
            self.con, "EP-B", source_kind="review", permission="authorized",
            hook="PROMESA DE ENTREGA ¿TIENES CAPACIDAD?",
            business_problem="La promesa no coincide con la capacidad.",
            solution_presented="Planificación de capacidad.", cta="Comenta CAPACIDAD.",
            target_audience="directores de operaciones", text_provenance="AI_ASSISTED_VISUAL_REVIEW",
        )
        add_analysis(self.con, self.b, cut_count=4, first_3s_cut_count=0, avg_shot_s=4.57,
                     brightness_mean=50.06, contrast_mean=40.75, freeze_ratio=0.155,
                     first_frame={"time_s": 0.233, "brightness": 21.06, "contrast": 39.57,
                                  "motion": None, "edge_density": 0.021,
                                  "lower_third_edge_density": 0.012})

    def tearDown(self):
        self.con.close()
        self.t.cleanup()

    def test_layers_are_separate_and_no_automatic_winner(self):
        result = compare(self.con, self.a, self.b)
        self.assertEqual(result["contract_version"], "ab-comparison.v0.1")
        self.assertIsNone(result["summary"]["automatic_winner"])
        self.assertIn(result["summary"]["decision_status"], {
            "HUMAN_REVIEW_AND_RESULTS_REQUIRED",
            "HUMAN_PREFERENCE_AVAILABLE_COMMERCIAL_RESULTS_MISSING",
        })
        self.assertEqual(result["human_preferences"]["status"], "NOT_AVAILABLE")
        self.assertEqual(result["commercial_results"]["status"], "NOT_COMPARABLE")
        self.assertTrue(result["observed_facts"])
        self.assertTrue(result["estimates"])
        self.assertTrue(any(item["direction"] == "A_higher" for item in result["observed_facts"]))
        self.assertTrue(any(item["interpretation"].startswith("Diferencia observada") for item in result["observed_facts"]))
        self.assertTrue(any("Ningún ganador" in item for item in [result["summary"]["winner_policy"]]))
        self.assertGreater(self.con.execute("select count(*) from ab_comparisons").fetchone()[0], 0)
        self.assertEqual(latest_comparison(self.con, self.a, self.b)["summary"], result["summary"])

    def test_human_evaluation_changes_human_layer_only(self):
        before = compare(self.con, self.a, self.b)
        record_evaluation(self.con, self.a, "reviewer-1", "human", hook=5, narrative=5,
                          production=5, commercial=4, cta=5, clarity=5, confidence=0.9,
                          evaluated_at="2026-11-17T10:00:00+00:00")
        after = compare(self.con, self.a, self.b)
        self.assertEqual(before["human_preferences"]["status"], "NOT_AVAILABLE")
        self.assertEqual(after["human_preferences"]["status"], "AVAILABLE")
        self.assertEqual(after["human_preferences"]["a"]["dimension_means_1_to_5"]["hook"], 5.0)
        self.assertEqual(after["summary"]["decision_status"],
                         "HUMAN_PREFERENCE_AVAILABLE_COMMERCIAL_RESULTS_MISSING")
        self.assertIsNone(after["summary"]["automatic_winner"])
        self.assertEqual(after["estimates"], before["estimates"])

    def test_ai_assisted_and_anonymous_are_excluded_from_human_layer(self):
        record_evaluation(self.con, self.a, "ai-1", "ai_assisted", hook=5, clarity=5)
        record_evaluation(self.con, self.a, "anonymous", "human", hook=5, clarity=5)
        result = compare(self.con, self.a, self.b)
        self.assertEqual(result["human_preferences"]["status"], "NOT_AVAILABLE")
        self.assertEqual(result["human_preferences"]["excluded_non_human"]["a"]["excluded_from_human_gate"], 2)
        self.assertEqual(result["human_preferences"]["excluded_non_human"]["a"]["excluded_non_human"], 1)
        self.assertEqual(result["human_preferences"]["excluded_non_human"]["a"]["excluded_anonymous"], 1)
        evaluations = list_evaluations(self.con, self.a)
        self.assertEqual(len(evaluations), 2)

    def test_pairwise_feedback_is_not_extrapolated(self):
        self.con.execute(
            "insert into feedback(variant_a_id,variant_b_id,winner,origin,provenance) values(?,?,?,?,?)",
            (self.a, self.b, "A", "human", "human"),
        )
        self.con.commit()
        result = compare(self.con, self.a, self.b)
        self.assertEqual(result["human_preferences"]["pairwise"]["status"], "AVAILABLE")
        self.assertEqual(result["human_preferences"]["pairwise"]["counts"]["A"], 1)
        self.assertIsNone(result["summary"]["automatic_winner"])

    def test_same_video_is_rejected(self):
        with self.assertRaises(ValueError):
            compare(self.con, self.a, self.a)


if __name__ == "__main__":
    unittest.main()
