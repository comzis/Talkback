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
        self.assertNotIn("Sentinel", text)
        self.assertNotIn("superhero", text.lower())


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
