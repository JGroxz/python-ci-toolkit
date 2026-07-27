from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
import site
import zipfile

import pytest

from python_ci_toolkit.actions.datatypes import ActionOutput


def _write_action_script(directory: Path, action_name: str, contents: str) -> Path:
    action_file = directory / action_name / f"{action_name}.py"
    action_file.parent.mkdir(parents=True, exist_ok=True)
    action_file.write_text(contents, encoding="utf-8")
    return action_file


def _patch_action_retrieval(monkeypatch: pytest.MonkeyPatch, action_file: Path) -> None:
    import python_ci_toolkit.actions.actions as action_runtime

    def retrieve_test_action(action_name: str, action_version: str | None = None):
        return action_file, f"test action file '{action_file}'"

    monkeypatch.setattr(action_runtime, "retrieve_ci_action_script", retrieve_test_action)


def _reset_runtime_state() -> None:
    import python_ci_toolkit.actions.actions as action_runtime

    action_runtime._running_actions_stack.clear()


@pytest.fixture(autouse=True)
def reset_action_runtime(monkeypatch: pytest.MonkeyPatch):
    from python_ci_toolkit.actions.protocol import PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS_ENV_VAR

    _reset_runtime_state()
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setenv(PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS_ENV_VAR, "[]")
    runtime_import_paths = [
        str(Path(__file__).parents[2]),
        *site.getsitepackages(),
    ]
    existing_python_path = os.environ.get("PYTHONPATH")
    if existing_python_path:
        runtime_import_paths.append(existing_python_path)
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(runtime_import_paths))
    yield
    _reset_runtime_state()


def test_run_ci_action_passes_retrieved_action_to_process_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    action_file = _write_action_script(tmp_path, "successful_action", "def action():\n    pass\n")
    _patch_action_retrieval(monkeypatch, action_file)
    process_calls = []

    def run_test_process(**kwargs):
        process_calls.append(kwargs)
        return ActionOutput(values={"status": "ok"})

    monkeypatch.setattr(action_runtime, "run_action_process", run_test_process)

    output = action_runtime.run_ci_action("successful_action", "local", ["--flag"])

    assert output.values == {"status": "ok"}
    assert process_calls == [
        {
            "action_script_path": action_file,
            "action_name": "successful_action",
            "action_version": "local",
            "args": ["--flag"],
            "action_stack": [("successful_action", "local")],
        }
    ]
    assert action_runtime._running_actions_stack == []


def test_run_ci_action_restores_stack_after_process_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    action_file = _write_action_script(tmp_path, "failing_action", "def action():\n    pass\n")
    _patch_action_retrieval(monkeypatch, action_file)

    def fail_process(**kwargs):
        raise RuntimeError("process failed")

    monkeypatch.setattr(action_runtime, "run_action_process", fail_process)

    with pytest.raises(RuntimeError, match="process failed"):
        action_runtime.run_ci_action("failing_action", "local")

    assert action_runtime._running_actions_stack == []


def test_run_ci_action_restores_stack_after_retrieval_failure(monkeypatch: pytest.MonkeyPatch):
    import python_ci_toolkit.actions.actions as action_runtime

    def fail_action_retrieval(action_name: str, action_version: str | None = None):
        raise FileNotFoundError("action not found")

    monkeypatch.setattr(action_runtime, "retrieve_ci_action_script", fail_action_retrieval)

    with pytest.raises(FileNotFoundError, match="action not found"):
        action_runtime.run_ci_action("missing_action", "local")

    assert action_runtime._running_actions_stack == []


def test_recursive_action_is_rejected_before_retrieval(monkeypatch: pytest.MonkeyPatch):
    import python_ci_toolkit.actions.actions as action_runtime
    from python_ci_toolkit.actions.exceptions import RecursiveActionError

    action_runtime._running_actions_stack.append(("recursive_action", "local"))

    with pytest.raises(RecursiveActionError, match="Recursive action calls are not allowed"):
        action_runtime.run_ci_action("recursive_action", "local")


