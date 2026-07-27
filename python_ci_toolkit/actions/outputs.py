"""
Structured output helpers for CI actions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .datatypes import JsonValue
from .exceptions import ActionOutputUnavailableError
from .protocol import PYCI_ACTION_OUTPUT_ENV_VAR


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON value '{value}' is not supported")


def read_action_output_file(output_path: Path) -> dict[str, JsonValue]:
    output_text = output_path.read_text(encoding="utf-8")
    output_values = json.loads(
        output_text,
        parse_constant=_reject_nonstandard_json_constant,
    )
    if not isinstance(output_values, dict):
        raise ValueError("the top-level JSON value must be an object")
    return output_values


def _write_action_output_file(output_path: Path, output_values: dict[str, JsonValue]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_text = json.dumps(
        output_values,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(f"{output_text}\n")
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def set_action_output(name: str, value: JsonValue) -> None:
    """
    Add or replace one value in the current action's JSON output object.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("Action output names must be non-empty strings.")

    output_path_value = os.environ.get(PYCI_ACTION_OUTPUT_ENV_VAR)
    if not output_path_value:
        raise ActionOutputUnavailableError()

    output_path = Path(output_path_value)
    output_values = read_action_output_file(output_path) if output_path.exists() else {}
    output_values[name] = value
    _write_action_output_file(output_path, output_values)
