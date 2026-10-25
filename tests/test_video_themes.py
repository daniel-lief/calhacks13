"""Palette selection must survive persistence, repairs and renderer boundaries."""
import ast
import importlib.util
import json
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend import app as api_module, config, renderer
from backend.jobs import Job, JobManager, JobOptions
from backend.themes import THEME_IDS, VIDEO_THEMES
from backend.validate import apply_scene_theme

ROOT = Path(__file__).resolve().parents[1]
SCENE = '''from animai import *
THEME = "paper"
class Explainer(AnimaiScene):
    def construct(self):
        with self.voiceover("A simple idea."):
            self.wait(1)
'''


class VideoThemeTests(unittest.TestCase):
    def test_palette_variants_change_colors_only(self):
        spec = importlib.util.spec_from_file_location("palette_definitions_test", ROOT / "animai/themes.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        base = asdict(module.THEMES["bubble"])
        for entry in VIDEO_THEMES:
            actual = asdict(module.THEMES[entry["id"]])
            for key, value in base.items():
                if key != "name" and key not in entry["colors"]:
                    self.assertEqual(actual[key], value, (entry["id"], key))
            self.assertEqual(actual["visual_style"], "bubble")
            self.assertEqual(actual["font"], "Fredoka")
            self.assertEqual(actual["mono_font"], "JetBrains Mono")
        self.assertEqual(len({module.THEMES[t].background for t in THEME_IDS}), len(THEME_IDS))

    def test_api_validates_and_passes_selection_to_job(self):
        client = TestClient(api_module.app)
        self.assertEqual(client.get("/api/themes").json()["default"], "bubble")
        self.assertEqual(len(client.get("/api/themes").json()["themes"]), 6)
        with patch.object(api_module.jobs, "create", return_value=object()) as create, \
             patch.object(api_module.jobs, "serialize", return_value={"id": "test"}):
            for selected in THEME_IDS:
                response = client.post("/api/jobs", json={"topic":"A simple idea", "theme":selected})
                self.assertEqual(response.status_code, 201)
                self.assertEqual(create.call_args.args[1].theme, selected)
                self.assertFalse(create.call_args.kwargs["public"])
            response = client.post("/api/jobs", json={"topic":"A simple idea"})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(create.call_args.args[1].theme, "bubble")
            create.reset_mock()
            for invalid in ["classic", "paper", "not-a-theme", "../ocean"]:
                self.assertEqual(client.post("/api/jobs", json={"topic":"A simple idea", "theme":invalid}).status_code, 422)
            create.assert_not_called()

    def test_selection_survives_saved_jobs_and_old_jobs_still_load(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(config, "JOBS_DIR", Path(temp)):
            manager = JobManager.__new__(JobManager)
            job = Job("saved", "Topic", JobOptions(theme="lavender"), status="done")
            manager._save(job)
            path = job.dir / "job.json"
            self.assertEqual(JobManager._read(path).options.theme, "lavender")
            old = json.loads(path.read_text(encoding="utf-8"))
            del old["options"]["theme"]
            path.write_text(json.dumps(old), encoding="utf-8")
            self.assertEqual(JobManager._read(path).options.theme, "bubble")

    def test_source_pinning_preserves_future_import_unicode_and_other_statements(self):
        source = '\"\"\"Café.\"\"\"\nfrom __future__ import annotations\nTITLE = "Café"; THEME = "paper"; N = 4  # keep\n'
        result = apply_scene_theme(source, "ocean")
        ast.parse(result)
        self.assertIn('TITLE = "Café"; THEME = \'ocean\'; N = 4  # keep', result)
        absent = '\"\"\"Doc.\"\"\"\nfrom __future__ import annotations\nN = 4\n'
        inserted = apply_scene_theme(absent, "rose")
        ast.parse(inserted)
        self.assertLess(inserted.index("from __future__"), inserted.index("THEME ="))
        self.assertIn("THEME = 'rose'", inserted)
        self.assertEqual(apply_scene_theme("def broken(", "ocean"), "def broken(")

    def test_repair_and_review_builds_force_the_same_palette(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(config, "JOBS_DIR", Path(temp)):
            manager = JobManager.__new__(JobManager)
            manager._update = Mock()
            job = Job("repair", "Topic", JobOptions(theme="ocean"))
            author = SimpleNamespace(repair=Mock(return_value=SCENE.replace('"paper"', '"classic"')))
            ok = SimpleNamespace(ok=True, warnings=[])
            failure = SimpleNamespace(ok=False, error="Test failure", warnings=[])
            with patch("backend.jobs.render_scene", side_effect=[failure, ok, ok, ok, ok]) as render:
                code, _ = manager._build(job, author, SCENE, budget=1, progress_span=(.2,.8))
                self.assertIn("THEME = 'ocean'", code)
                # A later visual review may produce a fresh file with the wrong constant.
                manager._build(job, author, SCENE, budget=0, progress_span=(.8,.99))
                self.assertTrue(all(c.kwargs["theme"] == "ocean" for c in render.call_args_list))
                self.assertTrue(all("THEME = 'ocean'" in c.args[0].read_text(encoding="utf-8") for c in render.call_args_list))
                author.repair.assert_called_once()

    def test_renderer_overrides_scene_constant_explicitly(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            source = out / "scene.py"
            source.write_text(SCENE, encoding="utf-8")
            (out / "explainer.mp4").write_bytes(b"test")
            process = Mock(stdout=[], returncode=0)
            with patch.object(renderer.subprocess, "Popen", return_value=process) as popen:
                self.assertTrue(renderer.render_scene(source, out, theme="meadow").ok)
            command = popen.call_args.args[0]
            self.assertEqual(command[command.index("--theme") + 1], "meadow")


if __name__ == "__main__":
    unittest.main()
