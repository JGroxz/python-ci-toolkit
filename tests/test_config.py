from pathlib import Path

import pytest

from python_ci_toolkit.config import get_pyci_config_path, load_pyci_config


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_pyci_config(contents: str) -> Path:
    config_path = get_pyci_config_path()
    config_path.parent.mkdir(parents=True)
    config_path.write_text(contents, encoding="utf-8")
    return config_path


def test_config_path_uses_project_ci_directory(project_root: Path):
    config_path = get_pyci_config_path()

    assert config_path == project_root / ".ci" / "pyci.toml"


def test_missing_config_returns_defaults(project_root: Path):
    config = load_pyci_config()

    assert config.actions.remote_repository is None


def test_empty_config_returns_defaults(project_root: Path):
    write_pyci_config("")

    config = load_pyci_config()

    assert config.actions.remote_repository is None


def test_actions_remote_repository_config(project_root: Path):
    write_pyci_config(
        '[actions]\n'
        'remote_repository = "git@github.com:team/python-ci-actions.git"\n'
    )

    config = load_pyci_config()

    assert config.actions.remote_repository == "git@github.com:team/python-ci-actions.git"


def test_unknown_config_values_are_ignored(project_root: Path):
    write_pyci_config(
        'unknown = "value"\n'
        '\n'
        '[actions]\n'
        'remote_repository = "https://github.com/team/python-ci-actions.git"\n'
        'unknown = "value"\n'
    )

    config = load_pyci_config()

    assert config.actions.remote_repository == "https://github.com/team/python-ci-actions.git"


def test_actions_config_must_be_a_table(project_root: Path):
    config_path = write_pyci_config('actions = "invalid"\n')

    with pytest.raises(
        ValueError,
        match=f"Invalid PyCI config at '{config_path}'.*'actions' must be a table"
    ):
        load_pyci_config()


def test_actions_remote_repository_must_be_a_string(project_root: Path):
    config_path = write_pyci_config(
        '[actions]\n'
        'remote_repository = 42\n'
    )

    with pytest.raises(
        ValueError,
        match=f"Invalid PyCI config at '{config_path}'.*'actions.remote_repository' must be a string"
    ):
        load_pyci_config()


def test_actions_remote_repository_must_not_be_empty(project_root: Path):
    config_path = write_pyci_config(
        '[actions]\n'
        'remote_repository = ""\n'
    )

    with pytest.raises(
        ValueError,
        match=f"Invalid PyCI config at '{config_path}'.*'actions.remote_repository' must not be empty"
    ):
        load_pyci_config()


def test_invalid_toml_raises_clear_error(project_root: Path):
    config_path = write_pyci_config("[actions\n")

    with pytest.raises(ValueError, match=f"Invalid PyCI config at '{config_path}'"):
        load_pyci_config()
