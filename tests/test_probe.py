from __future__ import annotations
import json, subprocess, tempfile, unittest
from pathlib import Path
from vlux_ci.probe import probe
from vlux_ci.analyzer import analyze

class TestProbe(unittest.TestCase):
    def test_corrupt_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'bad.mp4'; f.write_bytes(b'not a video')
            with self.assertRaises(ValueError): probe(f)
    def test_no_audio_is_valid_if_video_exists(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'silent.mp4'
            subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=blue:s=64x64:d=0.4','-an','-pix_fmt','yuv420p',str(f)],capture_output=True,check=True)
            m=probe(f); self.assertFalse(m['has_audio']); self.assertEqual(m['width'],64)
    def test_analysis_returns_timeline_and_observation_contract(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'static.mp4'
            subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=blue:s=64x64:d=2.2','-an','-pix_fmt','yuv420p',str(f)],capture_output=True,check=True)
            objective, estimated, observations = analyze(f)
            self.assertIn("timeline", objective)
            self.assertIn("scene_3d_note", estimated)
            self.assertTrue(any(x["category"] == "static_visual" for x in observations))
if __name__=='__main__': unittest.main()
