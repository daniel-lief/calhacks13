import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module
from backend import attachments
from backend.tests.test_attachments import pdf


class UploadTest(unittest.TestCase):
    def setUp(self):
        attachments._store.clear()
        # No worker thread in these tests
        patcher = mock.patch.object(app_module, "convex_configured", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(app_module.app)

    def upload(self, data: bytes, token: str | None = "good"):
        headers = {"Content-Type": "application/pdf"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.post("/api/attachments", content=data, headers=headers)

    def signed_in(self):
        return mock.patch.object(app_module, "user_for_token",
                                 side_effect=lambda t: {"username": "alice"} if t == "good" else None)

    def test_signed_in_upload_returns_a_token_for_the_pdf(self):
        with self.signed_in():
            r = self.upload(pdf(2))
        self.assertEqual(r.status_code, 201)
        token = r.json()["token"]
        self.assertEqual(attachments.take(token), pdf(2))

    def test_signed_out_upload_is_refused(self):
        with self.signed_in():
            self.assertEqual(self.upload(pdf(2), token=None).status_code, 401)
            self.assertEqual(self.upload(pdf(2), token="stale").status_code, 401)
        self.assertEqual(attachments._store, {})

    def test_non_pdf_is_refused_with_its_reason(self):
        with self.signed_in():
            r = self.upload(b"not a pdf")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "That file isn't a PDF")

    def test_too_many_pages_is_refused(self):
        with self.signed_in():
            r = self.upload(pdf(51))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "PDFs can be up to 20 MB and 50 pages")


if __name__ == "__main__":
    unittest.main()
