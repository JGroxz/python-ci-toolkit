from __future__ import annotations

import re
from pathlib import Path
from typing import List

import rich_click as click
from click import Context, Argument
from click.shell_completion import CompletionItem

from python_ci_toolkit.actions.actions import list_actions_in_directory

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


ACTION_IDENTIFIER_REGEX = re.compile(r'^\w+(?:@[\w\.\/\-\+]+)?', re.UNICODE)


def _validate_action_identifier(ctx: Context, param: Argument, value: str) -> str:
    from python_ci_toolkit.actions.actions import ACTION_VERSION_SEPARATOR

    action_identifier = str(value)

    if not ACTION_IDENTIFIER_REGEX.fullmatch(value):
        possible_match = ACTION_IDENTIFIER_REGEX.match(value)

        suggestion_string = ("\n"
                             "\n"
                             f"Did you mean '{possible_match.group()}'?") if possible_match else ""

        raise click.BadParameter(
            f"'{value}'\n\n"
            f"Action identifier must be in the format ACTION_NAME[{ACTION_VERSION_SEPARATOR}ACTION_VERSION], where:\n"
            f" - ACTION_NAME can only contain alphanumeric characters and underscores.\n"
            f" - ACTION_VERSION can be either:\n"
            f"     - 'local' (for local actions)\n"
            f"     - any valid Git tag or branch name (for remote actions){suggestion_string}"
        )

    return action_identifier


def _complete_action_identifier(ctx: Context, param: Argument, incomplete: str):
    # search for local actions
    from python_ci_toolkit.actions.actions import LOCAL_ACTIONS_DIRECTORY
    local_action_script_paths = list_actions_in_directory(LOCAL_ACTIONS_DIRECTORY)
    local_action_names = [f"{p.stem}@local" for p in local_action_script_paths]
    local_action_descriptions = [f"[local]  {_get_action_description_from_file(p)}" for p in local_action_script_paths]
    local_actions_metadata = sorted(list(zip(local_action_names, local_action_descriptions)))

    # remote actions
    from python_ci_toolkit.git import ci_repo
    if ci_repo is None:
        # do not pull remote actions repo if local project's directory is not a Git repo
        remote_actions_metadata = []
    else:
        # search for actions in the default Git repo
        from python_ci_toolkit.actions.actions import retrieve_action_repo, DEFAULT_ACTION_REPO_URL
        from python_ci_toolkit.git import get_default_ssh_private_key
        cloned_actions_directory = retrieve_action_repo(
            git_repo_url=DEFAULT_ACTION_REPO_URL,
            ssh_private_key=get_default_ssh_private_key()
        )
        remote_action_script_paths = list_actions_in_directory(cloned_actions_directory)
        remote_action_names = [f"{p.stem}" for p in remote_action_script_paths]
        remote_action_descriptions = [f"[remote] {_get_action_description_from_file(p)}" for p in remote_action_script_paths]
        remote_actions_metadata = sorted(list(zip(remote_action_names, remote_action_descriptions)))

    return [CompletionItem(x[0], help=x[1])
            for x in (local_actions_metadata + remote_actions_metadata)]


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
    Arbitrary arguments can be passed to the action in place of ACTION_ARGS.\n
    \n
    ACTION_IDENTIFIER must be in the format ACTION_NAME[@ACTION_VERSION], where:\n
     - ACTION_NAME can only contain alphanumeric characters and underscores.\n
     - ACTION_VERSION can be either:\n
         - 'local' (for local actions)\n
         - any valid Git tag or branch name (for remote actions)\n
    \n
    Notes:\n
     - If action version is set to 'local', utility will look for the action file in '.ci/actions' folder inside your CI project's root directory.\n
     - Any arguments passed after the action name/tag will be passed to the executed action script.\n
    """
    from python_ci_toolkit.actions import run_ci_action
    from python_ci_toolkit.actions.actions import ACTION_VERSION_SEPARATOR

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
