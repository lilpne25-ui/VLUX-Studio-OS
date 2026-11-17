from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from factory import add_analysis, add_video
from vlux_ci.ab import compare as ab_compare, record_evaluation
from vlux_ci.attention import analyze_attention
from vlux_ci.creative_loop import (
    CONTRACT_CREATIVE_REVIEW, CONTRACT_EPISODE_VERSION, CONTRACT_HUMAN_APPROVAL,
    CONTRACT_HUMAN_EVALUATION, CONTRACT_PERFORMANCE_COMPARISON,
    CONTRACT_PERFORMANCE_RECORD, CONTRACT_PRODUCTION_BRIEF,
    CONTRACT_RECOMMENDED_CHANGES, CONTRACT_VISUAL_DEFECTS,
    activate_episode_version, compare_episode_versions, create_production_brief,
    create_review, export_production_brief, export_review_bundle, get_episode_version,
    import_episode_version, import_version_contract, list_version_evaluations,
    loop_status, record_human_approval, record_performance,
    record_version_evaluation, recommended_changes_contract, rollback_episode_version,
    verify_version_integrity, visual_defects_contract,
)
from vlux_ci.db import connect, sha256_file
from vlux_ci.learning import gate_report
from vlux_ci.production import plan_version, render_version

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from validate_contracts import validate
REQUIRED_CHANGE_FIELDS = {
    "episode", "timestamp", "detected_problem", "evidence", "estimated_impact",
    "proposed_solution", "priority", "suggested_tool", "acceptance_criterion",
}


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class TestCreativeLoop(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.con = connect(self.root / "loop.sqlite")
        self.video_id = add_video(
            self.con, "EP-TEST", source_kind="synthetic", permission="synthetic",
            hook="¿Cuánto cuesta copiar datos a mano?",
            cta="Comenta FLUJO.",
            business_problem="Los datos se copian manualmente y se pierden horas.",
            solution_presented="Flujo trazable entre ingeniería y ERP.",
            target_audience="directores de operaciones",
        )
        add_analysis(self.con, self.video_id)

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    def _schema(self, name):
        return json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))

    def _validate(self, name, document):
        validate(document, self._schema(name))

    def _fixture(self, name="fixture.mp4", color="0x203040", frequency=440):
        if not _has_ffmpeg():
            self.skipTest("ffmpeg unavailable")
        path = self.root / name
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
             "-i", f"color=c={color}:s=160x90:d=2:r=25",
             "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration=2",
             "-shortest", "-pix_fmt", "yuv420p", str(path)],
            check=True, capture_output=True,
        )
        return path

    def _import_pair(self):
        a_path = self._fixture("a.mp4", "0x203040", 440)
        b_path = self._fixture("b.mp4", "0x405060", 660)
        a = import_episode_version(
            self.con, "EP-TEST", a_path, "synthetic",
            allowed_roots=[self.root], version_label="EP-TEST-A",
        )
        b = import_episode_version(
            self.con, "EP-TEST", b_path, "synthetic",
            parent_version_key=a["version_key"], allowed_roots=[self.root],
            version_label="EP-TEST-B",
        )
        return a, b

    def test_review_contains_actionable_changes_and_valid_contracts(self):
        bundle = create_review(self.con, self.video_id)
        review = bundle["review"]
        self.assertEqual(review["contract_version"], CONTRACT_CREATIVE_REVIEW)
        self.assertEqual(review["status"], "REVIEW_ESTIMATE_ONLY")
        self.assertTrue(bundle["defects"])
        self.assertTrue(bundle["changes"])
        for change in bundle["changes"]:
            self.assertTrue(REQUIRED_CHANGE_FIELDS.issubset(change), change.keys())
            self.assertEqual(change["episode"], "EP-TEST")
            self.assertEqual(change["estimated_impact"]["status"], "ESTIMATE_ONLY")
            self.assertTrue(change["estimated_impact"]["not_a_result"])
            self.assertFalse(change["automatic_execution"])
            self.assertTrue(change["requires_human_approval"])
            self.assertIn("start_s", change["timestamp"])
            self.assertIn("end_s", change["timestamp"])
            self.assertTrue(change["acceptance_criterion"])
            self.assertIn("mode", change["suggested_tool"])
        self.assertTrue(any("acercamiento cinematográfico" in item["proposed_solution"].lower()
                            for item in bundle["changes"]))
        self._validate("creative-review.v0.1.schema.json", review)
        self._validate("visual-defects.v0.1.schema.json", visual_defects_contract(bundle))
        self._validate("recommended-changes.v0.1.schema.json", recommended_changes_contract(bundle))

    def test_export_is_proposal_only_and_hashes_every_file(self):
        bundle = create_review(self.con, self.video_id)
        exported = export_review_bundle(
            self.con, bundle["review"]["review_key"], self.root / "exports"
        )
        self.assertEqual(exported["status"], "EXPORTED")
        manifest_path = Path(exported["manifest"]["path"])
        exported_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertFalse(exported_manifest["auto_apply"])
        self.assertFalse(exported_manifest["write_into_agent_workspace"])
        for name, item in exported["files"].items():
            path = Path(item["path"])
            self.assertTrue(path.exists(), name)
            self.assertEqual(item["sha256"], sha256_file(path))

        brief = create_production_brief(
            self.con, bundle["changes"][0]["change_key"], "EP-TEST-REV"
        )
        self.assertEqual(brief["contract_version"], CONTRACT_PRODUCTION_BRIEF)
        self.assertEqual(brief["status"], "PROPOSAL_ONLY")
        self.assertFalse(brief["handoff"]["auto_apply"])
        self.assertFalse(brief["handoff"]["write_into_agent_workspace"])
        self.assertEqual(brief["handoff"]["mode"], "EXPLICIT_IMPORT_ONLY")
        self.assertFalse(brief["source_permission"]["derivative_allowed"])
        self.assertTrue(brief["data_policy"]["no_higgsfield_derived_training"])
        self._validate("production-brief.v0.1.schema.json", brief)

        handoff = export_production_brief(self.con, brief["brief_key"], self.root / "handoff")
        self.assertEqual(handoff["status"], "EXPORTED")
        out = Path(handoff["output_dir"])
        self.assertTrue((out / "README.md").exists())
        template = json.loads((out / "import-template.json").read_text(encoding="utf-8"))
        self.assertEqual(template["contract_version"], CONTRACT_EPISODE_VERSION)
        self.assertEqual(template["status"], "TO_BE_COMPLETED_BY_PRODUCER")
        handoff_manifest = json.loads(
            (out / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertTrue(handoff_manifest["explicit_import_required"])

    def test_version_import_requires_permission_root_and_never_overwrites(self):
        source = self._fixture()
        with self.assertRaises(ValueError):
            import_episode_version(self.con, "EP-TEST", source, "unknown",
                                   allowed_roots=[self.root])
        with self.assertRaises(ValueError):
            import_episode_version(self.con, "EP-TEST", source, "synthetic",
                                   allowed_roots=[self.root / "elsewhere"])
        before = sha256_file(source)
        contract = import_episode_version(
            self.con, "EP-TEST", source, "synthetic",
            allowed_roots=[self.root], version_label="EP-TEST-A",
        )
        self.assertEqual(contract["contract_version"], CONTRACT_EPISODE_VERSION)
        self.assertEqual(contract["overwrite_policy"], "NEVER_OVERWRITE")
        self.assertEqual(before, sha256_file(source))
        self._validate("episode-version.v0.1.schema.json", contract)
        duplicate = import_episode_version(
            self.con, "EP-TEST", source, "synthetic",
            allowed_roots=[self.root], version_label="EP-TEST-A-AGAIN",
        )
        self.assertEqual(duplicate["status"], "DUPLICATE")
        self.assertEqual(duplicate["version_key"], contract["version_key"])
        self.assertEqual(verify_version_integrity(self.con, contract["version_key"])["status"], "MATCH")
        version = get_episode_version(self.con, contract["version_key"])
        self.assertEqual(version["db"]["episode"], "EP-TEST")
        self.assertTrue(version["db"]["version_key"])

    def test_completed_import_contract_round_trip_and_hash_check(self):
        source = self._fixture()
        contract = {
            "contract_version": CONTRACT_EPISODE_VERSION,
            "status": "PRODUCER_COMPLETED",
            "episode": "EP-TEST",
            "version_label": "EP-TEST-CONTRACT",
            "file_path": str(source),
            "file_sha256": sha256_file(source),
            "permission_status": "synthetic",
            "provenance": "PRODUCER_DECLARED",
        }
        path = self.root / "completed.json"
        path.write_text(json.dumps(contract), encoding="utf-8")
        imported = import_version_contract(self.con, path, allowed_roots=[self.root])
        self.assertEqual(imported["version_key"].startswith("ver-"), True)
        bad = dict(contract)
        bad["file_sha256"] = "0" * 64
        bad_path = self.root / "bad.json"
        bad_path.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(ValueError):
            import_version_contract(self.con, bad_path, allowed_roots=[self.root])

    def test_comparison_preserves_missing_and_zero_and_never_declares_winner(self):
        a, b = self._import_pair()
        record_performance(
            self.con, a["version_key"], "Synthetic", "2026-11-17",
            {"views": 0, "likes": 0, "qualified_leads": 0, "meetings": None},
            provenance="USER_PROVIDED",
        )
        record_performance(
            self.con, b["version_key"], "Synthetic", "2026-11-17",
            {"views": 10, "likes": 2, "qualified_leads": None, "meetings": None},
            provenance="USER_PROVIDED",
        )
        comparison = compare_episode_versions(
            self.con, a["version_key"], b["version_key"], platform="Synthetic"
        )
        metrics = {item["name"]: item for item in comparison["metrics"]}
        self.assertEqual(metrics["views"]["a"]["value"], 0)
        self.assertTrue(metrics["views"]["a"]["is_zero"])
        self.assertEqual(metrics["views"]["delta_b_minus_a"], 10)
        self.assertEqual(metrics["views"]["comparability"], "COMPARABLE")
        self.assertIsNone(metrics["meetings"]["a"]["value"])
        self.assertTrue(metrics["meetings"]["a"]["is_missing"])
        self.assertEqual(metrics["meetings"]["comparability"], "BOTH_MISSING")
        self.assertIsNone(metrics["qualified_leads"]["b"]["value"])
        self.assertTrue(metrics["qualified_leads"]["b"]["is_missing"])
        self.assertEqual(metrics["qualified_leads"]["comparability"], "MISSING_B")
        self.assertIsNone(comparison["summary"]["automatic_winner"])
        self.assertFalse(comparison["summary"]["commercial_improvement_claimed"])
        self.assertTrue(comparison["summary"]["requires_real_measurement"])
        self._validate("performance-comparison.v0.1.schema.json", comparison)

    def test_likes_cannot_become_leads(self):
        a, _ = self._import_pair()
        with self.assertRaises(ValueError) as caught:
            record_performance(
                self.con, a["version_key"], "Synthetic", "2026-11-17",
                {"qualified_leads": 5}, provenance="PLATFORM_LIKES",
            )
        self.assertIn("likes_are_not_leads", str(caught.exception))
        with self.assertRaises(ValueError):
            record_performance(
                self.con, a["version_key"], "Synthetic", "2026-11-17",
                {"leads": 5}, provenance="USER_PROVIDED",
            )

    def test_human_evaluation_is_persisted_and_gate_isolated(self):
        a, b = self._import_pair()
        human = record_version_evaluation(
            self.con, b["version_key"], "reviewer-identified",
            visual_impact=4, realism=3, clarity=4, hook=4, narrative=4,
            business_value=3, cta=4, preference="B",
            compared_version_key=a["version_key"], confidence=0.8,
            provenance="human", notes="revisión de prueba",
        )
        self.assertTrue(human["gate_eligible"])
        self.assertFalse(human["counts_for_training_gate"])
        self.assertEqual(human["contract_version"], CONTRACT_HUMAN_EVALUATION)
        self._validate("human-evaluation.v0.1.schema.json", human)
        demo = record_version_evaluation(
            self.con, b["version_key"], "demo-operator",
            visual_impact=5, provenance="demo",
        )
        self.assertFalse(demo["gate_eligible"])
        anonymous = record_version_evaluation(
            self.con, b["version_key"], "anonymous",
            visual_impact=5, provenance="human",
        )
        self.assertFalse(anonymous["gate_eligible"])
        self.assertEqual(len(list_version_evaluations(self.con, b["version_key"])), 3)
        with self.assertRaises(ValueError):
            record_version_evaluation(
                self.con, b["version_key"], "reviewer-identified", visual_impact=6,
            )

    def test_approval_requires_named_human_and_updates_change_status(self):
        bundle = create_review(self.con, self.video_id)
        change_key = bundle["changes"][0]["change_key"]
        with self.assertRaises(ValueError):
            record_human_approval(
                self.con, "recommended_change", change_key, "APPROVED",
                "ai-assistant", provenance="ai_assisted",
            )
        with self.assertRaises(ValueError):
            record_human_approval(
                self.con, "recommended_change", change_key, "APPROVED", "anonymous",
            )
        approval = record_human_approval(
            self.con, "recommended_change", change_key, "APPROVED",
            "reviewer-identified", notes="aprobado para producir",
        )
        self.assertTrue(approval["gate_eligible"])
        self._validate("human-approval.v0.1.schema.json", approval)
        status = self.con.execute(
            "select status from recommended_changes where change_key=?", (change_key,)
        ).fetchone()[0]
        self.assertEqual(status, "APPROVED_FOR_PRODUCTION")

    def test_episode_version_activation_and_rollback_are_state_only(self):
        a, b = self._import_pair()
        self.assertEqual(
            activate_episode_version(self.con, a["version_key"])["status"],
            "ACTIVE_FOR_COMPARISON",
        )
        self.assertEqual(
            activate_episode_version(self.con, b["version_key"])["status"],
            "ACTIVE_FOR_COMPARISON",
        )
        self.assertEqual(
            self.con.execute(
                "select status from episode_versions where version_key=?",
                (a["version_key"],),
            ).fetchone()[0],
            "SUPERSEDED",
        )
        rolled = rollback_episode_version(self.con, a["version_key"])
        self.assertEqual(rolled["status"], "ROLLED_BACK")
        self.assertEqual(rolled["active_version"], a["version_key"])
        self.assertEqual(
            self.con.execute(
                "select status from episode_versions where version_key=?",
                (b["version_key"],),
            ).fetchone()[0],
            "ROLLED_BACK",
        )
        self.assertEqual(
            self.con.execute(
                "select status from episode_versions where version_key=?",
                (a["version_key"],),
            ).fetchone()[0],
            "ACTIVE_FOR_COMPARISON",
        )

    def test_integrity_detects_tampering_without_touching_active_work(self):
        source = self._fixture("original.mp4")
        copy = self.root / "copy.mp4"
        shutil.copy2(source, copy)
        contract = import_episode_version(
            self.con, "EP-TEST", copy, "synthetic",
            allowed_roots=[self.root], version_label="EP-TEST-COPY",
        )
        with copy.open("ab") as handle:
            handle.write(b"tamper")
        integrity = verify_version_integrity(self.con, contract["version_key"])
        self.assertEqual(integrity["status"], "HASH_MISMATCH")
        self.assertEqual(sha256_file(source), contract["file"]["sha256"])

    def test_training_gate_stays_blocked_after_loop_activity(self):
        a, b = self._import_pair()
        bundle = create_review(self.con, self.video_id)
        record_version_evaluation(
            self.con, b["version_key"], "reviewer-identified",
            visual_impact=4, clarity=4, provenance="human",
        )
        record_human_approval(
            self.con, "recommended_change", bundle["changes"][0]["change_key"],
            "APPROVED", "reviewer-identified",
        )
        gate = gate_report(self.con)
        self.assertEqual(gate["training_state"], "NO_TRAINING_INSUFFICIENT_DATA")
        self.assertEqual(gate["status"], "BLOCKED")
        self.assertIn("human_evaluations", {item["name"] for item in gate["blocking_reasons"]})

    def test_loop_status_and_v05_compatibility(self):
        bundle = create_review(self.con, self.video_id)
        brief = create_production_brief(self.con, bundle["changes"][0]["change_key"])
        self.assertEqual(brief["status"], "PROPOSAL_ONLY")
        status = loop_status(self.con)
        self.assertEqual(status["schema_version"], "0.6")
        self.assertEqual(status["counts"]["creative_reviews"], 1)
        self.assertEqual(status["counts"]["production_briefs"], 1)
        self.assertEqual(status["training_state"], "NO_TRAINING_INSUFFICIENT_DATA")

        attention = analyze_attention(self.con, self.video_id)
        self.assertEqual(attention["contract_version"], "attention-lab.v0.1")
        self.assertEqual(attention["status"], "ESTIMATE_ONLY_NOT_VALIDATED")
        other_id = add_video(
            self.con, "EP-OTHER", source_kind="synthetic", permission="synthetic",
            hook="Otra pregunta", cta="Comenta OTRA",
        )
        add_analysis(self.con, other_id)
        record_evaluation(
            self.con, self.video_id, evaluator_id="compat-reviewer",
            provenance="human", hook=4, clarity=4,
        )
        ab = ab_compare(self.con, self.video_id, other_id)
        self.assertEqual(ab["contract_version"], "ab-comparison.v0.1")
        self.assertIsNone(ab["summary"]["automatic_winner"])
        self._validate("ab-comparison.v0.1.schema.json", ab)
        version = plan_version(
            self.con, {"episode": "EP-TEST", "business_problem": "traceability"},
            "manifest", video_id=self.video_id,
        )
        rendered = render_version(self.con, version["version_key"], self.root / "production")
        self.assertEqual(rendered["status"], "RENDERED")
        self.assertFalse(rendered["manifest"]["generation"]["ai_generated"])
        self._validate("production-manifest.v0.1.schema.json", rendered["manifest"])


if __name__ == "__main__":
    unittest.main()
