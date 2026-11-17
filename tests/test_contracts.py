from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from validate_contracts import validate
from vlux_ci.ab import compare, record_evaluation
from vlux_ci.attention import analyze_attention
from vlux_ci.db import connect
from vlux_ci.learning import training_status
from vlux_ci.production import plan_version, render_version
from factory import add_analysis, add_publication, add_video


class TestContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.con = connect(Path(self.temp.name) / "contracts.sqlite")

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    def _schema(self, name):
        return json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))

    def test_v05_contracts_validate(self):
        a = add_video(self.con, "SYN-A", source_kind="synthetic", permission="synthetic")
        b = add_video(self.con, "SYN-B", source_kind="synthetic", permission="synthetic")
        add_analysis(self.con, a)
        add_analysis(self.con, b)
        add_publication(self.con, "SYN-A", video_id=a, metrics=[
            ("likes", 80, "OBSERVED"),
            ("likes", 80, "OBSERVED"),
            ("views", 1000, "OBSERVED"),
        ])
        record_evaluation(
            self.con, a, evaluator_id="contract-reviewer", provenance="human",
            hook=4, narrative=4, production=4, commercial=3, cta=4, clarity=4,
            confidence=0.8, evaluated_at="2026-11-17T12:00:00+00:00",
        )
        attention = analyze_attention(self.con, a)
        ab = compare(self.con, a, b)
        learning = training_status(self.con)
        brief = {
            "contract_version": "creative-director.v0.2", "episode": "SYN-A",
            "topic": "traceability", "business_problem": "Manual copying costs hours.",
            "recommended_hook": "How many hours do you lose?", "target_duration_s": 6,
        }
        version = plan_version(self.con, brief, "manifest", video_id=a)
        rendered = render_version(self.con, version["version_key"], Path(self.temp.name) / "out")

        validate(attention, self._schema("attention-lab.v0.1.schema.json"))
        validate(ab, self._schema("ab-comparison.v0.1.schema.json"))
        validate(learning, self._schema("learning-gate.v0.1.schema.json"))
        validate(rendered["manifest"], self._schema("production-manifest.v0.1.schema.json"))

        self.assertEqual(attention["results"]["likes_observed"], 80)
        self.assertEqual(attention["results"]["observed_metrics"], 2)
        self.assertIsNone(ab["summary"]["automatic_winner"])
        self.assertEqual(learning["training_state"], "NO_TRAINING_INSUFFICIENT_DATA")
        self.assertFalse(rendered["manifest"]["generation"]["ai_generated"])


if __name__ == "__main__":
    unittest.main()
