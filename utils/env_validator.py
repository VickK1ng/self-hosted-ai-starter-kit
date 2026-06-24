"""Validator for .env configuration files.

Ensures that all required environment variables referenced by
docker-compose.yml are present and non-empty in the .env file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


REQUIRED_ENV_VARS = {
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "N8N_ENCRYPTION_KEY",
    "N8N_USER_MANAGEMENT_JWT_SECRET",
}


def load_env_file(path: str | Path) -> dict[str, str]:
    """Parse a .env file into a key-value dictionary.

    Handles blank lines, comments, optional quoting, and inline comments.

    Args:
        path: Path to the .env file.

    Returns:
        Dictionary of variable name to value.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f".env file not found: {path}")

    env: dict[str, str] = {}
    with open(path) as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
            if not match:
                continue
            key = match.group(1)
            value = match.group(2).strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            env[key] = value
    return env


def validate_required_vars(
    env: dict[str, str],
    required: set[str] | None = None,
) -> list[str]:
    """Check that all required variables are present and non-empty.

    Args:
        env: Parsed environment variables.
        required: Set of required variable names.
            Defaults to REQUIRED_ENV_VARS.

    Returns:
        List of error messages.
    """
    if required is None:
        required = REQUIRED_ENV_VARS

    errors: list[str] = []
    for var in sorted(required):
        if var not in env:
            errors.append(f"Missing required env var: '{var}'")
        elif not env[var]:
            errors.append(f"Env var '{var}' is empty")
    return errors


def validate_no_default_secrets(
    env: dict[str, str],
    secret_vars: set[str] | None = None,
    forbidden_values: set[str] | None = None,
) -> list[str]:
    """Warn if secret variables use obviously insecure default values.

    Args:
        env: Parsed environment variables.
        secret_vars: Variables to check. Defaults to password/key vars.
        forbidden_values: Values considered insecure.

    Returns:
        List of warning messages.
    """
    if secret_vars is None:
        secret_vars = {
            "POSTGRES_PASSWORD",
            "N8N_ENCRYPTION_KEY",
            "N8N_USER_MANAGEMENT_JWT_SECRET",
        }
    if forbidden_values is None:
        forbidden_values = {
            "password",
            "secret",
            "changeme",
            "super-secret-key",
            "even-more-secret",
            "123456",
            "",
        }

    warnings: list[str] = []
    for var in sorted(secret_vars):
        val = env.get(var, "")
        if val.lower() in {v.lower() for v in forbidden_values}:
            warnings.append(
                f"Env var '{var}' uses an insecure default value"
            )
    return warnings


def extract_compose_env_refs(compose_path: str | Path) -> set[str]:
    """Extract environment variable names referenced by docker-compose.yml.

    Looks for ``${VAR}`` and bare ``$VAR`` patterns as well as
    standalone variable names in service environment lists.

    Args:
        compose_path: Path to docker-compose.yml.

    Returns:
        Set of referenced variable names.
    """
    compose_path = Path(compose_path)
    if not compose_path.exists():
        raise FileNotFoundError(f"Compose file not found: {compose_path}")

    text = compose_path.read_text()

    refs: set[str] = set()
    # ${VAR} and $VAR patterns
    for m in re.finditer(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", text):
        refs.add(m.group(1))
    for m in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)", text):
        refs.add(m.group(1))

    # Bare variable names in environment lists (YAML anchored or inline)
    parsed = yaml.safe_load(text)
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            if key.startswith("x-") and isinstance(value, dict):
                _collect_env_names(value, refs)
            if key == "services" and isinstance(value, dict):
                for svc in value.values():
                    if isinstance(svc, dict):
                        _collect_env_names(svc, refs)
    return refs


def _collect_env_names(service: dict[str, Any], refs: set[str]) -> None:
    """Collect env var names from a service definition."""
    env = service.get("environment", [])
    if isinstance(env, list):
        for entry in env:
            entry = str(entry).strip().lstrip("- ")
            if "=" in entry:
                name = entry.split("=", 1)[0]
            else:
                name = entry
            name = re.sub(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", r"\1", name)
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                refs.add(name)
    elif isinstance(env, dict):
        refs.update(env.keys())


def validate_env_file(
    env_path: str | Path,
    compose_path: str | Path | None = None,
) -> list[str]:
    """Run all validations on a .env file.

    Args:
        env_path: Path to the .env file.
        compose_path: Optional path to docker-compose.yml to cross-reference.

    Returns:
        Aggregated list of error/warning messages.
    """
    env = load_env_file(env_path)
    messages: list[str] = []
    messages.extend(validate_required_vars(env))
    messages.extend(validate_no_default_secrets(env))
    return messages
