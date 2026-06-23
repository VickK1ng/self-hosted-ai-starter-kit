"""Tests for the n8n workflow validator module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.workflow_validator import (
    REQUIRED_NODE_FIELDS,
    REQUIRED_WORKFLOW_FIELDS,
    load_workflow,
    validate_connections,
    validate_nodes,
    validate_required_fields,
    validate_settings,
    validate_workflow,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_WORKFLOW = {
    "id": "abc123",
    "name": "Test Workflow",
    "nodes": [
        {
            "id": "node-1",
            "name": "Start",
            "type": "trigger",
            "typeVersion": 1,
            "position": [100, 200],
        },
        {
            "id": "node-2",
            "name": "End",
            "type": "action",
            "typeVersion": 1,
            "position": [300, 200],
        },
    ],
    "connections": {
        "Start": {
            "main": [[{"node": "End", "type": "main", "index": 0}]]
        }
    },
    "settings": {"executionOrder": "v1"},
}


@pytest.fixture()
def workflow_file(tmp_path: Path) -> Path:
    p = tmp_path / "workflow.json"
    p.write_text(json.dumps(MINIMAL_WORKFLOW))
    return p


@pytest.fixture()
def real_workflow_file() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "n8n"
        / "backup"
        / "workflows"
        / "srOnR8PAY3u4RSwb.json"
    )


# ---------------------------------------------------------------------------
# load_workflow
# ---------------------------------------------------------------------------


class TestLoadWorkflow:
    def test_loads_valid(self, workflow_file: Path) -> None:
        wf = load_workflow(workflow_file)
        assert wf["name"] == "Test Workflow"

    def test_raises_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_workflow(tmp_path / "nope.json")

    def test_raises_invalid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{not json")
        with pytest.raises(json.JSONDecodeError):
            load_workflow(p)

    def test_raises_non_dict(self, tmp_path: Path) -> None:
        p = tmp_path / "arr.json"
        p.write_text("[1,2,3]")
        with pytest.raises(ValueError, match="JSON object"):
            load_workflow(p)

    def test_accepts_string_path(self, workflow_file: Path) -> None:
        wf = load_workflow(str(workflow_file))
        assert isinstance(wf, dict)


# ---------------------------------------------------------------------------
# validate_required_fields
# ---------------------------------------------------------------------------


class TestValidateRequiredFields:
    def test_all_present(self) -> None:
        assert validate_required_fields(MINIMAL_WORKFLOW) == []

    def test_missing_id(self) -> None:
        wf = {k: v for k, v in MINIMAL_WORKFLOW.items() if k != "id"}
        errors = validate_required_fields(wf)
        assert any("id" in e for e in errors)

    def test_missing_all(self) -> None:
        errors = validate_required_fields({})
        assert len(errors) == len(REQUIRED_WORKFLOW_FIELDS)


# ---------------------------------------------------------------------------
# validate_nodes
# ---------------------------------------------------------------------------


class TestValidateNodes:
    def test_valid_nodes(self) -> None:
        assert validate_nodes(MINIMAL_WORKFLOW) == []

    def test_empty_nodes(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, nodes=[])
        errors = validate_nodes(wf)
        assert any("no nodes" in e for e in errors)

    def test_nodes_not_list(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, nodes="bad")
        errors = validate_nodes(wf)
        assert any("array" in e for e in errors)

    def test_node_not_dict(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, nodes=["not a dict"])
        errors = validate_nodes(wf)
        assert any("not a JSON object" in e for e in errors)

    def test_missing_node_field(self) -> None:
        node = {"id": "n1", "name": "X"}  # missing type, typeVersion, position
        wf = dict(MINIMAL_WORKFLOW, nodes=[node])
        errors = validate_nodes(wf)
        assert any("type" in e for e in errors)
        assert any("typeVersion" in e for e in errors)
        assert any("position" in e for e in errors)

    def test_duplicate_node_id(self) -> None:
        node = {
            "id": "dup",
            "name": "A",
            "type": "t",
            "typeVersion": 1,
            "position": [0, 0],
        }
        node2 = dict(node, name="B")
        wf = dict(MINIMAL_WORKFLOW, nodes=[node, node2])
        errors = validate_nodes(wf)
        assert any("Duplicate node id" in e for e in errors)

    def test_duplicate_node_name(self) -> None:
        base = {
            "type": "t",
            "typeVersion": 1,
            "position": [0, 0],
        }
        n1 = dict(base, id="a", name="Same")
        n2 = dict(base, id="b", name="Same")
        wf = dict(MINIMAL_WORKFLOW, nodes=[n1, n2])
        errors = validate_nodes(wf)
        assert any("Duplicate node name" in e for e in errors)

    def test_invalid_position_length(self) -> None:
        node = {
            "id": "n1",
            "name": "X",
            "type": "t",
            "typeVersion": 1,
            "position": [1, 2, 3],
        }
        wf = dict(MINIMAL_WORKFLOW, nodes=[node])
        errors = validate_nodes(wf)
        assert any("[x, y]" in e for e in errors)

    def test_invalid_position_values(self) -> None:
        node = {
            "id": "n1",
            "name": "X",
            "type": "t",
            "typeVersion": 1,
            "position": ["a", "b"],
        }
        wf = dict(MINIMAL_WORKFLOW, nodes=[node])
        errors = validate_nodes(wf)
        assert any("numbers" in e for e in errors)

    def test_no_nodes_key(self) -> None:
        wf = {"id": "x", "name": "y", "connections": {}}
        errors = validate_nodes(wf)
        assert any("no nodes" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_connections
# ---------------------------------------------------------------------------


class TestValidateConnections:
    def test_valid_connections(self) -> None:
        assert validate_connections(MINIMAL_WORKFLOW) == []

    def test_source_not_defined(self) -> None:
        wf = dict(MINIMAL_WORKFLOW)
        wf = dict(wf, connections={
            "Ghost": {"main": [[{"node": "End", "type": "main", "index": 0}]]}
        })
        errors = validate_connections(wf)
        assert any("Ghost" in e for e in errors)

    def test_target_not_defined(self) -> None:
        wf = dict(MINIMAL_WORKFLOW)
        wf = dict(wf, connections={
            "Start": {"main": [[{"node": "Ghost", "type": "main", "index": 0}]]}
        })
        errors = validate_connections(wf)
        assert any("Ghost" in e for e in errors)

    def test_connections_not_dict(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, connections="bad")
        errors = validate_connections(wf)
        assert any("JSON object" in e for e in errors)

    def test_empty_connections(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, connections={})
        assert validate_connections(wf) == []

    def test_non_dict_outputs(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, connections={
            "Start": "not a dict"
        })
        errors = validate_connections(wf)
        assert isinstance(errors, list)

    def test_non_list_output_type(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, connections={
            "Start": {"main": "not a list"}
        })
        # Should not crash
        errors = validate_connections(wf)
        assert isinstance(errors, list)

    def test_non_list_target_group(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, connections={
            "Start": {"main": ["not a list"]}
        })
        errors = validate_connections(wf)
        assert isinstance(errors, list)

    def test_non_dict_target(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, connections={
            "Start": {"main": [["not a dict"]]}
        })
        errors = validate_connections(wf)
        assert isinstance(errors, list)


# ---------------------------------------------------------------------------
# validate_settings
# ---------------------------------------------------------------------------


class TestValidateSettings:
    def test_valid_settings(self) -> None:
        assert validate_settings(MINIMAL_WORKFLOW) == []

    def test_no_settings(self) -> None:
        wf = {k: v for k, v in MINIMAL_WORKFLOW.items() if k != "settings"}
        assert validate_settings(wf) == []

    def test_none_settings(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, settings=None)
        assert validate_settings(wf) == []

    def test_invalid_settings(self) -> None:
        wf = dict(MINIMAL_WORKFLOW, settings="bad")
        errors = validate_settings(wf)
        assert any("JSON object" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_workflow (integration)
# ---------------------------------------------------------------------------


class TestValidateWorkflow:
    def test_valid_file(self, workflow_file: Path) -> None:
        assert validate_workflow(workflow_file) == []

    def test_real_workflow(self, real_workflow_file: Path) -> None:
        assert validate_workflow(real_workflow_file) == []

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            validate_workflow(tmp_path / "nope.json")
