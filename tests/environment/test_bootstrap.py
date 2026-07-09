from pathlib import Path


class _FakeCiPaths:
    def __init__(self, project_root: Path):
        self.project_root = project_root


def test_prepare_ci_project_runtime_skips_git_safe_directory_outside_github_actions(monkeypatch, tmp_path: Path):
    from python_ci_toolkit.environment import bootstrap
    from python_ci_toolkit.environment.platform import Local

    safe_directories: list[Path] = []

    monkeypatch.setattr(bootstrap, "_prepared_project_roots", set())
    monkeypatch.setattr(bootstrap, "ci_paths", _FakeCiPaths(tmp_path))
    monkeypatch.setattr(bootstrap, "ci_platform", Local)
    monkeypatch.setattr(bootstrap, "add_git_safe_directory", safe_directories.append)

    bootstrap.prepare_ci_project_runtime()

    assert safe_directories == []


def test_prepare_ci_project_runtime_adds_git_safe_directory_once_on_github_actions(monkeypatch, tmp_path: Path):
    from python_ci_toolkit.environment import bootstrap
    from python_ci_toolkit.environment.platform import GitHubActions

    safe_directories: list[Path] = []

    monkeypatch.setattr(bootstrap, "_prepared_project_roots", set())
    monkeypatch.setattr(bootstrap, "ci_paths", _FakeCiPaths(tmp_path))
    monkeypatch.setattr(bootstrap, "ci_platform", GitHubActions)
    monkeypatch.setattr(bootstrap, "add_git_safe_directory", safe_directories.append)

    bootstrap.prepare_ci_project_runtime()
    bootstrap.prepare_ci_project_runtime()

    assert safe_directories == [tmp_path]
