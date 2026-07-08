"""
Project-local PyCI configuration.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PYCI_CONFIG_FILE_NAME = "pyci.toml"


@dataclass(frozen=True)
class ActionsConfig:
    """
    Configuration for action discovery and retrieval.
    """

    remote_repository: str | None = None


@dataclass(frozen=True)
class PyCIConfig:
    """
    Project-local PyCI configuration.
    """

    actions: ActionsConfig = field(default_factory=ActionsConfig)


def get_pyci_config_path() -> Path:
    """
    Returns the expected project-local PyCI config file path.
    """
    from .environment import ci_paths

    return ci_paths.ci_files_directory / PYCI_CONFIG_FILE_NAME


def load_pyci_config() -> PyCIConfig:
    """
    Loads project-local PyCI configuration.

    Missing config files are valid and produce default config.
    """
    config_path = get_pyci_config_path()
    if not config_path.exists():
        return PyCIConfig()

    try:
        with config_path.open("rb") as file:
            raw_config = tomllib.load(file)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"Invalid PyCI config at '{config_path}': {error}") from error

    return _parse_pyci_config(raw_config, config_path)


def _parse_pyci_config(raw_config: dict[str, Any], config_path: Path) -> PyCIConfig:
    actions_raw = raw_config.get("actions", {})
    if not isinstance(actions_raw, dict):
        raise ValueError(f"Invalid PyCI config at '{config_path}': 'actions' must be a table.")

    return PyCIConfig(
        actions=_parse_actions_config(actions_raw, config_path)
    )


def _parse_actions_config(raw_config: dict[str, Any], config_path: Path) -> ActionsConfig:
    remote_repository = raw_config.get("remote_repository")
    if remote_repository is not None:
        if not isinstance(remote_repository, str):
            raise ValueError(
                f"Invalid PyCI config at '{config_path}': 'actions.remote_repository' must be a string."
            )
        if remote_repository == "":
            raise ValueError(
                f"Invalid PyCI config at '{config_path}': 'actions.remote_repository' must not be empty."
            )

    return ActionsConfig(remote_repository=remote_repository)
