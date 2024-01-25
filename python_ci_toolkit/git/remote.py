import logging

from git import Repo, GitCommandError


# TODO: make this a context manager
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


# TODO: make this a context manager
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
