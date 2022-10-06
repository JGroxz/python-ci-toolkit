import logging
from pathlib import Path

from semver import VersionInfo

import python_ci_toolkit.versions.version_file_handlers
from python_ci_toolkit.versions import get_project_version, get_latest_pypi_package_version, get_all_available_pypi_package_versions, parse_semantic_version


def test_project_version():
    project_root = "../"
    version = get_project_version(project_root)
    print(f"Project version: {version}")


def test_latest():
    test_package = "pip"
    latest_pip_version = get_latest_pypi_package_version(test_package)
    print(f"Latest available version of {test_package}: {latest_pip_version}")


def test_version_parsing():
    version_strings = [
        "0.0.0",
        "0.0.1",
        "0.1.0",
        "1.1.0",
        "0.0.0-dev",
        "0.0.1-dev",
        "0.1.0-dev",
        "1.0.0-dev",
        "v0.0.0-dev",
        "v0.0.1-dev",
        "v0.1.0-dev",
        "v1.0.0-dev.1",
    ]

    for version_string in version_strings:
        version = parse_semantic_version(version_string)
        print(f"{version_string} -> {version}")


def test_version_write():
    from python_ci_toolkit.versions.version_file_handlers import VERSION_FILE_HANDLERS

    for version_file_handler in VERSION_FILE_HANDLERS:
        print(f"Testing version file handler {type(version_file_handler)}...")

        version_file_name = version_file_handler.file_name
        version_file_path = Path("./test_version_files", version_file_name)
        if not version_file_path.exists():
            print(f"Version file '{version_file_path}' does not exist in this project.")
            continue

        print("Reading current version...")
        with open(version_file_path, "r") as file:
            original_version = version_file_handler.read_version(file.read())
            print(f"Current version from '{version_file_name}': {original_version}")

        test_version = VersionInfo(42, 69, 531008, "axolotl")
        print(f"Updating version to {test_version}...")
        with open(version_file_path, "r+") as file:
            updated_contents = version_file_handler.update_version(file.read(), test_version)
            file.write(updated_contents)
            print(f"Updated.")

        print("Reading updated version...")
        with open(version_file_path, "r") as file:
            original_version = version_file_handler.read_version(file.read())
            print(f"Updated version from '{version_file_name}' is {original_version}")

        print(f"Resetting to {original_version}...")
        with open(version_file_path, "r+") as file:
            updated_contents = version_file_handler.update_version(file.read(), original_version)
            file.write(updated_contents)
            print(f"Reset.")

        print("Reading reset version...")
        with open(version_file_path, "r") as file:
            original_version = version_file_handler.read_version(file.read())
            print(f"Reset version from '{version_file_name}' is {original_version}")

        version_file_handler.read_version(version_file_name)


if __name__ == '__main__':
    test_project_version()
    # test_latest()
    test_version_parsing()
    test_version_write()

