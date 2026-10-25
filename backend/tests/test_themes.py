"""The chosen color theme must reach Claude, every build and the renderer (ported from
tests/test_video_themes.py, whose API and job-store tests predate Convex)."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as api_module, config, jobs
from backend.tests.test_worker import CODE, FakeAuthor, FakeConvex, fake_render

SCENE = CODE.replace('TITLE = "Ice"', 'TITLE = "Ice"\nTHEME = "paper"')


class ThemeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        patcher = mock.patch.object(config, "DATA_DIR", self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_theme_list_is_served(self):
        data = TestClient(api_module.app).get("/api/themes").json()
        self.assertEqual(data["default"], "bubble")
        self.assertEqual(len(data["themes"]), 6)

    def test_a_claimed_theme_reaches_claude_and_every_render(self):
        seen = {}

        class Recording(FakeAuthor):
            def write(self, topic, length, extra, theme="bubble", pdf=None):
                seen["theme"] = theme
                return SCENE

        render = mock.Mock(side_effect=fake_render(self.tmp))
        claimed = {"id": "v1", "topic": "Ice", "attempts": 0,
                   "options": {"length": "short", "quality": "low", "narration": True, "review": False,
                               "extra": "", "voice": "", "theme": "ocean"}}
        with mock.patch.object(jobs, "SceneAuthor", Recording), \
             mock.patch.object(jobs, "render_scene", render), \
             mock.patch.object(jobs, "make_thumbnail", lambda video, timings, out: Path(out).write_bytes(b"jpg")), \
             mock.patch.object(jobs, "suggest_tags", return_value=[]), \
             mock.patch.object(jobs, "suggest_chapters", return_value=[]):
            convex = FakeConvex()
            jobs.JobManager(convex).run(claimed)
        self.assertEqual(convex.updates()[-1]["fields"]["status"], "done")
        self.assertEqual(seen["theme"], "ocean")
        self.assertTrue(render.call_args_list)
        self.assertTrue(all(c.kwargs["theme"] == "ocean" for c in render.call_args_list))

    def test_repairs_keep_the_chosen_palette(self):
        manager = jobs.JobManager(FakeConvex())
        manager._update = mock.Mock()
        job = jobs.Job(id="repair", topic="Ice", options=jobs.JobOptions(theme="ocean"))
        job.dir.mkdir(parents=True)
        author = SimpleNamespace(repair=mock.Mock(return_value=SCENE.replace('"paper"', '"classic"')))
        ok = SimpleNamespace(ok=True, warnings=[])
        failure = SimpleNamespace(ok=False, error="Test failure", warnings=[])
        with mock.patch.object(jobs, "render_scene", side_effect=[failure, ok, ok]) as render:
            code, _ = manager._build(job, author, SCENE, budget=1, progress_span=(.2, .8))
        self.assertIn("THEME = 'ocean'", code)
        self.assertTrue(all(c.kwargs["theme"] == "ocean" for c in render.call_args_list))
        author.repair.assert_called_once()


if __name__ == "__main__":
    unittest.main()
