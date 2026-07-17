#!/usr/bin/env python3
"""Collect, render, and verify the Hermes project control brief."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "project-control" / "project-control.json"
SCHEMA_PATH = ROOT / "project-control" / "project-control.schema.json"
BRIEF_PATH = ROOT / "docs" / "hermes-project-control-brief.md"
START_MARKER = "<!-- BEGIN GENERATED PROJECT CONTROL STATUS -->"
END_MARKER = "<!-- END GENERATED PROJECT CONTROL STATUS -->"
ALLOWED_STATUSES = {"recorded", "verified", "unresolved", "simulated", "failed"}
BOUNDARY_STATEMENT = (
    "Do not claim that agents, tasks, missions, models, telemetry, approvals, "
    "settings, artifacts, tools, or persistence are connected to a real Hermes "
    "backend unless independently verified."
)
AUTHORITATIVE_PROJECT = {
    "repository": "MerverliPy/hermes-webui",
    "siteSlug": "hermes-agent-web-ui",
    "siteProjectId": "appgprj_6a57ca3238c081919fcc5634802b2800",
    "trackedVersion": 24,
    "siteRevisionKey": "hermes-site-version-24-27b62e0a21a1",
    "adapterPhase": "host-synchronized",
    "lastSynchronizedAt": "2026-07-16T21:23:19.524Z",
    "visualDirection": "graphite-and-cyan",
}


class ControlError(RuntimeError):
    """Raised when control state cannot be safely updated."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ControlError(f"expected a JSON object in {path}")
    return value


def validate_state(state: dict[str, Any]) -> None:
    """Enforce the safety-critical subset of the Draft 2020-12 schema."""
    if state.get("schemaVersion") != 1:
        raise ControlError("schemaVersion must be 1")
    project = state.get("project")
    if not isinstance(project, dict):
        raise ControlError("project must be an object")
    for key, expected in AUTHORITATIVE_PROJECT.items():
        if project.get(key) != expected:
            raise ControlError(f"project.{key} must remain {expected!r}")

    rows = state.get("statusRows")
    if not isinstance(rows, list) or len(rows) != 10:
        raise ControlError("statusRows must contain exactly 10 rows")
    ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ControlError("each status row must be an object")
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id or row_id in ids:
            raise ControlError("status row IDs must be unique non-empty strings")
        ids.add(row_id)
        status = row.get("status")
        evidence = row.get("evidence")
        if status not in ALLOWED_STATUSES:
            raise ControlError(f"invalid status {status!r} for {row_id}")
        if not isinstance(evidence, list):
            raise ControlError(f"evidence must be an array for {row_id}")
        if status == "verified" and (not row.get("value") or not evidence):
            raise ControlError(f"verified row {row_id} requires a value and evidence")
        for item in evidence:
            if not isinstance(item, dict) or not item.get("source") or not item.get("detail"):
                raise ControlError(f"invalid evidence for {row_id}")

    boundary = state.get("simulationBoundary")
    if not isinstance(boundary, dict):
        raise ControlError("simulationBoundary must be an object")
    if boundary.get("protected") is not True or boundary.get("status") != "simulated":
        raise ControlError("simulationBoundary must remain protected and simulated")
    if boundary.get("statement") != BOUNDARY_STATEMENT:
        raise ControlError("simulationBoundary statement was changed")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _git(*args: str, cwd: Path = ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        raise ControlError(f"git {' '.join(args)} failed: {detail.strip()}") from exc
    return result.stdout.strip()


def collect_state(state_path: Path = STATE_PATH, repo_root: Path = ROOT) -> dict[str, Any]:
    """Collect all local facts before replacing the state file."""
    original = _load_json(state_path)
    validate_state(original)
    revision = _git("rev-parse", "HEAD", cwd=repo_root)
    branch = _git("branch", "--show-current", cwd=repo_root)
    if not branch:
        raise ControlError("cannot collect from a detached HEAD")

    updated = copy.deepcopy(original)
    rows = {row["id"]: row for row in updated["statusRows"]}
    rows["sourceRevision"].update({
        "value": revision,
        "status": "verified",
        "evidence": [{"source": "git", "detail": "git rev-parse HEAD"}],
    })
    rows["branch"].update({
        "value": branch,
        "status": "verified",
        "evidence": [{"source": "git", "detail": "git branch --show-current"}],
    })
    updated["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    validate_state(updated)
    _atomic_write(state_path, json.dumps(updated, indent=2, ensure_ascii=False) + "\n")
    return updated


def render_region(state: dict[str, Any]) -> str:
    validate_state(state)
    lines = [
        f"Generated: `{state.get('generatedAt') or 'not collected'}`",
        "",
        "| Control | Value | Status | Evidence |",
        "|---|---|---|---|",
    ]
    for row in state["statusRows"]:
        value = str(row["value"]) if row["value"] is not None else "Unresolved"
        value = value.replace("|", "\\|").replace("\n", " ")
        evidence = "; ".join(
            f"{item['source']}: {item['detail']}" for item in row["evidence"]
        ) or "—"
        evidence = evidence.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row['label']} | `{value}` | {row['status']} | {evidence} |")
    return "\n".join(lines)


def replace_generated_region(document: str, region: str) -> str:
    if document.count(START_MARKER) != 1 or document.count(END_MARKER) != 1:
        raise ControlError("brief must contain exactly one start marker and one end marker")
    start = document.index(START_MARKER) + len(START_MARKER)
    end = document.index(END_MARKER)
    if start >= end:
        raise ControlError("generated-region markers are malformed or reversed")
    return document[:start] + "\n" + region.rstrip() + "\n" + document[end:]


def render_brief(state_path: Path = STATE_PATH, brief_path: Path = BRIEF_PATH) -> str:
    state = _load_json(state_path)
    validate_state(state)
    try:
        current = brief_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ControlError(f"cannot read {brief_path}: {exc}") from exc
    rendered = replace_generated_region(current, render_region(state))
    _atomic_write(brief_path, rendered)
    return rendered


def verify(state_path: Path = STATE_PATH, schema_path: Path = SCHEMA_PATH,
           brief_path: Path = BRIEF_PATH) -> None:
    state = _load_json(state_path)
    validate_state(state)
    schema = _load_json(schema_path)
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ControlError("schema must declare JSON Schema Draft 2020-12")
    brief = brief_path.read_text(encoding="utf-8")
    expected = replace_generated_region(brief, render_region(state))
    if brief != expected:
        raise ControlError("generated brief region is stale; run render")
    if BOUNDARY_STATEMENT not in " ".join(brief.split()):
        raise ControlError("protected simulation boundary is missing from the brief")


def update() -> None:
    collect_state()
    render_brief()
    verify()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "render", "verify", "update"))
    args = parser.parse_args()
    try:
        if args.command == "collect":
            collect_state()
        elif args.command == "render":
            render_brief()
        elif args.command == "verify":
            verify()
        else:
            update()
    except ControlError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
