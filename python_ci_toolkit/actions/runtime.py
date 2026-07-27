"""
Isolated subprocess execution for CI actions.
"""

from __future__ import annotations

import json
import logging
import os
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
from typing import Any

from .datatypes import ActionOutput
from .exceptions import (
    ActionProcessError,
    ActionRuntimeStartupError,
    InvalidActionOutputError,
    InvalidActionResultError,
    MissingActionEntrypointError,
)
from .execution import get_action_event_manager, get_event_output
from .outputs import read_action_output_file
from .protocol import (
    PYCI_ACTION_OUTPUT_ENV_VAR,
    PYCI_ACTION_STACK_ENV_VAR,
    PYCI_INTERNAL_ACTION_RESULT_ENV_VAR,
    PYCI_INTERNAL_LOG_LEVEL_ENV_VAR,
    PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS_ENV_VAR,
)
from ..environment import ci_paths
from ..shell import run_shell_command

_PYCI_DISTRIBUTION_NAME = "python-ci-toolkit"


def read_action_stack_from_environment() -> list[tuple[str, str]]:
    stack_value = os.environ.get(PYCI_ACTION_STACK_ENV_VAR)
    if not stack_value:
        return []

    try:
        raw_stack = json.loads(stack_value)
    except json.JSONDecodeError as error:
        raise InvalidActionResultError("current process", f"invalid {PYCI_ACTION_STACK_ENV_VAR}: {error}") from error

    if not isinstance(raw_stack, list):
        raise InvalidActionResultError(
            "current process",
            f"{PYCI_ACTION_STACK_ENV_VAR} must contain a JSON array",
        )

    stack: list[tuple[str, str]] = []
    for item in raw_stack:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(value, str) for value in item)
        ):
            raise InvalidActionResultError(
                "current process",
                f"{PYCI_ACTION_STACK_ENV_VAR} entries must be [action_name, action_version] pairs",
            )
        stack.append((item[0], item[1]))
    return stack


def _find_pyci_source_project_root() -> Path | None:
    project_root = Path(__file__).resolve().parents[2]
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    with pyproject_path.open("rb") as pyproject_file:
        project_name = tomllib.load(pyproject_file).get("project", {}).get("name")
    return project_root if project_name == _PYCI_DISTRIBUTION_NAME else None


def _get_pyci_runtime_arguments() -> list[str]:
    inherited_arguments = os.environ.get(PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS_ENV_VAR)
    if inherited_arguments is not None:
        try:
            arguments = json.loads(inherited_arguments)
        except json.JSONDecodeError as error:
            raise InvalidActionResultError(
                "current process",
                f"invalid {PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS_ENV_VAR}: {error}",
            ) from error
        if not isinstance(arguments, list) or not all(isinstance(argument, str) for argument in arguments):
            raise InvalidActionResultError(
                "current process",
                f"{PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS_ENV_VAR} must contain a JSON string array",
            )
        return arguments

    source_project_root = _find_pyci_source_project_root()
    if source_project_root is not None:
        return ["--with-editable", str(source_project_root)]

    return ["--with", _get_installed_pyci_requirement()]


def _get_installed_pyci_requirement() -> str:
    installed_distribution = distribution(_PYCI_DISTRIBUTION_NAME)
    direct_url_text = installed_distribution.read_text("direct_url.json")
    if not direct_url_text:
        return f"{_PYCI_DISTRIBUTION_NAME}=={installed_distribution.version}"

    try:
        direct_url = json.loads(direct_url_text)
    except json.JSONDecodeError:
        return f"{_PYCI_DISTRIBUTION_NAME}=={installed_distribution.version}"

    source_url = direct_url.get("url")
    if not isinstance(source_url, str) or not source_url:
        return f"{_PYCI_DISTRIBUTION_NAME}=={installed_distribution.version}"

    vcs_info = direct_url.get("vcs_info")
    if isinstance(vcs_info, dict):
        vcs = vcs_info.get("vcs")
        commit_id = vcs_info.get("commit_id")
        if isinstance(vcs, str) and isinstance(commit_id, str):
            vcs_source_url = source_url if source_url.startswith(f"{vcs}+") else f"{vcs}+{source_url}"
            source_url = f"{vcs_source_url}@{commit_id}"

    subdirectory = direct_url.get("subdirectory")
    if isinstance(subdirectory, str) and subdirectory:
        source_url = f"{source_url}#subdirectory={subdirectory}"

    return f"{_PYCI_DISTRIBUTION_NAME} @ {source_url}"


def _find_uv_executable() -> str | None:
    executable_name = "uv.exe" if os.name == "nt" else "uv"
    environment_uv = Path(sys.executable).with_name(executable_name)
    if environment_uv.is_file():
        return str(environment_uv)
    return shutil.which("uv")


