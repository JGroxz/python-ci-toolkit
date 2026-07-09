"""
Utility functions for inspecting version info of PyCI projects.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from semver import VersionInfo

from .version_file_handlers import VERSION_FILE_HANDLERS, VersionFileHandler


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
    project_root_folder_path = Path(project_root_folder_path)

    if not project_root_folder_path.exists():
        raise FileNotFoundError(
            f"Cannot read project version: provided project directory path does not exist ('{project_root_folder_path}')."
        )

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
    project_root_folder_path = Path(project_root_folder_path)

    if not project_root_folder_path.exists():
        raise FileNotFoundError(
            f"Cannot write project version: provided project directory path does not exist ('{project_root_folder_path}')."
        )

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
