"""Read-only Markdown retrieval and structural knowledge checks.

Retrieval uses transparent term matching (English words and Chinese bigrams),
not embeddings or BM25. Results cite a one-based file line, not a PDF page.
The small frontmatter reader supports scalars and lists; it never executes YAML.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote


_WIKI_LINK = re.compile(r"\[\[([^\[\]\n]+)\]\]")
_FIELD = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_WORDS = re.compile(r"[A-Za-z0-9_]+")
_NAVIGATION_TYPES = {
    "index", "log", "project", "project-index", "project-overview",
    "knowledge-index", "knowledge-log", "knowledge-project",
}


@dataclass
class _Document:
    path: str
    lines: list[str]
    metadata: dict[str, Any]
    body_start: int
    malformed: bool = False


def _root(vault: Path) -> Path:
    vault = Path(vault)
    if vault.is_symlink() or not vault.is_dir():
        raise ValueError("vault must be an existing directory, not a symbolic link")
    return vault.resolve()


def _safe_files(root: Path) -> Iterator[Path]:
    """Never descend hidden directories or symbolic links, including internal ones."""
    for directory, directories, filenames in os.walk(root, followlinks=False):
        base = Path(directory)
        directories[:] = sorted(
            name for name in directories
            if not name.startswith(".") and not (base / name).is_symlink()
        )
        for name in sorted(filenames):
            path = base / name
            if name.startswith(".") or path.is_symlink() or not path.is_file():
                continue
            try:
                path.resolve().relative_to(root)
            except (OSError, ValueError):
                continue
            # Also reject an ancestor swapped to a link while walking.
            if any(parent.is_symlink() for parent in path.parents if parent != root
                   and root in parent.parents):
                continue
            yield path


def _scalar(raw: str) -> str:
    value = raw.strip()
    if value.startswith('"') and value.endswith('"'):
        try:
            decoded = json.loads(value)
            if isinstance(decoded, str):
                return decoded
        except (ValueError, TypeError):
            return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def _value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]") and not raw.startswith("[["):
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return [str(item) for item in result if item is not None]
        except ValueError:
            pass
        # Quoted YAML inline lists used by the Markdown templates.
        pieces = re.findall(r'''"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^,]+''', raw[1:-1])
        return [_scalar(piece) for piece in pieces if piece.strip()]
    return _scalar(raw)


def _frontmatter(lines: list[str]) -> tuple[dict[str, Any], int, bool]:
    if not lines or lines[0].strip() != "---":
        return {}, 0, False
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, len(lines), True
    metadata: dict[str, Any] = {}
    current: str | None = None
    for line in lines[1:end]:
        match = _FIELD.match(line)
        if match:
            current, raw = match.groups()
            # Repeated sensitivity fields are ambiguous, so fail closed.
            if current == "sensitivity" and current in metadata:
                metadata[current] = "restricted"
                current = None
                continue
            metadata[current] = _value(raw)
            continue
        item = re.match(r"^\s*-\s+(.+)$", line)
        if item and current is not None:
            if not isinstance(metadata[current], list):
                metadata[current] = []
            metadata[current].append(_scalar(item.group(1)))
    return metadata, end + 1, False


def _documents(root: Path, files: list[Path]) -> tuple[list[_Document], list[str]]:
    documents, unreadable = [], []
    for path in files:
        if path.suffix.casefold() != ".md":
            continue
        relative = path.relative_to(root).as_posix()
        try:
            if path.is_symlink():
                continue
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            unreadable.append(relative)
            continue
        metadata, start, malformed = _frontmatter(lines)
        documents.append(_Document(relative, lines, metadata, start, malformed))
    return documents, unreadable


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _sensitivity(document: _Document) -> str:
    value = _string(document.metadata.get("sensitivity"))
    if document.malformed:
        return "restricted"
    return value if value in {"public", "private", "restricted"} else "private"


def _title(document: _Document) -> str:
    value = _string(document.metadata.get("title"))
    if value:
        return value
    for line in document.lines[document.body_start:]:
        if line.startswith("# "):
            return line[2:].strip()
    return Path(document.path).stem


def _terms(query: str) -> list[tuple[str, bool, float]]:
    terms: dict[tuple[str, bool], float] = {}
    for word in _WORDS.findall(query.casefold()):
        terms[(word, True)] = 1.0
    for phrase in _CJK.findall(query):
        terms[(phrase, False)] = 2.0 if len(phrase) > 1 else 1.0
        for i in range(len(phrase) - 1):
            terms.setdefault((phrase[i:i + 2], False), 1.0)
    return [(term, word, weight) for (term, word), weight in terms.items()]


def _matches(text: str, terms: list[tuple[str, bool, float]]) -> tuple[float, int]:
    score, first = 0.0, len(text)
    for term, is_word, weight in terms:
        if is_word:
            # Match on the original string: casefold can expand characters
            # (for example, ß), which would corrupt excerpt offsets.
            match = re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])", text, re.IGNORECASE)
            position = match.start() if match else -1
        else:
            position = text.find(term)
        if position >= 0:
            score += weight
            first = min(first, position)
    return score, first


def search(vault: Path, query: str, public_only: bool = False, limit: int = 8) -> list[dict]:
    """Return permitted Markdown matches with file paths and one-based line citations.

    Missing/invalid sensitivity is private; restricted documents never appear.
    Raw source text and hidden files are not indexed. No network requests occur.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must contain non-whitespace text")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ValueError("limit must be a positive integer")
    root = _root(vault)
    terms = _terms(query)
    if not terms:
        return []
    documents, _ = _documents(root, list(_safe_files(root)))
    results = []
    for document in documents:
        sensitivity = _sensitivity(document)
        if sensitivity == "restricted" or (public_only and sensitivity != "public"):
            continue
        # Search content lines only, so metadata/link fields cannot masquerade
        # as a body match with a misleading excerpt.
        candidates = []
        total = 0.0
        for i in range(document.body_start, len(document.lines)):
            score, position = _matches(document.lines[i], terms)
            if score:
                total += score
                candidates.append((score, -i, position))
        if not candidates:
            continue
        score, negative_line, position = max(candidates)
        line_index = -negative_line
        line = document.lines[line_index]
        start = max(0, position - 50) if len(line) > 160 else 0
        title = _title(document)
        title_score, _ = _matches(title, terms)
        results.append({
            "path": document.path,
            "title": title,
            "as_of": _string(document.metadata.get("as_of")) or None,
            "sensitivity": sensitivity,
            "score": round(score + title_score * 3 + min(total, score * 5) * 0.1, 3),
            "line": line_index + 1,
            "line_end": line_index + 1,
            "excerpt": line[start:start + 160],
        })
    return sorted(results, key=lambda result: (-result["score"], result["path"]))[:limit]


