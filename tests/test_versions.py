import logging
from pathlib import Path

import rich
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
    from python_ci_toolkit.versions.version_file_handlers import VERSION_FILE_HANDLERS, VersionFileHandler

    for (version_file_name, version_file_handler) in VERSION_FILE_HANDLERS.items():
        version_file_handler_name = type(version_file_handler).__name__
        print(f"Testing version file handler '{version_file_handler_name}'...")

        version_file_handler: VersionFileHandler = version_file_handler

        test_files_folder = Path("./test_version_files")
        version_file_path = Path(test_files_folder, version_file_name)
        if not version_file_path.exists():
            print(f"Version file '{version_file_name}' does not exist in the test folder '{test_files_folder}'.")
            continue

        print("Reading current version...")
        original_version = version_file_handler.read_version(version_file_path)
        print(f"Original version from '{version_file_name}': '{original_version}'")

        test_version = VersionInfo(42, 69, 5318008, "axolotl")
        print(f"Updating version to '{test_version}'...")
        version_file_handler.write_version(version_file_path, test_version)
        print(f"Updated.")

        print("Reading updated version...")
        updated_version = version_file_handler.read_version(version_file_path)
        print(f"Updated version from '{version_file_name}' is '{updated_version}'")

        print(f"Resetting to '{original_version}'...")
        version_file_handler.write_version(version_file_path, original_version)
        print(f"Reset.")

        print("Reading reset version...")
        reset_version = version_file_handler.read_version(version_file_path)
        print(f"Reset version from '{version_file_name}' is '{original_version}'")

        if (reset_version == original_version):
            print(f"Reset version matches the original ({reset_version} == {original_version}). Handler '{version_file_handler_name}' works correctly.")
        else:
            raise RuntimeError(f"Reset version does not match the original ({reset_version} != {original_version}). Handler '{version_file_handler_name}' must be fixed.")


if __name__ == '__main__':
    # test_project_version()
    # test_latest()
    # test_version_parsing()
    test_version_write()

