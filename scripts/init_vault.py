#!/usr/bin/env python3
"""Create a private Personal OS vault from the public generic template."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path


def quarter_for(month: int) -> int:
    return (month - 1) // 3 + 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize a private Myself Personal OS vault."
    )
    parser.add_argument("target", type=Path, help="new or empty target directory")
    parser.add_argument(
        "--date",
        type=dt.date.fromisoformat,
        default=dt.date.today(),
        help="initialization date in YYYY-MM-DD format (defaults to today)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="do not run the read-only validator after initialization",
    )
    return parser.parse_args()


def assert_safe_target(target: Path, template_root: Path) -> None:
    resolved = target.resolve()
    if resolved == template_root.resolve() or template_root.resolve() in resolved.parents:
        raise ValueError("target cannot be the repository template directory")
    if target.exists() and not target.is_dir():
        raise ValueError("target exists and is not a directory")
    if target.exists() and any(target.iterdir()):
        raise ValueError("target directory is not empty; refusing to overwrite files")


def replace_tokens(root: Path, values: dict[str, str]) -> None:
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for token, value in values.items():
            text = text.replace(token, value)
        path.write_text(text, encoding="utf-8")


def initialize(target: Path, init_date: dt.date, skip_validation: bool) -> int:
    repository_root = Path(__file__).resolve().parents[1]
    template_root = repository_root / "vault-template"
    validator_source = repository_root / "scripts" / "validate_vault.py"

    assert_safe_target(target, template_root)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template_root, target, dirs_exist_ok=True)

    quarter = f"Q{quarter_for(init_date.month)}"
    values = {
        "__INIT_DATE__": init_date.isoformat(),
        "__INIT_YEAR__": str(init_date.year),
        "__INIT_QUARTER__": quarter,
        "__INIT_QUARTER_ID__": f"{init_date.year}-{quarter}",
    }
    replace_tokens(target, values)

    annual_source = target / "02 战略" / "年度主题.md"
    annual_target = target / "02 战略" / f"{init_date.year} 年度主题.md"
    annual_source.rename(annual_target)

    quarter_source = target / "03 季度" / "季度计划.md"
    quarter_target = target / "03 季度" / f"{init_date.year}-{quarter}.md"
    quarter_source.rename(quarter_target)

    validator_target = target / "99 系统" / "scripts" / "validate_vault.py"
    shutil.copy2(validator_source, validator_target)

    print(f"Initialized Personal OS at: {target.resolve()}")
    print(f"Current period: {init_date.year} {quarter}")

    if skip_validation:
        return 0
    result = subprocess.run(
        [sys.executable, str(validator_target), "--vault", str(target)],
        check=False,
    )
    return result.returncode


def main() -> int:
    args = parse_args()
    try:
        return initialize(args.target.expanduser(), args.date, args.skip_validation)
    except (OSError, ValueError) as exc:
        print(f"Initialization failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

