"""
Utility functions for inspecting version info of PyCI projects.
"""

from __future__ import annotations

from pathlib import Path

import toml
from semver import VersionInfo


def get_project_version_string(project_root_folder_path: str | Path) -> str:
    """
    Retrieves version from the version file in the given project folder.

    Notes:
        This will look for pyproject.toml, VERSION and version.txt files (in this order of priority)
        inside the given directory until the version can be read.

    Args:
        project_root_folder_path: Root directory of the project to get the version for.

    Returns:
        Project version string.

    Raises:
        FileNotFoundError if the version could not be determined (no version file).
    """
    if project_root_folder_path is not Path:
        project_root_folder_path = Path(project_root_folder_path)

    if not project_root_folder_path.exists():
        raise FileNotFoundError(f"Cannot read project version: provided project directory path does not exist ('{project_root_folder_path}').")

    # look for pyproject.toml
    pyproject_toml_path = Path(project_root_folder_path, "pyproject.toml")
    if pyproject_toml_path.exists():
        with open(pyproject_toml_path, "r") as file:
            contents = file.read()
            project_config = toml.loads(contents)
            version = project_config.get("tool").get("poetry").get("version")
            return version

    # look for VERSION
    version_path = Path(project_root_folder_path, "VERSION")
    if version_path.exists():
        with open(version_path, "r") as file:
            version = file.readline().strip()
            return version

    # look for version.txt
    version_txt_path = Path(project_root_folder_path, "version.txt")
    if version_txt_path.exists():
        with open(version_txt_path, "r") as file:
            version = file.readline().strip()
            return version

    # if version could not be read using any of the above options, we can't find it
    raise FileNotFoundError(f"Could not find a valid version file in the given project directory ('{project_root_folder_path}').")


def parse_semantic_version(version_string: str) -> VersionInfo:
    """
    Tries to parse semantic VersionInfo from the given string.

    Notes:
        Uses semver package under the hood.

    Args:
        version_string: String to parse the version from.

    Returns:
        Parsed VersionInfo.
    """
    return VersionInfo.parse(version_string)
