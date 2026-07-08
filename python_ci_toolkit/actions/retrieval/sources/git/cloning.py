"""
Functions for retrieving action repositories from Git.
"""

import logging
import shutil
from contextlib import nullcontext
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from .caching import create_action_cache_timestamp
from ....constants import ACTION_VERSION_DEFAULT_REMOTE_STRING, ACTION_VERSION_LOCAL_STRING
from ...exceptions import (
    ActionRepositoryLayoutError,
    AmbiguousGitActionRefError,
    MissingGitActionRefError,
    RemoteActionRepoNotConfiguredError,
    RemoteActionScriptNotFoundError,
)
from ....retrieval.sources.local import list_actions_in_directory, _LOCAL_ACTIONS_DIRECTORY_RELATIVE, get_actions_directory_in_project
from ....utils import log_execution_time, hash_string
from ....utils.logging import get_action_display_name
from .....config import load_pyci_config
from .....environment.paths.internal import ci_temp_files_shared_directory
from .....environment.variables import is_environment_variable_set, retrieve_environment_variable
from .....git import git_ssh_credentials, get_default_ssh_private_key
from .....shell import run_shell_command

logger = logging.getLogger(__name__)

ACTION_REPO_URL_ENV_VAR = "PYTHON_CI_ACTIONS_GIT_REPO_URL"
ACTION_REPO_SSH_PRIVATE_KEY_ENV_VAR = "PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY"
DOWNLOADED_ACTION_REPOS_DIRECTORY = ci_temp_files_shared_directory / "downloaded_action_repos"


class GitActionRefType(Enum):
    BRANCH = "branch"
    TAG = "tag"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class GitActionRef:
    name: str
    type: GitActionRefType


def _git_repo_url_uses_ssh(git_repo_url: str) -> bool:
    """
    Checks whether the given Git repository URL needs SSH credentials.
    """
    parsed_url = urlparse(git_repo_url)
    if parsed_url.scheme in ("ssh", "git+ssh"):
        return True
    if parsed_url.scheme:
        return False

    first_colon_index = git_repo_url.find(":")
    first_at_index = git_repo_url.find("@")

    return (first_at_index > 0) and (first_colon_index > first_at_index)


def _git_authentication_context(git_repo_url: str, ssh_private_key: str | None = None):
    if _git_repo_url_uses_ssh(git_repo_url):
        return git_ssh_credentials(ssh_private_key)

    return nullcontext()


def _get_configured_action_repo_url() -> str | None:
    if is_environment_variable_set(ACTION_REPO_URL_ENV_VAR):
        return retrieve_environment_variable(ACTION_REPO_URL_ENV_VAR)

    return load_pyci_config().actions.remote_repository


def get_remote_action_repo() -> tuple[str, str | None] | None:
    """
    Returns:
        None if no remote action repository is configured.
        Otherwise, a tuple with:
            - URL of the remote Git repository that contains actions.
            - Secret SSH key to access the remote Git repository, if the URL uses SSH.
    """
    actions_git_repo_url = _get_configured_action_repo_url()
    if actions_git_repo_url is None:
        return None

    actions_ssh_private_key = None
    if _git_repo_url_uses_ssh(actions_git_repo_url):
        actions_ssh_private_key = retrieve_environment_variable(
            ACTION_REPO_SSH_PRIVATE_KEY_ENV_VAR,
            "SSH private key is required to pull actions from SSH Git repositories.",
            fallback=get_default_ssh_private_key
        )

    return actions_git_repo_url, actions_ssh_private_key


def require_remote_action_repo() -> tuple[str, str | None]:
    """
    Returns configured remote action repository or raises a clear policy error.
    """
    action_repo = get_remote_action_repo()
    if action_repo is not None:
        return action_repo

    raise RemoteActionRepoNotConfiguredError(
        "Remote action repository is not configured.\n"
        f"To run remote actions, set '{ACTION_REPO_URL_ENV_VAR}' or add "
        "'actions.remote_repository' to '.ci/pyci.toml'.\n"
        "To run a local action, use '<action_name>@local'."
    )


