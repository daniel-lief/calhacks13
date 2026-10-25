import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend import jobs, worker
from backend.generator import GenerationError

CODE = 'from animai import *\nTITLE = "Ice"\nTAGS = ["chemistry", "water"]\n\nclass Explainer(AnimaiScene):\n    def construct(self):\n        with self.voiceover("Hi"):\n            pass\n'


class FakeConvex:
    """Records every call; hands out fake storage ids for uploads."""

    def __init__(self, jobs_to_claim=()):
        self.calls = []
        self.to_claim = list(jobs_to_claim)

    def mutation(self, path, args):
        self.calls.append((path, args))
        if path == "worker:claimNext":
            return self.to_claim.pop(0) if self.to_claim else None
        if path == "worker:failStale":
            return 0
        return None

    def upload(self, path, content_type):
        self.calls.append(("upload", {"name": Path(path).name, "type": content_type}))
        return f"storage-{Path(path).name}"

    def updates(self):
        return [args for path, args in self.calls if path == "worker:update"]


class FakeAuthor:
    def __init__(self, on_event):
        self.cost_usd = 0.01

    def write(self, topic, length, extra):
        return CODE

    def repair(self, problem, stage):
        return CODE

    def review(self, frames):
        return None


def fake_render(tmp: Path):
    def render_scene(scene_path, out_dir, **kwargs):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        video = out_dir / "explainer.mp4"
        video.write_bytes(b"mp4")
        timings = out_dir / "timings.json"
        timings.write_text(json.dumps({"segments": [{"index": 0, "text": "Hi", "start": 0, "end": 1}]}))
        return SimpleNamespace(ok=True, error=None, warnings=[], output_path=video,
                               timings_path=None if kwargs.get("dry_run") else timings)
    return render_scene


JOB = {"id": "vid1", "topic": "Why ice floats", "attempts": 0,
       "options": {"length": "short", "quality": "low", "narration": True, "review": False, "extra": "", "voice": ""}}


class WorkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        patches = [
            mock.patch.object(jobs.config, "DATA_DIR", self.tmp),
            mock.patch.object(jobs, "SceneAuthor", FakeAuthor),
            mock.patch.object(jobs, "render_scene", fake_render(self.tmp)),
            mock.patch.object(jobs, "make_thumbnail", lambda video, timings, out: Path(out).write_bytes(b"jpg")),
            mock.patch.object(jobs, "suggest_tags", lambda *a: ["fallback"]),
            mock.patch.object(jobs, "suggest_chapters", lambda *a: [{"start": 0, "title": "Intro"}]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_successful_run_uploads_files_and_finishes(self):
        convex = FakeConvex()
        jobs.JobManager(convex).run(dict(JOB))
        final = convex.updates()[-1]["fields"]
        self.assertEqual(final["status"], "done")
        attach = [args for path, args in convex.calls if path == "worker:attachFiles"]
        self.assertEqual(attach[-1]["files"]["video"], "storage-video.mp4")
        sent_tags = [u["fields"]["tags"] for u in convex.updates() if "tags" in u["fields"]]
        self.assertEqual(sent_tags[0], ["chemistry", "water"])
        self.assertFalse((self.tmp / "work" / "vid1").exists(), "scratch files are cleaned up")

    def test_generation_error_marks_the_video_failed(self):
        class Refusing(FakeAuthor):
            def write(self, *a):
                raise GenerationError("Claude declined to make a video about this topic.")

        convex = FakeConvex()
        with mock.patch.object(jobs, "SceneAuthor", Refusing):
            jobs.JobManager(convex).run(dict(JOB))
        final = convex.updates()[-1]["fields"]
        self.assertEqual(final["status"], "failed")
        self.assertEqual(final["error"], "Claude declined to make a video about this topic.")

    def test_run_forever_fails_stale_jobs_before_claiming(self):
        convex = FakeConvex()
        stop = threading.Event()
        original = convex.mutation

        def mutation(path, args):
            result = original(path, args)
            if path == "worker:claimNext":
                stop.set()
            return result

        convex.mutation = mutation
        worker.run_forever(convex, stop, poll_seconds=0)
        paths = [p for p, _ in convex.calls]
        self.assertEqual(paths[:2], ["worker:failStale", "worker:claimNext"])


if __name__ == "__main__":
    unittest.main()
