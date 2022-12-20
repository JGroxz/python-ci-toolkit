from pathlib import Path

from semver import VersionInfo

from python_ci_toolkit.versions import read_project_version, get_latest_pypi_package_version, parse_semantic_version
from python_ci_toolkit.versions.version_file_handlers import VERSION_FILE_HANDLERS, VersionFileHandler

TEST_VERSION_FILES_FOLDER = Path("./test_version_files")


def test_project_version():
    project_root = "../"
    version = read_project_version(project_root)
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
        "v1.0.0-dev1",
        "v1.0.0.dev1",
    ]

    for version_string in version_strings:
        version = parse_semantic_version(version_string)
        print(f"{version_string} -> {version}")


def test_version_write():
    for (version_file_name, version_file_handler) in VERSION_FILE_HANDLERS.items():
        version_file_handler_name = type(version_file_handler).__name__
        print(f"Testing version file handler '{version_file_handler_name}'...")

        version_file_handler: VersionFileHandler = version_file_handler

        version_file_path = Path(TEST_VERSION_FILES_FOLDER, version_file_name)
        if not version_file_path.exists():  # TODO: assert
            print(f"Version file '{version_file_name}' does not exist in the test folder '{TEST_VERSION_FILES_FOLDER}'.")
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

        if (reset_version == original_version):  # TODO: assert
            print(f"Reset version matches the original ({reset_version} == {original_version}). Handler '{version_file_handler_name}' works correctly.")
        else:
            raise RuntimeError(f"Reset version does not match the original ({reset_version} != {original_version}). Handler '{version_file_handler_name}' must be fixed.")


def test_version_bump():
    original_version = "v1.1.1"
    original_version = parse_semantic_version(original_version)

    # Test patch bump
    new_version = original_version.bump_patch()
    print(f"Patch bump: {original_version} -> {new_version}")
    assert f"{new_version}" == "1.1.2"

    # Test minor bump
    new_version = original_version.bump_minor()
    print(f"Minor bump: {original_version} -> {new_version}")
    assert f"{new_version}" == "1.2.0"

    # Test major bump
    new_version = original_version.bump_major()
    print(f"Major bump: {original_version} -> {new_version}")
    assert f"{new_version}" == "2.0.0"


if __name__ == '__main__':
    # test_project_version()
    # test_latest()
    test_version_parsing()
    # test_version_write()
    # test_version_bump()

    # handler = PyProjectVersionFileHandler()
    # path = Path("../", "pyproject.toml")
    # version = handler.read_version(path)
    # new_version = version.bump_minor()
    # handler.write_version(path, new_version)
