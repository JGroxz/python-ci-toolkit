"""
Provides functions to retrieve and run CI actions based on Python scripts.
"""
import glob
import hashlib
import logging
import os
import sys
import time
from contextlib import contextmanager
from logging import Logger
from pathlib import Path
from typing import List

from rich.progress import Progress

from .. import environment
from ..environment import assert_environment_variable_set, assert_multiline_environment_variable_set, \
    ci_files_directory, get_ci_environment_name, ci_project_root, _ci_temp_files_shared_directory
from ..git import git_ssh_credentials, get_default_ssh_private_key
from ..logging import get_logger, ci_output_console
from ..pip import ensure_requirements_installed
from ..python import import_module_from_file
from ..shell import run_shell_command

# Constants
ACTION_VERSION_SEPARATOR = "@"
DEFAULT_ACTION_REPO_URL = "git@bitbucket.org:pyci/python-ci-actions.git"
DOWNLOADED_ACTION_REPOS_DIRECTORY = _ci_temp_files_shared_directory / "downloaded_action_repos"
LOCAL_ACTIONS_DIRECTORY = ci_files_directory / "actions"

logger = get_logger(__name__)


def get_action_logger(name: str = None) -> Logger:
    """
    Returns a logger for use in CI actions.
    Automatically adds handlers to log into the console of the current CI environment.

    Args:
        name: Name of the CI action this logger is intended for.
    """
    if name is None:
        name = "default"

    # the naming ensures that the returned action logger inherits logging settings from the CI toolkit
    return get_logger(f"python_ci_toolkit.actions.external.{name}")


def list_actions_in_directory(directory: Path) -> List[Path]:
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
    complex_actions: List[Path] = []
    child_directories = [Path(x[0]) for x in os.walk(directory) if Path(x[0]) != directory]
    for child in child_directories:
        nested_action_script_path = child / f"{child.name}.py"
        if nested_action_script_path.exists():
            complex_actions.append(nested_action_script_path)

    return simple_actions + complex_actions


def _timeit(func):
    """Utility decorator to time the execution of functions."""

    def wrapped(*args, **kwargs):
        start = time.perf_counter()

        result = func(*args, **kwargs)

        duration = time.perf_counter() - start
        logger.debug(f"Function '{func.__name__}()' took {duration * 1000:.0f} ms to execute.")
        return result

    return wrapped


def get_clone_directory_from_action_repo_url(git_repo_url: str) -> Path:
    """
    Generates a deterministic local path to clone the given Git repository based on its URL.

    Args:
        git_repo_url: URL of the Git repository to generate path for.

    Returns:
        Local path generated based on the provided Git repo URL.
    """
    git_repo_hash = hashlib.md5(git_repo_url.encode()).hexdigest()
    cloned_repo_path = DOWNLOADED_ACTION_REPOS_DIRECTORY / git_repo_hash
    return cloned_repo_path


@_timeit
def retrieve_action_repo(git_repo_url: str, ssh_private_key: str = None) -> Path:
    """
    Retrieves the given Git repository into the standard actions cache location.

    Notes:
        This action will return the existing local repo if it was cloned before.
        The repo is guaranteed to have all updates fetched and the main branch checked out.

    Args:
        git_repo_url: URL of the Git repository to pull.
        ssh_private_key: Private SSH key to be used when accessing the specified Git repository (string value).

    Returns:
        Path to the directory in the cloned repository that contains actions.
    """

    # prepare downloads directory
    os.makedirs(DOWNLOADED_ACTION_REPOS_DIRECTORY, exist_ok=True)

    # generate local repo path based on remote
    cloned_repo_path = get_clone_directory_from_action_repo_url(git_repo_url)

    with git_ssh_credentials(ssh_private_key):
        if not cloned_repo_path.exists():
            logger.debug(f"Cloning action repo from '{git_repo_url}' to '{cloned_repo_path}'.")

            # execute a fresh pull
            run_shell_command(f'git clone "{git_repo_url}" "{cloned_repo_path}"',
                              silence_output=True, use_wsl_on_windows=False)
        else:
            logger.debug(f"Using cached action repo of '{git_repo_url}' from '{cloned_repo_path}'.")

        # fetch all available remote branches and tags
        run_shell_command("git fetch --tags",
                          cwd=cloned_repo_path, silence_output=True, use_wsl_on_windows=False)

        # switch existing clone to main branch
        run_shell_command("git checkout main",
                          cwd=cloned_repo_path, silence_output=True, use_wsl_on_windows=False)

    # check if actions directory is present before returning it
    actions_directory = cloned_repo_path / "actions"
    if not actions_directory.exists():
        logger.error(f"Repository '{git_repo_url}' does not have 'actions' directory in it.")
        sys.exit(1)

    return actions_directory


