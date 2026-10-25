"""Tests for filename rules, the answer prompt, and ingest progress math."""

import tempfile
import unittest
from pathlib import Path

import importlib.util
import os

import config
import store.embeddings as embeddings
import sources.filesystem as files
import library
import progress
import llm.prompts as prompts


class FilenameTests(unittest.TestCase):
    def test_keeps_a_plain_name(self):
        self.assertEqual(files.stored_filename("notes.pdf"), "notes.pdf")

    def test_drops_parent_directories(self):
        self.assertEqual(files.stored_filename("../../tmp/pwned.txt"), "pwned.txt")

    def test_drops_absolute_paths(self):
        self.assertEqual(files.stored_filename("/tmp/secret.txt"), "secret.txt")

    def test_relative_path_rejects_parent_segments(self):
        self.assertEqual(files.safe_relative_path("a/notes.pdf"), "a/notes.pdf")
        for name in (
            "../notes.pdf",
            "/tmp/notes.pdf",
            "a/../notes.pdf",
            ".hidden/notes.pdf",
        ):
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
        self.assertIn("language of the user's question", explanation)
        self.assertIn("original language", prompts.assistant_prompt("bonjour"))
        self.assertIn("Inlock\nSecure AI for Private Enterprise", explanation)
        padding = "The guide discusses packet filters and ICMP messages. " * 12
        fact = (
            "(icmp.type == 3 && icmp.code == 2) || (icmp.type == 4 && icmp.code == 0)"
        )
        chunk = f"{padding} {fact}"
        self.assertGreater(chunk.find("icmp.type"), 500)
        passage = prompts.prompt_passage(chunk)
        self.assertIn(fact, passage)
        card = prompts.display_excerpt(chunk, "Quel filtre ICMP ?")
        self.assertNotIn("icmp.type", card)
        self.assertLessEqual(len(card), 500)
        reached = prompts.explanation_prompt("Quel filtre ?", ["wire.pdf"], [passage])
        self.assertIn(fact, reached)
        grounded_fact = prompts.ground_library_reply(
            f"The filter is {fact}. [1]",
            [{"number": 1, "text": passage}],
            "Quel filtre ?",
        )
        self.assertIn(fact, grounded_fact)
        self.assertEqual(
            prompts.cited_source_indexes("See [1] and later [1] then [3]."), [1, 3]
        )
        self.assertNotIn("Sentinel", text)
        self.assertNotIn("superhero", text.lower())

    def test_general_questions_skip_the_library(self):
        files = ["Python Basics.pdf", "inlock campaign v4.pdf"]
        self.assertFalse(
            prompts.asks_about_library("How do I run hello-world.py?", files)
        )
        self.assertTrue(
            prompts.asks_about_library(
                "What does Python Basics say about loops?", files
            )
        )
        self.assertTrue(prompts.asks_about_library("What is Inlock?", files))
        self.assertTrue(
            prompts.asks_about_library(
                "What does the campaign say about privacy?", files
            )
        )
        self.assertTrue(
            prompts.asks_about_library(
                "Inlock\nSecure AI for Private Enterprise systems", files
            )
        )
        earlier = [("user", "What does Arbitration Agreement.pdf say about fees?")]
        self.assertIn(
            "Arbitration Agreement.pdf",
            prompts.retrieval_text("What about the deadline?", earlier),
        )
        self.assertEqual(
            prompts.retrieval_text("What about the deadline?", None),
            "What about the deadline?",
        )
        follow_up = prompts.explanation_prompt(
            "What about the deadline?",
            ["Arbitration Agreement.pdf"],
            ["The deadline is Monday."],
            earlier,
        )
        self.assertIn("Earlier in this conversation", follow_up)
        self.assertIn("What about the deadline?", follow_up)
        self.assertIn("Arbitration Agreement.pdf", follow_up)
        self.assertTrue(
            prompts.should_search_library(prompts.retrieval_text("and fees?", earlier))
        )
        snort = [
            ("user", "how to use snort"),
            ("assistant", "Snort detects attacks on the network."),
            ("user", "Give an example"),
            ("assistant", "What would you like an example of?"),
        ]
        self.assertTrue(prompts.is_follow_up("Give an example"))
        self.assertTrue(prompts.is_follow_up("snort"))
        self.assertTrue(
            prompts.is_follow_up(
                "Give a detailed explanation of each step for the operator"
            )
        )
        self.assertFalse(
            prompts.is_follow_up("How do you analyze network traffic with Wireshark?")
        )
        self.assertFalse(prompts.is_follow_up("hello"))
        self.assertFalse(prompts.is_follow_up("how to use snort"))
        wireshark = [("user", "How do you analyze network traffic with Wireshark?")]
        steps = prompts.retrieval_text(
            "Give a detailed explanation of each step for the operator", wireshark
        )
        self.assertIn("Wireshark", steps)
        self.assertIn("operator", steps)
        self.assertIn(
            "practical example", prompts.retrieval_text("Give an example", wireshark)
        )
        self.assertIn(
            "concrete example",
            prompts.explanation_prompt(
                "Give an example", [], ["Example 4 uses contains."]
            ),
        )
        self.assertEqual(
            prompts.repair_pdf_spacing("just a fter the header"),
            "just after the header",
        )
        self.assertEqual(
            prompts.repair_pdf_spacing("packets that cont ain a byte"),
            "packets that contain a byte",
        )
        self.assertEqual(
            prompts.repair_pdf_spacing("to view UDP packets"), "to view UDP packets"
        )
        invented = "Here is an example of a capture filter:\n```\ntcp.port == 80\n```\nThis filter shows TCP port 80. [1]"
        chunk = (
            "lving network problems. Example 1: UDP Packets Suppose that you want to view UDP packets "
            "that cont ain a byte sequence of 0x90, perhaps because certain malware uses this sequence: "
            "udp[8:4]==90:90:90:03"
        )
        grounded = prompts.ground_library_reply(
            invented,
            [{"number": 1, "source": "wire.pdf", "text": chunk}],
            "Give an example",
        )
        self.assertNotIn("tcp.port", grounded)
        self.assertTrue(grounded.startswith("Example 1: UDP Packets"))
        self.assertIn("udp[8:4]==90:90:90:03", grounded)
        self.assertIn("contain", grounded)
        linked = (
            "Example 1: UDP Packets Suppose that you want to view UDP packets. "
            "http://packetlife.net/filters.pdf udp[8:4]==90:90:90:03"
        )
        without_links = prompts.ground_library_reply(
            "invented", [{"number": 1, "text": linked}], "Give an example"
        )
        self.assertNotIn("http", without_links)
        self.assertIn("udp[8:4]==90:90:90:03", without_links)
        icmp = (
            "Example 2: ICMP Packets If you decide to use Wireshark due to a frequent loss in connection. "
            "The following example shows ICMP Protocol Unreachable or Source Quench error messages. "
            "(icmp.type == 3 && icmp.code == 2) || (icmp.type == 4 && icmp.code == 0)"
        )
        steps = prompts.ground_library_reply(
            "1. **Identify areas of concern:** Look at performance.\nLet me know if you have any other questions.",
            [{"number": 1, "text": icmp}],
            "Give a detailed explanation of each step for the operator",
        )
        self.assertIn("Protocol Unreachable", steps)
        self.assertIn("Source Quench", steps)
        self.assertIn("icmp.type == 3", steps)
        self.assertNotIn("**", steps)
        self.assertNotIn("Let me know", steps)
        kept_filter = "Use the filter `udp[8:4]==90:90:90:03`. [1]"
        udp = [{"number": 1, "text": "Filters only. udp[8:4]==90:90:90:03"}]
        quoted = prompts.ground_library_reply(kept_filter, udp, "Give an example")
        self.assertIn("udp[8:4]", quoted)
        self.assertNotIn("worked example", quoted)
        invented_code = "Examine ICMP packets. Use filters for ICMP Type 3, Code 2."
        icmp = [{"number": 1, "text": "Example 2 discusses ICMP Protocol Unreachable."}]
        steps = prompts.ground_library_reply(
            invented_code,
            icmp,
            "Give a detailed explanation of each step for the operator",
        )
        self.assertNotIn("Type 3", steps)
        self.assertIn("ICMP", steps)
        overview = "Wireshark is an open-source protocol analyzer and supports over 1100 protocols. [1]"
        about = [
            {
                "number": 1,
                "text": "Wireshark is an open-source protocol analyser. It supports over 1100 protocols.",
            }
        ]
        self.assertEqual(prompts.ground_library_reply(overview, about), overview)
        self.assertIn(
            "Number the steps",
            prompts.explanation_prompt(
                "Give a detailed explanation of each step for the operator",
                [],
                ["The first step is to capture traffic."],
            ),
        )
        found = prompts.retrieval_text("snort", snort)
        self.assertIn("how to use snort", found)
        self.assertIn("Snort detects attacks", found)

        class Turn:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        carried = prompts.clean_history(
            [
                Turn("user", "how to use snort"),
                Turn("assistant", "Snort detects attacks."),
            ]
        )
        self.assertEqual(
            carried,
            [("user", "how to use snort"), ("assistant", "Snort detects attacks.")],
        )
        self.assertFalse(prompts.should_search_library("hello"))
        self.assertFalse(prompts.should_search_library("What is 2 + 2?"))
        self.assertTrue(prompts.should_search_library("What is in the CV?"))
        self.assertEqual(
            prompts.named_library_files(
                "What is in the CV?", ["Milorad Stevanovic CV.pdf"]
            ),
            ["Milorad Stevanovic CV.pdf"],
        )
        self.assertEqual(
            prompts.named_library_files(
                "What is 2 + 2?", ["Milorad Stevanovic CV.pdf"]
            ),
            [],
        )
        self.assertTrue(
            prompts.excerpts_mention(
                "What privacy rules does the campaign describe?",
                ["Inlock is privacy-first for private enterprise."],
            )
        )
        self.assertFalse(prompts.excerpts_mention("What is 2 + 2?", ["Inlock privacy"]))

    def test_explanation_keeps_the_passage_it_describes(self):
        sources = [
            {
                "source": "inlock campaign v4.pdf",
                "text": "Inlock Secure AI for Private Enterprise",
            },
            {"source": "notes.pdf", "text": "license optional compatibility metadata"},
        ]
        answer = "Inlock offers secure private enterprise AI. [1]"
        kept = prompts.supporting_sources(answer, sources)
        self.assertEqual([item["source"] for item in kept], ["inlock campaign v4.pdf"])
        self.assertEqual(kept[0]["number"], 1)
        self.assertEqual(
            prompts.supporting_sources("See the later section. [9]", sources), []
        )
        uncited = prompts.supporting_sources(
            "Inlock keeps enterprise data completely private.",
            sources,
        )
        self.assertEqual([item["number"] for item in uncited], [1])
        self.assertEqual(
            prompts.library_miss("I think it is Paris."),
            "The library does not cover that.",
        )
        self.assertEqual(
            prompts.source_label({"path": "a/notes.pdf", "page": "3"}),
            "a/notes.pdf · p. 3",
        )
        self.assertEqual(prompts.source_label({"source": "notes.pdf"}), "notes.pdf")

    def test_general_reply_is_not_treated_as_a_citation(self):
        self.assertFalse(
            prompts.answered_from_sources("Paris is the capital of France.")
        )
        self.assertFalse(
            prompts.answered_from_sources(
                "I cannot find it in the retrieved excerpts [1]."
            )
        )
        self.assertTrue(prompts.answered_from_sources("Inlock offers private AI. [1]"))

    def test_unrelated_citation_does_not_count_as_grounded(self):
        answer = "The capital of France is Paris. [1]"
        sources = ["The capital of California is Sacramento."]
        self.assertFalse(prompts.grounded_in_sources(answer, sources))
        grounded = "Inlock offers private AI consulting. [1]"
        library = [
            "Inlock Secure AI for Private Enterprise. Privacy-First AI Consulting."
        ]
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

    def test_partial_file_is_indexed_again(self):
        signature = (10, "2026-10-24", 100)
        done = {
            "relative_path": "done.pdf",
            "file_size": 10,
            "last_modified_date": "2026-10-24",
            "source_mtime": 100,
            "index_complete": True,
        }
        partial = {
            "relative_path": "partial.pdf",
            "file_size": 10,
            "last_modified_date": "2026-10-24",
            "source_mtime": 100,
        }
        mixed_done = {
            "relative_path": "mixed.pdf",
            "file_size": 8,
            "last_modified_date": "2026-10-24",
            "source_mtime": 50,
            "index_complete": True,
        }
        mixed_open = {
            "relative_path": "mixed.pdf",
            "file_size": 8,
            "last_modified_date": "2026-10-24",
            "source_mtime": 50,
        }
        indexed, legacy, incomplete = library.classify_stored_chunks(
            [done, partial, mixed_done, mixed_open]
        )
        self.assertEqual(set(indexed), {"done.pdf"})
        self.assertEqual(legacy, set())
        self.assertEqual(incomplete, {"partial.pdf", "mixed.pdf"})
        embed, drop = library.index_plan(
            {
                "done.pdf": signature,
                "partial.pdf": signature,
                "mixed.pdf": (8, "2026-10-24", 50),
            },
            indexed,
            legacy,
            incomplete,
        )
        self.assertEqual(set(embed), {"partial.pdf", "mixed.pdf"})
        self.assertEqual(set(drop), {"partial.pdf", "mixed.pdf"})

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


