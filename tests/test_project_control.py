import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "project_control", ROOT / "scripts" / "project_control.py"
)
project_control = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(project_control)


@pytest.fixture
def state():
    return json.loads(
        (ROOT / "project-control" / "project-control.json").read_text(encoding="utf-8")
    )


def test_state_is_valid(state):
    project_control.validate_state(state)


def test_schema_declares_draft_2020_12():
    schema = json.loads(
        (ROOT / "project-control" / "project-control.schema.json").read_text(encoding="utf-8")
    )
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_exactly_ten_status_rows(state):
    assert len(state["statusRows"]) == 10


def test_verified_status_requires_evidence(state):
    changed = copy.deepcopy(state)
    row = changed["statusRows"][0]
    row.update(status="verified", evidence=[])
    with pytest.raises(project_control.ControlError, match="requires a value and evidence"):
        project_control.validate_state(changed)


def test_invalid_status_is_rejected(state):
    changed = copy.deepcopy(state)
    changed["statusRows"][0]["status"] = "complete"
    with pytest.raises(project_control.ControlError, match="invalid status"):
        project_control.validate_state(changed)


def test_simulation_boundary_cannot_be_promoted(state):
    changed = copy.deepcopy(state)
    changed["simulationBoundary"]["status"] = "verified"
    with pytest.raises(project_control.ControlError, match="protected and simulated"):
        project_control.validate_state(changed)


def test_renderer_is_idempotent(state):
    document = f"before\n{project_control.START_MARKER}\nold\n{project_control.END_MARKER}\nafter\n"
    once = project_control.replace_generated_region(document, project_control.render_region(state))
    twice = project_control.replace_generated_region(once, project_control.render_region(state))
    assert twice == once


def test_renderer_preserves_manual_content(state):
    document = f"manual before\n{project_control.START_MARKER}\nold\n{project_control.END_MARKER}\nmanual after\n"
    rendered = project_control.replace_generated_region(document, project_control.render_region(state))
    assert rendered.startswith("manual before\n")
    assert rendered.endswith("\nmanual after\n")


def test_malformed_markers_are_rejected(state):
    documents = [
        "no markers",
        f"{project_control.START_MARKER}\nmissing end",
        f"{project_control.END_MARKER}\n{project_control.START_MARKER}",
        f"{project_control.START_MARKER}\na\n{project_control.START_MARKER}\n{project_control.END_MARKER}",
    ]
    for document in documents:
        with pytest.raises(project_control.ControlError, match="marker"):
            project_control.replace_generated_region(document, project_control.render_region(state))


def test_failed_collection_preserves_existing_state(tmp_path, monkeypatch, state):
    state_path = tmp_path / "project-control.json"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    before = state_path.read_bytes()

    def fail_git(*_args, **_kwargs):
        raise project_control.ControlError("collection failed")

    monkeypatch.setattr(project_control, "_git", fail_git)
    with pytest.raises(project_control.ControlError, match="collection failed"):
        project_control.collect_state(state_path=state_path, repo_root=tmp_path)
    assert state_path.read_bytes() == before


def test_collect_promotes_only_git_facts(tmp_path, state):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "feature-test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "file").write_text("test", encoding="utf-8")
    subprocess.run(["git", "add", "file"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "test"], cwd=repo, check=True, capture_output=True)
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    collected = project_control.collect_state(state_path=state_path, repo_root=repo)
    rows = {row["id"]: row for row in collected["statusRows"]}
    assert rows["sourceRevision"]["status"] == "verified"
    assert rows["branch"]["value"] == "feature-test"
    assert rows["siteDeployment"]["status"] == "unresolved"
    assert collected["simulationBoundary"]["status"] == "simulated"
