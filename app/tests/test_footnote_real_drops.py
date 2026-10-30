"""The grounding footnote should fire only on a real content drop (#49).

Cosmetic-only reformatting (markdown stripped, indentation lost) must not
produce the "excerpts do not include that detail" footnote; an actual drop
(an unsupported fence, sentence, or technical token) must.
"""

import unittest

import llm.excerpts as excerpts
from llm.citations import correction_note

SOURCES = [
    {
        "text": (
            "Use event.type == login_failed and then:\n"
            "- name: Configure\n"
            "  hosts: routers"
        )
    }
]


class FootnoteScopedToRealDropsTests(unittest.TestCase):
    def test_cosmetic_only_change_produces_no_footnote(self):
        """Bold stripped and fence indentation lost, nothing unsupported removed."""
        shown = (
            "**Use** the filter `event.type == login_failed` and then:\n"
            "```yaml\n"
            "- name: Configure\n"
            "  hosts: routers\n"
            "```"
        )
        reply, dropped = excerpts.ground_library_reply(shown, SOURCES, "q")
        note = correction_note(dropped, reply, "q")
        self.assertIsNone(note)

    def test_real_drop_produces_footnote(self):
        """An unsupported fenced block is actually removed."""
        shown = (
            "Here is the filter.\n"
            "Use `event.type == login_failed` to narrow the list.\n"
            "```\n"
            "rm -rf /\n"
            "```"
        )
        reply, dropped = excerpts.ground_library_reply(shown, SOURCES, "q")
        note = correction_note(dropped, reply, "q")
        self.assertIsNotNone(note)


if __name__ == "__main__":
    unittest.main()
