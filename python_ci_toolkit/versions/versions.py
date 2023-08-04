"""
Utility functions for inspecting version info of PyCI projects.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Callable

from semver import VersionInfo

from .version_file_handlers import VERSION_FILE_HANDLERS, VersionFileHandler
from ..shell import run_shell_command


SUPPORTED_VERSION_FILES: List[str] = list(VERSION_FILE_HANDLERS.keys())
"""List of version file names supported by Python CI Toolkit."""


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

    # PyPI package versions can use dot '.' instead of a hyphen '-' as the last separator, but VersionInfo doesn't parse that out of the box
    if version_string.count(".") > 2:
        split = version_string.split(".")
        version_string = ".".join(split[:3]) + "-" + ".".join(split[3:])

    return VersionInfo.parse(version_string)


def read_project_version(project_root_folder_path: str | Path) -> VersionInfo:
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

    def get_file_in_project_root(file_name: str) -> Path:
        return Path(project_root_folder_path, file_name)

    # keep trying to parse supported version files until we get the version
    for (version_file_name, version_file_handler) in VERSION_FILE_HANDLERS.items():
        version_file_path = get_file_in_project_root(version_file_name)
        if version_file_path.exists():
            return version_file_handler.read_version(version_file_path)

    # if version could not be read using any of the above options, we can't find it
    raise FileNotFoundError(f"Could not find a valid version file in the given project directory ('{project_root_folder_path}').")


def write_project_version(project_root_folder_path: str | Path, version: VersionInfo) -> None:
    """
    Writes semantic version into the version files in the given project folder.

    Notes:
        This will look for pyproject.toml, package.json, VERSION and version.txt files (in this order of priority)
        inside the given directory until the version can be read.

    Args:
        project_root_folder_path: Root directory of the project to get the version for.
        version: Semantic version to write to the file.

    Raises:
        FileNotFoundError if the version file to write to could not be found.
    """
    if project_root_folder_path is not Path:
        project_root_folder_path = Path(project_root_folder_path)

    if not project_root_folder_path.exists():
        raise FileNotFoundError(f"Cannot write project version: provided project directory path does not exist ('{project_root_folder_path}').")

    # Helper functions
    def update_file_contents_in_project_root(file_name: str, write_callback: Callable[[str], str]) -> None:
        """
        Wrapper function which opens the given file in the project's root folder,
        reads its contents, updates them using the given callback, and writes them back.

        Notes:
            Does nothing if the file does not exist.

        Args:
            file_name: Name of the file to find and update the contents of.
            write_callback: Function which will return the new file contents.
        """
        # find full path to the file
        file_path = Path(project_root_folder_path, file_name)
        if file_path.exists():
            with open(file_path, "r+") as file:
                contents = file.read()
                updated_contents = write_callback(contents)
                file.write(updated_contents)

    # Update version in every supported version file in the project root folder
    updated_version_files: List[str] = []
    for (version_file_name, version_file_handler) in VERSION_FILE_HANDLERS.items():
        version_file_handler: VersionFileHandler = version_file_handler
        version_file_path = Path(project_root_folder_path, version_file_name)
        if version_file_path.exists():
            previous_version = version_file_handler.read_version(version_file_path)
            version_file_handler.write_version(version_file_path, version)

            updated_version_files.append(version_file_name)
            logging.info(f"Changed version in file '{version_file_name}' from {previous_version} to {version}.")

    if len(updated_version_files) == 0:
        # If version could not be read using any of the above options, we can't find it
        raise FileNotFoundError(f"Could not find a valid version file in the given project directory ('{project_root_folder_path}').")
    else:
        updated_file_names = "\n".join([f"  - '{file_name}'" for file_name in updated_version_files])
        logging.info(f"Updated version to {version} in {len(updated_version_files)} files in the repository:\n{updated_file_names}")


def get_latest_pypi_package_version(package_name: str) -> VersionInfo | None:
    """
    Returns the latest semantic version of the given PyPI package in currently configured repositories.

    Args:
        package_name: Name of the PyPI package to get the latest version of.

    Returns:
        The latest package version in semantic VersionInfo format.
    """
    all_versions = get_all_available_pypi_package_versions(package_name)

    if len(all_versions) == 0:
        return None

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
    result = run_shell_command(f"pip index versions {package_name}", raise_on_error=False, use_wsl_on_windows=False)

    missing_package_log = f"No matching distribution found for {package_name}"
    if missing_package_log in result.output:
        # the package does not exist in the remote repository
        return []

    if result.is_failed:
        # if the c
        raise RuntimeError(f"Could not get available versions for package '{package_name}'.\n"
                           f"  Executed command: {result.command}\n"
                           f"  Exit code: {result.exit_code}\n",
                           f"  Output: {result.output}")

    versions_anchor_string = "Available versions: "
    versions_start_index = result.output.find(versions_anchor_string) + len(versions_anchor_string)
    versions_list = result.output[versions_start_index:].split("\n")[0].split(",")
    available_versions = [parse_semantic_version(version_string.strip()) for version_string in versions_list]

    return available_versions
