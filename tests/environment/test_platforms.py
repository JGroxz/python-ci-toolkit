from pathlib import Path


def test_github_actions_project_root_uses_workspace_env(monkeypatch):
    from python_ci_toolkit.environment.platform.github import GitHubActions

    workspace = Path("/tmp/github-workspace")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))

    assert GitHubActions.get_ci_project_root() == workspace


def test_platform_detection_uses_platform_classes(monkeypatch):
    import python_ci_toolkit.environment.platform as platform_module

    monkeypatch.setattr(platform_module.BitbucketPipelines, "is_current", lambda: False)
    monkeypatch.setattr(platform_module.GitHubActions, "is_current", lambda: True)

    assert platform_module._get_ci_platform() is platform_module.GitHubActions
