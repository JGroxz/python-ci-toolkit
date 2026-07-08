from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _write_action_script(tmp_path: Path, action_name: str, contents: str) -> Path:
    action_file = tmp_path / action_name / f"{action_name}.py"
    action_file.parent.mkdir(parents=True)
    action_file.write_text(contents, encoding="utf-8")
    return action_file


def _patch_action_retrieval(monkeypatch: pytest.MonkeyPatch, action_file: Path) -> None:
    import python_ci_toolkit.actions.actions as action_runtime

    def retrieve_test_action(action_name: str, action_version: str | None = None):
        return action_file, f"test action file '{action_file}'"

    monkeypatch.setattr(action_runtime, "retrieve_ci_action_script", retrieve_test_action)


def _patch_action_retrieval_map(
    monkeypatch: pytest.MonkeyPatch,
    action_files: dict[tuple[str, str | None], Path],
) -> list[tuple[str, str | None]]:
    import python_ci_toolkit.actions.actions as action_runtime

    retrieval_calls: list[tuple[str, str | None]] = []

    def retrieve_test_action(action_name: str, action_version: str | None = None):
        retrieval_calls.append((action_name, action_version))
        action_key = (action_name, action_version)
        if action_key not in action_files:
            raise AssertionError(f"Unexpected action retrieval: {action_key}")

        action_file = action_files[action_key]
        return action_file, f"test action file '{action_file}'"

    monkeypatch.setattr(action_runtime, "retrieve_ci_action_script", retrieve_test_action)
    return retrieval_calls


def _disable_remote_action_cache_timestamp_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    import python_ci_toolkit.actions.actions as action_runtime

    monkeypatch.setattr(action_runtime, "get_remote_action_repo", lambda: None)


