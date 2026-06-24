"""Validator for Docker Compose configuration files.

Validates structure, required services, networks, volumes,
environment variables, and health checks in docker-compose.yml.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


REQUIRED_TOP_LEVEL_KEYS = {"services", "volumes", "networks"}
REQUIRED_SERVICES = {"postgres", "n8n", "n8n-import", "qdrant"}
REQUIRED_VOLUMES = {
    "n8n_storage",
    "postgres_storage",
    "ollama_storage",
    "qdrant_storage",
}
REQUIRED_NETWORKS = {"demo"}

POSTGRES_ENV_VARS = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"}
N8N_ENV_VARS = {
    "DB_TYPE",
    "DB_POSTGRESDB_HOST",
    "DB_POSTGRESDB_USER",
    "DB_POSTGRESDB_PASSWORD",
    "N8N_DIAGNOSTICS_ENABLED",
    "N8N_PERSONALIZATION_ENABLED",
    "N8N_ENCRYPTION_KEY",
    "N8N_USER_MANAGEMENT_JWT_SECRET",
}


def load_compose_file(path: str | Path) -> dict[str, Any]:
    """Load and parse a Docker Compose YAML file.

    Args:
        path: Path to the docker-compose.yml file.

    Returns:
        Parsed YAML content as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        ValueError: If the parsed content is not a dictionary.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Compose file not found: {path}")

    with open(path) as f:
        content = yaml.safe_load(f)

    if not isinstance(content, dict):
        raise ValueError("Compose file must be a YAML mapping at the top level")

    return content


def validate_top_level_keys(compose: dict[str, Any]) -> list[str]:
    """Check that required top-level keys are present.

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in compose:
            errors.append(f"Missing required top-level key: '{key}'")
    return errors


def validate_services(compose: dict[str, Any]) -> list[str]:
    """Validate that all required services are defined.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    services = compose.get("services", {})
    if not isinstance(services, dict):
        return ["'services' must be a mapping"]

    for svc in REQUIRED_SERVICES:
        if svc not in services:
            errors.append(f"Missing required service: '{svc}'")
    return errors


def validate_volumes(compose: dict[str, Any]) -> list[str]:
    """Validate that all required named volumes are declared.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    volumes = compose.get("volumes", {})
    if not isinstance(volumes, dict):
        return ["'volumes' must be a mapping"]

    for vol in REQUIRED_VOLUMES:
        if vol not in volumes:
            errors.append(f"Missing required volume: '{vol}'")
    return errors


def validate_networks(compose: dict[str, Any]) -> list[str]:
    """Validate that all required networks are declared.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    networks = compose.get("networks", {})
    if not isinstance(networks, dict):
        return ["'networks' must be a mapping"]

    for net in REQUIRED_NETWORKS:
        if net not in networks:
            errors.append(f"Missing required network: '{net}'")
    return errors


def _extract_env_var_names(env_list: list[str]) -> set[str]:
    """Extract variable names from a list of environment entries.

    Handles both ``VAR=value`` and bare ``VAR`` forms, and also
    entries using ``${VAR}`` substitution syntax.
    """
    names: set[str] = set()
    for entry in env_list:
        if "=" in entry:
            name = entry.split("=", 1)[0].strip().lstrip("- ")
            names.add(name)
        else:
            names.add(entry.strip().lstrip("- "))
    return names


def validate_service_environment(
    compose: dict[str, Any],
    service_name: str,
    required_vars: set[str],
) -> list[str]:
    """Validate that a service defines the required environment variables.

    Checks in the service definition and any YAML anchors (x-*) it extends.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    services = compose.get("services", {})
    service = services.get(service_name)
    if service is None:
        return [f"Service '{service_name}' not found"]

    env = service.get("environment", [])
    if isinstance(env, dict):
        found_vars = set(env.keys())
    elif isinstance(env, list):
        found_vars = _extract_env_var_names(env)
    else:
        return [f"Service '{service_name}': 'environment' has unexpected type"]

    for var in required_vars:
        if var not in found_vars:
            errors.append(
                f"Service '{service_name}': missing env var '{var}'"
            )
    return errors


def validate_healthcheck(compose: dict[str, Any], service_name: str) -> list[str]:
    """Validate that a service has a healthcheck configured.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    services = compose.get("services", {})
    service = services.get(service_name)
    if service is None:
        return [f"Service '{service_name}' not found"]

    hc = service.get("healthcheck")
    if hc is None:
        errors.append(f"Service '{service_name}': missing healthcheck")
        return errors

    if "test" not in hc:
        errors.append(f"Service '{service_name}': healthcheck missing 'test'")
    return errors


def validate_service_image(
    compose: dict[str, Any],
    service_name: str,
) -> list[str]:
    """Validate that a service specifies a Docker image.

    Returns:
        List of error messages.
    """
    services = compose.get("services", {})
    service = services.get(service_name)
    if service is None:
        return [f"Service '{service_name}' not found"]
    if "image" not in service:
        return [f"Service '{service_name}': missing 'image'"]
    return []


def validate_compose(path: str | Path) -> list[str]:
    """Run all validations on a Docker Compose file.

    Returns:
        Aggregated list of error messages.
    """
    compose = load_compose_file(path)
    errors: list[str] = []
    errors.extend(validate_top_level_keys(compose))
    errors.extend(validate_services(compose))
    errors.extend(validate_volumes(compose))
    errors.extend(validate_networks(compose))
    errors.extend(
        validate_service_environment(compose, "postgres", POSTGRES_ENV_VARS)
    )
    errors.extend(validate_healthcheck(compose, "postgres"))
    for svc in ("postgres", "qdrant"):
        errors.extend(validate_service_image(compose, svc))
    return errors
