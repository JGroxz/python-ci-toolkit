"""
Child-process entrypoint for executing one CI action.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

from .exceptions import MissingActionEntrypointError
from .logging import configure_ci_logging
from .protocol import (
    PYCI_INTERNAL_ACTION_RESULT_ENV_VAR,
    PYCI_INTERNAL_LOG_LEVEL_ENV_VAR,
)
from ..python import import_module_from_file

_ACTION_ENTRY_POINT_FUNCTION_NAME = "action"
logger = logging.getLogger(__name__)


def _configure_logging_from_environment() -> None:
    log_level_value = os.environ.get(PYCI_INTERNAL_LOG_LEVEL_ENV_VAR)
    if log_level_value is None:
        return

    try:
        log_level = int(log_level_value)
    except ValueError as error:
        raise RuntimeError(
            f"{PYCI_INTERNAL_LOG_LEVEL_ENV_VAR} must contain a numeric logging level."
        ) from error

    configure_ci_logging(log_level)


def _write_result(result: dict[str, Any]) -> None:
    result_path_value = os.environ.get(PYCI_INTERNAL_ACTION_RESULT_ENV_VAR)
    if not result_path_value:
        raise RuntimeError(f"{PYCI_INTERNAL_ACTION_RESULT_ENV_VAR} is not set.")

    Path(result_path_value).write_text(
        f"{json.dumps(result, ensure_ascii=False, allow_nan=False)}\n",
        encoding="utf-8",
    )


def _run_action(
    action_script_path: Path,
    action_name: str,
    action_version: str,
    action_args: list[str],
) -> None:
    action_module = import_module_from_file(action_name, action_script_path, True)
    if not hasattr(action_module, _ACTION_ENTRY_POINT_FUNCTION_NAME):
        action_display_name = f"{action_name}@{action_version}"
        raise MissingActionEntrypointError(action_display_name, _ACTION_ENTRY_POINT_FUNCTION_NAME)

    sys.argv = [action_name, *action_args]
    action_function = getattr(action_module, _ACTION_ENTRY_POINT_FUNCTION_NAME)
    extra_kwargs = {"standalone_mode": False} if hasattr(action_function, "no_args_is_help") else {}
    action_function(**extra_kwargs)


def main() -> int:
    _configure_logging_from_environment()

    if len(sys.argv) < 4:
        raise RuntimeError(
            "Action bootstrap requires ACTION_SCRIPT_PATH, ACTION_NAME, and ACTION_VERSION arguments."
        )

    action_script_path = Path(sys.argv[1])
    action_name = sys.argv[2]
    action_version = sys.argv[3]
    action_args = sys.argv[4:]

    try:
        _run_action(action_script_path, action_name, action_version, action_args)
    except MissingActionEntrypointError as error:
        _write_result(
            {
                "status": "missing_entrypoint",
                "exception_type": type(error).__name__,
                "message": str(error),
                "exit_code": error.exit_code,
            }
        )
        return error.exit_code
    except SystemExit as error:
        if error.code is None or error.code == 0:
            _write_result({"status": "success", "exit_code": 0})
            return 0

        exit_code = error.code if isinstance(error.code, int) else 1
        if not isinstance(error.code, int):
            print(error.code, file=sys.stderr)
        _write_result(
            {
                "status": "error",
                "exception_type": type(error).__name__,
                "message": str(error),
                "exit_code": exit_code,
            }
        )
        return exit_code
    except BaseException as error:
        logger.debug("Action raised an exception.", exc_info=True)
        _write_result(
            {
                "status": "error",
                "exception_type": type(error).__name__,
                "message": str(error),
                "exit_code": 1,
            }
        )
        return 1

    _write_result({"status": "success", "exit_code": 0})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
