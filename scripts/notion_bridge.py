#!/usr/bin/env python3
"""Generate review Markdown and optionally create a Notion page."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Some bundled or isolated Python runtimes do not add the executed script's
# directory to sys.path. Make the sibling module import deterministic.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from notion_api import create_page_with_markdown


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("<"):
        raise RuntimeError(f"Missing {name}. Set it in the process environment.")
    return value


def split_items(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def bullets(items: list[str], empty: str = "暂无") -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- {empty}"


def daily_markdown(date: str, completed: list[str], issues: list[str], actions: list[str]) -> str:
    return f"""# 日复盘 {date}

## 今日完成

{bullets(completed)}

## 问题与阻塞

{bullets(issues)}

## 下一步行动

{bullets(actions)}
"""


def weekly_markdown(date: str, highlights: list[str], challenges: list[str], actions: list[str]) -> str:
    return f"""# 周复盘 {date}

## 本周完成

{bullets(highlights)}

## 主要阻塞

{bullets(challenges)}

## 下周行动

{bullets(actions)}
"""


def monthly_markdown(date: str, highlights: list[str], obstacles: list[str], focus: list[str]) -> str:
    return f"""# 月复盘 {date}

## 本月进展

{bullets(highlights)}

## 主要问题

{bullets(obstacles)}

## 下月重点

{bullets(focus)}
"""


def yearly_markdown(date: str, growth: list[str], lessons: list[str], goals: list[str]) -> str:
    return f"""# 年复盘 {date}

## 年度进展

{bullets(growth)}

## 经验与教训

{bullets(lessons)}

## 下一年度目标

{bullets(goals)}
"""


def add_common(parser: argparse.ArgumentParser, fields: tuple[str, str, str]) -> None:
    parser.add_argument("--date", required=True)
    for field in fields:
        parser.add_argument(f"--{field}", default="")
    parser.add_argument("--dry-run", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    add_common(sub.add_parser("daily"), ("completed", "issues", "actions"))
    add_common(sub.add_parser("weekly"), ("highlights", "challenges", "actions"))
    add_common(sub.add_parser("monthly"), ("highlights", "obstacles", "focus"))
    add_common(sub.add_parser("yearly"), ("growth", "lessons", "goals"))
    return parser


def render(args: argparse.Namespace) -> tuple[str, str, str]:
    if args.command == "daily":
        return (
            f"日复盘 {args.date}",
            daily_markdown(args.date, split_items(args.completed), split_items(args.issues), split_items(args.actions)),
            "NOTION_DIARY_PAGE_ID",
        )
    if args.command == "weekly":
        markdown = weekly_markdown(
            args.date,
            split_items(args.highlights),
            split_items(args.challenges),
            split_items(args.actions),
        )
    elif args.command == "monthly":
        markdown = monthly_markdown(
            args.date,
            split_items(args.highlights),
            split_items(args.obstacles),
            split_items(args.focus),
        )
    else:
        markdown = yearly_markdown(
            args.date,
            split_items(args.growth),
            split_items(args.lessons),
            split_items(args.goals),
        )
    return f"{args.command.title()} review {args.date}", markdown, "NOTION_PARENT_PAGE_ID"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    title, markdown, parent_variable = render(args)
    if args.dry_run:
        print(markdown)
        return 0
    try:
        parent_id = require_env(parent_variable)
        page = create_page_with_markdown(parent_id, title, markdown)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Created review page: {page.get('id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
