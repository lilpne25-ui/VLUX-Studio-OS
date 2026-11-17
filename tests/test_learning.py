from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factory import add_analysis, add_publication, add_video, make_eligible_dataset
from vlux_ci.ab import record_evaluation
from vlux_ci.db import connect, json_dumps
from vlux_ci.learning import (
    GATE_THRESHOLDS, dataset_registry, gate_report, list_experiments, list_models,
    promote_model, rollback_model, run_gated_training, training_status,
)


class TestLearningGate(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.con = connect(Path(self.t.name) / "learning.sqlite")

    def tearDown(self):
        self.con.close()
        self.t.cleanup()

    def test_empty_database_is_blocked(self):
        gate = gate_report(self.con)
        self.assertEqual(gate["status"], "BLOCKED")
        self.assertEqual(gate["training_state"], "NO_TRAINING_INSUFFICIENT_DATA")
        self.assertTrue(gate["blocking_reasons"])
        status = training_status(self.con)
        self.assertEqual(status["training_state"], "NO_TRAINING_INSUFFICIENT_DATA")
        self.assertIsNone(status["active_model_version"])

    def test_ai_assisted_and_anonymous_do_not_unlock_gate(self):
        video_ids = []
        for index in range(GATE_THRESHOLDS["eligible_videos"]):
            video_id = add_video(
                self.con, f"SYN-{index % 4}", source_kind="synthetic", permission="synthetic",
                file_hash=f"ai-{index:02d}",
            )
            add_analysis(self.con, video_id)
            video_ids.append(video_id)
        for index, video_id in enumerate(video_ids):
            record_evaluation(self.con, video_id, f"ai-{index}", "ai_assisted", hook=5, clarity=5)
            record_evaluation(self.con, video_id, "anonymous", "human", hook=5, clarity=5)
        for index in range(5):
            add_publication(self.con, f"SYN-{index % 4}", provenance="USER_PROVIDED_SCREENSHOT",
                            metrics=[("qualified_leads", index + 1, "OBSERVED")])
        gate = gate_report(self.con)
        self.assertEqual(gate["status"], "BLOCKED")
        evaluations_check = next(c for c in gate["checks"] if c["name"] == "human_evaluations")
        self.assertEqual(evaluations_check["have"], 0)
        self.assertGreaterEqual(gate["counts"]["excluded_ai_evaluations"], 12)
        self.assertGreaterEqual(gate["counts"]["excluded_anonymous_evaluations"], 12)

    def test_legitimate_fixture_unlocks_gate_and_trains_or_reports(self):
        make_eligible_dataset(self.con)
        gate = gate_report(self.con)
        self.assertEqual(gate["status"], "ELIGIBLE")
        self.assertEqual(gate["training_state"], "READY_FOR_GATED_TRAINING")
        self.assertEqual(gate["counts"]["eligible_videos"], 12)
        self.assertEqual(gate["counts"]["human_evaluations"], 12)
        self.assertEqual(gate["counts"]["commercial_records"], 5)
        result = run_gated_training(self.con, Path(self.t.name) / "artifacts")
        self.assertIn(result["status"], {"TRAINED", "TRAINING_FAILED", "NO_TRAINING_INSUFFICIENT_DATA"})
        self.assertTrue(list_experiments(self.con))
        if result["status"] == "TRAINED":
            self.assertTrue(result["model_created"])
            models = list_models(self.con)
            self.assertEqual(len(models), 1)
            self.assertEqual(models[0]["approval_status"], "candidate")

    def test_blocked_training_records_experiment_and_no_model(self):
        result = run_gated_training(self.con, Path(self.t.name) / "artifacts")
        self.assertEqual(result["status"], "NO_TRAINING_INSUFFICIENT_DATA")
        self.assertFalse(result["model_created"])
        self.assertEqual(len(list_experiments(self.con)), 1)
        self.assertEqual(list_models(self.con), [])

    def test_dataset_registry_is_stable_and_contains_no_raw_evaluator_ids(self):
        make_eligible_dataset(self.con)
        first = dataset_registry(self.con)
        second = dataset_registry(self.con)
        self.assertEqual(first["dataset_key"], second["dataset_key"])
        self.assertEqual(first["dataset_hash"], second["dataset_hash"])
        self.assertEqual(first["counts"]["videos"], 12)
        text = json_dumps(first["payload"])
        self.assertNotIn("reviewer-", text)
        self.assertIn("evaluator_hash", text)
        self.assertEqual(first["status"], "REGISTERED_ELIGIBLE")

    def test_promotion_requires_gate_named_human_and_improvement(self):
        video_id = add_video(self.con, "SYN-0", source_kind="synthetic", permission="synthetic")
        add_analysis(self.con, video_id)
        self.con.execute(
            "insert into models(model_version,model_type,dataset_hash,parameters_json,metrics_json,artifact_path,artifact_hash,baseline_metrics_json,approval_status) values(?,?,?,?,?,?,?,?,?)",
            ("candidate-test", "logistic_numpy", "hash", "{}", json_dumps({"accuracy": 0.8, "baseline_accuracy": 0.5}),
             "artifacts/model-test.json", "artifact-hash", "{}", "candidate"),
        )
        self.con.commit()
        refused = promote_model(self.con, "candidate-test", "reviewer-1")
        self.assertEqual(refused["status"], "REFUSED")
        self.assertEqual(refused["reason"], "TRAINING_GATE_BLOCKED")
        self.assertEqual(promote_model(self.con, "candidate-test", "anonymous")["status"], "REFUSED")

        make_eligible_dataset(self.con)
        promoted = promote_model(self.con, "candidate-test", "reviewer-1")
        self.assertEqual(promoted["status"], "PROMOTED")
        self.assertEqual(training_status(self.con)["active_model_version"], "candidate-test")

    def test_model_rollback_restores_previous_version(self):
        for version in ("model-a", "model-b"):
            self.con.execute(
                "insert into models(model_version,model_type,dataset_hash,parameters_json,metrics_json,artifact_path,artifact_hash,baseline_metrics_json,approval_status) values(?,?,?,?,?,?,?,?,?)",
                (version, "logistic_numpy", "hash", "{}", "{}", f"artifacts/{version}.json", "h", "{}",
                 "active" if version == "model-b" else "superseded"),
            )
        self.con.execute("insert into model_registry_state(key,value) values('active_model_version','model-b')")
        self.con.execute("insert into model_registry_state(key,value) values('previous_model_version','model-a')")
        self.con.commit()
        result = rollback_model(self.con, "model-a")
        self.assertEqual(result["status"], "ROLLED_BACK")
        self.assertEqual(result["active_model_version"], "model-a")
        self.assertEqual(result["rolled_back_from"], "model-b")
        self.assertEqual(training_status(self.con)["active_model_version"], "model-a")


if __name__ == "__main__":
    unittest.main()
