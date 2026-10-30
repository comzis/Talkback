"""Answer display: short corrections, citation cleanup, card renumbering."""

import unittest

import llm.prompts as prompts


class DisplayCitationTests(unittest.TestCase):
    def test_correction_note_is_short_never_the_full_reply(self):
        reply = "The level is -23.0 LUFS. [1]"
        note = prompts.correction_note(
            ["The level is -99 LUFS. [1]"], reply, "What loudness?"
        )
        self.assertIsNotNone(note)
        self.assertEqual(note, prompts.user_line("no_detail", "What loudness?"))
        self.assertNotIn("-23.0", note)
        self.assertIsNone(prompts.correction_note([], reply, "What loudness?"))

    def test_finalize_citations_drops_dead_markers_and_renumbers(self):
        answer = (
            "Greedy algorithms make a sequence of choices. [1] "
            "Dynamic programming stores subproblem answers. [2] "
            "Network flow is covered later. [5] "
            "An unused claim. [6] "
            "[1] [2] [5] [6] [1] [2] [5]"
        )
        sources = [
            {"number": 1, "source": "a.pdf", "text": "greedy", "page": "1"},
            {"number": 2, "source": "a.pdf", "text": "dynamic", "page": "2"},
            {"number": 5, "source": "a.pdf", "text": "flow", "page": "5"},
        ]
        text, cards = prompts.finalize_citations(answer, sources)
        self.assertNotIn("[6]", text)
        self.assertNotIn("[5]", text)
        self.assertEqual(cards[0]["number"], 1)
        self.assertEqual(cards[1]["number"], 2)
        self.assertEqual(cards[2]["number"], 3)
        self.assertEqual([card["page"] for card in cards], ["1", "2", "5"])
        self.assertEqual(text.count("[1]"), 1)
        self.assertEqual(text.count("[2]"), 1)
        self.assertEqual(text.count("[3]"), 1)
        self.assertIn("choices. [1]", text)
        self.assertIn("answers. [2]", text)
        self.assertIn("later. [3]", text)
        self.assertNotIn("[1] [2] [3] [1]", text)

    def test_finalize_citations_keeps_marker_once_per_sentence(self):
        answer = "Stable matching is taught early. [2] [2] [5]"
        sources = [
            {"number": 2, "source": "a.pdf", "text": "stable", "page": "2"},
            {"number": 5, "source": "a.pdf", "text": "matching", "page": "5"},
        ]
        text, cards = prompts.finalize_citations(answer, sources)
        self.assertEqual(text, "Stable matching is taught early. [1] [2]")
        self.assertEqual([card["number"] for card in cards], [1, 2])

    def test_finalize_citations_keeps_fenced_code_indentation_no_sources(self):
        answer = (
            "Here is an example.\n\n"
            "```yaml\n"
            "- name: Configure\n"
            "  hosts: routers\n"
            "\n"
            "  tasks:\n"
            "    - name: Set hostname\n"
            "```\n"
        )
        text, cards = prompts.finalize_citations(answer, [])
        self.assertEqual(cards, [])
        self.assertEqual(
            text,
            "Here is an example.\n\n"
            "```yaml\n"
            "- name: Configure\n"
            "  hosts: routers\n"
            "\n"
            "  tasks:\n"
            "    - name: Set hostname\n"
            "```",
        )

    def test_finalize_citations_keeps_fenced_code_indentation_with_cited_source(self):
        answer = (
            "Here is an example [1].\n\n"
            "```yaml\n"
            "- name: Configure\n"
            "  hosts: routers\n"
            "\n"
            "  tasks:\n"
            "    - name: Set hostname\n"
            "```"
        )
        sources = [
            {"number": 1, "source": "a.yml", "text": "ansible playbook", "page": "1"}
        ]
        text, cards = prompts.finalize_citations(answer, sources)
        self.assertEqual(
            text,
            "Here is an example. [1]\n"
            "```yaml\n"
            "- name: Configure\n"
            "  hosts: routers\n"
            "\n"
            "  tasks:\n"
            "    - name: Set hostname\n"
            "```",
        )
        self.assertEqual([card["number"] for card in cards], [1])

    def test_finalize_citations_leaves_marker_look_alike_inside_code_block(self):
        answer = (
            "See the array index below. [1]\n\n"
            "```python\n"
            "items[3]  # fetch the fourth element\n"
            "```"
        )
        sources = [
            {"number": 1, "source": "a.py", "text": "index example", "page": "1"}
        ]
        text, cards = prompts.finalize_citations(answer, sources)
        self.assertEqual(
            text,
            "See the array index below. [1]\n"
            "```python\n"
            "items[3]  # fetch the fourth element\n"
            "```",
        )
        self.assertEqual([card["number"] for card in cards], [1])

    def test_greeting_assistant_turns_do_not_enter_history(self):
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Hello! How can I help?"},
            {"role": "user", "content": "tell me about engineering algorithm design"},
        ]
        turns = prompts.clean_history(history)
        self.assertEqual(
            turns,
            [
                ("user", "hello"),
                ("user", "tell me about engineering algorithm design"),
            ],
        )
        self.assertNotIn("Hello!", prompts.format_history(history))


if __name__ == "__main__":
    unittest.main()
