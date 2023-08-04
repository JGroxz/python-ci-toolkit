"""
Command for finding available CI actions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import rich
from rich import print, box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_FIRST_COMMENT_REGEX = re.compile(r'"""(?:\n)(.*?)"""', re.MULTILINE | re.UNICODE | re.DOTALL)


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
            description=get_action_description_from_file(filepath),
        )


def get_action_description_from_file(file_path: Path) -> str:
    """
    Tries to retrieve action description from the action script file.
    The first line of the top-level docstring is taken as action description.
    """
    assert file_path.exists()

    with file_path.open("r") as file:
        file_content = file.read()

    matches: list[str] = _FIRST_COMMENT_REGEX.findall(file_content)
    if len(matches) <= 0:
        return "<action has no description>"

    description = matches[0].splitlines()[0]

    return description


def list_available_actions(cache_timeout: float = -1) -> list[ActionMetadata]:
    """
    Returns a list of all available CI actions in the current project (both remote and local).

    Notes:
        Honors _AUTOCOMPLETION_REMOTE_CLONE_DELAY_TIME_WINDOW and caches the results for that time to avoid cloning the remote action repo on every consecutive call.

    Args:
        cache_timeout: Time in seconds after which the cache should be invalidated. If set to -1, the cache is never invalidated.
    """
    # determine how much time passed since the last call to this autocompletion function;
    # this is done to avoid cloning the remote action repo on every consecutive call within a specific time window
    from ...environment.paths.internal import ci_temp_files_shared_directory
    from ...actions.utils.file_timestamps import time_since_file_timestamp, reset_file_timestamp
    timestamp_file_path = ci_temp_files_shared_directory / "cli_actions_last_autocomplete.timestamp"
    time_since_last_call = time_since_file_timestamp(timestamp_file_path)

    # search for local actions
    from ...actions.retrieval.sources.local import list_actions_in_directory, LOCAL_ACTIONS_DIRECTORY
    local_action_script_paths = list_actions_in_directory(LOCAL_ACTIONS_DIRECTORY)
    local_actions_metadata = [ActionMetadata.from_action_file(p) for p in local_action_script_paths]
    local_actions_metadata = [ActionMetadata(f"{m.name}@local", f"[local] {m.description}") for m in local_actions_metadata]
    local_actions_metadata.sort()

    # remote actions
    from ...actions.retrieval.sources.git.cloning import get_remote_action_repo, retrieve_action_repo, get_clone_directory_from_action_repo_url
    from ...actions.retrieval.sources.local import get_actions_directory_in_project
    action_repo_url, action_repo_ssh_private_key = get_remote_action_repo()
    cloned_repo_directory = get_clone_directory_from_action_repo_url(action_repo_url)
    cloned_actions_directory = get_actions_directory_in_project(cloned_repo_directory)
    if time_since_last_call >= cache_timeout:
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


def find_actions_by_name_or_description(search_query: str) -> list[ActionMetadata]:
    """
    Searches for actions by their name or description.

    Args:
        search_query: Search query to filter the actions by.

    Returns:
        List of available actions metadata that match the search query.
    """
    available_actions_metadata = list_available_actions()

    # return all actions if no search query was provided
    if not search_query:
        return available_actions_metadata

    # filter out the actions based on the provided search query
    filter_regex = re.compile(rf"{search_query}", re.IGNORECASE)
    filtered_actions_metadata = [a for a in available_actions_metadata if filter_regex.search(a.name) or filter_regex.search(a.description)]

    return filtered_actions_metadata


def print_search_results(search_query: str, actions_metadata: list[ActionMetadata]) -> None:
    """
    Prints the given list of actions metadata to the console.
    """
    something_found = len(actions_metadata) > 0

    # panel title
    title = f"Search results for [yellow]'{search_query}'[/]"
    if something_found:
        title += f": {len(actions_metadata)} actions"

    # panel content
    if something_found:
        # sort results (alphabetically by name, local actions first)
        actions_metadata = sorted(actions_metadata)
        actions_metadata = sorted(actions_metadata, key=lambda a: a.name.endswith("@local"), reverse=True)

        # prepare display grid
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(header="Name", style="green")
        grid.add_column(header="Description")

        # prepare a highlighter
        def text_with_highlighted_search_query(text: str) -> Text:
            text = Text(text)
            text.highlight_words([search_query], "yellow underline", case_sensitive=False)
            return text

        for metadata in actions_metadata:
            grid.add_row(
                text_with_highlighted_search_query(metadata.name),
                text_with_highlighted_search_query(metadata.description),
            )
        panel_content = grid
    else:
        panel_content = Text.from_markup(f"[red]No actions found containing [green]'{search_query}'")
        panel_content.align("center", (80 - 4))

    # print panel
    panel = Panel(
        panel_content,
        box=box.ROUNDED, border_style="blue",
        title=title, title_align="left",
        expand=False, highlight=False
    )

    print(panel)


def find_action_command(search_query: str) -> None:
    """
    Searches for actions by their name or description and prints the results to the console.

    Args:
        search_query: Search query to filter the actions by.
    """
    from python_ci_toolkit.actions.utils.logging import loading_animation
    with loading_animation(f"Looking for actions containing [green]'{search_query}'[/]"):
        matches = find_actions_by_name_or_description(search_query)

    print_search_results(search_query, matches)
