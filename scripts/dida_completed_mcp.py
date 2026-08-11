#!/usr/bin/env python3
"""Read completed TickTick/Dida365 tasks through the official MCP endpoint."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_MCP_URL = "https://mcp.dida365.com"


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("<"):
        raise RuntimeError(f"Missing {name}. Set it in the process environment.")
    return value


def timezone_from_offset(value: str) -> dt.timezone:
    try:
        sign = 1 if value.startswith("+") else -1
        hours, minutes = value[1:].split(":", 1)
        return dt.timezone(sign * dt.timedelta(hours=int(hours), minutes=int(minutes)))
    except (ValueError, IndexError) as exc:
        raise RuntimeError("WORKFLOW_TIMEZONE_OFFSET must look like +08:00.") from exc


def parse_timestamp(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    if normalized.endswith("+0800") or normalized.endswith("+0000"):
        normalized = normalized[:-5] + normalized[-5:-2] + ":" + normalized[-2:]
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def mcp_call(token: str, endpoint: str, day: str, timeout: int) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "list_completed_tasks_by_date",
            "arguments": {"search": {"date": day}},
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"MCP HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MCP connection failed: {exc.reason}") from exc


def extract_items(response: dict) -> list[dict]:
    items: list[dict] = []
    for content in response.get("result", {}).get("content", []):
        if not isinstance(content, dict):
            continue
        text = content.get("text", "")
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            items.append(value)
        elif isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD.")
    parser.add_argument("--end", help="Inclusive end date in YYYY-MM-DD.")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--redact-titles", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        token = require_env("DIDA_API_TOKEN")
        endpoint = os.environ.get("DIDA_MCP_URL", DEFAULT_MCP_URL).strip()
        timezone = timezone_from_offset(
            os.environ.get("WORKFLOW_TIMEZONE_OFFSET", "+08:00")
        )
        start_date = dt.date.fromisoformat(args.start)
        end_date = dt.date.fromisoformat(args.end) if args.end else dt.datetime.now(timezone).date()
    except (RuntimeError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if end_date < start_date:
        print("Date error: --end must not be earlier than --start.", file=sys.stderr)
        return 2

    start = dt.datetime.combine(start_date, dt.time.min, timezone)
    end = dt.datetime.combine(end_date, dt.time.max, timezone)
    seen: dict[str, tuple[dt.datetime, str, str]] = {}

    day = start_date
    while day <= end_date:
        try:
            response = mcp_call(token, endpoint, day.isoformat(), args.timeout)
            if response.get("error"):
                raise RuntimeError(f"MCP returned an error: {response['error']}")
        except RuntimeError as exc:
            print(f"Warning: {day.isoformat()}: {exc}", file=sys.stderr)
            day += dt.timedelta(days=1)
            continue

        for item in extract_items(response):
            completed = parse_timestamp(item.get("completedTime"))
            if completed is None:
                continue
            local_completed = completed.astimezone(timezone)
            if start <= local_completed <= end:
                task_id = str(item.get("id") or f"missing-id-{len(seen)}")
                seen[task_id] = (
                    local_completed,
                    str(item.get("projectId", "")),
                    str(item.get("title", "")),
                )
        day += dt.timedelta(days=1)

    rows = sorted(seen.values(), key=lambda row: row[0])
    print(f"TOTAL completed in window: {len(rows)}")
    for index, (completed, project_id, title) in enumerate(rows, start=1):
        visible_title = f"Task {index}" if args.redact_titles else title[:120]
        visible_project = "<redacted>" if args.redact_titles else project_id
        print(f"{completed:%Y-%m-%d %H:%M} | {visible_project} | {visible_title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
