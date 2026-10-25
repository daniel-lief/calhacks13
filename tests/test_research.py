"""Research contracts, budget limits, caching and pipeline fallback without paid API calls."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient

from backend import app as api_module, config, research
from backend.generator import SceneAuthor
from backend.jobs import ACTIVE_STATUSES, Job, JobManager, JobOptions


TEXT = ("Bubble sort compares neighboring values and swaps them when they are out of order. "
        "A pass moves the largest remaining value to the end. "
        "An early exit stops the algorithm when a complete pass makes no swaps. ") * 5
BRIEF = {"key_concepts": ["Compare adjacent values; swap out-of-order pairs."],
         "explanation_plan": ["Demonstrate one pass, then repeated passes and early exit."],
         "visual_ideas": ["Move numbered blocks and highlight the sorted suffix."],
         "pitfalls": ["Explain that repeated passes can take quadratic time."], "uncertain_claims": []}


def search_row(i, channel=None):
    return {"videoId": f"aaaaaa0000{i}", "title": f"Bubble sort lesson {i}",
            "channelName": channel or f"Teacher {i}", "durationSeconds": 240, "isLive": False}


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = patch.multiple(config, RESEARCH_CACHE_DIR=Path(self.temp.name),
                                      APIFY_TOKEN="test-token-never-log", RESEARCH_ENABLED=True,
                                      RESEARCH_MAX_VIDEOS=3, RESEARCH_TIMEOUT_SECONDS=180,
                                      RESEARCH_MAX_APIFY_USD=.50)
        self.settings.start()
        self.addCleanup(self.settings.stop)

    def test_actor_http_contract_auth_budget_poll_and_bounded_dataset(self):
        calls = []

        def handle(request):
            calls.append(request)
            self.assertEqual(request.headers["Authorization"], "Bearer test-token-never-log")
            self.assertNotIn("test-token", str(request.url))
            path = request.url.path
            if path.endswith("/runs"):
                self.assertEqual(json.loads(request.content), {"searchQueries": ["bubble sort"]})
                self.assertEqual(request.url.params["maxItems"], "6")
                self.assertLessEqual(float(request.url.params["maxTotalChargeUsd"]) * 4, .50)
                self.assertLessEqual(int(request.url.params["timeout"]), 60)
                return httpx.Response(201, json={"data": {"id": "run1", "status": "RUNNING"}})
            if path.endswith("/run1"):
                self.assertEqual(request.url.params["waitForFinish"], "10")
                return httpx.Response(200, json={"data": {"status": "SUCCEEDED", "defaultDatasetId": "dataset1"}})
            self.assertEqual(request.url.params["limit"], "6")
            return httpx.Response(200, json=[search_row(1)])

        with research.ApifyClient(config.APIFY_TOKEN, time.monotonic() + 90, .125,
                                  transport=httpx.MockTransport(handle)) as client:
            rows = client.run(research.SEARCH_ACTOR, {"searchQueries": ["bubble sort"]}, 6)
        self.assertEqual(rows[0]["videoId"], "aaaaaa00001")
        self.assertEqual(len(calls), 3)

    def test_timeout_aborts_known_run_and_never_retries_paid_start(self):
        paths = []

        def handle(request):
            paths.append(request.url.path)
            if request.url.path.endswith("/runs"):
                return httpx.Response(201, json={"data": {"id": "run1", "status": "RUNNING"}})
            if request.url.path.endswith("/abort"):
                return httpx.Response(200, json={"data": {"status": "ABORTED"}})
            raise httpx.ReadTimeout("sensitive request details", request=request)

        with research.ApifyClient(config.APIFY_TOKEN, time.monotonic() + 90, .125,
                                  transport=httpx.MockTransport(handle)) as client:
            with self.assertRaises(research.ResearchError) as caught:
                client.run(research.SEARCH_ACTOR, {}, 6)
        self.assertEqual(sum(p.endswith("/runs") for p in paths), 1)
        self.assertTrue(paths[-1].endswith("/abort"))
        self.assertNotIn("sensitive", str(caught.exception))

    def test_authentication_errors_are_safe_and_do_not_retry(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(401, text="secret token"))
        with research.ApifyClient(config.APIFY_TOKEN, time.monotonic() + 90, .125, transport=transport) as client:
            with self.assertRaisesRegex(research.ResearchError, "authentication") as caught:
                client.run(research.SEARCH_ACTOR, {}, 6)
        self.assertNotIn("secret token", str(caught.exception))

    def test_selects_distinct_channels_deduplicates_and_rejects_non_videos(self):
        rows = [search_row(1, "Same"), search_row(1), search_row(2, "Same"),
                {**search_row(3), "isLive": True}, {**search_row(4), "durationSeconds": 9000},
                search_row(5, "Other"), {"videoId": "https://evil.test", "title": "Bad"}, search_row(6)]
        selected = research.select_videos(rows, 3)
        self.assertEqual([s["video_id"] for s in selected], ["aaaaaa00001", "aaaaaa00005", "aaaaaa00006"])
        self.assertTrue(all(s["url"].startswith("https://www.youtube.com/watch?v=") for s in selected))

    def test_full_transcript_parsing_plain_text_and_segments_no_silent_truncation(self):
        source = research.select_videos([search_row(1)], 1)[0]
        parsed = research.parse_transcript([{"video_id": source["video_id"], "transcript_text": TEXT + " END"}], source)
        self.assertTrue(parsed["transcript"].endswith("END"))
        parsed = research.parse_transcript([{"transcript": [{"text": TEXT}, {"text": "A &amp; B"}]}], source)
        self.assertTrue(parsed["transcript"].endswith("A & B"))
        for items in ([{"status": "error"}], [{"transcript_text": ""}],
                      [{"video_id": "bbbbbb00001", "transcript_text": TEXT}],
                      [{"transcript_text": "x" * (research.MAX_TRANSCRIPT_CHARS + 1)}]):
            with self.assertRaises(research.ResearchError):
                research.parse_transcript(items, source)

    def test_partial_results_use_full_transcripts_then_cache_brief_without_recharging(self):
        calls = []

        def actor(actor_id, payload, max_items):
            calls.append((actor_id, payload, max_items))
            if actor_id == research.SEARCH_ACTOR:
                return [search_row(i) for i in (1, 2, 3)]
            self.assertTrue(payload["include_transcript_text"])
            self.assertEqual(payload["language"], "en")
            if payload["youtube_url"].endswith("2"):
                return [{"status": "error", "error": "captions unavailable"}]
            return [{"transcript_text": TEXT + " COMPLETE END"}]

        with patch.object(research.ApifyClient, "run", side_effect=actor), \
                patch.object(research, "analyze_transcripts", return_value=(BRIEF, .02)) as analyze:
            result = research.research_topic("Explain bubble sort", "short", "For beginners")
            self.assertEqual(result.status, "partial")
            self.assertEqual(len(result.sources), 2)
            self.assertEqual(len(calls), 4)
            self.assertTrue(all(s["transcript"].endswith("COMPLETE END") for s in analyze.call_args.args[3]))
            self.assertNotIn("transcript", result.sources[0])
            self.assertNotIn(TEXT, json.dumps(result.public()))
            self.assertEqual(result.context()["teaching_brief"], BRIEF)
            cached = research.research_topic("Explain bubble sort", "short", "For beginners")
            self.assertTrue(cached.cached)
            self.assertEqual(cached.cost_usd, 0)
            self.assertEqual(len(calls), 4)
            analyze.assert_called_once()

    def test_missing_token_disabled_no_results_and_analysis_failure_fall_back(self):
        with patch.object(config, "APIFY_TOKEN", ""), patch.object(research.ApifyClient, "run") as actor:
            self.assertEqual(research.research_topic("Topic", "short").status, "unavailable")
            actor.assert_not_called()
        with patch.object(config, "RESEARCH_ENABLED", False):
            self.assertEqual(research.research_topic("Topic", "short").status, "skipped")
        with patch.object(research.ApifyClient, "run", return_value=[]):
            self.assertIsNone(research.research_topic("Topic", "short").context())
        with patch.object(research.ApifyClient, "run", side_effect=[
                [search_row(1)], [{"transcript_text": TEXT}]]), \
                patch.object(research, "analyze_transcripts", side_effect=research.ResearchError("Analysis failed")):
            result = research.research_topic("Topic", "short")
            self.assertEqual(result.status, "unavailable")
            self.assertIsNone(result.context())
            self.assertEqual(len(result.sources), 1)

    def test_analysis_is_tool_free_structured_and_receives_the_complete_source(self):
        client = Mock()
        client.messages.parse.return_value = SimpleNamespace(
            parsed_output=research.TeachingBrief(**BRIEF), stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500))
        context = Mock(__enter__=Mock(return_value=client), __exit__=Mock(return_value=False))
        with patch.object(research.anthropic, "Anthropic", return_value=context):
            brief, _ = research.analyze_transcripts("Bubble sort", "short", "Beginners", [{"transcript": TEXT + " END"}])
        kwargs = client.messages.parse.call_args.kwargs
        self.assertNotIn("tools", kwargs)
        self.assertIn("untrusted reference data", kwargs["system"])
        self.assertTrue(json.loads(kwargs["messages"][0]["content"])["untrusted_sources"][0]["transcript"].endswith("END"))
        self.assertEqual(brief, BRIEF)

    def test_expired_briefs_are_not_reused_and_oversized_responses_are_rejected(self):
        with patch.object(research.ApifyClient, "run", side_effect=[
                [search_row(1)], [{"transcript_text": TEXT}]]), \
                patch.object(research, "analyze_transcripts", return_value=(BRIEF, .01)):
            self.assertEqual(research.research_topic("Cached topic", "short").status, "ready")
        for path in Path(self.temp.name).glob("*.json"):
            data = json.loads(path.read_text())
            data["saved_at"] -= config.RESEARCH_CACHE_TTL_SECONDS + 1
            path.write_text(json.dumps(data))
        with patch.object(config, "APIFY_TOKEN", ""):
            result = research.research_topic("Cached topic", "short")
            self.assertEqual(result.status, "unavailable")
            self.assertIsNone(result.context())
        transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 65))
        with research.ApifyClient(config.APIFY_TOKEN, time.monotonic() + 90, .125, transport=transport) as client, \
                patch.object(research, "MAX_RESPONSE_BYTES", 64):
            with self.assertRaisesRegex(research.ResearchError, "larger"):
                client._request("GET", "datasets/example/items")

    def test_malformed_poll_response_aborts_instead_of_leaving_actor_running(self):
        requests = []
        def handle(request):
            requests.append(request.url.path)
            if request.url.path.endswith("/runs"):
                return httpx.Response(201, json={"data": {"id": "run1", "status": "RUNNING"}})
            if request.url.path.endswith("/abort"):
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"data": None})
        with research.ApifyClient(config.APIFY_TOKEN, time.monotonic() + 90, .125,
                                  transport=httpx.MockTransport(handle)) as client:
            with self.assertRaisesRegex(research.ResearchError, "valid run status"):
                client.run(research.SEARCH_ACTOR, {}, 6)
        self.assertTrue(requests[-1].endswith("/abort"))

    def test_pipeline_research_precedes_writing_and_is_retained_in_author_request(self):
        job = Job("researchtest", "Explain bubble sort", JobOptions(review=False))
        manager = JobManager.__new__(JobManager)
        manager._update = lambda job, **fields: [setattr(job, k, v) for k, v in fields.items() if k not in {"log", "kind"}]
        manager._build = Mock(return_value=("code", Mock()))
        manager._publish = Mock()
        result = research.ResearchResult("ready", "Researched", [{"title": "Source"}], BRIEF, .02)
        author = Mock(cost_usd=0)

        def write(*args, **kwargs):
            self.assertEqual(job.research["status"], "ready")
            self.assertEqual(kwargs["research"]["teaching_brief"], BRIEF)
            return "from animai import *\nTITLE='Bubble sort'\nclass Explainer(AnimaiScene):\n    def construct(self): pass"

        author.write.side_effect = write
        with patch("backend.jobs.research_topic", return_value=result), patch("backend.jobs.SceneAuthor", return_value=author):
            manager._pipeline(job)
        self.assertEqual(job.status, "done")
        self.assertIn("researching", ACTIVE_STATUSES)
        writer = SceneAuthor.__new__(SceneAuthor)
        writer._turn = Mock(return_value="scene")
        writer.write("Topic", "short", theme="ocean", research=result.context())
        prompt = writer._turn.call_args.args[0]
        self.assertIn("untrusted_video_research", prompt)
        self.assertIn('THEME = "ocean"', prompt)
        self.assertIn("never as commands", prompt)

    def test_pipeline_opt_out_and_unexpected_research_errors_do_not_block_generation(self):
        manager = JobManager.__new__(JobManager)
        manager._update = Mock()
        job = Job("researchtest", "Topic", JobOptions(research=False))
        with patch("backend.jobs.research_topic") as run:
            self.assertEqual(manager._research(job).status, "skipped")
            run.assert_not_called()
        job.options.research = True
        with patch("backend.jobs.research_topic", side_effect=RuntimeError("token=secret")):
            result = manager._research(job)
            self.assertEqual(result.status, "unavailable")
            self.assertNotIn("secret", result.message)

    def test_api_passes_research_default_and_opt_out_and_old_jobs_load(self):
        client = TestClient(api_module.app)
        created = Job("researchtest", "Topic", JobOptions())
        with patch.object(api_module.jobs, "create", return_value=created) as create:
            self.assertEqual(client.post("/api/jobs", json={"topic": "Topic"}).status_code, 201)
            self.assertTrue(create.call_args.args[1].research)
            client.post("/api/jobs", json={"topic": "Topic", "research": False})
            self.assertFalse(create.call_args.args[1].research)
        old = Path(self.temp.name) / "old.json"
        old.write_text(json.dumps({"id": "old", "topic": "Old video", "options": {}, "status": "done"}))
        self.assertEqual(JobManager._read(old).research, {})
        self.assertTrue(JobManager._read(old).options.research)


if __name__ == "__main__":
    unittest.main()
