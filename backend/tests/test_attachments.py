import unittest
from unittest import mock

from backend import attachments


def pdf(pages: int, size: int = 0) -> bytes:
    body = b"".join(b"%d 0 obj << /Type /Page /Parent 1 0 R >> endobj\n" % (i + 2) for i in range(pages))
    data = b"%PDF-1.7\n1 0 obj << /Type /Pages /Count " + str(pages).encode() + b" >> endobj\n" + body + b"%%EOF"
    return data + b" " * max(0, size - len(data))


class ValidateTest(unittest.TestCase):
    def test_accepts_a_small_pdf(self):
        self.assertIsNone(attachments.problem_with(pdf(3)))

    def test_rejects_non_pdfs(self):
        self.assertEqual(attachments.problem_with(b"hello world"), "That file isn't a PDF")

    def test_rejects_too_many_pages(self):
        self.assertEqual(attachments.problem_with(pdf(51)), "PDFs can be up to 20 MB and 50 pages")

    def test_rejects_too_large(self):
        self.assertEqual(attachments.problem_with(pdf(1, size=20 * 1024 * 1024 + 1)),
                         "PDFs can be up to 20 MB and 50 pages")


class StoreTest(unittest.TestCase):
    def setUp(self):
        attachments._store.clear()

    def test_take_returns_the_pdf_once(self):
        token = attachments.put(b"%PDF-data")
        self.assertRegex(token, r"^[A-Za-z0-9_-]{16,64}$")
        self.assertEqual(attachments.take(token), b"%PDF-data")
        self.assertIsNone(attachments.take(token))

    def test_unknown_token_returns_none(self):
        self.assertIsNone(attachments.take("nope"))

    def test_pdfs_expire_after_30_minutes(self):
        with mock.patch.object(attachments.time, "monotonic", return_value=1000.0):
            token = attachments.put(b"%PDF-data")
        with mock.patch.object(attachments.time, "monotonic", return_value=1000.0 + 30 * 60 + 1):
            self.assertIsNone(attachments.take(token))


if __name__ == "__main__":
    unittest.main()