def get_clone_directory_from_action_repo_url(git_repo_url: str) -> Path:
    """
    Generates a deterministic local path to clone the given Git repository based on its URL.

    Args:
        git_repo_url: URL of the Git repository to generate path for.

    Returns:
        Local path generated based on the provided Git repo URL.
    """
    cloned_repo_path = DOWNLOADED_ACTION_REPOS_DIRECTORY / hash_string(git_repo_url)
    return cloned_repo_path


def _is_git_work_tree(path: Path) -> bool:
    if not path.is_dir():
        return False

    result = run_shell_command(
        "git rev-parse --is-inside-work-tree",
        cwd=path,
        silence_output=True,
        raise_on_error=False,
        use_wsl_on_windows=False,
    )
    return result.is_successful and result.output_stripped == "true"


def _get_git_origin_url(path: Path) -> str | None:
    result = run_shell_command(
        "git config --get remote.origin.url",
        cwd=path,
        silence_output=True,
        raise_on_error=False,
        use_wsl_on_windows=False,
    )
    return result.output_value


def _git_ref_exists(repo_path: Path, ref: str) -> bool:
    result = run_shell_command(
        f'git show-ref --verify --quiet "{ref}"',
        cwd=repo_path,
        silence_output=True,
        raise_on_error=False,
        use_wsl_on_windows=False,
    )
    return result.is_successful


