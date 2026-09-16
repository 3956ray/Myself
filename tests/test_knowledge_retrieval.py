from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from knowledge_retrieval import lint, search


class KnowledgeRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "vault"
        self.root.mkdir()

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def page(self, relative: str, body: str, fields: str = "") -> Path:
        return self.write(relative, "---\n" + fields + "---\n" + body + "\n")

    def test_chinese_retrieval_has_exact_line_provenance(self) -> None:
        path = self.page("70 知识/检索.md", "# 知识方法\n保留来源，能够核对知识检索结果。", "as_of: 2030-04-02\nsensitivity: private\n")
        result = search(self.root, "检索机制")[0]
        self.assertEqual(result["path"], "70 知识/检索.md")
        self.assertEqual(result["title"], "知识方法")
        self.assertEqual(result["as_of"], "2030-04-02")
        self.assertEqual(result["sensitivity"], "private")
        self.assertEqual(result["excerpt"], path.read_text().splitlines()[result["line"] - 1])
        self.assertEqual(result["line_end"], result["line"])

    def test_privacy_defaults_and_strict_public_filter(self) -> None:
        self.page("public.md", "# retrieval public", "sensitivity: public\n")
        self.page("private.md", "# retrieval private", "sensitivity: private\n")
        self.page("unmarked.md", "# retrieval unmarked")
        self.page("invalid.md", "# retrieval invalid", "sensitivity: PUBLIC\n")
        self.page("restricted.md", "# retrieval secret", "sensitivity: restricted\n")
        self.page("duplicate.md", "# retrieval secret", "sensitivity: public\nsensitivity: public\n")
        self.assertEqual({x["path"] for x in search(self.root, "retrieval")}, {"public.md", "private.md", "unmarked.md", "invalid.md"})
        self.assertEqual([x["path"] for x in search(self.root, "retrieval", public_only=True)], ["public.md"])

    def test_hidden_files_raw_text_and_symlinks_are_not_retrieved(self) -> None:
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("# retrieval secret", encoding="utf-8")
        self.write("normal.md", "# retrieval allowed")
        self.write("80 来源/source.txt", "retrieval raw")
        for relative in [".git/secret.md", ".obsidian/secret.md", ".myself/secret.md", ".other/secret.md", "nested/.secret.md"]:
            self.write(relative, "# retrieval hidden")
        (self.root / "outside.md").symlink_to(outside)
        (self.root / "linked-dir").symlink_to(outside.parent, target_is_directory=True)
        (self.root / "inside-link.md").symlink_to(self.root / "normal.md")
        self.assertEqual([x["path"] for x in search(self.root, "retrieval")], ["normal.md"])

    def test_search_is_word_based_deterministic_and_bounded(self) -> None:
        self.page("a.md", "# RAG\n" + "前" * 210 + "rag" + "后" * 200, "title: Retrieval\n")
        self.page("b.md", "# RAG")
        self.page("c.md", "# Fragile catalog")
        results = search(self.root, "RAG", limit=1)
        self.assertEqual(len(results), 1)
        self.assertLessEqual(len(results[0]["excerpt"]), 160)
        self.assertEqual(results, search(self.root, "RAG", limit=1))
        self.assertNotIn("c.md", {item["path"] for item in search(self.root, "rag")})

    def test_long_match_excerpt_includes_match(self) -> None:
        self.write("long.md", "无" * 400 + "知识检索" + "后" * 400)
        result = search(self.root, "知识检索")[0]
        self.assertIn("知识检索", result["excerpt"])
        self.assertLessEqual(len(result["excerpt"]), 160)
        self.assertEqual(result["line"], 1)

    def test_unicode_casefold_does_not_change_excerpt_offsets(self) -> None:
        self.write("mixed.md", "ß" * 400 + " RAG " + "后" * 400)
        result = search(self.root, "rag")[0]
        self.assertIn("RAG", result["excerpt"])

    def test_invalid_arguments(self) -> None:
        for query in ["", " \t\n"]:
            with self.assertRaises(ValueError):
                search(self.root, query)
        for limit in [0, -1, True]:
            with self.assertRaises(ValueError):
                search(self.root, "test", limit=limit)
        with self.assertRaises(ValueError):
            search(self.root / "missing", "test")
        self.assertEqual(search(self.root, "?!"), [])

    def test_lint_source_attachment_and_incoming_link(self) -> None:
        self.write("80 来源/session/source.txt", "A fictional discussion.")
        self.page("70 知识/理解.md", "# 理解", "id: understanding\ntype: knowledge\nsource_refs:\n  - '[[80 来源/session/source.txt]]'\n")
        self.page("70 知识/索引.md", "# 索引\n[[70 知识/理解]]", "id: index\ntype: knowledge-index\n")
        self.write("00 首页.md", "[[70 知识/索引]]")
        findings = lint(self.root)
        self.assertEqual([f["code"] for f in findings], ["STRUCTURAL_ONLY"])
        self.assertEqual(findings[0]["severity"], "info")

    def test_lint_missing_source_orphan_and_duplicate_id(self) -> None:
        self.page("70 知识/first.md", "# PRIVATE-BODY-SECRET\n[[70 知识/first]]", "id: repeated\nsource_refs: [\"[[80 来源/missing/source.txt]]\"]\n")
        self.page("70 知识/second.md", "# PRIVATE-BODY-SECRET", "id: repeated\nsource_refs: []\n")
        findings = lint(self.root)
        codes = [f["code"] for f in findings]
        self.assertEqual(codes.count("ID_DUPLICATE"), 2)
        self.assertEqual(codes.count("ORPHAN"), 2)
        self.assertIn("SOURCE_REF_MISSING", codes)
        self.assertIn("SOURCE_REFS_REQUIRED", codes)
        self.assertNotIn("PRIVATE-BODY-SECRET", str(findings))

    def test_lint_missing_id_and_ambiguous_source(self) -> None:
        self.write("80 来源/a/source.txt", "a")
        self.write("80 来源/b/source.txt", "b")
        self.page("70 知识/topic.md", "# Topic", "source_refs: ['[[source.txt]]']\n")
        codes = {finding["code"] for finding in lint(self.root)}
        self.assertIn("ID_REQUIRED", codes)
        self.assertIn("SOURCE_REF_AMBIGUOUS", codes)

    def test_lint_rejects_symlink_source_and_escaping_path(self) -> None:
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("private", encoding="utf-8")
        (self.root / "linked.txt").symlink_to(outside)
        self.page("70 知识/topic.md", "# Topic", "id: topic\nsource_refs:\n  - '[[linked.txt]]'\n  - '[[../../outside.txt]]'\n")
        codes = [finding["code"] for finding in lint(self.root)]
        self.assertEqual(codes.count("SOURCE_REF_MISSING"), 2)

    def test_lint_rejects_self_source_and_does_not_traverse_hidden_pages(self) -> None:
        self.page("70 知识/topic.md", "# Topic", "id: topic\nsource_refs: ['[[70 知识/topic]]']\n")
        self.write(".hidden/link.md", "[[70 知识/topic]]")
        codes = {finding["code"] for finding in lint(self.root)}
        self.assertIn("SOURCE_REF_SELF", codes)
        self.assertIn("ORPHAN", codes)

    def test_metadata_parse_failure_is_not_public(self) -> None:
        self.write("broken.md", "---\nsensitivity: public\n# retrieval secret")
        self.assertEqual(search(self.root, "retrieval", public_only=True), [])

    def test_source_digest_detects_changed_original_bytes(self) -> None:
        original = "A fictional source.\n"
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
        self.page("80 来源/session/record.md", "# Source", f"content_sha256: {digest}\n")
        self.write("80 来源/session/source.txt", original)
        self.assertEqual([item["code"] for item in lint(self.root)], ["STRUCTURAL_ONLY"])
        self.write("80 来源/session/source.txt", "PRIVATE-CHANGED-BODY")
        findings = lint(self.root)
        changed = [item for item in findings if item["code"] == "SOURCE_BYTES_CHANGED"]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["severity"], "error")
        self.assertNotIn("PRIVATE-CHANGED-BODY", str(findings))

    def test_missing_or_linked_source_is_rejected_even_when_digest_matches(self) -> None:
        original = "Sensitive fictional source."
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
        self.page("80 来源/session/record.md", "# Source", f"content_sha256: {digest}\n")
        self.assertIn("SOURCE_MISSING", {item["code"] for item in lint(self.root)})
        external = Path(self.temp.name) / "external.txt"
        external.write_text(original, encoding="utf-8")
        (self.root / "80 来源/session/source.txt").symlink_to(external)
        self.assertIn("SOURCE_MISSING", {item["code"] for item in lint(self.root)})

    def test_unhashed_legacy_source_record_remains_allowed(self) -> None:
        self.page("80 来源/legacy/record.md", "# Legacy source")
        self.assertEqual([item["code"] for item in lint(self.root)], ["STRUCTURAL_ONLY"])


if __name__ == "__main__":
    unittest.main()
