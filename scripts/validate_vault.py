#!/usr/bin/env python3
"""Read-only structural validator for a Myself Personal OS vault."""

from __future__ import annotations

import argparse
import datetime as dt
import posixpath
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Optional, Sequence
from urllib.parse import unquote


ALLOWED_STATUSES = {
    "active", "archived", "cancelled", "captured", "completed", "draft",
    "failed", "open", "proposed", "rejected", "superseded", "validated",
}
ALLOWED_VERIFIER = {
    "insufficient_evidence", "not_required", "pending", "rejected", "validated",
}
ALLOWED_APPROVAL = {
    "approved", "approved_with_changes", "not_required", "pending", "rejected",
}
ALLOWED_SENSITIVITY = {"public", "private", "restricted"}
REQUIRED_FIELDS = ("type", "id", "status", "time_scope", "sensitivity")

CORE_FILES = (
    "AGENTS.md",
    "00 首页.md",
    "00 收件箱/收件箱说明.md",
    "01 基础/人生罗盘.md",
    "01 基础/当前状态.md",
    "01 基础/人生维度.md",
    "02 战略/三年情景.md",
    "03 季度/当前季度.md",
    "04 复盘/复盘说明.md",
    "05 日志/证据日志.md",
    "05 日志/决策日志.md",
    "05 日志/变更日志.md",
    "05 日志/工作流运行记录.md",
    "06 实验/实验索引.md",
    "90 模板/周复盘.md",
    "90 模板/月复盘.md",
    "90 模板/季度复盘.md",
    "90 模板/年度复盘.md",
    "90 模板/决策记录.md",
    "90 模板/证据记录.md",
    "90 模板/实验记录.md",
    "90 模板/变更提案.md",
    "99 系统/首次设置.md",
    "99 系统/运行规则.md",
    "99 系统/数据契约.md",
    "99 系统/工作流地图.md",
    "99 系统/验证与检查点.md",
    "99 系统/Agent 协作.md",
)
EXEMPT_FRONTMATTER = {"AGENTS.md", "99 系统/scripts/README.md"}
WIKI_LINK = re.compile(r"\[\[([^\[\]\n]+)\]\]")
INLINE_CODE = re.compile(r"`[^`]*`")
SENSITIVE_PATTERNS = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("TOKEN", re.compile(r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b")),
    ("AWS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("SECRET_FIELD", re.compile(r"(?i)(?:password|passwd|pwd|密码|api[_ -]?key|access[_ -]?token|private[_ -]?key|私钥)\s*[:=：]\s*[\"']?[^\s\"'{}<>]{8,}")),
    ("MNEMONIC", re.compile(r"(?i)(?:mnemonic|seed phrase|助记词|种子短语)\s*[:=：]\s*(?:[a-z]{3,}\s+){7,}[a-z]{3,}")),
)
REVIEW_TYPES = {
    "weekly-review": "周复盘",
    "monthly-review": "月复盘",
    "quarterly-review": "季度复盘",
    "annual-review": "年度复盘",
}


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    line: Optional[int]
    message: str


@dataclass(frozen=True)
class Document:
    path: Path
    relative: str
    lines: list[str]
    frontmatter: Mapping[str, str]
    frontmatter_end: Optional[int]


def normalized(value: str) -> str:
    value = posixpath.normpath(value.replace("\\", "/").strip("/"))
    return unicodedata.normalize("NFC", "" if value == "." else value).casefold()


def parse_frontmatter(lines: list[str]) -> tuple[dict[str, str], Optional[int]]:
    if not lines or lines[0].strip() != "---":
        return {}, None
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return {}, -1
    fields: dict[str, str] = {}
    pattern = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
    for line in lines[1:end]:
        if line.startswith((" ", "\t")):
            continue
        match = pattern.match(line)
        if match:
            value = match.group(2).strip().strip("\"'")
            fields[match.group(1)] = value
    return fields, end


def read_documents(vault: Path, findings: list[Finding]) -> dict[str, Document]:
    documents: dict[str, Document] = {}
    for path in sorted(vault.rglob("*.md")):
        relative = path.relative_to(vault).as_posix()
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            findings.append(Finding("ERROR", "UNREADABLE", relative, None, "Markdown is not readable as UTF-8"))
            continue
        frontmatter, end = parse_frontmatter(lines)
        if end == -1:
            findings.append(Finding("ERROR", "FRONTMATTER_UNCLOSED", relative, 1, "frontmatter has no closing delimiter"))
        documents[relative] = Document(path, relative, lines, frontmatter, end)
    return documents


def check_core(vault: Path, template_mode: bool, findings: list[Finding]) -> None:
    for relative in CORE_FILES:
        if not (vault / relative).is_file():
            findings.append(Finding("ERROR", "CORE_FILE_MISSING", relative, None, "required core file is missing"))
    annual = (vault / "02 战略" / "年度主题.md").is_file() if template_mode else any((vault / "02 战略").glob("[0-9][0-9][0-9][0-9] 年度主题.md"))
    quarter = (vault / "03 季度" / "季度计划.md").is_file() if template_mode else any((vault / "03 季度").glob("[0-9][0-9][0-9][0-9]-Q[1-4].md"))
    if not annual:
        findings.append(Finding("ERROR", "ANNUAL_PAGE_MISSING", "02 战略", None, "annual theme page is missing"))
    if not quarter:
        findings.append(Finding("ERROR", "QUARTER_PAGE_MISSING", "03 季度", None, "quarter plan page is missing"))


def check_metadata(documents: Mapping[str, Document], findings: list[Finding]) -> None:
    ids: dict[str, list[str]] = {}
    for document in documents.values():
        if document.relative not in EXEMPT_FRONTMATTER:
            if document.frontmatter_end is None:
                findings.append(Finding("ERROR", "FRONTMATTER_REQUIRED", document.relative, 1, "managed page requires frontmatter"))
            for field in REQUIRED_FIELDS:
                if not document.frontmatter.get(field):
                    findings.append(Finding("ERROR", "FIELD_REQUIRED", document.relative, 1, f"missing required field: {field}"))
        checks = (
            ("status", ALLOWED_STATUSES),
            ("verifier_status", ALLOWED_VERIFIER),
            ("human_approval", ALLOWED_APPROVAL),
            ("sensitivity", ALLOWED_SENSITIVITY),
        )
        for field, allowed in checks:
            value = document.frontmatter.get(field)
            if value and value not in allowed:
                findings.append(Finding("ERROR", "ENUM_INVALID", document.relative, 1, f"invalid {field}: {value}"))
        entity_id = document.frontmatter.get("id")
        if entity_id:
            ids.setdefault(unicodedata.normalize("NFC", entity_id).casefold(), []).append(document.relative)
            if "{{title}}" in entity_id or entity_id in {"{{date}}", "{{time}}"}:
                findings.append(Finding("ERROR", "ID_TEMPLATE_UNSAFE", document.relative, 1, "template id must include stable formatted date/time and no title"))
    for paths in ids.values():
        if len(paths) > 1:
            joined = ", ".join(paths)
            for path in paths:
                findings.append(Finding("ERROR", "ID_DUPLICATE", path, 1, f"duplicated id across: {joined}"))


def check_dates(documents: Mapping[str, Document], findings: list[Finding], template_mode: bool) -> None:
    """Validate populated date fields; blank optional dates remain valid."""
    fields = ("as_of", "scope_start", "scope_end", "review_due", "result_review_date", "started_on")
    for document in documents.values():
        dates: dict[str, dt.date] = {}
        is_template = document.relative.startswith("90 模板/")
        for field in fields:
            value = document.frontmatter.get(field)
            if not value:
                continue
            if (is_template and "{{" in value) or (template_mode and "__INIT_" in value):
                continue
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError
                dates[field] = dt.date.fromisoformat(value)
            except ValueError:
                findings.append(Finding("ERROR", "DATE_INVALID", document.relative, 1, f"{field} must be a valid YYYY-MM-DD date"))
        start, end = dates.get("scope_start"), dates.get("scope_end")
        if start and end and start > end:
            findings.append(Finding("ERROR", "DATE_RANGE_REVERSED", document.relative, 1, "scope_start is after scope_end"))
        review = dates.get("review_due")
        legacy_review = dates.get("result_review_date")
        if review and legacy_review and review != legacy_review:
            findings.append(Finding("ERROR", "REVIEW_DATE_CONFLICT", document.relative, 1, "review_due and result_review_date disagree"))
        started = dates.get("started_on")
        as_of = dates.get("as_of")
        if started and as_of and started > as_of:
            findings.append(Finding("ERROR", "START_AFTER_AS_OF", document.relative, 1, "actual started_on is after as_of"))


def build_index(vault: Path) -> tuple[set[str], dict[str, set[str]]]:
    files: set[str] = set()
    names: dict[str, set[str]] = {}
    for path in vault.rglob("*"):
        if not path.is_file():
            continue
        rel = normalized(path.relative_to(vault).as_posix())
        files.add(rel)
        for name in (path.name, path.stem):
            names.setdefault(unicodedata.normalize("NFC", name).casefold(), set()).add(rel)
    return files, names


def target_exists(target: str, source: str, files: set[str], names: Mapping[str, set[str]]) -> bool:
    target = unquote(target.split("|", 1)[0].split("#", 1)[0].split("^", 1)[0].strip())
    if not target or target.startswith(("#", "^")) or "{{" in target or "__INIT_" in target:
        return True
    if re.match(r"^[a-z][a-z0-9+.-]*://", target, re.I):
        return True
    parent = PurePosixPath(source).parent.as_posix()
    candidates = {normalized(target), normalized(posixpath.join(parent, target))}
    if not PurePosixPath(target).suffix:
        candidates |= {item + ".md" for item in tuple(candidates)}
    if candidates & files:
        return True
    key = unicodedata.normalize("NFC", PurePosixPath(target).name).casefold()
    return key in names or key + ".md" in names


def check_links(vault: Path, documents: Mapping[str, Document], findings: list[Finding]) -> int:
    files, names = build_index(vault)
    count = 0
    for document in documents.values():
        in_fence = False
        for number, original in enumerate(document.lines, 1):
            if original.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            line = INLINE_CODE.sub("", original)
            for match in WIKI_LINK.finditer(line):
                count += 1
                if not target_exists(match.group(1), document.relative, files, names):
                    findings.append(Finding("ERROR", "WIKI_TARGET_MISSING", document.relative, number, "Wiki-link target does not resolve"))
    return count


def check_sensitive(documents: Mapping[str, Document], findings: list[Finding]) -> None:
    for document in documents.values():
        for number, line in enumerate(document.lines, 1):
            for code, pattern in SENSITIVE_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding("ERROR", f"SENSITIVE_{code}", document.relative, number, "possible sensitive value; matched text withheld"))


