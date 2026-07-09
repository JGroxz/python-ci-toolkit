import shutil
from pathlib import Path

import pytest
from semver import VersionInfo

from python_ci_toolkit.versions import read_project_version, parse_semantic_version, write_project_version
from python_ci_toolkit.versions.version_file_handlers import VERSION_FILE_HANDLERS, VersionFileHandler

TEMPLATE_VERSION_FILES_DIRECTORY = Path(__file__).parent / "input/template_version_files"
TEMPLATE_VERSION = VersionInfo(1, 0, 0, "test")


def test_version_parsing():
    version_strings = {
        "0.0.0": VersionInfo(0, 0, 0),
        "0.0.1": VersionInfo(0, 0, 1),
        "0.1.0": VersionInfo(0, 1, 0),
        "1.1.0": VersionInfo(1, 1, 0),
        "0.0.0-dev": VersionInfo(0, 0, 0, "dev"),
        "0.0.1-dev": VersionInfo(0, 0, 1, "dev"),
        "0.1.0-dev": VersionInfo(0, 1, 0, "dev"),
        "1.0.0-dev": VersionInfo(1, 0, 0, "dev"),
        "v0.0.0-dev": VersionInfo(0, 0, 0, "dev"),
        "v0.0.1-dev": VersionInfo(0, 0, 1, "dev"),
        "v0.1.0-dev": VersionInfo(0, 1, 0, "dev"),
        "v1.0.0-dev.1": VersionInfo(1, 0, 0, "dev-1"),
        "v1.0.0-dev1": VersionInfo(1, 0, 0, "dev1"),
        "v1.0.0.dev1": VersionInfo(1, 0, 0, "dev1"),
    }

    for (version_string, expected_version_info) in version_strings.items():
        version = parse_semantic_version(version_string)
        assert version == expected_version_info, \
            f"Version string '{version_string}' should be parsed as '{expected_version_info}', but it was '{version}'"


def create_version_file_from_template(template_name: str, tmp_path: Path) -> Path:
    """
    Creates a version file from the given template.

    Notes:
        This can be used in tests to avoid modifying the original template files.

    Args:
        template_name: Name of the original version file.
        tmp_path: Temporary directory to create the test file in.

    Returns:
        Path to the created temporary version file.
    """

    # make sure the template exists
    template_path = Path(TEMPLATE_VERSION_FILES_DIRECTORY, template_name)
    assert template_path.exists(), \
        f"Template version file '{template_name}' does not exist in '{TEMPLATE_VERSION_FILES_DIRECTORY}'."

    # create a copy
    version_file_path = tmp_path / template_name
    shutil.copyfile(template_path, version_file_path)

    return version_file_path


def test_read_project_version_reads_supported_files(tmp_path: Path):
    for version_file_name in VERSION_FILE_HANDLERS:
        project_root = tmp_path / version_file_name
        project_root.mkdir()
        create_version_file_from_template(version_file_name, project_root)

        version = read_project_version(project_root)

        assert version == TEMPLATE_VERSION


