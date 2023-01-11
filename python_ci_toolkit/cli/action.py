from __future__ import annotations

import glob
import re
from pathlib import Path
from typing import List

import rich_click as click
from click import Context, Argument
from click.shell_completion import CompletionItem

import python_ci_toolkit.actions
from python_ci_toolkit.actions import run_ci_action
from python_ci_toolkit.actions.actions import ACTION_VERSION_SEPARATOR

_FIRST_COMMENT_REGEX = re.compile(r'"""(?:\n)(.*?)"""', re.MULTILINE | re.UNICODE | re.DOTALL)


def _get_action_description_from_file(file_path: Path) -> str:
    """
    Tries to retrieve action description from the action script file.
    The first line of the top-level docstring is taken as action description.
    """
    assert file_path.exists()

    with file_path.open("r") as file:
        file_content = file.read()

    matches: List[str] = _FIRST_COMMENT_REGEX.findall(file_content)
    if len(matches) <= 0:
        return "<action has no description>"

    description = matches[0].splitlines()[0]

    return description


ACTION_IDENTIFIER_REGEX = re.compile(r'^\w+(?:@[\w\.]+)?', re.UNICODE)


def _validate_action_identifier(ctx: Context, param: Argument, value: str) -> str:
    action_identifier = str(value)

    if not ACTION_IDENTIFIER_REGEX.fullmatch(value):
        possible_match = ACTION_IDENTIFIER_REGEX.match(value)

        suggestion_string = ("\n"
                             "\n"
                             f"Did you mean '{possible_match.group()}'?") if possible_match else ""

        raise click.BadParameter(
            f"'{value}'\n\n"
            f"Action identifier must be in format ACTION_NAME[{ACTION_VERSION_SEPARATOR}ACTION_VERSON], where:\n"
            f" - ACTION_NAME can only contain alphanumeric characters and underscores.\n"
            f" - ACTION_VERSION can be either:\n"
            f"     - 'local' (for local actions)\n"
            f"     - any valid Git tag or branch name (for remote actions){suggestion_string}"
        )

    return action_identifier


def _complete_action_identifier(ctx: Context, param: Argument, incomplete: str):
    # search for local actions
    local_actions_directory = python_ci_toolkit.environment.ci_files_directory / "actions"
    local_action_script_paths = [Path(p) for p in glob.glob(str(local_actions_directory / "*.py"))]

    action_names = [f"{p.stem}@local" for p in local_action_script_paths]
    action_descriptions = [f"[local] {_get_action_description_from_file(p)}" for p in local_action_script_paths]

    # TODO: search for actions in the default repo

    return [CompletionItem(x[0], help=x[1])
            for x in list(zip(action_names, action_descriptions))]


@click.command(context_settings=dict(
    ignore_unknown_options=True,
))
@click.argument("action_identifier",
                required=1,
                type=str,
                callback=_validate_action_identifier,
                shell_complete=_complete_action_identifier)
@click.argument('action_args', nargs=-1, type=click.UNPROCESSED)
def action(action_identifier: str, action_args: List[str]) -> None:
    """
    Execute CI action based on the given ACTION_IDENTIFIER.\n
    Arbitrary arguments can be passed to the action in place of ACTION_ARGS.
    \n
    Notes:\n
     - Action name must correspond to the name of action's Python file without a '.py' extension.\n
     - Action version can be either a Git branch name or a Git tag. The corresponding branch/tag will be pulled from the action repository.\n
     - If action version is set to 'local', utility will look for the action file in '.ci/actions' folder inside your CI project's root directory.\n
     - Any arguments passed after the action name/tag will be passed to the executed action script.\n
    \n
    Examples:\n
    > python-ci-action build_dockers          # Runs 'build_dockers' action from Git branch 'main'\n
    > python-ci-action build_dockers@develop  # Runs 'build_dockers' action from Git branch 'develop'\n
    > python-ci-action build_dockers@v1.0.0   # Runs 'build_dockers' action from Git tag 'v1.0.0'\n
    > python-ci-action build_dockers@local    # Runs 'build_dockers' located at '.ci/actions/build_dockers.py' at your CI project's root folder\n
    """
    from python_ci_toolkit.console import initialize_ci_console

    # initialize CI console for formatted output
    initialize_ci_console()

    # version can be included in the first argument, separated from the action name by a semicolon
    if ACTION_VERSION_SEPARATOR in action_identifier:
        split_by_first_colon = action_identifier.split(ACTION_VERSION_SEPARATOR, 1)
        action_name = split_by_first_colon[0]
        action_version = split_by_first_colon[1]
    else:
        action_name = action_identifier
        action_version = None

    run_ci_action(action_name, action_version, action_args)


if __name__ == '__main__':
    action()