def _remove_cached_action_repo(path: Path, reason: str) -> None:
    logger.debug(f"Removing cached action repo at '{path}': {reason}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _ensure_cached_action_repo_is_usable(git_repo_url: str, cloned_repo_path: Path) -> None:
    if not cloned_repo_path.exists():
        return

    if not _is_git_work_tree(cloned_repo_path):
        _remove_cached_action_repo(cloned_repo_path, "path is not a Git worktree")
        return

    origin_url = _get_git_origin_url(cloned_repo_path)
    if origin_url != git_repo_url:
        _remove_cached_action_repo(
            cloned_repo_path,
            f"remote origin is '{origin_url}', expected '{git_repo_url}'"
        )


def normalize_git_action_version(action_version: str | None) -> str:
    action_version = action_version or ACTION_VERSION_DEFAULT_REMOTE_STRING
    if action_version == ACTION_VERSION_LOCAL_STRING:
        raise ValueError(
            f"'{ACTION_VERSION_LOCAL_STRING}' is reserved for local action retrieval and cannot be resolved as a Git ref."
        )

    return action_version


def resolve_git_action_ref(repo_path: Path, action_version: str | None) -> GitActionRef:
    action_version = normalize_git_action_version(action_version)
    branch_exists = _git_ref_exists(repo_path, f"refs/remotes/origin/{action_version}")
    tag_exists = _git_ref_exists(repo_path, f"refs/tags/{action_version}")

    if branch_exists and tag_exists:
        return GitActionRef(name=action_version, type=GitActionRefType.AMBIGUOUS)
    if branch_exists:
        return GitActionRef(name=action_version, type=GitActionRefType.BRANCH)
    if tag_exists:
        return GitActionRef(name=action_version, type=GitActionRefType.TAG)

    return GitActionRef(name=action_version, type=GitActionRefType.MISSING)


def checkout_git_action_ref(repo_path: Path, git_repo_url: str, action_name: str, action_version: str | None) -> str:
    action_ref = resolve_git_action_ref(repo_path, action_version)
    action_display_name = get_action_display_name(action_name, action_ref.name)

    if action_ref.type == GitActionRefType.AMBIGUOUS:
        raise AmbiguousGitActionRefError(
            f"Both a branch and a tag named '{action_ref.name}' exist in remote repository '{git_repo_url}'.\n"
            f"The action '{action_display_name}' will not be pulled to avoid ambiguity.\n"
            f"Please remove the redundant branch or tag ('{action_ref.name}') from the repo before pulling this version again."
        )

    if action_ref.type == GitActionRefType.MISSING:
        raise MissingGitActionRefError(
            f"Cannot pull action '{action_display_name}' from Git:\n"
            f"  Repository '{git_repo_url}' has neither a branch nor a tag named '{action_ref.name}'.\n"
            f"  Please make sure that the corresponding branch or tag ('{action_ref.name}') exists before pulling this version again."
        )

    run_shell_command("git reset --hard", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    run_shell_command("git clean -fdx", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)

    if action_ref.type == GitActionRefType.BRANCH:
        logger.debug(f"'{action_ref.name}' is a branch in '{git_repo_url}'.")
        run_shell_command(
            f'git checkout -B "{action_ref.name}" "origin/{action_ref.name}"',
            cwd=repo_path,
            silence_output=True,
            use_wsl_on_windows=False,
        )
    elif action_ref.type == GitActionRefType.TAG:
        logger.debug(f"'{action_ref.name}' is a tag in '{git_repo_url}'.")
        run_shell_command(
            f'git checkout --detach "refs/tags/{action_ref.name}"',
            cwd=repo_path,
            silence_output=True,
            use_wsl_on_windows=False,
        )

    return action_ref.name


@log_execution_time
def retrieve_action_repo(git_repo_url: str, ssh_private_key: str | None = None) -> Path:
    """
    Retrieves the given Git repository into the standard actions download location.

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
    DOWNLOADED_ACTION_REPOS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # generate local repo path based on remote
    cloned_repo_path = get_clone_directory_from_action_repo_url(git_repo_url)
    _ensure_cached_action_repo_is_usable(git_repo_url, cloned_repo_path)

    with _git_authentication_context(git_repo_url, ssh_private_key):
        if not cloned_repo_path.exists():
            logger.debug(f"Cloning action repo from '{git_repo_url}' to '{cloned_repo_path}'.")

            # execute a fresh pull
            run_shell_command(f'git clone "{git_repo_url}" "{cloned_repo_path}"', silence_output=True, use_wsl_on_windows=False)
        else:
            logger.debug(f"Using local clone of action repo '{git_repo_url}' at '{cloned_repo_path}'.")

        # default settings for running shell commands inside the cloned repo
        def run_repo_command(c: str):
            return run_shell_command(c, cwd=cloned_repo_path, silence_output=True, use_wsl_on_windows=False)

        run_repo_command("git reset --hard")
        run_repo_command("git clean -fdx")
        run_repo_command("git fetch --prune --tags")
        run_repo_command("git checkout -B main origin/main")
        run_repo_command("git clean -fdx")

    # check if actions directory is present before returning it
    actions_directory = get_actions_directory_in_project(cloned_repo_path)
    if not actions_directory.exists():
        raise ActionRepositoryLayoutError(
            f"Repository '{git_repo_url}' does not have '{_LOCAL_ACTIONS_DIRECTORY_RELATIVE}' directory in it."
        )

    return actions_directory


@log_execution_time
def retrieve_ci_action_script_from_git(git_repo_url: str, action_name: str, action_version: str = None,
                                       ssh_private_key: str | None = None) -> Path:
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

    action_version = normalize_git_action_version(action_version)

    # retrieve repo
    cloned_actions_directory = retrieve_action_repo(git_repo_url, ssh_private_key)

    # prepare paths
    action_script_directory = cloned_actions_directory / f"{action_name}"
    action_script_path = action_script_directory / f"{action_name}.py"

    with _git_authentication_context(git_repo_url, ssh_private_key):
        checkout_git_action_ref(cloned_actions_directory, git_repo_url, action_name, action_version)

    # create cache entries for each complex action script in the cloned repo
    for action_path in list_actions_in_directory(cloned_actions_directory, include_simple_actions=False):
        create_action_cache_timestamp(
            git_repo_url=git_repo_url,
            action_name=action_path.stem,  # <- name of the action is the name of the script
            action_version=action_version
        )

    # check if the repo had the requested action script
    if not action_script_path.exists():
        raise RemoteActionScriptNotFoundError(
            f"Cloned repository '{git_repo_url}' does not include action '{action_name}' (expected script path is '{action_script_path}').\n"
            f"Please make sure that the remote repository has the required action script."
        )

    return action_script_path
