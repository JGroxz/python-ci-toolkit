import logging
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

from ..environment import BitbucketPipelines, ci_paths, ci_platform, retrieve_environment_variable


def get_default_ssh_private_key_file_path() -> Path:
    """
    Returns the path to the default location of the private SSH key file on the current system.
    """
    if ci_platform is BitbucketPipelines:
        bitbucket_ssh_key_path = retrieve_environment_variable(
            "BITBUCKET_SSH_KEY_FILE",
            "This variable is only available for pipelines running on Bitbucket Cloud and the Linux Docker Pipelines runner. "
            "See https://support.atlassian.com/bitbucket-cloud/docs/variables-and-secrets/.")
        return Path(bitbucket_ssh_key_path)

    # both in UNIX and in Windows, default SSH private key location is in '~/.ssh/id_rsa'
    return Path.home() / ".ssh/id_rsa"


def get_default_ssh_private_key() -> str | None:
    """
    Returns private SSH key from the default system location, or None if such key is not present.
    """
    default_ssh_key_file_path = get_default_ssh_private_key_file_path()

    if not default_ssh_key_file_path.exists():
        logging.error(f"Default private SSH key file does not exist at '{default_ssh_key_file_path}'.")
        return None

    with default_ssh_key_file_path.open() as file:
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
    # save current GIT_SSH_COMMAND
    original_git_ssh_command = os.environ.get("GIT_SSH_COMMAND", default="")

    # in case SSH key is not provided, try retrieving a default one
    if (ssh_private_key is None) or (ssh_private_key == ""):
        # try to retrieve the default SSH key
        logging.info("Private SSH key string is not provided, trying to locate SSH keys file in the default directory...")
        default_path = get_default_ssh_private_key_file_path()
        ssh_private_key = get_default_ssh_private_key()

        if ssh_private_key is None:
            # if the default key is missing, there is nothing we can do here
            raise RuntimeError(f"Private SSH key string is not provided, and the key could not be found in the default location ('{default_path}').")
        else:
            # if all is good, print path to the used private key file for info
            logging.info(f"Default private SSH key loaded successfully from '{default_path}'.")

    # make sure that temporary folder for the key file exists
    temp_private_ssh_key_file_path = ci_paths.temp_files_directory / f"ssh/{uuid.uuid4()}"
    temp_private_ssh_key_file_path.parent.mkdir(exist_ok=True)

    try:
        # save Git SSH key to file
        with temp_private_ssh_key_file_path.open("w", newline="\n") as file:
            file.write(ssh_private_key)

        # adjust SSH key permissions on UNIX-like systems to prevent 'ssh' command from complaining
        if os.name == "posix":
            os.chmod(temp_private_ssh_key_file_path, 0o600)

        # tell Git to use the new SSH key file
        os.environ["GIT_SSH_COMMAND"] = f'ssh -i "{temp_private_ssh_key_file_path}" ' \
                                        f'-o IdentitiesOnly=yes ' \
                                        f'-o StrictHostKeyChecking=accept-new'

        yield  # <- within this context, clone repos, push changes etc.
    except Exception:
        raise
    finally:
        # restore original GIT_SSH_COMMAND
        os.environ["GIT_SSH_COMMAND"] = original_git_ssh_command

        # clean up the temporary key file; this will throw an error if the file cannot be deleted due to permissions etc.
        if temp_private_ssh_key_file_path.exists():
            os.remove(temp_private_ssh_key_file_path)
