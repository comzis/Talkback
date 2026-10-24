"""Tests for filename rules, the answer prompt, and ingest progress math."""

import tempfile
import unittest
from pathlib import Path

import files
import library
import progress
import prompts


class FilenameTests(unittest.TestCase):
    def test_keeps_a_plain_name(self):
        self.assertEqual(files.stored_filename("notes.pdf"), "notes.pdf")

    def test_drops_parent_directories(self):
        self.assertEqual(files.stored_filename("../../tmp/pwned.txt"), "pwned.txt")

    def test_drops_absolute_paths(self):
        self.assertEqual(files.stored_filename("/tmp/secret.txt"), "secret.txt")

    def test_relative_path_rejects_parent_segments(self):
        self.assertEqual(files.safe_relative_path("a/notes.pdf"), "a/notes.pdf")
        for name in ("../notes.pdf", "/tmp/notes.pdf", "a/../notes.pdf", ".hidden/notes.pdf"):
            with self.assertRaises(files.InvalidFilename):
                files.safe_relative_path(name)

    def test_rejects_empty_and_dot_names(self):
        for name in ("", ".", "..", None):
            with self.assertRaises(files.InvalidFilename):
                files.stored_filename(name)

    def test_visible_files_skip_dotfiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gitkeep").write_text("keep", encoding="utf-8")
            (root / "notes.txt").write_text("hello", encoding="utf-8")
            names = {path.name for path in files.visible_files(root)}
        self.assertEqual(names, {"notes.txt"})

    def test_json_is_data_not_code(self):
        self.assertEqual(files.get_file_type("report.json"), "data")
        self.assertEqual(files.get_file_type("page.html"), "code")


class PromptTests(unittest.TestCase):
    def test_prompt_asks_for_numbered_citations(self):
        text = prompts.citation_prompt(["inlock campaign v4.pdf", "Python Basics.pdf"])
        self.assertIn("{context_str}", text)
        self.assertIn("{query_str}", text)
        self.assertIn("[1]", text)
        self.assertIn("inlock campaign v4.pdf", text)
        self.assertIn("Python Basics.pdf", text)
        self.assertIn("helpful assistant", text)
        self.assertIn("reply from your own knowledge", text)
        explanation = prompts.explanation_prompt(
            "Inlock\nSecure AI for Private Enterprise",
            ["inlock campaign v4.pdf"],
            ["Inlock deploys private AI systems."],
        )
        self.assertIn("explain that text", explanation)
        self.assertIn("walk through the lines", explanation)
        self.assertIn("Inlock\nSecure AI for Private Enterprise", explanation)
        self.assertEqual(prompts.cited_source_indexes("See [1] and later [1] then [3]."), [1, 3])
        self.assertNotIn("Sentinel", text)
        self.assertNotIn("superhero", text.lower())

    def test_general_questions_skip_the_library(self):
        files = ["Python Basics.pdf", "inlock campaign v4.pdf"]
        self.assertFalse(prompts.asks_about_library("How do I run hello-world.py?", files))
        self.assertTrue(prompts.asks_about_library("What does Python Basics say about loops?", files))
        self.assertTrue(prompts.asks_about_library("What is Inlock?", files))
        self.assertTrue(prompts.asks_about_library("What does the campaign say about privacy?", files))
        self.assertTrue(prompts.asks_about_library("Inlock\nSecure AI for Private Enterprise systems", files))
        self.assertFalse(prompts.should_search_library("hello"))
        self.assertFalse(prompts.should_search_library("What is 2 + 2?"))
        self.assertTrue(prompts.excerpts_mention(
            "What privacy rules does the campaign describe?",
            ["Inlock is privacy-first for private enterprise."],
        ))
        self.assertFalse(prompts.excerpts_mention("What is 2 + 2?", ["Inlock privacy"]))

    def test_explanation_keeps_the_passage_it_describes(self):
        sources = [
            {"source": "inlock campaign v4.pdf", "text": "Inlock Secure AI for Private Enterprise"},
            {"source": "notes.pdf", "text": "license optional compatibility metadata"},
        ]
        answer = "Inlock offers secure private enterprise AI. [1]"
        kept = prompts.supporting_sources(answer, sources)
        self.assertEqual([item["source"] for item in kept], ["inlock campaign v4.pdf"])
        self.assertEqual(kept[0]["number"], 1)
        self.assertEqual(prompts.supporting_sources("See the later section. [9]", sources), [])
        uncited = prompts.supporting_sources(
            "Inlock keeps enterprise data completely private.",
            sources,
        )
        self.assertEqual([item["number"] for item in uncited], [1])
        self.assertEqual(prompts.library_miss("I think it is Paris."), "The library does not cover that.")
        self.assertEqual(
            prompts.source_label({"path": "a/notes.pdf", "page": "3"}),
            "a/notes.pdf · p. 3",
        )
        self.assertEqual(prompts.source_label({"source": "notes.pdf"}), "notes.pdf")

    def test_general_reply_is_not_treated_as_a_citation(self):
        self.assertFalse(prompts.answered_from_sources("Paris is the capital of France."))
        self.assertFalse(prompts.answered_from_sources(
            "I cannot find it in the retrieved excerpts [1]."
        ))
        self.assertTrue(prompts.answered_from_sources("Inlock offers private AI. [1]"))

    def test_unrelated_citation_does_not_count_as_grounded(self):
        answer = "The capital of France is Paris. [1]"
        sources = ["The capital of California is Sacramento."]
        self.assertFalse(prompts.grounded_in_sources(answer, sources))
        grounded = "Inlock offers private AI consulting. [1]"
        library = ["Inlock Secure AI for Private Enterprise. Privacy-First AI Consulting."]
        self.assertTrue(prompts.grounded_in_sources(grounded, library))


