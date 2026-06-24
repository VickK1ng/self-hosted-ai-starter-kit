"""Tests for the n8n credential validator module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.credential_validator import (
    KNOWN_CREDENTIAL_TYPES,
    REQUIRED_CREDENTIAL_FIELDS,
    load_credential,
    validate_credential,
    validate_credential_consistency,
    validate_credential_type,
    validate_encrypted_data,
    validate_nodes_access,
    validate_required_fields,
    validate_timestamps,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_CREDENTIAL = {
    "id": "abc123",
    "name": "Test Credential",
    "type": "ollamaApi",
    "data": "U2FsdGVkX18encrypted==",
    "createdAt": "2024-01-01T00:00:00.000Z",
    "updatedAt": "2024-01-01T00:00:00.000Z",
    "nodesAccess": [
        {"nodeType": "@n8n/n8n-nodes-langchain.lmChatOllama", "date": "2024-01-01T00:00:00.000Z"}
    ],
}


@pytest.fixture()
def cred_file(tmp_path: Path) -> Path:
    p = tmp_path / "abc123.json"
    p.write_text(json.dumps(MINIMAL_CREDENTIAL))
    return p


@pytest.fixture()
def real_cred_files() -> list[Path]:
    creds_dir = (
        Path(__file__).resolve().parents[1] / "n8n" / "backup" / "credentials"
    )
    return sorted(creds_dir.glob("*.json"))


# ---------------------------------------------------------------------------
# load_credential
# ---------------------------------------------------------------------------


class TestLoadCredential:
    def test_loads_valid(self, cred_file: Path) -> None:
        cred = load_credential(cred_file)
        assert cred["name"] == "Test Credential"

    def test_raises_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_credential(tmp_path / "nope.json")

    def test_raises_invalid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{nope")
        with pytest.raises(json.JSONDecodeError):
            load_credential(p)

    def test_raises_non_dict(self, tmp_path: Path) -> None:
        p = tmp_path / "arr.json"
        p.write_text("[1]")
        with pytest.raises(ValueError, match="JSON object"):
            load_credential(p)

    def test_accepts_string_path(self, cred_file: Path) -> None:
        cred = load_credential(str(cred_file))
        assert isinstance(cred, dict)


# ---------------------------------------------------------------------------
# validate_required_fields
# ---------------------------------------------------------------------------


class TestValidateRequiredFields:
    def test_all_present(self) -> None:
        assert validate_required_fields(MINIMAL_CREDENTIAL) == []

    def test_missing_id(self) -> None:
        cred = {k: v for k, v in MINIMAL_CREDENTIAL.items() if k != "id"}
        errors = validate_required_fields(cred)
        assert any("id" in e for e in errors)

    def test_missing_all(self) -> None:
        errors = validate_required_fields({})
        assert len(errors) == len(REQUIRED_CREDENTIAL_FIELDS)


# ---------------------------------------------------------------------------
# validate_credential_type
# ---------------------------------------------------------------------------


class TestValidateCredentialType:
    def test_known_type(self) -> None:
        for t in KNOWN_CREDENTIAL_TYPES:
            assert validate_credential_type({"type": t}) == []

    def test_unknown_type(self) -> None:
        warnings = validate_credential_type({"type": "mysqlApi"})
        assert any("Unknown" in w for w in warnings)

    def test_no_type_key(self) -> None:
        assert validate_credential_type({}) == []


# ---------------------------------------------------------------------------
# validate_encrypted_data
# ---------------------------------------------------------------------------


class TestValidateEncryptedData:
    def test_valid_data(self) -> None:
        assert validate_encrypted_data(MINIMAL_CREDENTIAL) == []

    def test_no_data_key(self) -> None:
        assert validate_encrypted_data({}) == []

    def test_non_string_data(self) -> None:
        errors = validate_encrypted_data({"data": 42})
        assert any("encrypted string" in e for e in errors)

    def test_empty_data(self) -> None:
        errors = validate_encrypted_data({"data": "  "})
        assert any("empty" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_nodes_access
# ---------------------------------------------------------------------------


class TestValidateNodesAccess:
    def test_valid(self) -> None:
        assert validate_nodes_access(MINIMAL_CREDENTIAL) == []

    def test_no_key(self) -> None:
        assert validate_nodes_access({}) == []

    def test_not_a_list(self) -> None:
        errors = validate_nodes_access({"nodesAccess": "bad"})
        assert any("array" in e for e in errors)

    def test_entry_not_dict(self) -> None:
        errors = validate_nodes_access({"nodesAccess": ["bad"]})
        assert any("JSON object" in e for e in errors)

    def test_missing_node_type(self) -> None:
        errors = validate_nodes_access(
            {"nodesAccess": [{"date": "2024-01-01"}]}
        )
        assert any("nodeType" in e for e in errors)

    def test_multiple_entries(self) -> None:
        cred = dict(MINIMAL_CREDENTIAL)
        cred["nodesAccess"] = [
            {"nodeType": "a", "date": "2024-01-01"},
            {"nodeType": "b", "date": "2024-01-02"},
        ]
        assert validate_nodes_access(cred) == []


# ---------------------------------------------------------------------------
# validate_timestamps
# ---------------------------------------------------------------------------


class TestValidateTimestamps:
    def test_valid(self) -> None:
        assert validate_timestamps(MINIMAL_CREDENTIAL) == []

    def test_no_timestamps(self) -> None:
        assert validate_timestamps({}) == []

    def test_non_string_created(self) -> None:
        errors = validate_timestamps({"createdAt": 123})
        assert any("string" in e for e in errors)

    def test_empty_updated(self) -> None:
        errors = validate_timestamps({"updatedAt": "  "})
        assert any("empty" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_credential_consistency
# ---------------------------------------------------------------------------


class TestValidateCredentialConsistency:
    def test_matching(self) -> None:
        assert validate_credential_consistency(MINIMAL_CREDENTIAL, "abc123.json") == []

    def test_mismatch(self) -> None:
        errors = validate_credential_consistency(MINIMAL_CREDENTIAL, "xyz.json")
        assert any("does not match" in e for e in errors)

    def test_no_filename(self) -> None:
        assert validate_credential_consistency(MINIMAL_CREDENTIAL, None) == []

    def test_empty_id(self) -> None:
        assert validate_credential_consistency({"id": ""}, "x.json") == []


# ---------------------------------------------------------------------------
# validate_credential (integration)
# ---------------------------------------------------------------------------


class TestValidateCredential:
    def test_valid_file(self, cred_file: Path) -> None:
        assert validate_credential(cred_file) == []

    def test_real_credentials(self, real_cred_files: list[Path]) -> None:
        for cred_path in real_cred_files:
            errors = validate_credential(cred_path)
            assert errors == [], f"{cred_path.name}: {errors}"

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            validate_credential(tmp_path / "nope.json")

    def test_filename_mismatch(self, tmp_path: Path) -> None:
        p = tmp_path / "wrong_name.json"
        p.write_text(json.dumps(MINIMAL_CREDENTIAL))
        errors = validate_credential(p, check_filename=True)
        assert any("does not match" in e for e in errors)

    def test_skip_filename_check(self, tmp_path: Path) -> None:
        p = tmp_path / "wrong_name.json"
        p.write_text(json.dumps(MINIMAL_CREDENTIAL))
        errors = validate_credential(p, check_filename=False)
        assert not any("does not match" in e for e in errors)
