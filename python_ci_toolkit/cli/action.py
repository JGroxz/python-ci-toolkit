from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

import rich_click as click
from click import Context, Argument
from click.shell_completion import CompletionItem

from python_ci_toolkit.actions.retrieval.sources.local import get_actions_directory_in_project

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
_ACTION_AUTOCOMPLETE_REMOTE_CLONE_DELAY_TIME_WINDOW = 30


def _validate_action_identifier(ctx: Context, param: Argument, value: str) -> str:
    from ..actions.constants import ACTION_VERSION_SEPARATOR

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


@dataclass(eq=True, frozen=True)
class ActionMetadata:
    name: str
    """Name of the action."""
    description: str
    """Description of the action."""

    def __lt__(self, other: ActionMetadata) -> bool:
        return self.name < other.name

    @staticmethod
    def from_action_file(filepath: Path) -> ActionMetadata:
        """
        Creates an ActionMetadata object from the given action file.
        """
        assert filepath.exists(), f"Action file '{filepath}' does not exist."
        assert filepath.is_file(), f"Action file '{filepath}' is not a file."

        return ActionMetadata(
            name=filepath.stem,
            description=_get_action_description_from_file(filepath),
        )


def _list_available_actions() -> list[ActionMetadata]:
    """
    Returns a list of all available CI actions in the current project (both remote and local).
    """
    # determine how much time passed since the last call to this autocompletion function;
    # this is done to avoid cloning the remote action repo on every consecutive call within a specific time window
    from ..environment.paths.internal import ci_temp_files_shared_directory
    from ..actions.utils.file_timestamps import time_since_file_timestamp, reset_file_timestamp
    timestamp_file_path = ci_temp_files_shared_directory / "cli_actions_last_autocomplete.timestamp"
    time_since_last_call = time_since_file_timestamp(timestamp_file_path)

    # search for local actions
    from ..actions.retrieval.sources.local import list_actions_in_directory, LOCAL_ACTIONS_DIRECTORY
    local_action_script_paths = list_actions_in_directory(LOCAL_ACTIONS_DIRECTORY)
    local_actions_metadata = [ActionMetadata.from_action_file(p) for p in local_action_script_paths]
    local_actions_metadata = [ActionMetadata(f"{m.name}@local", f"[local] {m.description}") for m in local_actions_metadata]
    local_actions_metadata.sort()

    # remote actions
    from ..actions.retrieval.sources.git.cloning import get_remote_action_repo, retrieve_action_repo, get_clone_directory_from_action_repo_url
    action_repo_url, action_repo_ssh_private_key = get_remote_action_repo()
    cloned_repo_directory = get_clone_directory_from_action_repo_url(action_repo_url)
    cloned_actions_directory = get_actions_directory_in_project(cloned_repo_directory)
    if time_since_last_call >= _ACTION_AUTOCOMPLETE_REMOTE_CLONE_DELAY_TIME_WINDOW:
        cloned_actions_directory = retrieve_action_repo(
            git_repo_url=action_repo_url,
            ssh_private_key=action_repo_ssh_private_key
        )
    remote_action_script_paths = list_actions_in_directory(cloned_actions_directory)
    remote_actions_metadata = [ActionMetadata.from_action_file(p) for p in remote_action_script_paths]
    remote_actions_metadata = [ActionMetadata(f"{m.name}", f"[remote] {m.description}") for m in remote_actions_metadata]
    remote_actions_metadata.sort()

    # recreate the timestamp file
    reset_file_timestamp(timestamp_file_path)

    # return all actions
    return local_actions_metadata + remote_actions_metadata


def _complete_action_identifier(ctx: Context, param: Argument, incomplete: str):
    # disable logging (to avoid messages in the console during autocompletion)
    logging.root.disabled = True

    available_actions_metadata = _list_available_actions()

    # filter out the actions based on the incomplete string
    filtered_actions_metadata = [a for a in available_actions_metadata
                                 if a.name.startswith(incomplete)]  # <- TODO: replace this with regex lookup to match inner parts of action names, too

    # enable logging again
    logging.root.disabled = False

    return [CompletionItem(a.name, help=a.description)
            for a in filtered_actions_metadata]


@click.command(context_settings=dict(
    ignore_unknown_options=True,
), no_args_is_help=True)
@click.option("--debug",
              is_flag=True,
              help="Enable debug logging.")
@click.argument("action_identifier",
                required=1,
                type=str,
                callback=_validate_action_identifier,
                shell_complete=_complete_action_identifier)
@click.argument('action_args', nargs=-1, type=click.UNPROCESSED)
def action(action_identifier: str, action_args: List[str], debug: bool = False) -> None:
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

    # initialize logging
    from ..logging import configure_ci_logging
    is_debug_enabled = (debug or os.environ.get("DEBUG", None))
    configure_ci_logging("DEBUG" if is_debug_enabled else "INFO")

    from ..actions import run_ci_action
    from ..actions.constants import ACTION_VERSION_SEPARATOR

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
