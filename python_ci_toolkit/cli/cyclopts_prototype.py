"""Isolated Cyclopts prototype for the ``pyci`` action entry point."""

from __future__ import annotations

import logging
import os
import re
import sys
from collections.abc import Iterable, Sequence
from typing import Annotated, Literal

from cyclopts import App, Parameter
from rich.console import Console

from .action.find import ActionMetadata

Shell = Literal["bash", "zsh", "fish"]

_ACTION_IDENTIFIER_REGEX = re.compile(r"^\w+(?:@[\w./\-+]+)?$", re.UNICODE)
_COMMAND_NAME_REGEX = re.compile(r"^[A-Za-z0-9_.-]+$")
_HELP_FLAGS = frozenset(("-h", "--help"))

app = App(
    name="pyci-cyclopts",
    help="Execute Python CI Toolkit actions.",
    help_flags=(),
    version_flags=(),
)


def _validate_action_identifier(type_: type[str], value: str) -> None:
    del type_

    if _ACTION_IDENTIFIER_REGEX.fullmatch(value):
        return

    possible_match = _ACTION_IDENTIFIER_REGEX.match(value)
    suggestion = f"\n\nDid you mean '{possible_match.group()}'?" if possible_match else ""
    raise ValueError(
        f"Action identifier must be in the format ACTION_NAME[@ACTION_VERSION].{suggestion}"
    )


def _split_action_identifier(action_identifier: str) -> tuple[str, str | None]:
    from ..actions.constants import ACTION_VERSION_SEPARATOR

    if ACTION_VERSION_SEPARATOR not in action_identifier:
        return action_identifier, None

    action_name, action_version = action_identifier.split(ACTION_VERSION_SEPARATOR, 1)
    return action_name, action_version


def _list_action_metadata() -> list[ActionMetadata]:
    from .action.find import list_available_actions

    logging_was_disabled = logging.root.disabled
    logging.root.disabled = True
    try:
        return list_available_actions()
    finally:
        logging.root.disabled = logging_was_disabled


def action_completion_candidates(incomplete: str) -> list[ActionMetadata]:
    """Return action candidates from the project active at completion time."""
    return [
        metadata
        for metadata in _list_action_metadata()
        if metadata.name.startswith(incomplete)
    ]


def _clean_completion_description(description: str) -> str:
    return " ".join(description.split())


def _escape_zsh_completion_part(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", r"\:")


def format_completion_candidates(
    candidates: Sequence[ActionMetadata],
    shell: Shell,
) -> list[str]:
    if shell == "bash":
        return [candidate.name for candidate in candidates]

    if shell == "fish":
        return [
            f"{candidate.name}\t{_clean_completion_description(candidate.description)}"
            for candidate in candidates
        ]

    return [
        f"{_escape_zsh_completion_part(candidate.name)}:"
        f"{_escape_zsh_completion_part(_clean_completion_description(candidate.description))}"
        for candidate in candidates
    ]


def generate_dynamic_completion_script(shell: Shell, command_name: str = "pyci") -> str:
    """Generate a minimal dynamic action-completion adapter."""
    if not _COMMAND_NAME_REGEX.fullmatch(command_name):
        raise ValueError(f"Unsupported completion command name: {command_name!r}")

    function_name = command_name.replace("-", "_").replace(".", "_")

    if shell == "bash":
        return f"""# Dynamic action completion for {command_name}
_{function_name}_complete() {{
    if [[ $COMP_CWORD -ne 1 ]]; then
        return
    fi

    local candidate
    while IFS= read -r candidate; do
        COMPREPLY+=("$candidate")
    done < <(command {command_name} _complete-action bash "${{COMP_WORDS[COMP_CWORD]}}" 2>/dev/null)
}}
complete -F _{function_name}_complete {command_name}
"""

    if shell == "fish":
        return f"""# Dynamic action completion for {command_name}
function __{function_name}_complete_actions
    command {command_name} _complete-action fish (commandline -ct) 2>/dev/null
end
complete -c {command_name} -n 'test (count (commandline -opc)) -eq 1' -f -a '(__{function_name}_complete_actions)'
"""

    return f"""#compdef {command_name}
# Dynamic action completion for {command_name}
_{function_name}_complete() {{
    if (( CURRENT != 2 )); then
        return
    fi

    local -a actions
    actions=("${{(@f)$(command {command_name} _complete-action zsh "${{words[CURRENT]}}" 2>/dev/null)}}")
    _describe 'action' actions
}}
compdef _{function_name}_complete {command_name}
"""


@app.command(name="_complete-action", show=False)
def _complete_action(shell: Shell, incomplete: str = "") -> None:
    """Emit dynamic action candidates for a shell adapter."""
    candidates = action_completion_candidates(incomplete)
    for candidate in format_completion_candidates(candidates, shell):
        print(candidate)


@app.command(name="_completion-script", show=False)
def _completion_script(shell: Shell, command_name: str = "pyci") -> None:
    """Emit the prototype completion adapter for manual inspection."""
    print(generate_dynamic_completion_script(shell, command_name), end="")


@app.default
def execute_action(
    action_identifier: Annotated[
        str,
        Parameter(
            help="Action name and optional version.",
            validator=_validate_action_identifier,
        ),
    ],
    /,
    *action_args: Annotated[
        str,
        Parameter(
            show=False,
            allow_leading_hyphen=True,
        ),
    ],
    debug: Annotated[
        bool,
        Parameter(
            name="--debug",
            help="Enable debug logging.",
            show=False,
        ),
    ] = False,
) -> int:
    """Execute a CI action, forwarding all remaining arguments."""
    from ..actions import run_ci_action
    from ..actions.exceptions import ActionRuntimeError
    from ..actions.logging import configure_ci_logging
    from ..actions.retrieval.exceptions import ActionRetrievalError

    is_debug_enabled = debug or bool(os.environ.get("DEBUG"))
    configure_ci_logging("DEBUG" if is_debug_enabled else "INFO")

    action_name, action_version = _split_action_identifier(action_identifier)

    try:
        run_ci_action(action_name, action_version, list(action_args))
    except (ActionRetrievalError, ActionRuntimeError) as error:
        Console(stderr=True).print(f"[pyci.error]Error:[/] {error}")
        return error.exit_code

    return 0


def _toolkit_help_requested(tokens: Sequence[str]) -> bool:
    if not tokens:
        return True

    for token in tokens:
        if token in _HELP_FLAGS:
            return True
        if token == "--debug":
            continue
        return False

    return True


def invoke(
    tokens: Iterable[str] | None = None,
    *,
    exit_on_error: bool = True,
) -> int:
    """Invoke the prototype while preserving delegated action help."""
    arguments = list(sys.argv[1:] if tokens is None else tokens)

    if _toolkit_help_requested(arguments):
        app.help_print()
        return 0

    result = app(
        arguments,
        exit_on_error=exit_on_error,
        result_action="return_value",
    )
    return result if isinstance(result, int) else 0


def main() -> None:
    raise SystemExit(invoke())


if __name__ == "__main__":
    main()