def test_action_stack_is_loaded_from_child_environment(monkeypatch: pytest.MonkeyPatch):
    from python_ci_toolkit.actions.runtime import (
        read_action_stack_from_environment,
    )
    from python_ci_toolkit.actions.protocol import PYCI_ACTION_STACK_ENV_VAR

    monkeypatch.setenv(
        PYCI_ACTION_STACK_ENV_VAR,
        json.dumps([["parent_action", "local"], ["child_action", "main"]]),
    )

    assert read_action_stack_from_environment() == [
        ("parent_action", "local"),
        ("child_action", "main"),
    ]


def test_action_stack_rejects_invalid_child_environment(monkeypatch: pytest.MonkeyPatch):
    from python_ci_toolkit.actions.exceptions import InvalidActionResultError
    from python_ci_toolkit.actions.runtime import (
        read_action_stack_from_environment,
    )
    from python_ci_toolkit.actions.protocol import PYCI_ACTION_STACK_ENV_VAR

    monkeypatch.setenv(PYCI_ACTION_STACK_ENV_VAR, '{"not": "a stack"}')

    with pytest.raises(InvalidActionResultError, match="must contain a JSON array"):
        read_action_stack_from_environment()


def test_installed_runtime_requirement_reuses_direct_wheel_url(monkeypatch: pytest.MonkeyPatch):
    import python_ci_toolkit.actions.runtime as process_runtime

    class InstalledDistribution:
        version = "1.2.3"

        @staticmethod
        def read_text(filename: str) -> str | None:
            assert filename == "direct_url.json"
            return json.dumps({"url": "file:///tmp/python_ci_toolkit-1.2.3-py3-none-any.whl"})

    monkeypatch.setattr(process_runtime, "distribution", lambda name: InstalledDistribution())

    assert process_runtime._get_installed_pyci_requirement() == (
        "python-ci-toolkit @ file:///tmp/python_ci_toolkit-1.2.3-py3-none-any.whl"
    )


def test_installed_runtime_requirement_pins_registry_version(monkeypatch: pytest.MonkeyPatch):
    import python_ci_toolkit.actions.runtime as process_runtime

    class InstalledDistribution:
        version = "1.2.3"

        @staticmethod
        def read_text(filename: str) -> None:
            assert filename == "direct_url.json"
            return None

    monkeypatch.setattr(process_runtime, "distribution", lambda name: InstalledDistribution())

    assert process_runtime._get_installed_pyci_requirement() == "python-ci-toolkit==1.2.3"


def test_inherited_runtime_arguments_reject_invalid_json(monkeypatch: pytest.MonkeyPatch):
    import python_ci_toolkit.actions.runtime as process_runtime
    from python_ci_toolkit.actions.exceptions import InvalidActionResultError
    from python_ci_toolkit.actions.protocol import PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS_ENV_VAR

    monkeypatch.setenv(PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS_ENV_VAR, "{")

    with pytest.raises(InvalidActionResultError, match="invalid PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS"):
        process_runtime._get_pyci_runtime_arguments()