class ConfigTests(unittest.TestCase):
    def test_embed_defaults_and_required_chat_model(self):
        saved = {
            name: os.environ.get(name)
            for name in (
                "EMBED_MODEL",
                "EMBED_BATCH",
                "OLLAMA_MODEL",
                "CHUNK_SIZE",
                "CHUNK_OVERLAP",
                "RETRIEVE_CANDIDATES",
                "RETRIEVE_LIMIT",
                "RETRIEVE_PER_FILE",
                "OLLAMA_CONTEXT",
                "OLLAMA_KEEP_ALIVE",
                "OLLAMA_THINK",
                "TORCH_THREADS",
                "RELEVANCE_THRESHOLD",
            )
        }
        try:
            os.environ.pop("EMBED_MODEL", None)
            os.environ.pop("EMBED_BATCH", None)
            os.environ.pop("OLLAMA_MODEL", None)
            self.assertEqual(
                config.embed_model_name(), "intfloat/multilingual-e5-small"
            )
            self.assertEqual(config.SERVER_EMBED_MODEL, "BAAI/bge-m3")
            self.assertEqual(config.embed_batch(), 16)
            self.assertEqual(config.configured_model(), "")
            with self.assertRaises(ValueError):
                config.require_ollama_model()
            os.environ["EMBED_BATCH"] = "4"
            self.assertEqual(config.embed_batch(), 4)
            os.environ["OLLAMA_MODEL"] = "pilot-model"
            self.assertEqual(config.require_ollama_model(), "pilot-model")
            for name in (
                "CHUNK_SIZE",
                "CHUNK_OVERLAP",
                "RETRIEVE_CANDIDATES",
                "RETRIEVE_LIMIT",
                "RETRIEVE_PER_FILE",
                "OLLAMA_CONTEXT",
                "OLLAMA_KEEP_ALIVE",
                "OLLAMA_THINK",
                "TORCH_THREADS",
            ):
                os.environ.pop(name, None)
            self.assertEqual(config.chunk_size(), 512)
            self.assertEqual(config.chunk_overlap(), 64)
            self.assertEqual(config.retrieve_candidates(), 8)
            self.assertEqual(config.retrieve_limit(), 4)
            self.assertEqual(config.retrieve_per_file(), 2)
            self.assertEqual(config.ollama_context(), 4096)
            self.assertEqual(config.ollama_keep_alive(), "30m")
            self.assertFalse(config.ollama_think())
            os.environ["OLLAMA_THINK"] = "true"
            self.assertTrue(config.ollama_think())
            os.environ["OLLAMA_THINK"] = "false"
            self.assertFalse(config.ollama_think())
            os.environ.pop("RELEVANCE_THRESHOLD", None)
            self.assertEqual(config.relevance_threshold(), 0.75)
            self.assertGreaterEqual(config.torch_threads(), 1)
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


