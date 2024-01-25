"""
Functions for retrieving actions from local CI project.
"""

import glob
import logging
import os
from pathlib import Path

from ....environment import ci_paths

logger = logging.getLogger(__name__)

_LOCAL_ACTIONS_DIRECTORY_RELATIVE = ci_paths.ci_files_directory.relative_to(ci_paths.project_root) / "actions"
"""
Relative path to the directory where local actions are stored in a CI project.
"""


def get_actions_directory_in_project(project_root_path: Path) -> Path:
    """
    Returns an absolute path to the default directory where local actions are stored in the given CI project.

    Args:
        project_root_path: Absolute path to the root directory of the CI project.
    """
    return project_root_path / _LOCAL_ACTIONS_DIRECTORY_RELATIVE


LOCAL_ACTIONS_DIRECTORY = get_actions_directory_in_project(ci_paths.project_root)
"""
Absolute path to the directory where local actions are stored in the current CI project.
"""


def get_simple_action_path_in_directory(directory: Path, action_name: str) -> Path:
    """
    Returns the expected path to the given simple action script in the given directory.

    Notes:
        Simple actions are individual Python files.
    """
    return directory / f"{action_name}.py"


def get_complex_action_path_in_directory(directory: Path, action_name: str) -> Path:
    """
    Returns the expected path to the given complex action script in the given directory.

    Notes:
        Complex actions are Python scripts nested in the directories with the matching name.
    """
    return directory / action_name / f"{action_name}.py"


def list_actions_in_directory(directory: Path,
                              include_simple_actions: bool = True,
                              include_complex_actions: bool = True) -> list[Path]:
    """
    Lists all action scripts available in the given directory.

    Notes:
        - 'simple' actions are individual Python files
        - 'complex' actions are Python scripts nested in the directories with the matching name

    Args:
        directory: Directory to search for actions in.
        include_simple_actions: Whether to include 'simple' action scripts in the search (enabled by default).
        include_complex_actions: Whether to include 'complex' action scripts in the search (enabled by default).

    Returns:
        List of absolute paths of the located action scripts.
    """
    if not directory.exists():
        logger.debug(f"Directory '{directory}' does not exist, so no actions can be found there.")
        return []

    assert directory.exists(), f"Directory '{directory}' does not exist."
    assert include_simple_actions or include_complex_actions, "At least one of 'include_simple_actions' or 'include_complex_actions' must be set to True."

    found_actions: list[Path] = []

    if include_simple_actions:
        # find all 'simple' action scripts; these are scripts that are individual Python files
        simple_actions = [Path(p) for p in glob.glob(str(directory / "*.py"))]
        found_actions.extend(simple_actions)

    if include_complex_actions:
        # find all 'complex' action scripts; these are Python scripts nested in the directories with the matching name
        complex_actions: list[Path] = []
        child_directories = [Path(d.path) for d in os.scandir(directory) if (Path(d.path) != directory) and (Path(d.path).is_dir())]
        for child in child_directories:
            nested_action_script_path = child / f"{child.name}.py"
            if nested_action_script_path.exists():
                complex_actions.append(nested_action_script_path)
        found_actions.extend(complex_actions)

    # return requested actions
    return found_actions


def retrieve_ci_action_script_local(action_name: str) -> Path:
    """
    Tries to locate the given Python CI action in the current CI project's '.ci/actions' directory.

    Args:
        action_name: Name of the action to locate.

    Returns:
        Full path to the given action's Python file.
    """
    simple_action_file_path = LOCAL_ACTIONS_DIRECTORY / f"{action_name}.py"
    complex_action_file_path = LOCAL_ACTIONS_DIRECTORY / action_name / f"{action_name}.py"

    if simple_action_file_path.exists() and complex_action_file_path.exists():
        raise ValueError(
            f"Found both simple and complex action scripts for local action '{action_name}':\n"
            f" - Simple: '{simple_action_file_path}'\n"
            f" - Complex: '{complex_action_file_path}'\n"
            f"Please remove one of them to avoid ambiguity before trying to retrieve the action again."
        )

    action_file_path = simple_action_file_path if simple_action_file_path.exists() else complex_action_file_path
    if not action_file_path.exists():
        raise FileNotFoundError(
            f"Action '{action_name}' does not exist locally.\n"
            f"When you run actions in local mode, make sure that the corresponding action file exists in '.ci/actions' directory in your CI project's root."
        )

    return action_file_path