def test_isolated_action_returns_json_outputs_and_process_streams(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    action_file = _write_action_script(
        tmp_path,
        "output_action",
        "import sys\n"
        "from python_ci_toolkit.actions import set_action_output\n"
        "\n"
        "def action():\n"
        "    print('action stdout')\n"
        "    print('action stderr', file=sys.stderr)\n"
        "    set_action_output('argv', sys.argv)\n"
        "    set_action_output('metadata', {'count': 2, 'ready': True})\n"
        "    return object()\n",
    )
    _patch_action_retrieval(monkeypatch, action_file)

    output = action_runtime.run_ci_action("output_action", "local", ["--flag", "value"])

    assert output.values == {
        "argv": ["output_action", "--flag", "value"],
        "metadata": {"count": 2, "ready": True},
    }
    assert output.exit_code == 0
    assert "action stdout" in output.stdout
    assert "action stderr" in output.stderr
    assert action_runtime._running_actions_stack == []


def test_isolated_action_inherits_parent_log_level(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    import python_ci_toolkit.actions.actions as action_runtime

    action_file = _write_action_script(
        tmp_path,
        "logging_action",
        "from python_ci_toolkit.actions import get_action_logger\n"
        "\n"
        "logger = get_action_logger(__name__)\n"
        "\n"
        "def action():\n"
        "    logger.info('action info log')\n"
        "    logger.debug('action debug log')\n",
    )
    _patch_action_retrieval(monkeypatch, action_file)
    caplog.set_level(logging.INFO)

    output = action_runtime.run_ci_action("logging_action", "local")

    assert "action info log" in output.stdout
    assert "action debug log" not in output.stdout


def test_isolated_action_inherits_parent_debug_level(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    import python_ci_toolkit.actions.actions as action_runtime

    action_file = _write_action_script(
        tmp_path,
        "debug_logging_action",
        "from python_ci_toolkit.actions import get_action_logger\n"
        "\n"
        "logger = get_action_logger(__name__)\n"
        "\n"
        "def action():\n"
        "    logger.debug('action debug log')\n",
    )
    _patch_action_retrieval(monkeypatch, action_file)
    caplog.set_level(logging.DEBUG)

    output = action_runtime.run_ci_action("debug_logging_action", "local")

    assert "action debug log" in output.stdout


def test_isolated_action_missing_entrypoint_is_structured_runtime_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime
    from python_ci_toolkit.actions.exceptions import MissingActionEntrypointError

    action_file = _write_action_script(
        tmp_path,
        "missing_entrypoint_action",
        "def helper():\n    pass\n",
    )
    _patch_action_retrieval(monkeypatch, action_file)

    with pytest.raises(MissingActionEntrypointError) as error:
        action_runtime.run_ci_action("missing_entrypoint_action", "local")

    assert error.value.exit_code == 1
    assert "does not have a 'action()' function" in str(error.value)
    assert action_runtime._running_actions_stack == []


def test_isolated_action_exception_crosses_boundary_as_process_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
):
    import python_ci_toolkit.actions.actions as action_runtime
    from python_ci_toolkit.actions.exceptions import ActionProcessError

    action_file = _write_action_script(
        tmp_path,
        "failing_action",
        "def action():\n    raise ValueError('action failed')\n",
    )
    _patch_action_retrieval(monkeypatch, action_file)
    caplog.set_level(logging.INFO)

    with pytest.raises(ActionProcessError) as error:
        action_runtime.run_ci_action("failing_action", "local")

    captured = capsys.readouterr()
    assert error.value.exit_code == 1
    assert "ValueError" in str(error.value)
    assert "action failed" in str(error.value)
    assert "Action raised an exception" not in captured.out
    assert "Traceback" not in captured.err
    assert action_runtime._running_actions_stack == []


def test_isolated_action_exception_includes_traceback_at_debug_level(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
):
    import python_ci_toolkit.actions.actions as action_runtime
    from python_ci_toolkit.actions.exceptions import ActionProcessError

    action_file = _write_action_script(
        tmp_path,
        "debug_failing_action",
        "def action():\n    raise ValueError('debug action failed')\n",
    )
    _patch_action_retrieval(monkeypatch, action_file)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(ActionProcessError):
        action_runtime.run_ci_action("debug_failing_action", "local")

    captured = capsys.readouterr()
    assert "Action raised an exception" in captured.out
    assert "ValueError" in captured.out
    assert "debug action failed" in captured.out


def test_isolated_action_rejects_invalid_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime
    from python_ci_toolkit.actions.exceptions import InvalidActionOutputError

    action_file = _write_action_script(
        tmp_path,
        "invalid_output_action",
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "def action():\n"
        "    Path(os.environ['PYCI_ACTION_OUTPUT']).write_text('[]', encoding='utf-8')\n",
    )
    _patch_action_retrieval(monkeypatch, action_file)

    with pytest.raises(InvalidActionOutputError, match="top-level JSON value must be an object"):
        action_runtime.run_ci_action("invalid_output_action", "local")


def _write_test_dependency_wheel(directory: Path) -> Path:
    wheel_path = directory / "pyci_isolation_probe-1.0.0-py3-none-any.whl"
    dist_info = "pyci_isolation_probe-1.0.0.dist-info"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr("pyci_isolation_probe.py", "VALUE = 'isolated dependency'\n")
        wheel.writestr(
            f"{dist_info}/METADATA",
            "Metadata-Version: 2.1\n"
            "Name: pyci-isolation-probe\n"
            "Version: 1.0.0\n",
        )
        wheel.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\n"
            "Generator: python-ci-toolkit-tests\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )
        wheel.writestr(f"{dist_info}/RECORD", "")
    return wheel_path


def test_action_requirements_are_available_only_in_isolated_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    action_file = _write_action_script(
        tmp_path,
        "dependency_action",
        "from python_ci_toolkit.actions import set_action_output\n"
        "from pyci_isolation_probe import VALUE\n"
        "\n"
        "def action():\n"
        "    set_action_output('dependency', VALUE)\n",
    )
    dependency_wheel = _write_test_dependency_wheel(tmp_path)
    (action_file.parent / "requirements.txt").write_text(
        f"{dependency_wheel}\n",
        encoding="utf-8",
    )
    _patch_action_retrieval(monkeypatch, action_file)
    assert importlib.util.find_spec("pyci_isolation_probe") is None

    output = action_runtime.run_ci_action("dependency_action", "local")

    assert output.values == {"dependency": "isolated dependency"}
    assert importlib.util.find_spec("pyci_isolation_probe") is None


def _write_local_project_action(project_root: Path, action_name: str, contents: str) -> Path:
    action_path = project_root / ".ci" / "actions" / action_name / f"{action_name}.py"
    action_path.parent.mkdir(parents=True, exist_ok=True)
    action_path.write_text(contents, encoding="utf-8")
    return action_path


def test_nested_action_uses_its_own_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime

    project_root = tmp_path / "project"
    project_root.mkdir()
    parent_action = _write_local_project_action(
        project_root,
        "parent_action",
        "from python_ci_toolkit.actions import run_ci_action, set_action_output\n"
        "\n"
        "def action():\n"
        "    child = run_ci_action('child_action', 'local', ['--child-flag'])\n"
        "    set_action_output('child', child.values)\n",
    )
    _write_local_project_action(
        project_root,
        "child_action",
        "import sys\n"
        "from python_ci_toolkit.actions import set_action_output\n"
        "\n"
        "def action():\n"
        "    set_action_output('argv', sys.argv)\n",
    )
    monkeypatch.chdir(project_root)
    _patch_action_retrieval(monkeypatch, parent_action)

    output = action_runtime.run_ci_action("parent_action", "local")

    assert output.values == {
        "child": {
            "argv": ["child_action", "--child-flag"],
        }
    }


def test_nested_action_recursion_is_blocked_across_processes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import python_ci_toolkit.actions.actions as action_runtime
    from python_ci_toolkit.actions.exceptions import ActionProcessError

    project_root = tmp_path / "project"
    project_root.mkdir()
    parent_action = _write_local_project_action(
        project_root,
        "recursive_parent",
        "from python_ci_toolkit.actions import run_ci_action\n"
        "\n"
        "def action():\n"
        "    run_ci_action('recursive_child', 'local')\n",
    )
    _write_local_project_action(
        project_root,
        "recursive_child",
        "from python_ci_toolkit.actions import run_ci_action\n"
        "\n"
        "def action():\n"
        "    run_ci_action('recursive_parent', 'local')\n",
    )
    monkeypatch.chdir(project_root)
    _patch_action_retrieval(monkeypatch, parent_action)

    with pytest.raises(ActionProcessError, match="Recursive action calls are not allowed"):
        action_runtime.run_ci_action("recursive_parent", "local")
