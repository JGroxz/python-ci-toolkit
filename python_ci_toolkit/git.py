"""
Utility functions for interacting with remote Git repositories.
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path

from git import Repo, GitCommandError

from .environment import ci_platform, platforms, retrieve_environment_variable, ci_temp_files_directory


def get_default_ssh_private_key_file_path() -> Path:
    """
    Returns the path to the default location of the private SSH key file on the current system.
    """
    if ci_platform == platforms.BitbucketPipelines:
        bitbucket_ssh_key_path = retrieve_environment_variable(
            "BITBUCKET_SSH_KEY_FILE",
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


@contextmanager
def git_ssh_credentials(ssh_private_key: str = None) -> None:
    """
    Context manager that configures Git to use the provided private SSH key when interacting with remote repositories
    by setting 'GIT_SSH_COMMAND' variable.

    Notes:
        This generates a temporary key file at '.ci/temp/ssh_key' at the current CI project root.
        This file is automatically deleted when this context manager exits.

    Args:
        ssh_private_key: Private SSH key to use with Git.
    """
    # Save current GIT_SSH_COMMAND
    original_git_ssh_command = os.environ.get("GIT_SSH_COMMAND", default="")

    # In case SSH key is not provided, try retrieving a default one
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
    temp_private_ssh_key_file_path = ci_temp_files_directory.joinpath("ssh", f"{uuid.uuid4()}")
    os.makedirs(os.path.dirname(temp_private_ssh_key_file_path), exist_ok=True)

    try:
        # Save Git SSH key to file
        with io.open(temp_private_ssh_key_file_path, "w", newline="\n") as file:
            file.write(ssh_private_key)

        # Adjust SSH key permissions on UNIX-like systems to prevent 'ssh' command from complaining
        if os.name == "posix":
            os.chmod(temp_private_ssh_key_file_path, 0o600)

        # Tell Git to use the new SSH key file
        os.environ["GIT_SSH_COMMAND"] = f'ssh -i "{temp_private_ssh_key_file_path}" ' \
                                        f'-o IdentitiesOnly=yes ' \
                                        f'-o StrictHostKeyChecking=accept-new'

        yield  # <- within this context, clone repos, push changes etc.
    except Exception:
        raise
    finally:
        # Restore original GIT_SSH_COMMAND
        os.environ["GIT_SSH_COMMAND"] = original_git_ssh_command

        # Clean up the temporary key file; this will throw an error if the file cannot be deleted due to permissions etc.
        if temp_private_ssh_key_file_path.exists():
            os.remove(temp_private_ssh_key_file_path)


def ensure_remote_is_ssh(repo: Repo) -> None:
    """
    Makes sure that the remote origin repository's address is in SSH format.

    Notes:
        If the remote's URL is in HTTP(S) format, this function will automatically convert it to SSH.

    Args:
        repo: Repository to check the origin in.
    """
    logging.info("Checking remote address...")

    remote_url = repo.remote().url

    if remote_url.startswith("git"):
        # It's an SSH address, all good
        logging.info(f"Remote '{remote_url}' is already an SSH address.")
        return

    logging.warning(f"Remote '{remote_url}' is an HTTP(S) address.")

    # If there are files tracked by Git LFS in this repository, it is unsafe to proceed (LFS requires HTTP(S) to work correctly)
    try:
        lfs_output = repo.git.lfs(["ls-files", "--all"])
        number_of_tracked_lfs_files = len(lfs_output.split("\n")) - 1
        if number_of_tracked_lfs_files > 0:
            logging.error(f"Current repository has {number_of_tracked_lfs_files} file(s) tracked by Git LFS, which only works with HTTP(S) remotes.\n"
                          f"  Remote will not be overwritten.")
            raise SystemExit(1)
    except GitCommandError:
        # If this command failed, Git LFS is not installed; in this case, we don't care
        pass

    # Convert origin remote URL into SSH format
    logging.info("Converting remote URL into SSH format...")

    host = remote_url.split("://")[1].split("@")[-1].split("/")[0]
    user_name = remote_url.split("://")[1].split("/")[1]
    repository_name = remote_url.split("://")[1].split("/")[2]

    ssh_remote_url = f"git@{host}:{user_name}/{repository_name}"

    # Update remote URL
    repo.remote().set_url(ssh_remote_url)
    logging.info(f"Updated remote URL: '{ssh_remote_url}'.")


def ensure_remote_is_https(repo: Repo) -> None:
    """
    Makes sure that the remote origin repository's address is in HTTPS format.

    Notes:
        If the remote's URL is in SSH format, this function will automatically convert it to HTTPS.

    Args:
        repo: Repository to check the origin in.
    """
    logging.info("Checking remote address...")

    remote_url = repo.remote().url

    if remote_url.startswith("http"):
        if not remote_url.startswith("https"):
            # It's an HTTP address, just make sure its HTTPS
            logging.info("Remote URL uses HTTP. Switching to HTTPS...")
            https_remote_url = remote_url.replace("http", "https", 1)
            repo.remote().set_url(https_remote_url)
            logging.info(f"Updated remote URL: '{https_remote_url}'.")
        else:
            # All good
            logging.info(f"Remote '{remote_url}' is an HTTPS address.")
        return

    logging.warning(f"Remote '{remote_url}' is an SSH address.")

    # Convert origin remote URL into HTTPS format
    logging.info("Converting remote URL into HTTPS format...")

    host = remote_url.split("@")[1].split(":")[0]
    user_name = remote_url.split("@")[1].split(":")[1].split("/")[0]
    repository_name = remote_url.split("@")[1].split(":")[1].split("/")[1]

    https_remote_url = f"https://{host}/{user_name}/{repository_name}"

    # Update remote URL
    repo.remote().set_url(https_remote_url)
    logging.info(f"Updated remote URL: '{https_remote_url}'.")


def delete_git_repo(repo_path: Path) -> None:
    """
    Deletes Git repository in the given folder.

    Notes:
        Deleting Git directory requires special treatment, because a normal shutil.rmtree() call can fail
        because of certain files in .git folder which get marked as read-only when cloning.

    Args:
        repo_path: Path to the Git repository's folder.
    """
    if not repo_path.exists():
        return

    def on_rm_error(func, path, exc_info):
        # from: https://stackoverflow.com/a/4829285
        os.chmod(path, stat.S_IWRITE)
        os.unlink(path)

    shutil.rmtree(repo_path, onerror=on_rm_error)