class EmbeddingIdentityTests(unittest.TestCase):
    def test_e5_strings_are_exactly_prefixed(self):
        self.assertEqual(
            embeddings.embedded_query("intfloat/multilingual-e5-small", "le coffre"),
            "query: le coffre",
        )
        self.assertEqual(
            embeddings.embedded_passage("intfloat/multilingual-e5-small", "le coffre"),
            "passage: le coffre",
        )
        self.assertEqual(
            embeddings.join_instruction("query:", "le coffre"), "query: le coffre"
        )
        self.assertEqual(
            embeddings.join_instruction("passage:", "le coffre"), "passage: le coffre"
        )
        self.assertEqual(
            embeddings.join_instruction("query: ", "le coffre"), "query:  le coffre"
        )
        self.assertEqual(
            embeddings.embedded_query("BAAI/bge-m3", "le coffre"), "le coffre"
        )

    def test_installed_embedder_joins_with_one_space(self):
        if importlib.util.find_spec("llama_index") is None:
            self.skipTest("llama-index is not installed in this interpreter")
        from llama_index.embeddings.huggingface.utils import format_query, format_text

        self.assertEqual(
            format_query("le coffre", "intfloat/multilingual-e5-small", "query:"),
            "query: le coffre",
        )
        self.assertEqual(
            format_text("le coffre", "intfloat/multilingual-e5-small", "passage:"),
            "passage: le coffre",
        )

    def test_legacy_vectors_need_a_full_reindex(self):
        current = "intfloat/multilingual-e5-small"
        self.assertFalse(embeddings.full_reindex_required(None, 0, current))
        self.assertTrue(embeddings.full_reindex_required(None, 674, current))
        self.assertEqual(
            embeddings.collection_embed_model(None, 674), embeddings.LEGACY_EMBED_MODEL
        )
        self.assertFalse(
            embeddings.full_reindex_required({"embed_model": current}, 10, current)
        )
        self.assertFalse(embeddings.is_e5("BAAI/bge-m3"))
        self.assertTrue(embeddings.is_e5("intfloat/multilingual-e5-small"))
        self.assertTrue(embeddings.relevant_enough([0.875, 0.79], 0.82))
        self.assertFalse(embeddings.relevant_enough([0.777, 0.76], 0.82))
        self.assertTrue(embeddings.relevant_enough([None], 0.82))
        self.assertEqual(
            prompts.GENERAL_NOTICE, "No matching documents found; answering generally."
        )
        self.assertEqual(
            prompts.NOT_INDEXED_NOTICE,
            "These files are in the library folder but are not indexed yet.",
        )
        compare_path = (
            Path(__file__).resolve().parents[2] / "scripts" / "compare_models.py"
        )
        spec = importlib.util.spec_from_file_location("compare_models", compare_path)
        compare_models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compare_models)
        self.assertEqual(compare_models.tokens_per_second(8, 80_000_000), 100)
        self.assertIsNone(compare_models.tokens_per_second(0, 80_000_000))
        self.assertEqual(len(compare_models.PROMPTS), 3)
        self.assertEqual(
            prompts.UNMATCHED_SOURCE_NOTE, "No source could be matched to this answer."
        )


