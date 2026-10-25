import json
import tempfile
import unittest
from pathlib import Path

import httpx2 as httpx

from backend.convex_api import Convex, ConvexError


def recorder(responses):
    """A mock transport that answers in order and records each request."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responses.pop(0)(request)

    return calls, httpx.MockTransport(handler)


def ok(value):
    return lambda request: httpx.Response(200, json={"status": "success", "value": value, "logLines": []})


class ConvexClientTest(unittest.TestCase):
    def test_mutation_returns_value_and_adds_secret(self):
        calls, transport = recorder([ok({"id": "abc"})])
        convex = Convex("https://example.convex.cloud", "s3cret", transport=transport)
        self.assertEqual(convex.mutation("worker:claimNext", {}), {"id": "abc"})
        body = json.loads(calls[0].content)
        self.assertEqual(str(calls[0].url), "https://example.convex.cloud/api/mutation")
        self.assertEqual(body["path"], "worker:claimNext")
        self.assertEqual(body["args"], {"secret": "s3cret"})
        self.assertEqual(body["format"], "json")

    def test_error_reply_raises_with_message(self):
        reply = lambda request: httpx.Response(
            200, json={"status": "error", "errorMessage": "Uncaught ConvexError: Forbidden", "errorData": "Forbidden"})
        _, transport = recorder([reply])
        convex = Convex("https://example.convex.cloud", "bad", transport=transport)
        with self.assertRaises(ConvexError) as cm:
            convex.mutation("worker:failStale", {})
        self.assertIn("Forbidden", str(cm.exception))

    def test_upload_posts_bytes_and_returns_storage_id(self):
        upload = lambda request: httpx.Response(200, json={"storageId": "kg2abc"})
        calls, transport = recorder([ok("https://upload.example/xyz"), upload])
        convex = Convex("https://example.convex.cloud", "s3cret", transport=transport)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "video.mp4"
            path.write_bytes(b"fake mp4")
            self.assertEqual(convex.upload(path, "video/mp4"), "kg2abc")
        self.assertEqual(str(calls[1].url), "https://upload.example/xyz")
        self.assertEqual(calls[1].headers["content-type"], "video/mp4")
        self.assertEqual(calls[1].content, b"fake mp4")


if __name__ == "__main__":
    unittest.main()