def _normal(path: str) -> str:
    return unicodedata.normalize("NFC", posixpath.normpath(path)).casefold()


def _resolve(target: str, origin: str, paths: set[str]) -> set[str]:
    target = unquote(target.split("|", 1)[0].split("#", 1)[0].strip()).replace("\\", "/")
    if not target:
        return {origin}  # A heading-only link stays on this page.
    if target.startswith("/") or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return set()
    wanted = [target, posixpath.join(posixpath.dirname(origin), target)]
    for candidate in wanted:
        if _normal(candidate).startswith("../"):
            continue
        variants = {_normal(candidate), _normal(candidate + ".md")}
        matches = {path for path in paths if _normal(path) in variants}
        if matches:
            return matches
    # Obsidian permits unique basenames, including attachments.
    if "/" not in target:
        names = {_normal(target), _normal(target + ".md")}
        return {path for path in paths if _normal(posixpath.basename(path)) in names}
    return set()


def _source_refs(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    refs = []
    for item in values:
        if not isinstance(item, str) or item.strip().lower() in {"", "[]", "null", "~"}:
            continue
        links = _WIKI_LINK.findall(item)
        refs.extend(links or [item.strip()])
    return refs


def _source_digest(root: Path, relative: str) -> str:
    """Hash local source bytes, refusing linked files and parent directories."""
    source = root / relative
    if source.is_symlink() or any(
        parent.is_symlink() for parent in source.parents
        if parent != root and root in parent.parents
    ):
        raise OSError("symbolic links are not source files")
    source.resolve().relative_to(root)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(source, flags)
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lint(vault: Path) -> list[dict]:
    """Check knowledge page structure; never assess truth or semantic contradictions.

    Knowledge checks apply to Markdown under ``70 知识/``. Source records
    under ``80 来源/<id>/record.md`` can also declare ``content_sha256`` to
    verify the original source.txt bytes. Other visible Markdown can supply
    IDs and incoming links. Findings contain paths, never body excerpts.
    """
    root = _root(vault)
    files = list(_safe_files(root))
    paths = {path.relative_to(root).as_posix() for path in files}
    documents, unreadable = _documents(root, files)
    findings = [{
        "severity": "info", "code": "STRUCTURAL_ONLY", "path": "70 知识",
        "message": "仅检查结构与链接；不能证明内容正确、识别语义矛盾或确认知识仍然有效。",
    }]

    def finding(severity: str, code: str, path: str, message: str) -> None:
        findings.append({"severity": severity, "code": code, "path": path, "message": message})

    for path in unreadable:
        if path.startswith("70 知识/"):
            finding("error", "UNREADABLE", path, "Knowledge page cannot be read as UTF-8.")
    identifiers: dict[str, set[str]] = {}
    incoming: dict[str, set[str]] = {}
    for document in documents:
        identifier = _string(document.metadata.get("id")).strip()
        if identifier:
            identifiers.setdefault(_normal(identifier), set()).add(document.path)
        for target in _WIKI_LINK.findall("\n".join(document.lines)):
            resolved = _resolve(target, document.path, paths)
            if len(resolved) == 1:
                destination = next(iter(resolved))
                if destination != document.path:
                    incoming.setdefault(destination, set()).add(document.path)
    for document in documents:
        parts = Path(document.path).parts
        expected_digest = _string(document.metadata.get("content_sha256")).strip()
        if len(parts) == 3 and parts[0] == "80 来源" and parts[2] == "record.md" and expected_digest:
            source_path = posixpath.join(posixpath.dirname(document.path), "source.txt")
            if source_path not in paths:
                finding("error", "SOURCE_MISSING", document.path, "Original source.txt is missing or is not a visible, local, non-symlink file.")
            else:
                try:
                    actual_digest = _source_digest(root, source_path)
                except (OSError, ValueError):
                    finding("error", "SOURCE_MISSING", document.path, "Original source.txt cannot be safely read.")
                else:
                    if actual_digest != expected_digest.lower():
                        finding("error", "SOURCE_BYTES_CHANGED", document.path, "Original source.txt no longer matches the recorded SHA-256 digest.")
        if not document.path.startswith("70 知识/"):
            continue
        if document.malformed:
            finding("error", "FRONTMATTER_UNCLOSED", document.path, "Frontmatter has no closing delimiter.")
        identifier = _string(document.metadata.get("id")).strip()
        if not identifier:
            finding("error", "ID_REQUIRED", document.path, "Knowledge page requires a stable ID.")
        elif len(identifiers.get(_normal(identifier), set())) > 1:
            finding("error", "ID_DUPLICATE", document.path, "Knowledge page ID is also used by another page.")
        refs = _source_refs(document.metadata.get("source_refs"))
        page_type = _string(document.metadata.get("type")).replace("_", "-")
        if not refs and page_type not in _NAVIGATION_TYPES:
            finding("error", "SOURCE_REFS_REQUIRED", document.path, "Knowledge content requires nonempty source_refs.")
        for target in refs:
            if not target.split("|", 1)[0].split("#", 1)[0].strip():
                resolved = set()
            else:
                resolved = _resolve(target, document.path, paths)
            if not resolved:
                finding("error", "SOURCE_REF_MISSING", document.path, "A source reference does not resolve to a visible, local, non-symlink file.")
            elif len(resolved) > 1:
                finding("error", "SOURCE_REF_AMBIGUOUS", document.path, "A source reference has multiple possible targets; use its vault-relative path.")
            elif document.path in resolved:
                finding("error", "SOURCE_REF_SELF", document.path, "A page cannot be its own source.")
        if not incoming.get(document.path):
            finding("warning", "ORPHAN", document.path, "No other Markdown page links to this knowledge page.")
    return findings
