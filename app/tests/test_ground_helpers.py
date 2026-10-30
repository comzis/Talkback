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
        cleaned, dropped = excerpts._strip_unsupported_fences(text, BLOB)
        self.assertEqual(cleaned, "Run this.\n\nDone.")
        self.assertEqual(dropped, ["rm -rf /"])

    def test_keeps_supported_fence(self):
        text = "Use:\n```\nevent.type == login_failed\n```"
        cleaned, dropped = excerpts._strip_unsupported_fences(text, BLOB)
        self.assertEqual(cleaned, text)
        self.assertEqual(dropped, [])


class KeepSentencesTests(unittest.TestCase):
    def test_drops_inventing_sentence(self):
        text = "Logins are listed. Use `secret_flag` to hide them."
        cleaned, dropped = excerpts._keep_supported_sentences(text, BLOB)
        self.assertEqual(cleaned, "Logins are listed.")
        self.assertEqual(dropped, ["Use `secret_flag` to hide them."])

    def test_keeps_supported_sentence(self):
        text = "Use `event.type == login_failed` to narrow the list."
        cleaned, dropped = excerpts._keep_supported_sentences(text, BLOB)
        self.assertEqual(cleaned, text)
        self.assertEqual(dropped, [])

    def test_drops_bare_citation_markers(self):
        cleaned, dropped = excerpts._keep_supported_sentences(
            "Logins are listed.\n[1] [2]", BLOB
        )
        self.assertEqual(cleaned, "Logins are listed.")
        self.assertEqual(dropped, [])

    def test_empty_input(self):
        cleaned, dropped = excerpts._keep_supported_sentences("", BLOB)
        self.assertEqual(cleaned, "")
        self.assertEqual(dropped, [])


class ExampleLeadTests(unittest.TestCase):
    def test_drops_lead_without_example(self):
        cleaned = "Here is the filter.\nLogins are listed."
        result, dropped = excerpts._drop_ungrounded_example_leads(cleaned, BLOB)
        self.assertEqual(result, "Logins are listed.")
        self.assertEqual(dropped, ["Here is the filter."])

    def test_keeps_lead_when_example_is_shown(self):
        cleaned = "Here is the filter.\nUse `event.type == login_failed` now."
        result, dropped = excerpts._drop_ungrounded_example_leads(cleaned, BLOB)
        self.assertEqual(result, cleaned)
        self.assertEqual(dropped, [])


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
        reply, dropped = excerpts.ground_library_reply("", SOURCES, "q")
        self.assertEqual(reply, "")
        self.assertEqual(dropped, [])

    def test_structured_reply_wins(self):
        query = "show an example"
        reply, dropped = excerpts.ground_library_reply("anything", SOURCES, query)
        self.assertEqual(reply, excerpts._quote_example(SOURCES, query))
        self.assertEqual(dropped, [])

    def test_invented_content_is_removed(self):
        reply, dropped = excerpts.ground_library_reply(
            "Logins are listed. Use `secret_flag` to hide them.", SOURCES, "q"
        )
        self.assertEqual(reply, "Logins are listed.")
        self.assertEqual(dropped, ["Use `secret_flag` to hide them."])

    def test_cosmetic_only_change_has_empty_drop_report(self):
        """Stripped bold and fence indentation lost, nothing unsupported removed."""
        shown = (
            "**Use** the filter `event.type == login_failed` and then:\n"
            "```yaml\n"
            "- name: Configure\n"
            "  hosts: routers\n"
            "```"
        )
        sources = [
            {
                "text": (
                    "Use event.type == login_failed and then:\n"
                    "- name: Configure\n"
                    "  hosts: routers"
                )
            }
        ]
        _reply, dropped = excerpts.ground_library_reply(shown, sources, "q")
        self.assertEqual(dropped, [])

    def test_real_drop_has_non_empty_drop_report(self):
        """An unsupported fenced block is actually removed."""
        shown = (
            "Here is the filter.\n"
            "Use `event.type == login_failed` to narrow the list.\n"
            "```\n"
            "rm -rf /\n"
            "```"
        )
        _reply, dropped = excerpts.ground_library_reply(shown, SOURCES, "q")
        self.assertEqual(dropped, ["rm -rf /"])


if __name__ == "__main__":
    unittest.main()