def _build_uv_command(
    action_script_path: Path,
    action_name: str,
    action_version: str,
    args: list[str],
    pyci_runtime_arguments: list[str],
) -> list[str]:
    uv_executable = _find_uv_executable()
    if uv_executable is None:
        raise ActionRuntimeStartupError(
            f"{action_name}@{action_version}",
            1,
            "The 'uv' executable is not available.",
        )

    command = [
        uv_executable,
        "run",
        "--quiet",
        "--isolated",
        "--no-project",
        "--no-python-downloads",
        "--python",
        sys.executable,
        *pyci_runtime_arguments,
    ]

    requirements_path = action_script_path.parent / "requirements.txt"
    if requirements_path.exists():
        command.extend(["--with-requirements", str(requirements_path)])

    command.extend(
        [
            "--module",
            "python_ci_toolkit.actions.bootstrap",
            str(action_script_path),
            action_name,
            action_version,
            *args,
        ]
    )
    return command


def _read_runtime_result(result_path: Path, action_display_name: str) -> dict[str, Any]:
    if not result_path.exists():
        raise InvalidActionResultError(action_display_name, "the bootstrap did not write a result file")

    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InvalidActionResultError(action_display_name, str(error)) from error

    if not isinstance(result, dict):
        raise InvalidActionResultError(action_display_name, "the result file must contain a JSON object")
    return result


def _raise_for_failed_action(
    action_display_name: str,
    process_exit_code: int,
    result: dict[str, Any],
) -> None:
    status = result.get("status")

    if status == "missing_entrypoint":
        raise MissingActionEntrypointError(action_display_name, "action")
    if status != "error":
        raise InvalidActionResultError(
            action_display_name,
            f"expected error status for process exit code {process_exit_code}",
        )

    exception_type = result.get("exception_type")
    details = result.get("message")
    raise ActionProcessError(
        action_display_name,
        process_exit_code,
        exception_type if isinstance(exception_type, str) else None,
        details if isinstance(details, str) else None,
    )


def run_action_process(
    action_script_path: Path,
    action_name: str,
    action_version: str,
    args: list[str],
    action_stack: list[tuple[str, str]],
    run_id: str,
) -> ActionOutput:
    action_display_name = f"{action_name}@{action_version}"

    with tempfile.TemporaryDirectory(prefix="pyci-action-") as runtime_directory_value:
        runtime_directory = Path(runtime_directory_value)
        output_path = runtime_directory / "output.json"
        result_path = runtime_directory / "result.json"
        output_path.write_text("{}\n", encoding="utf-8")

        child_environment = os.environ.copy()
        child_environment[PYCI_ACTION_OUTPUT_ENV_VAR] = str(output_path)
        child_environment[PYCI_INTERNAL_ACTION_RESULT_ENV_VAR] = str(result_path)
        child_environment[PYCI_ACTION_STACK_ENV_VAR] = json.dumps(action_stack)
        child_environment[PYCI_INTERNAL_LOG_LEVEL_ENV_VAR] = str(
            logging.getLogger().getEffectiveLevel()
        )
        pyci_runtime_arguments = _get_pyci_runtime_arguments()
        child_environment[PYCI_INTERNAL_UV_RUNTIME_ARGUMENTS_ENV_VAR] = json.dumps(pyci_runtime_arguments)
        event_manager = get_action_event_manager()
        child_environment.update(
            event_manager.child_environment(
                run_id,
                depth=max(len(action_stack) - 1, 0),
            )
        )

        captured_stdout: list[str] = []
        captured_stderr: list[str] = []

        def handle_action_output_line(line: str, stream: str) -> None:
            event = event_manager.accept_child_line(line, stream, run_id)
            event_output = get_event_output(event)
            if event_output is None:
                return

            output_stream, text = event_output
            if output_stream == "stderr":
                captured_stderr.append(text)
            else:
                captured_stdout.append(text)

        command = _build_uv_command(
            action_script_path,
            action_name,
            action_version,
            args,
            pyci_runtime_arguments,
        )
        process_result = run_shell_command(
            command,
            cwd=ci_paths.project_root,
            raw_output=True,
            check=False,
            wsl=False,
            env=child_environment,
            on_output_line=handle_action_output_line,
        )

        try:
            runtime_result = _read_runtime_result(result_path, action_display_name)
        except InvalidActionResultError as error:
            if process_result.is_successful:
                raise
            details = "\n".join(captured_stderr).strip() or str(error)
            raise ActionRuntimeStartupError(action_display_name, process_result.exit_code, details) from error

        if process_result.is_failed:
            _raise_for_failed_action(action_display_name, process_result.exit_code, runtime_result)
        if runtime_result.get("status") != "success":
            raise InvalidActionResultError(action_display_name, "successful process did not report success")

        try:
            output_values = read_action_output_file(output_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise InvalidActionOutputError(action_display_name, str(error)) from error

        return ActionOutput(
            values=output_values,
            exit_code=process_result.exit_code,
            stdout="\n".join(captured_stdout),
            stderr="\n".join(captured_stderr),
        )
