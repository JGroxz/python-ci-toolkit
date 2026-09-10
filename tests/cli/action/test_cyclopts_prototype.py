from __future__ import annotations

import pytest

from python_ci_toolkit.cli.action.find import ActionMetadata
from python_ci_toolkit.cli import cyclopts_prototype


@pytest.mark.parametrize(
    "arguments, expected_action_arguments",
    [
        (
            ["demo@local", "--message", "hello"],
            ["--message", "hello"],
        ),
        (
            ["demo@local", "--", "--message", "hello"],
            ["--message", "hello"],
        ),
        (
            ["demo@local", "--help"],
            ["--help"],
        ),
    ],
)
def test_prototype_forwards_action_arguments(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    expected_action_arguments: list[str],
) -> None:
    import python_ci_toolkit.actions as actions_module

    calls: list[tuple[str, str | None, list[str] | None]] = []

    def record_run(
        action_name: str,
        action_version: str | None = None,
        args: list[str] | None = None,
    ) -> None:
        calls.append((action_name, action_version, args))

    monkeypatch.setattr(actions_module, "run_ci_action", record_run)

    assert cyclopts_prototype.invoke(arguments, exit_on_error=False) == 0
    assert calls == [("demo", "local", expected_action_arguments)]


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--help"],
        ["--debug"],
        ["--debug", "--help"],
    ],
)
def test_prototype_handles_toolkit_help_before_action(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
) -> None:
    import python_ci_toolkit.actions as actions_module

    def unexpected_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("The action should not run for toolkit help.")

    monkeypatch.setattr(actions_module, "run_ci_action", unexpected_run)

    assert cyclopts_prototype.invoke(arguments, exit_on_error=False) == 0

    output = capsys.readouterr().out
    assert "Usage:" in output
    assert "ACTION_IDENTIFIER" in output


def test_action_completion_is_resolved_at_request_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    available_actions = [
        ActionMetadata("build@local", "[local] Build the project."),
        ActionMetadata("test@local", "[local] Run tests."),
    ]

    def list_actions() -> list[ActionMetadata]:
        return available_actions

    monkeypatch.setattr(cyclopts_prototype, "_list_action_metadata", list_actions)

    assert cyclopts_prototype.action_completion_candidates("b") == [
        ActionMetadata("build@local", "[local] Build the project."),
    ]

    available_actions[:] = [
        ActionMetadata("benchmark@local", "[local] Run benchmarks."),
    ]

    assert cyclopts_prototype.action_completion_candidates("b") == [
        ActionMetadata("benchmark@local", "[local] Run benchmarks."),
    ]


@pytest.mark.parametrize(
    "shell, expected_output",
    [
        ("bash", "build@local"),
        ("fish", "build@local\t[local] Build the project."),
        ("zsh", r"build@local:[local] Build the project."),
    ],
)
def test_hidden_completion_command_emits_shell_candidates(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    shell: cyclopts_prototype.Shell,
    expected_output: str,
) -> None:
    monkeypatch.setattr(
        cyclopts_prototype,
        "_list_action_metadata",
        lambda: [
            ActionMetadata("build@local", "[local] Build the project."),
            ActionMetadata("test@local", "[local] Run tests."),
        ],
    )

    assert (
        cyclopts_prototype.invoke(
            ["_complete-action", shell, "b"],
            exit_on_error=False,
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == expected_output


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion_adapter_calls_hidden_dynamic_endpoint(
    shell: cyclopts_prototype.Shell,
) -> None:
    script = cyclopts_prototype.generate_dynamic_completion_script(
        shell,
        "pyci",
    )

    assert "pyci _complete-action" in script
    assert "build@local" not in script


def test_prototype_preserves_action_error_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import python_ci_toolkit.actions as actions_module
    from python_ci_toolkit.actions.retrieval.exceptions import MissingGitActionRefError

    def fail_run(
        action_name: str,
        action_version: str | None = None,
        args: list[str] | None = None,
    ) -> None:
        raise MissingGitActionRefError("Missing action ref.")

    monkeypatch.setattr(actions_module, "run_ci_action", fail_run)

    result = cyclopts_prototype.invoke(
        ["demo@missing"],
        exit_on_error=False,
    )

    assert result == MissingGitActionRefError.exit_code
    error_output = capsys.readouterr().err
    assert "Error: Missing action ref." in error_output
    assert "Traceback" not in error_output