def check_reviews(documents: Mapping[str, Document], findings: list[Finding], template_mode: bool) -> None:
    counts = {kind: 0 for kind in REVIEW_TYPES}
    for document in documents.values():
        if document.relative.startswith("90 模板/") or document.path.name == "说明.md":
            continue
        page_type = document.frontmatter.get("type")
        if page_type in counts:
            counts[page_type] += 1
    for kind, label in REVIEW_TYPES.items():
        findings.append(Finding("INFO", "REVIEW_COUNT", "04 复盘", None, f"{label}实例数: {counts[kind]}"))
        if counts[kind] == 0 and not template_mode:
            findings.append(Finding("WARNING", "REVIEW_NONE", "04 复盘", None, f"尚无实际{label}实例"))


def default_vault() -> Path:
    script = Path(__file__).resolve()
    if script.parent.name == "scripts" and script.parent.parent.name == "99 系统":
        return script.parents[2]
    return Path.cwd()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Myself Personal OS vault without modifying it.")
    parser.add_argument("--vault", type=Path, default=default_vault())
    parser.add_argument("--template-mode", action="store_true", help="validate the uninitialized public template")
    return parser.parse_args(argv)


def run(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    vault = args.vault.expanduser().resolve()
    if not vault.is_dir():
        print(f"ERROR [VAULT_NOT_FOUND] {vault}: directory does not exist")
        return 2
    findings: list[Finding] = []
    check_core(vault, args.template_mode, findings)
    documents = read_documents(vault, findings)
    check_metadata(documents, findings)
    check_dates(documents, findings, args.template_mode)
    links = check_links(vault, documents, findings)
    check_sensitive(documents, findings)
    check_reviews(documents, findings, args.template_mode)
    order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    findings.sort(key=lambda item: (order[item.severity], item.path.casefold(), item.line or 0, item.code))
    for item in findings:
        location = f"{item.path}:{item.line}" if item.line else item.path
        print(f"{item.severity} [{item.code}] {location}: {item.message}")
    errors = sum(item.severity == "ERROR" for item in findings)
    warnings = sum(item.severity == "WARNING" for item in findings)
    infos = sum(item.severity == "INFO" for item in findings)
    print(f"SUMMARY files={len(documents)} wiki_links={links} errors={errors} warnings={warnings} info={infos}")
    print("RESULT FAIL" if errors else "RESULT PASS")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(run())