class LibraryPlanTests(unittest.TestCase):
    def test_new_file_is_added_and_existing_file_stays(self):
        embed, drop = library.plan_updates(
            {"old.pdf": (10, "2026-10-23", 100), "new.pdf": (20, "2026-10-24", 200)},
            {"old.pdf": (10, "2026-10-23", None)},
        )
        self.assertEqual(embed, ["new.pdf"])
        self.assertEqual(drop, [])

    def test_changed_file_is_replaced_without_touching_others(self):
        embed, drop = library.plan_updates(
            {"old.pdf": (10, "2026-10-23", 100), "notes.pdf": (99, "2026-10-24", 300)},
            {"old.pdf": (10, "2026-10-23", None), "notes.pdf": (50, "2026-10-24", 250)},
        )
        self.assertEqual(embed, ["notes.pdf"])
        self.assertEqual(drop, ["notes.pdf"])

    def test_read_only_defaults_off_and_interval_defaults_off(self):
        self.assertFalse(library.read_only_requested(None))
        self.assertFalse(library.read_only_requested(""))
        self.assertTrue(library.read_only_requested("true"))
        self.assertIsNone(library.reindex_minutes(None))
        self.assertIsNone(library.reindex_minutes("0"))
        self.assertEqual(library.reindex_minutes("30"), 30)

    def test_same_name_in_two_folders_are_both_indexed(self):
        signature = (10, "2026-10-24", 100)
        embed, drop = library.plan_updates(
            {"a/notes.pdf": signature, "b/notes.pdf": signature},
            {},
        )
        self.assertEqual(embed, ["a/notes.pdf", "b/notes.pdf"])
        self.assertEqual(drop, [])

    def test_delete_matches_only_the_chosen_path(self):
        folder_a = {"relative_path": "a/notes.pdf", "file_name": "notes.pdf"}
        folder_b = {"relative_path": "b/notes.pdf", "file_name": "notes.pdf"}
        legacy = {"file_name": "notes.pdf"}
        self.assertTrue(library.chunk_belongs_to(folder_a, "a/notes.pdf"))
        self.assertFalse(library.chunk_belongs_to(folder_a, "b/notes.pdf"))
        self.assertTrue(library.chunk_belongs_to(legacy, "notes.pdf"))
        self.assertFalse(library.chunk_belongs_to(legacy, "b/notes.pdf"))
        self.assertFalse(library.chunk_belongs_to(folder_b, "notes.pdf"))

    def test_moved_file_is_reindexed_under_the_new_path(self):
        signature = (10, "2026-10-24", 100)
        embed, drop = library.index_plan(
            {"b/notes.pdf": signature},
            {"notes.pdf": signature},
            {"notes.pdf"},
        )
        self.assertEqual(embed, ["b/notes.pdf"])
        self.assertEqual(drop, ["notes.pdf"])

    def test_legacy_root_file_is_rewritten_once(self):
        signature = (10, "2026-10-24", 100)
        embed, drop = library.index_plan(
            {"notes.pdf": signature},
            {"notes.pdf": signature},
            {"notes.pdf"},
        )
        self.assertEqual(embed, ["notes.pdf"])
        self.assertEqual(drop, ["notes.pdf"])

    def test_missing_file_is_removed_from_the_index(self):
        embed, drop = library.plan_updates(
            {"kept.pdf": (10, "2026-10-24", 100)},
            {"kept.pdf": (10, "2026-10-24", 100), "gone.pdf": (5, "2026-10-01", 1)},
        )
        self.assertEqual(embed, [])
        self.assertEqual(drop, ["gone.pdf"])

    def test_balance_keeps_a_small_document_beside_a_large_one(self):
        class Node:
            def __init__(self, name):
                self.metadata = {"file_name": name}

        nodes = [Node("Python Basics.pdf") for _ in range(6)]
        nodes.insert(3, Node("inlock campaign v4.pdf"))
        chosen = library.balance_matches(nodes, per_file=2, limit=4)
        names = [node.metadata["file_name"] for node in chosen]
        self.assertIn("inlock campaign v4.pdf", names)
        self.assertEqual(names.count("Python Basics.pdf"), 2)
        self.assertLessEqual(len(chosen), 4)


class ProgressTests(unittest.TestCase):
    def test_reports_speed_and_remaining_time(self):
        metrics = progress.ingest_metrics(done=4, total=8, elapsed_seconds=2)
        self.assertEqual(metrics["chunks_per_second"], 2.0)
        self.assertEqual(metrics["estimated_time_remaining"], 2)
        self.assertEqual(metrics["progress"], 50)
        self.assertEqual(metrics["current"], 4)

    def test_zero_elapsed_does_not_divide_by_zero(self):
        metrics = progress.ingest_metrics(done=0, total=3, elapsed_seconds=0)
        self.assertEqual(metrics["chunks_per_second"], 0.0)
        self.assertEqual(metrics["estimated_time_remaining"], 0)


if __name__ == "__main__":
    unittest.main()
