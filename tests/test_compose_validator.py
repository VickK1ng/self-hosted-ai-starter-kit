"""Tests for the Docker Compose validator module."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from utils.compose_validator import (
    POSTGRES_ENV_VARS,
    REQUIRED_NETWORKS,
    REQUIRED_SERVICES,
    REQUIRED_VOLUMES,
    _extract_env_var_names,
    load_compose_file,
    validate_compose,
    validate_healthcheck,
    validate_networks,
    validate_service_environment,
    validate_service_image,
    validate_services,
    validate_top_level_keys,
    validate_volumes,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_COMPOSE = {
    "services": {
        "postgres": {
            "image": "postgres:16-alpine",
            "environment": [
                "POSTGRES_USER",
                "POSTGRES_PASSWORD",
                "POSTGRES_DB",
            ],
            "healthcheck": {
                "test": ["CMD-SHELL", "pg_isready"],
                "interval": "5s",
            },
        },
        "n8n": {"image": "n8nio/n8n:latest"},
        "n8n-import": {"image": "n8nio/n8n:latest"},
        "qdrant": {"image": "qdrant/qdrant"},
    },
    "volumes": {
        "n8n_storage": None,
        "postgres_storage": None,
        "ollama_storage": None,
        "qdrant_storage": None,
    },
    "networks": {"demo": None},
}


@pytest.fixture()
def compose_file(tmp_path: Path) -> Path:
    """Write a minimal valid compose file and return its path."""
    p = tmp_path / "docker-compose.yml"
    p.write_text(yaml.dump(MINIMAL_COMPOSE))
    return p


@pytest.fixture()
def real_compose_file() -> Path:
    """Return the path to the repo's actual docker-compose.yml."""
    return Path(__file__).resolve().parents[1] / "docker-compose.yml"


# ---------------------------------------------------------------------------
# load_compose_file
# ---------------------------------------------------------------------------


class TestLoadComposeFile:
    def test_loads_valid_file(self, compose_file: Path) -> None:
        result = load_compose_file(compose_file)
        assert isinstance(result, dict)
        assert "services" in result

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_compose_file(tmp_path / "nope.yml")

    def test_raises_on_invalid_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yml"
        p.write_text("{unclosed: [bracket")
        with pytest.raises(yaml.YAMLError):
            load_compose_file(p)

    def test_raises_on_non_dict(self, tmp_path: Path) -> None:
        p = tmp_path / "list.yml"
        p.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="mapping"):
            load_compose_file(p)

    def test_accepts_path_string(self, compose_file: Path) -> None:
        result = load_compose_file(str(compose_file))
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# validate_top_level_keys
# ---------------------------------------------------------------------------


class TestValidateTopLevelKeys:
    def test_valid(self) -> None:
        assert validate_top_level_keys(MINIMAL_COMPOSE) == []

    def test_missing_services(self) -> None:
        compose = {k: v for k, v in MINIMAL_COMPOSE.items() if k != "services"}
        errors = validate_top_level_keys(compose)
        assert any("services" in e for e in errors)

    def test_missing_volumes(self) -> None:
        compose = {k: v for k, v in MINIMAL_COMPOSE.items() if k != "volumes"}
        errors = validate_top_level_keys(compose)
        assert any("volumes" in e for e in errors)

    def test_missing_networks(self) -> None:
        compose = {k: v for k, v in MINIMAL_COMPOSE.items() if k != "networks"}
        errors = validate_top_level_keys(compose)
        assert any("networks" in e for e in errors)

    def test_all_missing(self) -> None:
        errors = validate_top_level_keys({})
        assert len(errors) == 3


# ---------------------------------------------------------------------------
# validate_services
# ---------------------------------------------------------------------------


