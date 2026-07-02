"""
Loads candidate.yaml, resolves ${ENV_VAR} references against the process
environment, and validates the result through the Pydantic AppConfig model.

Usage:
    from config.loader import load_config
    cfg = load_config("config/candidate.yaml")
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from config.schema import AppConfig

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _resolve_env_vars(value):
    """Recursively replace ${VAR_NAME} with the value of the environment
    variable VAR_NAME. Raises a clear error if a referenced var is unset,
    instead of silently embedding the literal string "${VAR_NAME}" into
    config (e.g. into an email address, which then fails oddly downstream).
    """
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            resolved = os.environ.get(var_name)
            if resolved is None:
                raise ValueError(
                    f"Config references ${{{var_name}}} but that environment "
                    f"variable is not set. Set it in your .env / shell before "
                    f"loading this config."
                )
            return resolved

        return _ENV_VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(v) for v in value]
    return value


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    resolved = _resolve_env_vars(raw)

    try:
        return AppConfig(**resolved)
    except ValidationError as e:
        # Re-raise with a clearer, config-focused message rather than
        # a raw Pydantic dump -- this is meant to be read by a human
        # editing a YAML file, not a developer reading a stack trace.
        raise ValueError(f"Invalid configuration in {path}:\n{e}") from e
