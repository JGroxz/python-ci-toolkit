"""
Utility functions for interacting with remote Git repositories.
"""
import io
import logging
import os
from pathlib import Path

from git import Repo

from python_ci_toolkit.environment import ci_project_root, ci_environment_type, CiEnvironmentType, assert_environment_variable_set

TEMP_PRIVATE_SSH_KEY_FILE_PATH = ci_project_root.joinpath(".ci/temp/ssh_key")

ci_repo = Repo(ci_project_root)
"""GitPython reference to the local Git repository of the current CI project."""


def get_default_ssh_private_key_file_path() -> Path:
    """
    Returns the path to the default location of the private SSH key file on the current system.
    """
    if ci_environment_type == CiEnvironmentType.BitbucketPipelines:
        bitbucket_ssh_key_path = assert_environment_variable_set(
            "BITBUCKET_SSH_KEY_FILE"
            "This variable is only available for pipelines running on Bitbucket Cloud and the Linux Docker Pipelines runner. "
            "See https://support.atlassian.com/bitbucket-cloud/docs/variables-and-secrets/.")
        return Path(bitbucket_ssh_key_path)

    # Both in UNIX and in Windows, default SSH private key location is in '~/.ssh/id_rsa'
    return Path(Path.home(), ".ssh/id_rsa")


def get_default_ssh_private_key() -> str | None:
    """
    Returns private SSH key from the default system location, or None if such key is not present.
    """
    default_ssh_key_file_path = get_default_ssh_private_key_file_path()

    if not default_ssh_key_file_path.exists():
        logging.error(f"Default private SSH key file does not exist at '{default_ssh_key_file_path}'.")
        return None

    with io.open(default_ssh_key_file_path) as file:
        default_ssh_key = file.read()

    return default_ssh_key


def prepare_git_ssh(ssh_private_key: str = None) -> None:
    """
    Configures Git to use the provided private SSH key when interacting with remote repositories
    by setting 'GIT_SSH_COMMAND' variable.

    Notes:
        This generates a temporary key file at '.ci/temp/ssh_key' at the current CI project root.
        To clean up this file after you are done, call 'reset_git_ssh()'.

    Args:
        ssh_private_key: Private SSH key to use with Git.
    """
    if (ssh_private_key is None) or (ssh_private_key == ""):
        # Try to retrieve the default SSH key
        logging.info("Private SSH key string is not provided, trying to locate SSH keys file in the default directory...")
        default_path = get_default_ssh_private_key_file_path()
        ssh_private_key = get_default_ssh_private_key()

        if ssh_private_key is None:
            # If the default key is missing, there is nothing we can do here
            raise RuntimeError(f"Private SSH key string is not provided, and the key could not be found in the default location ('{default_path}').")
        else:
            # If all is good, print path to the used private key file for info
            logging.info(f"Default private SSH key loaded successfully from '{default_path}'.")

    # Make sure that temporary folder for the key file exists
    os.makedirs(os.path.dirname(TEMP_PRIVATE_SSH_KEY_FILE_PATH), exist_ok=True)

    # Save Git SSH key to file
    with io.open(TEMP_PRIVATE_SSH_KEY_FILE_PATH, "w", newline="\n") as file:
        file.write(ssh_private_key)

    # Adjust SSH key permissions on UNIX-like systems to prevent 'ssh' command from complaining
    if os.name == "posix":
        os.chmod(TEMP_PRIVATE_SSH_KEY_FILE_PATH, 0o600)

    # Tell Git to use the new SSH key file
    os.environ["GIT_SSH_COMMAND"] = f'ssh -i "{TEMP_PRIVATE_SSH_KEY_FILE_PATH}" -o IdentitiesOnly=yes'


def reset_git_ssh() -> None:
    """
    Removes temporary private SSH key file created by 'prepare_git_ssh()' command and resets 'GIT_SSH_COMMAND' environment variable.
    """
    # Reset environment variable
    os.environ["GIT_SSH_COMMAND"] = ""

    # Clean up the file; this will throw an error if the file cannot be deleted due to permissions etc.
    if TEMP_PRIVATE_SSH_KEY_FILE_PATH.exists():
        os.remove(TEMP_PRIVATE_SSH_KEY_FILE_PATH)