@_timeit
def retrieve_ci_action_script_from_git(git_repo_url: str, action_name: str, action_version: str = None,
                                       ssh_private_key: str = None) -> Path:
    """
    Retrieves Python CI script file with the given name from Git repository specified in 'PYTHON_CI_ACTIONS_GIT_REPO_URL' environment variable.
    If the repository is private, a private SSH key can be supplied in 'PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY' environment variable.

    Notes:
        Action scripts must be located in a Git repository which URL is specified in 'PYTHON_CI_ACTIONS_GIT_REPO_URL' environment variable.
        Repository must contain a folder named 'actions', where each action script must be located inside an individual folder of the same name, e.g.:
        'build_dockers.py' must be located in 'GIT_REPO_ROOT/actions/build_dockers/build_dockers.py'.

        Downloaded scripts will be placed in the folder named '.ci' at the root of the current CI project.

    Args:
        git_repo_url: URL of the Git repository to pull the action from.
        action_name: Name of the action to download.
        action_version: Version of the action to pull. Can be either a Git branch or a Git tag in the source repository.
        ssh_private_key: Private SSH key to be used when accessing the specified Git repository (string value).

    Returns:
        Local path to the downloaded action file.
    """

    # retrieve repo
    cloned_actions_directory = retrieve_action_repo(git_repo_url, ssh_private_key)

    # prepare paths
    action_display_name = f"{action_name}{ACTION_VERSION_SEPARATOR}{action_version}"
    action_script_directory = cloned_actions_directory / f"{action_name}"
    action_script_path = action_script_directory / f"{action_name}.py"

    # settings for running CLI commands
    run_shell_command_kwargs = {
        "cwd": cloned_actions_directory,
        "silence_output": (logger.getEffectiveLevel() > logging.DEBUG),
        "use_wsl_on_windows": False
    }

    with git_ssh_credentials(ssh_private_key):
        # clone the repo
        if action_version is None:
            # if no version specified, use the main branch (it's checked out by default)
            run_shell_command("git merge origin/main", **run_shell_command_kwargs)
        else:
            # find branches or tags matching the given version
            result = run_shell_command(f'git show-ref', **run_shell_command_kwargs)
            output = result.output
            branch_exists = (f"refs/heads/{action_version}" in output) or (f"refs/remotes/origin/{action_version}" in output)
            tag_exists = (f"refs/tags/{action_version}" in output)

            if branch_exists:
                logger.debug(f"'{action_version}' is a branch in '{git_repo_url}'.")
            if tag_exists:
                logger.debug(f"'{action_version}' is a tag in '{git_repo_url}'.")

            # if both a branch and a tag exist with the same name, do not pull to avoid ambiguity
            if tag_exists and branch_exists:
                logger.error(f"Both a branch and a tag named '{action_version}' exist in remote repository '{git_repo_url}'.\n"
                             f"The action '{action_display_name}' wil not be pulled to avoid ambiguity.\n"
                             f"Please remove the redundant branch or tag ('{action_version}') from the repo before pulling this version again.")
                sys.exit(2)

            # if nothing matches the version, there is nothing we can do
            if (not tag_exists) and (not branch_exists):
                logger.error(f"Cannot pull action '{action_display_name}' from Git:\n"
                             f"  Repository '{git_repo_url}' has neither a branch nor a tag named '{action_version}'.\n"
                             f"  Please make sure that the corresponding branch or tag ('{action_version}') exists before pulling this version again.")
                sys.exit(3)

            # checkout required branch/tag
            run_shell_command(f'git checkout "{action_version}"', **run_shell_command_kwargs)

            # if on a branch, pull updates
            result = run_shell_command(f'git status', **run_shell_command_kwargs)
            is_on_a_branch = ("On branch" in result.output)
            if is_on_a_branch:
                run_shell_command(f'git merge "origin/{action_version}"', **run_shell_command_kwargs)

    # check if the repo had the requested action script
    if not action_script_path.exists():
        logger.error(f"Cloned repository '{git_repo_url}' does not include action '{action_name}' (expected script path is '{action_script_path}').\n"
                     f"Please make sure that the remote repository has the required action script.")
        sys.exit(4)

    return action_script_path


def retrieve_ci_action_script_local(action_name: str) -> Path:
    """
    Tries to locate the given Python CI action in the current CI project's '.ci/actions' directory.

    Args:
        action_name: Name of the action to locate.

    Returns:
        Full path to the given action's Python file.
    """
    action_file_path = Path(LOCAL_ACTIONS_DIRECTORY, f"{action_name}.py")

    if not action_file_path.exists():
        raise FileNotFoundError(
            f"Cannot run action '{action_name}' from local file '{action_file_path}': file does not exist.\n"
            f"When you run actions in local mode, make sure that the corresponding action file exists in '.ci/actions' folder in your CI project's root.")

    return action_file_path