class MultilingualRetrievalTests(unittest.TestCase):
    def test_same_question_in_three_languages_retrieves_its_document(self):
        if importlib.util.find_spec("llama_index") is None:
            self.skipTest("embedding libraries are not installed here")
        needle = "models--intfloat--multilingual-e5-small"
        roots = [
            Path(__file__).resolve().parents[2] / "hf_cache" / "llama_index",
            Path.home() / ".cache" / "llama_index",
            Path("/home/appuser/.cache/llama_index"),
        ]
        if not any((root / needle).exists() for root in roots):
            self.skipTest("multilingual-e5-small is not in the local cache")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        from llama_index.core import Document, VectorStoreIndex
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        model = "intfloat/multilingual-e5-small"
        embed = HuggingFaceEmbedding(
            model_name=model,
            query_instruction=embeddings.query_instruction(model),
            text_instruction=embeddings.text_instruction(model),
        )
        fixture_dir = Path(__file__).resolve().parent / "fixtures"
        documents = [
            Document(
                text=path.read_text(encoding="utf-8"), metadata={"file_name": path.name}
            )
            for path in sorted(fixture_dir.glob("*.txt"))
        ]
        index = VectorStoreIndex.from_documents(documents, embed_model=embed)
        questions = (
            ("Quel est le code du portail nord ?", "fr.txt"),
            ("What is the north gate code?", "en.txt"),
            ("¿Cuál es el código de la puerta norte?", "es.txt"),
        )
        for question, expected in questions:
            nodes = index.as_retriever(similarity_top_k=1).retrieve(question)
            self.assertTrue(nodes, question)
            self.assertEqual(nodes[0].metadata.get("file_name"), expected, question)


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
