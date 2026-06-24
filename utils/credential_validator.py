"""Validator for n8n credential JSON backup files.

Validates structure, required fields, and consistency of
credential definitions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_CREDENTIAL_FIELDS = {"id", "name", "type", "data"}

KNOWN_CREDENTIAL_TYPES = {
    "ollamaApi",
    "qdrantApi",
    "openAiApi",
    "postgresApi",
    "httpBasicAuth",
    "httpHeaderAuth",
}


def load_credential(path: str | Path) -> dict[str, Any]:
    """Load and parse an n8n credential JSON file.

    Args:
        path: Path to the credential JSON file.

    Returns:
        Parsed credential as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If the parsed content is not a dictionary.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Credential file not found: {path}")

    with open(path) as f:
        content = json.load(f)

    if not isinstance(content, dict):
        raise ValueError("Credential file must contain a JSON object")

    return content


def validate_required_fields(credential: dict[str, Any]) -> list[str]:
    """Check that all required fields are present.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    for field in REQUIRED_CREDENTIAL_FIELDS:
        if field not in credential:
            errors.append(f"Missing required credential field: '{field}'")
    return errors


def validate_credential_type(credential: dict[str, Any]) -> list[str]:
    """Check that the credential type is recognized.

    Returns:
        List of warning messages (unknown types are warnings, not errors).
    """
    cred_type = credential.get("type")
    if cred_type is None:
        return []  # handled by required fields check
    if cred_type not in KNOWN_CREDENTIAL_TYPES:
        return [f"Unknown credential type: '{cred_type}'"]
    return []


def validate_encrypted_data(credential: dict[str, Any]) -> list[str]:
    """Validate that the data field is a non-empty encrypted string.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    data = credential.get("data")
    if data is None:
        return []  # handled by required fields check
    if not isinstance(data, str):
        errors.append("Credential 'data' must be an encrypted string")
    elif not data.strip():
        errors.append("Credential 'data' is empty")
    return errors


def validate_nodes_access(credential: dict[str, Any]) -> list[str]:
    """Validate the nodesAccess field structure if present.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    access = credential.get("nodesAccess")
    if access is None:
        return []

    if not isinstance(access, list):
        errors.append("'nodesAccess' must be an array")
        return errors

    for idx, entry in enumerate(access):
        if not isinstance(entry, dict):
            errors.append(f"nodesAccess[{idx}] must be a JSON object")
            continue
        if "nodeType" not in entry:
            errors.append(f"nodesAccess[{idx}]: missing 'nodeType'")

    return errors


def validate_timestamps(credential: dict[str, Any]) -> list[str]:
    """Validate that timestamp fields are present and well-formed.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    for field in ("createdAt", "updatedAt"):
        val = credential.get(field)
        if val is not None and not isinstance(val, str):
            errors.append(f"'{field}' must be a string")
        elif val is not None and not val.strip():
            errors.append(f"'{field}' is empty")
    return errors


def validate_credential_consistency(
    credential: dict[str, Any],
    filename: str | None = None,
) -> list[str]:
    """Validate that filename (if provided) matches the credential id.

    Returns:
        List of error messages.
    """
    if filename is None:
        return []

    cred_id = credential.get("id", "")
    stem = Path(filename).stem
    if cred_id and stem and cred_id != stem:
        return [
            f"Credential id '{cred_id}' does not match filename '{filename}'"
        ]
    return []


def validate_credential(
    path: str | Path,
    check_filename: bool = True,
) -> list[str]:
    """Run all validations on an n8n credential file.

    Args:
        path: Path to the credential JSON file.
        check_filename: Whether to validate filename matches id.

    Returns:
        Aggregated list of error/warning messages.
    """
    path = Path(path)
    credential = load_credential(path)
    errors: list[str] = []
    errors.extend(validate_required_fields(credential))
    errors.extend(validate_credential_type(credential))
    errors.extend(validate_encrypted_data(credential))
    errors.extend(validate_nodes_access(credential))
    errors.extend(validate_timestamps(credential))
    if check_filename:
        errors.extend(
            validate_credential_consistency(credential, path.name)
        )
    return errors
