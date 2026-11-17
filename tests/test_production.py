from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from vlux_ci.db import connect
from vlux_ci.probe import probe
from vlux_ci.production import (
    activate_version, get_version, history, list_versions, plan_version,
    render_version, rollback_version, summary,
)

BRIEF = {
    "contract_version": "creative-director.v0.2",
    "episode": "EP-TEST",
    "topic": "trazabilidad",
    "business_problem": "Los datos se copian a mano y cuestan horas.",
    "target_audience": "directores de operaciones",
    "recommended_hook": "¿Cuántas horas pierdes copiando datos?",
    "cta_primary": "Solicita un diagnóstico del flujo.",
}


class TestProduction(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        self.con = connect(self.root / "production.sqlite")

    def tearDown(self):
        self.con.close()
        self.t.cleanup()

    def test_manifest_version_activation_and_rollback(self):
        first = plan_version(self.con, BRIEF, "manifest")
        self.assertEqual(first["status"], "candidate")
        rendered = render_version(self.con, first["version_key"], self.root / "out")
        self.assertEqual(rendered["status"], "RENDERED")
        manifest = json.loads(Path(rendered["output_path"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "PLACEHOLDER_NO_RENDER")
        self.assertFalse(manifest["generation"]["ai_generated"])
        self.assertFalse(manifest["generation"]["gpu_used"])
        self.assertTrue(manifest["scenes"])
        activated = activate_version(self.con, first["version_key"])
        self.assertEqual(activated["status"], "ACTIVATED")

        second = plan_version(self.con, {**BRIEF, "episode": "EP-TEST-B"},
                              "manifest", parent_version_id=first["id"])
        second_render = render_version(self.con, second["version_key"], self.root / "out")
        self.assertEqual(second_render["status"], "RENDERED")
        self.assertEqual(activate_version(self.con, second["version_key"])["status"], "ACTIVATED")
        self.assertEqual(get_version(self.con, first["version_key"])["status"], "superseded")
        rolled = rollback_version(self.con, first["version_key"])
        self.assertEqual(rolled["status"], "ROLLED_BACK")
        self.assertEqual(get_version(self.con, first["version_key"])["status"], "active")
        self.assertEqual(get_version(self.con, second["version_key"])["status"], "rolled_back")
        chain = history(self.con, first["version_key"])["chain"]
        self.assertTrue(chain)

    def test_activation_requires_render(self):
        version = plan_version(self.con, BRIEF, "manifest")
        result = activate_version(self.con, version["version_key"])
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason"], "RENDER_REQUIRED_BEFORE_ACTIVATION")

    def test_animatic_is_cpu_placeholder(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg unavailable")
        version = plan_version(self.con, BRIEF, "ffmpeg_animatic")
        result = render_version(self.con, version["version_key"], self.root / "out")
        self.assertEqual(result["status"], "RENDERED", result)
        output = Path(result["output_path"])
        self.assertTrue(output.exists())
        meta = probe(output)
        self.assertEqual(meta["width"], 540)
        self.assertEqual(meta["height"], 960)
        self.assertFalse(result["manifest"]["generation"]["ai_generated"])
        self.assertFalse(result["manifest"]["generation"]["gpu_used"])
        self.assertEqual(result["manifest"]["audio"]["status"], "SILENT")

    def test_unknown_adapter_and_missing_brief_are_rejected(self):
        with self.assertRaises(ValueError):
            plan_version(self.con, BRIEF, "external_paid_api")
        with self.assertRaises(ValueError):
            plan_version(self.con, {}, "manifest")

    def test_summary_lists_only_local_adapters(self):
        plan_version(self.con, BRIEF, "manifest")
        result = summary(self.con)
        self.assertEqual(set(result["adapters"]), {"manifest", "ffmpeg_animatic"})
        self.assertTrue(any("GPU" in item for item in result["guardrails"]))


if __name__ == "__main__":
    unittest.main()
