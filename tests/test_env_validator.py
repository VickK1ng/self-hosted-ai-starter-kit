"""Tests for the .env validator module."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.env_validator import (
    REQUIRED_ENV_VARS,
    _collect_env_names,
    extract_compose_env_refs,
    load_env_file,
    validate_env_file,
    validate_no_default_secrets,
    validate_required_vars,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_env(tmp_path: Path, content: str) -> Path:
    p = tmp_path / ".env"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# load_env_file
# ---------------------------------------------------------------------------


class TestLoadEnvFile:
    def test_loads_simple(self, tmp_path: Path) -> None:
        p = _write_env(tmp_path, "KEY=value\n")
        env = load_env_file(p)
        assert env == {"KEY": "value"}

    def test_strips_quotes(self, tmp_path: Path) -> None:
        p = _write_env(tmp_path, 'DB="mydb"\nPW=\'secret\'\n')
        env = load_env_file(p)
        assert env["DB"] == "mydb"
        assert env["PW"] == "secret"

    def test_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        p = _write_env(tmp_path, "# comment\n\nA=1\n")
        env = load_env_file(p)
        assert env == {"A": "1"}

    def test_handles_empty_value(self, tmp_path: Path) -> None:
        p = _write_env(tmp_path, "EMPTY=\n")
        env = load_env_file(p)
        assert env["EMPTY"] == ""

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_env_file(tmp_path / "nope")

    def test_accepts_path_string(self, tmp_path: Path) -> None:
        p = _write_env(tmp_path, "X=1\n")
        env = load_env_file(str(p))
        assert env == {"X": "1"}

    def test_ignores_malformed_lines(self, tmp_path: Path) -> None:
        p = _write_env(tmp_path, "no-equals\nGOOD=yes\n")
        env = load_env_file(p)
        assert env == {"GOOD": "yes"}

    def test_value_with_equals(self, tmp_path: Path) -> None:
        p = _write_env(tmp_path, "URL=https://host?a=1&b=2\n")
        env = load_env_file(p)
        assert env["URL"] == "https://host?a=1&b=2"

    def test_real_env_file(self) -> None:
        real = Path(__file__).resolve().parents[1] / ".env"
        env = load_env_file(real)
        assert "POSTGRES_USER" in env


# ---------------------------------------------------------------------------
# validate_required_vars
# ---------------------------------------------------------------------------


class TestValidateRequiredVars:
    def test_all_present(self) -> None:
        env = {v: "val" for v in REQUIRED_ENV_VARS}
        assert validate_required_vars(env) == []

    def test_missing_var(self) -> None:
        env = {v: "val" for v in REQUIRED_ENV_VARS}
        del env["POSTGRES_DB"]
        errors = validate_required_vars(env)
        assert any("POSTGRES_DB" in e for e in errors)

    def test_empty_var(self) -> None:
        env = {v: "val" for v in REQUIRED_ENV_VARS}
        env["POSTGRES_USER"] = ""
        errors = validate_required_vars(env)
        assert any("empty" in e for e in errors)

    def test_custom_required(self) -> None:
        errors = validate_required_vars({}, required={"CUSTOM"})
        assert any("CUSTOM" in e for e in errors)

    def test_empty_env(self) -> None:
        errors = validate_required_vars({})
        assert len(errors) == len(REQUIRED_ENV_VARS)


# ---------------------------------------------------------------------------
# validate_no_default_secrets
# ---------------------------------------------------------------------------


class TestValidateNoDefaultSecrets:
    def test_safe_values(self) -> None:
        env = {
            "POSTGRES_PASSWORD": "r4nd0m_str0ng_p@ss!",
            "N8N_ENCRYPTION_KEY": "a9b8c7d6e5f4",
            "N8N_USER_MANAGEMENT_JWT_SECRET": "jwt-x7y8z9",
        }
        assert validate_no_default_secrets(env) == []

    def test_default_password(self) -> None:
        env = {"POSTGRES_PASSWORD": "password"}
        warnings = validate_no_default_secrets(env)
        assert any("POSTGRES_PASSWORD" in w for w in warnings)

    def test_default_encryption_key(self) -> None:
        env = {"N8N_ENCRYPTION_KEY": "super-secret-key"}
        warnings = validate_no_default_secrets(env)
        assert any("N8N_ENCRYPTION_KEY" in w for w in warnings)

    def test_case_insensitive_check(self) -> None:
        env = {"POSTGRES_PASSWORD": "PASSWORD"}
        warnings = validate_no_default_secrets(env)
        assert any("POSTGRES_PASSWORD" in w for w in warnings)

    def test_custom_secret_vars(self) -> None:
        env = {"MY_KEY": "changeme"}
        warnings = validate_no_default_secrets(
            env, secret_vars={"MY_KEY"}
        )
        assert len(warnings) == 1

    def test_custom_forbidden_values(self) -> None:
        env = {"POSTGRES_PASSWORD": "letmein"}
        warnings = validate_no_default_secrets(
            env, forbidden_values={"letmein"}
        )
        assert len(warnings) == 1

    def test_real_env_has_defaults(self) -> None:
        real = Path(__file__).resolve().parents[1] / ".env"
        env = load_env_file(real)
        warnings = validate_no_default_secrets(env)
        # The shipped .env has insecure defaults
        assert len(warnings) > 0


# ---------------------------------------------------------------------------
# _collect_env_names
# ---------------------------------------------------------------------------


class TestCollectEnvNames:
    def test_list_env(self) -> None:
        refs: set[str] = set()
        _collect_env_names({"environment": ["FOO=bar", "BAZ"]}, refs)
        assert "FOO" in refs
        assert "BAZ" in refs

    def test_dict_env(self) -> None:
        refs: set[str] = set()
        _collect_env_names({"environment": {"A": "1", "B": "2"}}, refs)
        assert refs == {"A", "B"}

    def test_no_env(self) -> None:
        refs: set[str] = set()
        _collect_env_names({"image": "foo"}, refs)
        assert refs == set()

    def test_substitution_syntax(self) -> None:
        refs: set[str] = set()
        _collect_env_names(
            {"environment": ["DB_USER=${POSTGRES_USER}"]}, refs
        )
        assert "DB_USER" in refs


# ---------------------------------------------------------------------------
# extract_compose_env_refs
# ---------------------------------------------------------------------------


class TestExtractComposeEnvRefs:
    def test_real_compose(self) -> None:
        compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yml"
        refs = extract_compose_env_refs(compose_path)
        assert "POSTGRES_USER" in refs
        assert "POSTGRES_PASSWORD" in refs
        assert "N8N_ENCRYPTION_KEY" in refs

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            extract_compose_env_refs(tmp_path / "nope.yml")

    def test_dollar_brace_syntax(self, tmp_path: Path) -> None:
        p = tmp_path / "compose.yml"
        p.write_text("services:\n  web:\n    image: nginx\n    environment:\n      - DB=${MY_DB}\n")
        refs = extract_compose_env_refs(p)
        assert "MY_DB" in refs

    def test_bare_dollar_syntax(self, tmp_path: Path) -> None:
        p = tmp_path / "compose.yml"
        p.write_text("services:\n  web:\n    image: nginx\n    command: echo $TOKEN\n")
        refs = extract_compose_env_refs(p)
        assert "TOKEN" in refs


# ---------------------------------------------------------------------------
# validate_env_file (integration)
# ---------------------------------------------------------------------------


class TestValidateEnvFile:
    def test_valid_env(self, tmp_path: Path) -> None:
        content = "\n".join(
            f"{v}=strong_value_{i}" for i, v in enumerate(REQUIRED_ENV_VARS)
        )
        p = _write_env(tmp_path, content + "\n")
        messages = validate_env_file(p)
        # No missing-var errors; may still have insecure-default warnings
        assert not any("Missing" in m for m in messages)

    def test_real_env(self) -> None:
        real = Path(__file__).resolve().parents[1] / ".env"
        messages = validate_env_file(real)
        # Real file has insecure defaults
        assert any("insecure" in m for m in messages)

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            validate_env_file(tmp_path / "nope")
