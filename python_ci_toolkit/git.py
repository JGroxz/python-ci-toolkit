"""
Utility functions for interacting with remote Git repositories.
"""
import io
import logging
import os

from python_ci_toolkit.environment import ci_project_root

PRIVATE_SSH_KEY_FILE_PATH = ci_project_root.joinpath(".ci/temp/ssh_key")


def prepare_git_ssh_from_file(ssh_private_key_file_path: str) -> None:
    raise NotImplementedError


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
    if ssh_private_key:
        # save Git SSH key to file
        with io.open(PRIVATE_SSH_KEY_FILE_PATH, "w", newline="\n") as file:
            file.write(ssh_private_key)

        # adjust SSH key permissions on UNIX-like systems to prevent 'ssh' command from complaining
        if os.name == "posix":
            os.chmod(PRIVATE_SSH_KEY_FILE_PATH, 0o600)

        # tell Git to use the new SSH key file
        os.environ["GIT_SSH_COMMAND"] = f"ssh -i \"{PRIVATE_SSH_KEY_FILE_PATH}\" -o IdentitiesOnly=yes"
    else:
        logging.info("Private SSH key string is not provided, trying to locate SSH keys file in the default directory...")
        # TODO: configure Git to use a local SSH file

        # os.environ["GIT_SSH_COMMAND"] =
        pass


def reset_git_ssh() -> None:
    """
    Removes temporary private SSH key file created by 'prepare_git_ssh()' command and resets 'GIT_SSH_COMMAND' environment variable.
    """
    # Reset environment variable
    os.environ["GIT_SSH_COMMAND"] = ""

    # Clean up the file; this will throw an error if the file cannot be deleted due to permissions etc.
    if PRIVATE_SSH_KEY_FILE_PATH.exists():
        os.remove(PRIVATE_SSH_KEY_FILE_PATH)
