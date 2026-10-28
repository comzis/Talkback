"""Tests for the helpers behind ground_library_reply."""

import unittest

import llm.excerpts as excerpts
from llm.language import user_line

EXAMPLE_TEXT = (
    "Example 1: Find recent logins. Suppose you need failed logins. "
    "Use the filter event.type == login_failed to narrow the list."
)
SOURCES = [{"text": EXAMPLE_TEXT}]
BLOB = excerpts._source_blob(SOURCES)


class StructuredReplyTests(unittest.TestCase):
    def test_none_for_plain_question(self):
        self.assertIsNone(
            excerpts._structured_library_reply(SOURCES, "what is a login?")
        )

    def test_steps_come_first(self):
        result = excerpts._structured_library_reply(SOURCES, "explain the steps")
        self.assertEqual(
            result, excerpts._steps_from_sources(SOURCES, "explain the steps")
        )
        self.assertTrue(result.startswith("Example 1"))
        self.assertIn("1. ", result)

    def test_example_when_no_steps(self):
        query = "show an example filter"
        result = excerpts._structured_library_reply(SOURCES, query)
        self.assertEqual(result, excerpts._quote_example(SOURCES, query))

    def test_none_when_no_example_in_sources(self):
        self.assertIsNone(
            excerpts._structured_library_reply(
                [{"text": "Nothing relevant."}], "show an example"
            )
        )


class StripFencesTests(unittest.TestCase):
    def test_removes_unsupported_fence(self):
        text = "Run this.\n```\nrm -rf /\n```\nDone."
        self.assertEqual(
            excerpts._strip_unsupported_fences(text, BLOB), "Run this.\n\nDone."
        )

    def test_keeps_supported_fence(self):
        text = "Use:\n```\nevent.type == login_failed\n```"
        self.assertEqual(excerpts._strip_unsupported_fences(text, BLOB), text)


class KeepSentencesTests(unittest.TestCase):
    def test_drops_inventing_sentence(self):
        text = "Logins are listed. Use `secret_flag` to hide them."
        self.assertEqual(
            excerpts._keep_supported_sentences(text, BLOB), "Logins are listed."
        )

    def test_keeps_supported_sentence(self):
        text = "Use `event.type == login_failed` to narrow the list."
        self.assertEqual(excerpts._keep_supported_sentences(text, BLOB), text)

    def test_drops_bare_citation_markers(self):
        self.assertEqual(
            excerpts._keep_supported_sentences("Logins are listed.\n[1] [2]", BLOB),
            "Logins are listed.",
        )

    def test_empty_input(self):
        self.assertEqual(excerpts._keep_supported_sentences("", BLOB), "")


class ExampleLeadTests(unittest.TestCase):
    def test_drops_lead_without_example(self):
        cleaned = "Here is the filter.\nLogins are listed."
        self.assertEqual(
            excerpts._drop_ungrounded_example_leads(cleaned, BLOB),
            "Logins are listed.",
        )

    def test_keeps_lead_when_example_is_shown(self):
        cleaned = "Here is the filter.\nUse `event.type == login_failed` now."
        self.assertEqual(
            excerpts._drop_ungrounded_example_leads(cleaned, BLOB), cleaned
        )


class AppendExampleTests(unittest.TestCase):
    def test_unchanged_when_example_not_requested(self):
        self.assertEqual(
            excerpts._append_example_if_needed("Logins.", SOURCES, "what is a login?"),
            "Logins.",
        )

    def test_unchanged_when_example_already_shown(self):
        cleaned = "Use `event.type == login_failed` now."
        self.assertEqual(
            excerpts._append_example_if_needed(cleaned, SOURCES, "show an example"),
            cleaned,
        )

    def test_appends_quoted_example(self):
        query = "show an example"
        quoted = excerpts._quote_example(SOURCES, query)
        self.assertEqual(
            excerpts._append_example_if_needed("Logins.", SOURCES, query),
            f"Logins.\n{quoted}",
        )

    def test_quoted_example_replaces_empty_text(self):
        query = "show an example"
        self.assertEqual(
            excerpts._append_example_if_needed("", SOURCES, query),
            excerpts._quote_example(SOURCES, query),
        )

    def test_notice_when_no_example_exists(self):
        query = "show an example"
        notice = user_line("no_example", query)
        other = [{"text": "Nothing relevant."}]
        self.assertEqual(
            excerpts._append_example_if_needed("Logins.", other, query),
            f"Logins.\n{notice}",
        )
        self.assertEqual(excerpts._append_example_if_needed("", other, query), notice)


class OrNoDetailTests(unittest.TestCase):
    def test_returns_text_with_content(self):
        self.assertEqual(excerpts._or_no_detail("Logins [1]", "q"), "Logins [1]")

    def test_falls_back_when_only_citations(self):
        self.assertEqual(
            excerpts._or_no_detail("[1]", "q"), user_line("no_detail", "q")
        )
        self.assertEqual(excerpts._or_no_detail("", "q"), user_line("no_detail", "q"))


class GroundLibraryReplyTests(unittest.TestCase):
    def test_empty_answer_passes_through(self):
        self.assertEqual(excerpts.ground_library_reply("", SOURCES, "q"), "")

    def test_structured_reply_wins(self):
        query = "show an example"
        self.assertEqual(
            excerpts.ground_library_reply("anything", SOURCES, query),
            excerpts._quote_example(SOURCES, query),
        )

    def test_invented_content_is_removed(self):
        reply = excerpts.ground_library_reply(
            "Logins are listed. Use `secret_flag` to hide them.", SOURCES, "q"
        )
        self.assertEqual(reply, "Logins are listed.")


if __name__ == "__main__":
    unittest.main()
