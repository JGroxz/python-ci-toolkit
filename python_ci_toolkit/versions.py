"""
Utility functions for inspecting version info of PyCI projects.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import toml
from semver import VersionInfo

from .shell import run_shell_command


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

    # feature version with patch 0, add ".0" so that VersionInfo can parse it
    if version_string.count(".") == 1:
        version_string += ".0"

    # major version with feature/patch 0, add ".0.0" so that VersionInfo can parse it
    if version_string.count(".") == 0:
        version_string += ".0.0"

    return VersionInfo.parse(version_string)


def get_project_version_from_file(project_root_folder_path: str | Path) -> VersionInfo:
    """
    Retrieves semantic version from the version file in the given project folder.

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
            return parse_semantic_version(version)

    # look for VERSION
    version_path = Path(project_root_folder_path, "VERSION")
    if version_path.exists():
        with open(version_path, "r") as file:
            version = file.readline().strip()
            return parse_semantic_version(version)

    # look for version.txt
    version_txt_path = Path(project_root_folder_path, "version.txt")
    if version_txt_path.exists():
        with open(version_txt_path, "r") as file:
            version = file.readline().strip()
            return parse_semantic_version(version)

    # if version could not be read using any of the above options, we can't find it
    raise FileNotFoundError(f"Could not find a valid version file in the given project directory ('{project_root_folder_path}').")


def get_latest_pypi_package_version(package_name: str) -> VersionInfo:
    """
    Returns the latest semantic version of the given PyPI package in currently configured repositories.

    Args:
        package_name: Name of the PyPI package to get the latest version of.

    Returns:
        The latest package version in semantic VersionInfo format.
    """
    all_versions = get_all_available_pypi_package_versions(package_name)
    latest_version = all_versions[0]

    return latest_version


def get_all_available_pypi_package_versions(package_name: str) -> List[VersionInfo]:
    """
    Returns the list of all available semantic versions of the given PyPI package in currently configured repositories.

    Notes:
        Versions in the returned list are sorted in descending order, from the latest to the oldest.

    Args:
        package_name: Name of the PyPI package to get the versions of.

    Returns:
        List of package versions in semantic VersionInfo format.
    """
    _, output = run_shell_command(f"pip index versions {package_name}", use_wsl_on_windows=False)

    versions_anchor_string = "Available versions: "
    versions_start_index = output.find(versions_anchor_string) + len(versions_anchor_string)
    versions_list = output[versions_start_index:].split("\n")[0].split(",")
    available_versions = [parse_semantic_version(version_string.strip()) for version_string in versions_list]

    return available_versions
