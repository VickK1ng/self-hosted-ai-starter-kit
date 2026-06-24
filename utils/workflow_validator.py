"""Validator for n8n workflow JSON backup files.

Validates structure, required fields, node definitions,
and connection integrity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_WORKFLOW_FIELDS = {"id", "name", "nodes", "connections"}

REQUIRED_NODE_FIELDS = {"id", "name", "type", "typeVersion", "position"}


def load_workflow(path: str | Path) -> dict[str, Any]:
    """Load and parse an n8n workflow JSON file.

    Args:
        path: Path to the workflow JSON file.

    Returns:
        Parsed workflow as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If the parsed content is not a dictionary.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")

    with open(path) as f:
        content = json.load(f)

    if not isinstance(content, dict):
        raise ValueError("Workflow file must contain a JSON object")

    return content


def validate_required_fields(workflow: dict[str, Any]) -> list[str]:
    """Check that all required top-level fields are present.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    for field in REQUIRED_WORKFLOW_FIELDS:
        if field not in workflow:
            errors.append(f"Missing required workflow field: '{field}'")
    return errors


def validate_nodes(workflow: dict[str, Any]) -> list[str]:
    """Validate structure of each node in the workflow.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    nodes = workflow.get("nodes", [])
    if not isinstance(nodes, list):
        return ["'nodes' must be an array"]

    if not nodes:
        errors.append("Workflow has no nodes defined")
        return errors

    seen_ids: set[str] = set()
    seen_names: set[str] = set()

    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"Node at index {idx} is not a JSON object")
            continue

        for field in REQUIRED_NODE_FIELDS:
            if field not in node:
                errors.append(
                    f"Node at index {idx}: missing required field '{field}'"
                )

        node_id = node.get("id", "")
        if node_id:
            if node_id in seen_ids:
                errors.append(f"Duplicate node id: '{node_id}'")
            seen_ids.add(node_id)

        node_name = node.get("name", "")
        if node_name:
            if node_name in seen_names:
                errors.append(f"Duplicate node name: '{node_name}'")
            seen_names.add(node_name)

        position = node.get("position")
        if position is not None:
            if not isinstance(position, list) or len(position) != 2:
                errors.append(
                    f"Node '{node_name}': position must be a [x, y] array"
                )
            elif not all(isinstance(p, (int, float)) for p in position):
                errors.append(
                    f"Node '{node_name}': position values must be numbers"
                )

    return errors


def validate_connections(workflow: dict[str, Any]) -> list[str]:
    """Validate that connections reference existing node names.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    connections = workflow.get("connections", {})
    if not isinstance(connections, dict):
        return ["'connections' must be a JSON object"]

    nodes = workflow.get("nodes", [])
    node_names = {n.get("name") for n in nodes if isinstance(n, dict)}

    for source_name, outputs in connections.items():
        if source_name not in node_names:
            errors.append(
                f"Connection source '{source_name}' is not a defined node"
            )

        if not isinstance(outputs, dict):
            continue

        for output_type, target_lists in outputs.items():
            if not isinstance(target_lists, list):
                continue
            for target_group in target_lists:
                if not isinstance(target_group, list):
                    continue
                for target in target_group:
                    if not isinstance(target, dict):
                        continue
                    target_node = target.get("node", "")
                    if target_node and target_node not in node_names:
                        errors.append(
                            f"Connection target '{target_node}' "
                            f"(from '{source_name}') is not a defined node"
                        )

    return errors


def validate_settings(workflow: dict[str, Any]) -> list[str]:
    """Validate workflow settings if present.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    settings = workflow.get("settings")
    if settings is not None and not isinstance(settings, dict):
        errors.append("'settings' must be a JSON object")
    return errors


def validate_workflow(path: str | Path) -> list[str]:
    """Run all validations on an n8n workflow file.

    Returns:
        Aggregated list of error messages.
    """
    workflow = load_workflow(path)
    errors: list[str] = []
    errors.extend(validate_required_fields(workflow))
    errors.extend(validate_nodes(workflow))
    errors.extend(validate_connections(workflow))
    errors.extend(validate_settings(workflow))
    return errors
