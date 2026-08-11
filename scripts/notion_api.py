#!/usr/bin/env python3
"""Small Notion API client with environment-only credential loading."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_BASE = os.environ.get("NOTION_API_BASE", "https://api.notion.com/v1").rstrip("/")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("<"):
        raise RuntimeError(f"Missing {name}. Set it in the process environment.")
    return value


def request_json(method: str, path: str, payload: dict | None = None) -> dict:
    token = require_env("NOTION_API_KEY")
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": os.environ.get("NOTION_API_VERSION", "2025-09-03"),
        "Content-Type": "application/json",
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_BASE}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Notion HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Notion connection failed: {exc.reason}") from exc


def rich_text(content: str) -> list[dict]:
    return [{"type": "text", "text": {"content": content[:2000]}}]


def markdown_to_blocks(markdown: str) -> list[dict]:
    blocks: list[dict] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        block_type = "paragraph"
        content = line
        if line.startswith("### "):
            block_type, content = "heading_3", line[4:]
        elif line.startswith("## "):
            block_type, content = "heading_2", line[3:]
        elif line.startswith("# "):
            block_type, content = "heading_1", line[2:]
        elif line.startswith(("- ", "* ")):
            block_type, content = "bulleted_list_item", line[2:]
        blocks.append(
            {
                "object": "block",
                "type": block_type,
                block_type: {"rich_text": rich_text(content)},
            }
        )
    return blocks


def create_page(parent_id: str, title: str) -> dict:
    return request_json(
        "POST",
        "/pages",
        {
            "parent": {"page_id": parent_id},
            "properties": {"title": {"title": rich_text(title)}},
        },
    )


def append_markdown(page_id: str, markdown: str) -> dict:
    blocks = markdown_to_blocks(markdown)
    return request_json("PATCH", f"/blocks/{page_id}/children", {"children": blocks})


def create_page_with_markdown(parent_id: str, title: str, markdown: str) -> dict:
    page = create_page(parent_id, title)
    page_id = str(page.get("id", ""))
    if not page_id:
        raise RuntimeError("Notion created a page but returned no page id.")
    append_markdown(page_id, markdown)
    return page


def block_text(block: dict) -> str:
    block_type = block.get("type")
    node = block.get(block_type, {}) if block_type else {}
    return "".join(item.get("plain_text", "") for item in node.get("rich_text", []))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    children = sub.add_parser("children")
    children.add_argument("page_id")
    children.add_argument("--max", type=int, default=100)

    read = sub.add_parser("read")
    read.add_argument("page_id")

    create = sub.add_parser("create")
    create.add_argument("parent_id")
    create.add_argument("title")
    create.add_argument("markdown_file", type=Path)

    append = sub.add_parser("append")
    append.add_argument("page_id")
    append.add_argument("markdown_file", type=Path)

    archive = sub.add_parser("archive")
    archive.add_argument("page_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"children", "read"}:
            query = urllib.parse.urlencode({"page_size": getattr(args, "max", 100)})
            data = request_json("GET", f"/blocks/{args.page_id}/children?{query}")
            for block in data.get("results", []):
                text = block_text(block)
                if args.command == "children":
                    print(f"{block.get('id')} | {block.get('type')} | {text[:200]}")
                elif text:
                    print(f"[{block.get('type')}] {text}")
        elif args.command == "create":
            markdown = args.markdown_file.read_text(encoding="utf-8")
            page = create_page_with_markdown(args.parent_id, args.title, markdown)
            print(f"Created page: {page.get('id')}")
        elif args.command == "append":
            markdown = args.markdown_file.read_text(encoding="utf-8")
            data = append_markdown(args.page_id, markdown)
            print(f"Appended blocks: {len(data.get('results', []))}")
        elif args.command == "archive":
            request_json("PATCH", f"/pages/{args.page_id}", {"archived": True})
            print("Page archived.")
    except (RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
