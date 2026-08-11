#!/usr/bin/env python3
"""List incomplete TickTick/Dida365 tasks project by project.

Configuration is read only from environment variables. No Hermes configuration
file is opened or modified.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    project_id: str
    name: str


def load_projects() -> list[Project]:
    raw = os.environ.get("DIDA_PROJECTS_JSON", "").strip()
    if not raw:
        raise RuntimeError(
            "Missing DIDA_PROJECTS_JSON. Set it to a JSON array such as "
            "[{\"id\":\"<PROJECT_ID>\",\"name\":\"Demo\"}]."
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"DIDA_PROJECTS_JSON is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, list) or not data:
        raise RuntimeError("DIDA_PROJECTS_JSON must be a non-empty JSON array.")

    projects: list[Project] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"Project item {index} must be an object.")
        project_id = str(item.get("id", "")).strip()
        name = str(item.get("name", f"Project {index}")).strip()
        if not project_id or project_id.startswith("<"):
            raise RuntimeError(f"Project item {index} has no usable id.")
        projects.append(Project(project_id=project_id, name=name or f"Project {index}"))
    return projects


def resolve_cli() -> str:
    configured = os.environ.get("DIDA_CLI_PATH", "dida").strip() or "dida"
    resolved = shutil.which(configured)
    if resolved:
        return resolved
    if os.path.isfile(configured):
        return configured
    raise RuntimeError(
        "Dida CLI was not found. Install it or set DIDA_CLI_PATH to the executable."
    )


def fetch_project(cli: str, project: Project, timeout: int) -> dict:
    result = subprocess.run(
        [cli, "project", "data", project.project_id, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown CLI error").strip()[:200]
        raise RuntimeError(f"CLI exited with {result.returncode}: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI returned invalid JSON: {exc.msg}") from exc


def incomplete_tasks(data: dict) -> list[dict]:
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return []
    return [
        task
        for task in tasks
        if isinstance(task, dict)
        and task.get("status") == 0
        and not task.get("completedTime")
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-names",
        help="Comma-separated display names from DIDA_PROJECTS_JSON.",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--redact-titles",
        action="store_true",
        help="Print numbered placeholders instead of task titles.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        projects = load_projects()
        cli = resolve_cli()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.project_names:
        wanted = {name.strip() for name in args.project_names.split(",") if name.strip()}
        projects = [project for project in projects if project.name in wanted]
        if not projects:
            print("No configured project matched --project-names.", file=sys.stderr)
            return 2

    total = 0
    for project in projects:
        try:
            tasks = incomplete_tasks(fetch_project(cli, project, args.timeout))
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"Warning: {project.name}: {exc}", file=sys.stderr)
            continue

        if not tasks:
            continue
        print(f"== {project.name} ({len(tasks)}) ==")
        for index, task in enumerate(tasks, start=1):
            title = str(task.get("title", "")).strip() or "(untitled)"
            priority = int(task.get("priority", 0) or 0)
            marker = "[HIGH]" if priority >= 3 else "[TASK]"
            visible_title = f"Task {index}" if args.redact_titles else title[:120]
            print(f"  {marker} {visible_title}")
            total += 1

    print(f"TOTAL incomplete: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
