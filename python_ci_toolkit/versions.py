"""
Utility functions for inspecting version info of PyCI projects.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Callable

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

    # 'v' prefix often used in version tags
    prefix = "v"
    if version_string.startswith(prefix):
        version_string = version_string[len(prefix):]

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
        This will look for pyproject.toml, package.json, VERSION and version.txt files (in this order of priority)
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

    def get_file_in_project(file_name: str) -> Path:
        return Path(project_root_folder_path, file_name)

    # look for pyproject.toml
    pyproject_toml_path = get_file_in_project("pyproject.toml")
    if pyproject_toml_path.exists():
        with open(pyproject_toml_path, "r") as file:
            contents = file.read()
            project_config = toml.loads(contents)
            version = project_config.get("tool").get("poetry").get("version")
            return parse_semantic_version(version)

    # look for package.json
    package_json_path = get_file_in_project("package.json")
    if package_json_path.exists():
        with open(package_json_path, "r") as file:
            contents = file.read()
            project_config = json.loads(contents)
            version = project_config.get("version")
            if version is None:
                logging.warning("Project contains 'package.json' file, but the file does not have 'version' key in it.")
            else:
                return parse_semantic_version(version)

    # look for VERSION
    version_path = get_file_in_project("VERSION")
    if version_path.exists():
        with open(version_path, "r") as file:
            version = file.readline().strip()
            return parse_semantic_version(version)

    # look for version.txt
    version_txt_path = get_file_in_project("version.txt")
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


def write_project_version_to_file(project_root_folder_path: str | Path, version: VersionInfo, suffix: str = None) -> None:
    """
    Writes semantic version into the version files in the given project folder.

    Notes:
        This will look for pyproject.toml, package.json, VERSION and version.txt files (in this order of priority)
        inside the given directory until the version can be read.

    Args:
        project_root_folder_path: Root directory of the project to get the version for.
        version: Semantic version to write to the file.
        suffix: Optional suffix to append to the version number when writing to the file (e.g. "-dev", "-rc").

    Raises:
        FileNotFoundError if the version file to write to could not be found.
    """
    if project_root_folder_path is not Path:
        project_root_folder_path = Path(project_root_folder_path)

    if not project_root_folder_path.exists():
        raise FileNotFoundError(f"Cannot write project version: provided project directory path does not exist ('{project_root_folder_path}').")

    def nested_set(dic, keys, value):
        for key in keys[:-1]:
            dic = dic.setdefault(key, {})
        dic[keys[-1]] = value

    def write_version_to_file_in_project(file_name: str, write_callback: Callable[[str], str]) -> None:
        """
        Wrapper function which opens the given version file, reads its contents, updates them with the new given version, and writing it back.

        Args:
            file_name: Name of the version file to find and update the contents of.
            write_callback:
        """
        # find full path to the file
        file_path = Path(project_root_folder_path, file_name)
        if file_path.exists():
            with open(file_path, "r+") as file:
                contents = file.read()
                updated_contents = write_callback(contents)
                file.write(updated_contents)

    def write_pyproject_toml(file_contents: str) -> str:
        project_config = toml.loads(file_contents)
        version = project_config["tool"]["poetry"]["version"]
        return parse_semantic_version(version)

    def write_project_json(file_contents: str) -> str:
        project_config = json.loads(file_contents)
        version = project_config.set("version", )
        return parse_semantic_version(version)

    def write_pyproject_toml(file_contents: str) -> str:
        project_config = toml.loads(file_contents)
        version = project_config.get("tool").get("poetry").get("version")
        return parse_semantic_version(version)

    def write_pyproject_toml(file_contents: str) -> str:
        project_config = toml.loads(file_contents)
        version = project_config.get("tool").get("poetry").get("version")
        return parse_semantic_version(version)

    write_version_to_file_in_project("pyproject.toml", write_pyproject_toml)

    # look for pyproject.toml
    pyproject_toml_path = get_file_in_project("pyproject.toml")
    if pyproject_toml_path.exists():
        with open(pyproject_toml_path, "r") as file:
            contents = file.read()
            project_config = toml.loads(contents)
            version = project_config.get("tool").get("poetry").get("version")
            return parse_semantic_version(version)

    # look for package.json
    package_json_path = get_file_in_project("package.json")
    if package_json_path.exists():
        with open(package_json_path, "r") as file:
            contents = file.read()
            project_config = json.loads(contents)
            version = project_config.get("version")
            if version is None:
                logging.warning("Project contains 'package.json' file, but the file does not have 'version' key in it.")
            else:
                return parse_semantic_version(version)

    # look for VERSION
    version_path = get_file_in_project("VERSION")
    if version_path.exists():
        with open(version_path, "r") as file:
            version = file.readline().strip()
            return parse_semantic_version(version)

    # look for version.txt
    version_txt_path = get_file_in_project("version.txt")
    if version_txt_path.exists():
        with open(version_txt_path, "r") as file:
            version = file.readline().strip()
            return parse_semantic_version(version)

    # if version could not be read using any of the above options, we can't find it
    raise FileNotFoundError(f"Could not find a valid version file in the given project directory ('{project_root_folder_path}').")