def _print_action_header(action_name: str, action_version: str, action_source: str) -> None:
    ci_environment_name = get_ci_environment_name()

    # noinspection PyBroadException
    try:
        import pkg_resources
        version = pkg_resources.get_distribution('python-ci-toolkit').version
    except Exception:
        from ..versions import read_project_version
        version = read_project_version(ci_project_root)

    action_display_name = f"{action_name}{ACTION_VERSION_SEPARATOR}{action_version}"

    logger.info(f"[green]>_[/][rgb(146,202,85)] Running CI action '{action_display_name}'[/]...\n"
                f"     CI toolkit version: [blue]{version}[/]\n"
                f"     CI environment: [blue]{ci_environment_name}[/]\n"
                f"     Action version: [blue]{action_version}[/]\n"
                f"     Action source: {action_source}", extra={"markup": True, "highlighter": None})


@contextmanager
def loading_animation(description: str) -> None:
    """
    Context manager that displays a loading animation in the console.
    To be displayed to the user while doing prolonged tasks like cloning action Git repo.

    Notes:
        Animation is disabled in cloud CI environments, as their consoles normally don't support this level of rendering.

    Args:
        description: Info message describing what's happening. Will be displayed next to the animation.
    """
    if environment.ci_environment_type == environment.CiEnvironmentType.Unknown:
        # in a local environment, display animated progress bar for visual feedback
        with Progress(console=ci_output_console, transient=True, refresh_per_second=60) as progress:
            progress.add_task(f"[blue]{description}...", total=None)

            # TODO: add thread which will update description of the task with a timer if it takes longer than 10 s

            yield  # <- within this context, clone repos, install requirements etc.
    else:
        # cloud environments normally don't support erasing terminal output,
        # so progres bars get messed up; in this case we don't display them
        yield


def run_ci_action(action_name: str, action_version: str = None, argv: List[str] = None) -> None:
    """
    Executes CI action by the given action name.
    """
    """
    Executes CI action by the given action name.
    """
    # craft action name for logs
    action_display_name = (action_name
                           if (action_version is None)
                           else f"{action_name}{ACTION_VERSION_SEPARATOR}{action_version}")

    # locate action script
    logger.debug(f"Locating action '{action_display_name}'...")
    if action_version == "local":
        # local folder
        action_script_path = retrieve_ci_action_script_local(action_name)
        action_source = f"'{action_script_path}'"
        logger.debug(f"Retrieved local action '{action_name}'. Running...")
    else:
        with loading_animation(f"Retrieving action from Git"):
            start_time = time.perf_counter()

            # Git repo
            actions_git_repo_url = assert_environment_variable_set(
                "PYTHON_CI_ACTIONS_GIT_REPO_URL",
                f"URL address of the Git repository is required to pull the code for action '{action_display_name}'.",
                fallback_value_getter=lambda: DEFAULT_ACTION_REPO_URL)
            actions_ssh_private_key = assert_multiline_environment_variable_set(
                "PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY",
                "SSH private key is required to pull actions from the private remote Git repositories.",
                fallback_value_getter=get_default_ssh_private_key)

            action_script_path = retrieve_ci_action_script_from_git(
                git_repo_url=actions_git_repo_url,
                action_name=action_name,
                action_version=action_version,
                ssh_private_key=actions_ssh_private_key
            )

            branch_or_tag_name = "main" if (action_version is None) else action_version
            action_source = f"'{branch_or_tag_name}' at '{actions_git_repo_url}'"

            duration = time.perf_counter() - start_time
        logger.info(f"Retrieved action '{action_display_name}' from Git in {duration:.3f} seconds.")

    # install action's requirements if present
    action_requirements_path = action_script_path.parent / "requirements.txt"
    if action_requirements_path.exists():
        logger.debug(f"Action '{action_name}' has requirements file supplied with it. Installing requirements...")

        with loading_animation("Installing action's dependencies"):
            ensure_requirements_installed(action_requirements_path, silence_pip_stdout=False)

        logger.debug("Requirements installation complete.")

    # prepare action's CLI arguments
    sys.argv = sys.argv[:1]
    if argv is not None:
        sys.argv.extend(argv)

    # run CI action using its cli() method with the given arguments
    logger.debug(f"Importing Python module of the action '{action_name}'...")
    with loading_animation("Importing action's Python module..."):
        try:
            action_module = import_module_from_file(f"{action_name}", action_script_path)
        except Exception:
            logger.error(
                f"Error when importing Python module from action script '{action_script_path}' (action '{action_display_name}' from {action_source}).")
            raise
    logger.debug("Import completed.")

    _print_action_header(action_name, action_version, action_source)

    with loading_animation(f"[rgb(146,202,85)]Running CI action '{action_display_name}'"):
        action_module.cli()
