"""
Functions for retrieving actions from local CI project.
"""
import glob
import os
from pathlib import Path

from .._constants import LOCAL_ACTIONS_DIRECTORY


def list_actions_in_directory(directory: Path) -> list[Path]:
    """
    Lists all action scripts available in the given directory.

    Args:
        directory: Directory to search for actions in.

    Returns:
        List of absolute paths of the located action scripts.
    """
    # find all 'simple' action scripts; these are scripts that are individual Python files
    simple_actions = [Path(p) for p in glob.glob(str(directory / "*.py"))]

    # find all 'complex' action scripts; these are Python scripts nested in the directories with the matching name
    complex_actions: list[Path] = []
    child_directories = [Path(x[0]) for x in os.walk(directory) if Path(x[0]) != directory]
    for child in child_directories:
        nested_action_script_path = child / f"{child.name}.py"
        if nested_action_script_path.exists():
            complex_actions.append(nested_action_script_path)

    return simple_actions + complex_actions


def retrieve_ci_action_script_local(action_name: str) -> Path:
    """
    Tries to locate the given Python CI action in the current CI project's '.ci/actions' directory.

    Args:
        action_name: Name of the action to locate.

    Returns:
        Full path to the given action's Python file.
    """
    action_file_path = LOCAL_ACTIONS_DIRECTORY / f"{action_name}.py"

    if not action_file_path.exists():
        raise FileNotFoundError(
            f"Cannot run action '{action_name}' from local file '{action_file_path}': file does not exist.\n"
            f"When you run actions in local mode, make sure that the corresponding action file exists in '.ci/actions' folder in your CI project's root."
        )

    return action_file_path