def _reset_runtime_state(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    import python_ci_toolkit.actions.actions as action_runtime

    action_runtime._running_actions_stack.clear()
    monkeypatch.setattr(sys, "argv", argv.copy())


def test_run_ci_action_restores_runtime_state_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    action_name = "successful_action"
    original_argv = ["pyci", action_name, "--flag"]
    action_file = _write_action_script(
        tmp_path,
        action_name,
        "def action():\n"
        "    import sys\n"
        "    sys.argv[:] = ['action-mutated-argv']\n"
        "    return 'ok'\n",
    )
    _patch_action_retrieval(monkeypatch, action_file)
    _reset_runtime_state(monkeypatch, original_argv)

    output = action_runtime.run_ci_action(action_name, "local")

    assert output.value == "ok"
    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []

    action_file.write_text("def action():\n    return 'ok after failure'\n", encoding="utf-8")
    output = action_runtime.run_ci_action(action_name, "local")

    assert output.value == "ok after failure"
    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []


def test_run_ci_action_restores_runtime_state_after_action_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    action_name = "failing_action"
    original_argv = ["pyci", action_name, "--flag"]
    action_file = _write_action_script(
        tmp_path,
        action_name,
        "def action():\n"
        "    import sys\n"
        "    sys.argv[:] = ['action-mutated-argv']\n"
        "    raise RuntimeError('action failed')\n",
    )
    _patch_action_retrieval(monkeypatch, action_file)
    _reset_runtime_state(monkeypatch, original_argv)

    with pytest.raises(RuntimeError, match="action failed"):
        action_runtime.run_ci_action(action_name, "local")

    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []


def test_nested_action_receives_explicit_args_and_restores_parent_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    parent_action_name = "parent_action"
    child_action_name = "child_action"
    original_argv = ["pyci", parent_action_name, "--parent-flag"]
    parent_action_file = _write_action_script(
        tmp_path,
        parent_action_name,
        "def action():\n"
        "    import sys\n"
        "    from python_ci_toolkit.actions import run_ci_action\n"
        "    parent_argv_before_child = sys.argv.copy()\n"
        "    child_output = run_ci_action('child_action', 'local', ['--child-flag']).value\n"
        "    parent_argv_after_child = sys.argv.copy()\n"
        "    return {\n"
        "        'parent_argv_before_child': parent_argv_before_child,\n"
        "        'child_output': child_output,\n"
        "        'parent_argv_after_child': parent_argv_after_child,\n"
        "    }\n",
    )
    child_action_file = _write_action_script(
        tmp_path,
        child_action_name,
        "def action():\n"
        "    import sys\n"
        "    return sys.argv.copy()\n",
    )
    _patch_action_retrieval_map(
        monkeypatch,
        {
            (parent_action_name, "local"): parent_action_file,
            (child_action_name, "local"): child_action_file,
        },
    )
    _reset_runtime_state(monkeypatch, original_argv)

    output = action_runtime.run_ci_action(parent_action_name, "local")

    assert output.value == {
        "parent_argv_before_child": ["pyci parent_action", "--parent-flag"],
        "child_output": ["child_action", "--child-flag"],
        "parent_argv_after_child": ["pyci parent_action", "--parent-flag"],
    }
    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []


def test_caught_nested_action_failure_restores_parent_runtime_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    parent_action_name = "catching_parent_action"
    child_action_name = "failing_child_action"
    original_argv = ["pyci", parent_action_name, "--parent-flag"]
    parent_action_file = _write_action_script(
        tmp_path,
        parent_action_name,
        "def action():\n"
        "    import sys\n"
        "    from python_ci_toolkit.actions import run_ci_action\n"
        "    try:\n"
        "        run_ci_action('failing_child_action', 'local', ['--child-flag'])\n"
        "    except RuntimeError as error:\n"
        "        return {\n"
        "            'caught': str(error),\n"
        "            'parent_argv_after_child': sys.argv.copy(),\n"
        "        }\n",
    )
    child_action_file = _write_action_script(
        tmp_path,
        child_action_name,
        "def action():\n"
        "    import sys\n"
        "    sys.argv[:] = ['mutated-child-argv']\n"
        "    raise RuntimeError('child failed')\n",
    )
    _patch_action_retrieval_map(
        monkeypatch,
        {
            (parent_action_name, "local"): parent_action_file,
            (child_action_name, "local"): child_action_file,
        },
    )
    _reset_runtime_state(monkeypatch, original_argv)

    output = action_runtime.run_ci_action(parent_action_name, "local")

    assert output.value == {
        "caught": "child failed",
        "parent_argv_after_child": ["pyci catching_parent_action", "--parent-flag"],
    }
    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []


def test_uncaught_nested_action_failure_propagates_and_restores_runtime_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    parent_action_name = "uncaught_parent_action"
    child_action_name = "uncaught_child_action"
    original_argv = ["pyci", parent_action_name]
    parent_action_file = _write_action_script(
        tmp_path,
        parent_action_name,
        "def action():\n"
        "    from python_ci_toolkit.actions import run_ci_action\n"
        "    run_ci_action('uncaught_child_action', 'local')\n",
    )
    child_action_file = _write_action_script(
        tmp_path,
        child_action_name,
        "def action():\n"
        "    import sys\n"
        "    sys.argv[:] = ['mutated-child-argv']\n"
        "    raise RuntimeError('uncaught child failed')\n",
    )
    _patch_action_retrieval_map(
        monkeypatch,
        {
            (parent_action_name, "local"): parent_action_file,
            (child_action_name, "local"): child_action_file,
        },
    )
    _reset_runtime_state(monkeypatch, original_argv)

    with pytest.raises(RuntimeError, match="uncaught child failed"):
        action_runtime.run_ci_action(parent_action_name, "local")

    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []


def test_nested_action_recursion_is_blocked_by_action_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    parent_action_name = "recursive_parent_action"
    child_action_name = "recursive_child_action"
    original_argv = ["pyci", parent_action_name]
    parent_action_file = _write_action_script(
        tmp_path,
        parent_action_name,
        "def action():\n"
        "    from python_ci_toolkit.actions import run_ci_action\n"
        "    run_ci_action('recursive_child_action', 'local')\n",
    )
    child_action_file = _write_action_script(
        tmp_path,
        child_action_name,
        "def action():\n"
        "    from python_ci_toolkit.actions import run_ci_action\n"
        "    run_ci_action('recursive_parent_action')\n",
    )
    retrieval_calls = _patch_action_retrieval_map(
        monkeypatch,
        {
            (parent_action_name, "local"): parent_action_file,
            (child_action_name, "local"): child_action_file,
        },
    )
    _reset_runtime_state(monkeypatch, original_argv)

    with pytest.raises(RuntimeError, match="Recursive action calls are not allowed"):
        action_runtime.run_ci_action(parent_action_name, "local")

    assert retrieval_calls == [
        (parent_action_name, "local"),
        (child_action_name, "local"),
    ]
    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []


def test_nested_action_without_version_resolves_to_default_remote_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    parent_action_name = "default_version_parent_action"
    child_action_name = "default_version_child_action"
    original_argv = ["pyci", parent_action_name]
    parent_action_file = _write_action_script(
        tmp_path,
        parent_action_name,
        "def action():\n"
        "    from python_ci_toolkit.actions import run_ci_action\n"
        "    return run_ci_action('default_version_child_action').value\n",
    )
    child_action_file = _write_action_script(
        tmp_path,
        child_action_name,
        "def action():\n"
        "    return 'child result'\n",
    )
    retrieval_calls = _patch_action_retrieval_map(
        monkeypatch,
        {
            (parent_action_name, "local"): parent_action_file,
            (child_action_name, "main"): child_action_file,
        },
    )
    _disable_remote_action_cache_timestamp_reset(monkeypatch)
    _reset_runtime_state(monkeypatch, original_argv)

    output = action_runtime.run_ci_action(parent_action_name, "local")

    assert output.value == "child result"
    assert retrieval_calls == [
        (parent_action_name, "local"),
        (child_action_name, "main"),
    ]
    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []


def test_nested_action_explicit_version_overrides_default_remote_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    parent_action_name = "explicit_version_parent_action"
    child_action_name = "explicit_version_child_action"
    child_action_version = "feature-branch"
    original_argv = ["pyci", parent_action_name]
    parent_action_file = _write_action_script(
        tmp_path,
        parent_action_name,
        "def action():\n"
        "    from python_ci_toolkit.actions import run_ci_action\n"
        "    return run_ci_action('explicit_version_child_action', 'feature-branch').value\n",
    )
    child_action_file = _write_action_script(
        tmp_path,
        child_action_name,
        "def action():\n"
        "    return 'versioned child result'\n",
    )
    retrieval_calls = _patch_action_retrieval_map(
        monkeypatch,
        {
            (parent_action_name, "local"): parent_action_file,
            (child_action_name, child_action_version): child_action_file,
        },
    )
    _disable_remote_action_cache_timestamp_reset(monkeypatch)
    _reset_runtime_state(monkeypatch, original_argv)

    output = action_runtime.run_ci_action(parent_action_name, "local")

    assert output.value == "versioned child result"
    assert retrieval_calls == [
        (parent_action_name, "local"),
        (child_action_name, child_action_version),
    ]
    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []


def test_run_ci_action_restores_runtime_state_after_retrieval_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    action_name = "missing_action"
    original_argv = ["pyci", action_name]

    def fail_action_retrieval(action_name: str, action_version: str | None = None):
        raise FileNotFoundError("action not found")

    monkeypatch.setattr(action_runtime, "retrieve_ci_action_script", fail_action_retrieval)
    _reset_runtime_state(monkeypatch, original_argv)

    with pytest.raises(FileNotFoundError, match="action not found"):
        action_runtime.run_ci_action(action_name, "local")

    assert sys.argv == original_argv
    assert action_runtime._running_actions_stack == []
