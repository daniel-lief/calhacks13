import base64
import unittest
from unittest import mock

from backend import prompts
from backend.generator import SceneAuthor


class WritePdfTest(unittest.TestCase):
    def capture(self, **kwargs):
        author = SceneAuthor.__new__(SceneAuthor)  # skip creating an API client
        with mock.patch.object(SceneAuthor, "_turn", autospec=True, return_value="code") as turn:
            author.write("Problem 3: projectile motion", "short", "", **kwargs)
        return turn.call_args.args[1]

    def test_without_a_pdf_the_request_is_plain_text(self):
        content = self.capture()
        self.assertTrue(content.startswith(prompts.initial_request("Problem 3: projectile motion", "short", "")))

    def test_the_chosen_theme_is_requested_with_or_without_a_pdf(self):
        self.assertIn('Set THEME = "ocean"', self.capture(theme="ocean"))
        self.assertIn('Set THEME = "ocean"', self.capture(theme="ocean", pdf=b"%PDF-1.7 fake")[1]["text"])

    def test_a_pdf_goes_first_as_a_document_then_the_topic(self):
        content = self.capture(pdf=b"%PDF-1.7 fake")
        self.assertEqual(content[0]["type"], "document")
        self.assertEqual(content[0]["source"]["media_type"], "application/pdf")
        self.assertEqual(base64.standard_b64decode(content[0]["source"]["data"]), b"%PDF-1.7 fake")
        text = content[1]["text"]
        self.assertIn("Problem 3: projectile motion", text)
        self.assertIn(prompts.PDF_GUIDANCE, text)

    def test_the_guidance_forbids_mentioning_the_document(self):
        for phrase in ("document", "PDF", "homework", "slides"):
            self.assertIn(phrase, prompts.PDF_GUIDANCE)


if __name__ == "__main__":
    unittest.main()