def test_read_project_version_prefers_supported_file_order(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
version = "1.2.3"
""",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text('{"version": "9.9.9"}', encoding="utf-8")

    version = read_project_version(tmp_path)

    assert version == VersionInfo(1, 2, 3)


def test_read_project_version_rejects_missing_project_path(tmp_path: Path):
    missing_project_path = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match="provided project directory path does not exist"):
        read_project_version(missing_project_path)


def test_read_project_version_rejects_project_without_version_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Could not find a valid version file"):
        read_project_version(tmp_path)


def test_write_project_version_updates_all_supported_files(tmp_path: Path):
    new_version = VersionInfo(4, 5, 6, "dev")
    for version_file_name in VERSION_FILE_HANDLERS:
        create_version_file_from_template(version_file_name, tmp_path)

    write_project_version(tmp_path, new_version)

    for version_file_name, version_file_handler in VERSION_FILE_HANDLERS.items():
        version_file_path = tmp_path / version_file_name
        assert version_file_handler.read_version(version_file_path) == new_version


def test_write_project_version_rejects_missing_project_path(tmp_path: Path):
    missing_project_path = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match="provided project directory path does not exist"):
        write_project_version(missing_project_path, VersionInfo(1, 2, 3))


def test_write_project_version_rejects_project_without_version_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Could not find a valid version file"):
        write_project_version(tmp_path, VersionInfo(1, 2, 3))


def test_version_read(tmp_path: Path):
    for (version_file_name, version_file_handler) in VERSION_FILE_HANDLERS.items():
        version_file_handler_name = type(version_file_handler).__name__
        print(f"Testing reading with version file handler '{version_file_handler_name}'...")

        version_file_path = create_version_file_from_template(version_file_name, tmp_path)

        version_file_handler: VersionFileHandler = version_file_handler
        read_version = version_file_handler.read_version(version_file_path)

        assert read_version == TEMPLATE_VERSION, \
            f"Version read from '{version_file_name}' should be '{TEMPLATE_VERSION}', but it was '{read_version}'"


def test_version_write(tmp_path: Path):
    for (version_file_name, version_file_handler) in VERSION_FILE_HANDLERS.items():
        version_file_handler_name = type(version_file_handler).__name__
        print(f"Testing version file handler '{version_file_handler_name}'...")

        version_file_path = create_version_file_from_template(version_file_name, tmp_path)

        # read original version
        version_file_handler: VersionFileHandler = version_file_handler
        original_version = version_file_handler.read_version(version_file_path)

        # write new version
        test_version = VersionInfo(42, 69, 5318008, "axolotl")
        version_file_handler.write_version(version_file_path, test_version)

        # read new version
        updated_version = version_file_handler.read_version(version_file_path)
        assert updated_version == test_version, \
            (f"Version read from '{version_file_name}' should be '{test_version}', but it was '{updated_version}'.\n"
             f"Handler '{version_file_handler_name}' must be fixed.")

        # reset to the original version
        version_file_handler.write_version(version_file_path, original_version)
        reset_version = version_file_handler.read_version(version_file_path)
        assert reset_version == original_version, \
            (f"Version read from '{version_file_name}' should be '{test_version}', but it was '{updated_version}'.\n"
             f"Handler '{version_file_handler_name}' must be fixed.")

        print(f"Handler '{version_file_handler_name}' works correctly.")


def test_legacy_poetry_pyproject_version_read():
    file_contents = """
[tool.poetry]
name = "legacy-poetry-project"
version = "1.2.3-test"
"""
    handler = VERSION_FILE_HANDLERS["pyproject.toml"]

    version = handler._read_version_from_file_contents(file_contents)

    assert version == VersionInfo(1, 2, 3, "test")


def test_plain_text_version_handler_reads_first_line():
    handler = VERSION_FILE_HANDLERS["VERSION"]

    version = handler._read_version_from_file_contents("1.2.3\nignored metadata")

    assert version == VersionInfo(1, 2, 3)


def test_version_bump():
    original_version = "v1.1.1"
    original_version = parse_semantic_version(original_version)

    # Test patch bump
    new_version = original_version.bump_patch()
    print(f"Patch bump: {original_version} -> {new_version}")
    expected_version = "1.1.2"
    assert f"{new_version}" == expected_version, \
        f"Patch bump failed: {original_version} -> {new_version} (expected {expected_version})"

    # Test minor bump
    new_version = original_version.bump_minor()
    print(f"Minor bump: {original_version} -> {new_version}")
    expected_version = "1.2.0"
    assert f"{new_version}" == expected_version, \
        f"Minor bump failed: {original_version} -> {new_version} (expected {expected_version})"

    # Test major bump
    new_version = original_version.bump_major()
    print(f"Major bump: {original_version} -> {new_version}")
    expected_version = "2.0.0"
    assert f"{new_version}" == expected_version, \
        f"Major bump failed: {original_version} -> {new_version} (expected {expected_version})"