class TestValidateServices:
    def test_all_present(self) -> None:
        assert validate_services(MINIMAL_COMPOSE) == []

    def test_missing_one_service(self) -> None:
        compose = dict(MINIMAL_COMPOSE)
        svcs = dict(compose["services"])
        del svcs["qdrant"]
        compose["services"] = svcs
        errors = validate_services(compose)
        assert any("qdrant" in e for e in errors)

    def test_no_services_key(self) -> None:
        errors = validate_services({})
        assert len(errors) == len(REQUIRED_SERVICES)

    def test_services_not_a_dict(self) -> None:
        errors = validate_services({"services": "bad"})
        assert any("mapping" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_volumes
# ---------------------------------------------------------------------------


class TestValidateVolumes:
    def test_all_present(self) -> None:
        assert validate_volumes(MINIMAL_COMPOSE) == []

    def test_missing_volume(self) -> None:
        compose = dict(MINIMAL_COMPOSE)
        vols = dict(compose["volumes"])
        del vols["qdrant_storage"]
        compose["volumes"] = vols
        errors = validate_volumes(compose)
        assert any("qdrant_storage" in e for e in errors)

    def test_volumes_not_a_dict(self) -> None:
        errors = validate_volumes({"volumes": "bad"})
        assert any("mapping" in e for e in errors)

    def test_no_volumes_key(self) -> None:
        errors = validate_volumes({})
        assert len(errors) == len(REQUIRED_VOLUMES)


# ---------------------------------------------------------------------------
# validate_networks
# ---------------------------------------------------------------------------


class TestValidateNetworks:
    def test_all_present(self) -> None:
        assert validate_networks(MINIMAL_COMPOSE) == []

    def test_missing_network(self) -> None:
        errors = validate_networks({"networks": {}})
        assert any("demo" in e for e in errors)

    def test_networks_not_a_dict(self) -> None:
        errors = validate_networks({"networks": ["demo"]})
        assert any("mapping" in e for e in errors)


# ---------------------------------------------------------------------------
# _extract_env_var_names
# ---------------------------------------------------------------------------


class TestExtractEnvVarNames:
    def test_key_value(self) -> None:
        result = _extract_env_var_names(["FOO=bar", "BAZ=qux"])
        assert result == {"FOO", "BAZ"}

    def test_bare_var(self) -> None:
        result = _extract_env_var_names(["SOME_VAR"])
        assert "SOME_VAR" in result

    def test_mixed(self) -> None:
        result = _extract_env_var_names(["A=1", "B"])
        assert result == {"A", "B"}

    def test_empty_list(self) -> None:
        assert _extract_env_var_names([]) == set()

    def test_with_substitution(self) -> None:
        result = _extract_env_var_names(["DB_USER=${POSTGRES_USER}"])
        assert "DB_USER" in result


# ---------------------------------------------------------------------------
# validate_service_environment
# ---------------------------------------------------------------------------


class TestValidateServiceEnvironment:
    def test_postgres_has_required_vars(self) -> None:
        errors = validate_service_environment(
            MINIMAL_COMPOSE, "postgres", POSTGRES_ENV_VARS
        )
        assert errors == []

    def test_missing_service(self) -> None:
        errors = validate_service_environment(
            MINIMAL_COMPOSE, "nonexistent", {"FOO"}
        )
        assert any("not found" in e for e in errors)

    def test_missing_var(self) -> None:
        compose = dict(MINIMAL_COMPOSE)
        compose["services"] = dict(compose["services"])
        compose["services"]["postgres"] = dict(compose["services"]["postgres"])
        compose["services"]["postgres"]["environment"] = ["POSTGRES_USER"]
        errors = validate_service_environment(
            compose, "postgres", {"POSTGRES_USER", "POSTGRES_PASSWORD"}
        )
        assert any("POSTGRES_PASSWORD" in e for e in errors)

    def test_dict_style_env(self) -> None:
        compose = dict(MINIMAL_COMPOSE)
        compose["services"] = dict(compose["services"])
        compose["services"]["postgres"] = dict(compose["services"]["postgres"])
        compose["services"]["postgres"]["environment"] = {
            "POSTGRES_USER": "root",
            "POSTGRES_PASSWORD": "pass",
            "POSTGRES_DB": "db",
        }
        errors = validate_service_environment(
            compose, "postgres", POSTGRES_ENV_VARS
        )
        assert errors == []

    def test_unexpected_env_type(self) -> None:
        compose = dict(MINIMAL_COMPOSE)
        compose["services"] = dict(compose["services"])
        compose["services"]["postgres"] = dict(compose["services"]["postgres"])
        compose["services"]["postgres"]["environment"] = 42
        errors = validate_service_environment(
            compose, "postgres", POSTGRES_ENV_VARS
        )
        assert any("unexpected type" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_healthcheck
# ---------------------------------------------------------------------------


class TestValidateHealthcheck:
    def test_valid_healthcheck(self) -> None:
        assert validate_healthcheck(MINIMAL_COMPOSE, "postgres") == []

    def test_missing_healthcheck(self) -> None:
        compose = dict(MINIMAL_COMPOSE)
        compose["services"] = dict(compose["services"])
        compose["services"]["postgres"] = {"image": "postgres:16"}
        errors = validate_healthcheck(compose, "postgres")
        assert any("missing healthcheck" in e for e in errors)

    def test_healthcheck_without_test(self) -> None:
        compose = dict(MINIMAL_COMPOSE)
        compose["services"] = dict(compose["services"])
        compose["services"]["postgres"] = dict(compose["services"]["postgres"])
        compose["services"]["postgres"]["healthcheck"] = {"interval": "5s"}
        errors = validate_healthcheck(compose, "postgres")
        assert any("missing 'test'" in e for e in errors)

    def test_service_not_found(self) -> None:
        errors = validate_healthcheck(MINIMAL_COMPOSE, "ghost")
        assert any("not found" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_service_image
# ---------------------------------------------------------------------------


class TestValidateServiceImage:
    def test_has_image(self) -> None:
        assert validate_service_image(MINIMAL_COMPOSE, "postgres") == []

    def test_missing_image(self) -> None:
        compose = dict(MINIMAL_COMPOSE)
        compose["services"] = dict(compose["services"])
        compose["services"]["postgres"] = {"environment": []}
        errors = validate_service_image(compose, "postgres")
        assert any("missing 'image'" in e for e in errors)

    def test_service_not_found(self) -> None:
        errors = validate_service_image(MINIMAL_COMPOSE, "nope")
        assert any("not found" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_compose (integration)
# ---------------------------------------------------------------------------


class TestValidateCompose:
    def test_valid_file(self, compose_file: Path) -> None:
        errors = validate_compose(compose_file)
        assert errors == []

    def test_real_compose_file(self, real_compose_file: Path) -> None:
        errors = validate_compose(real_compose_file)
        assert errors == []

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            validate_compose(tmp_path / "missing.yml")
