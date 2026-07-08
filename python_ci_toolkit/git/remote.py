import logging
from pathlib import Path

from ..shell import run_shell_command


def _get_remote_origin_url(repo_path: Path) -> str:
    return run_shell_command(
        "git remote get-url origin",
        cwd=repo_path,
        silence_output=True,
        use_wsl_on_windows=False,
    ).output_stripped


def _set_remote_origin_url(repo_path: Path, remote_url: str) -> None:
    run_shell_command(
        f'git remote set-url origin "{remote_url}"',
        cwd=repo_path,
        silence_output=True,
        use_wsl_on_windows=False,
    )


def _repo_has_lfs_files(repo_path: Path) -> bool:
    result = run_shell_command(
        "git lfs ls-files --all",
        cwd=repo_path,
        silence_output=True,
        raise_on_error=False,
        use_wsl_on_windows=False,
    )
    return result.is_successful and bool(result.output_value)


def ensure_remote_is_ssh(repo_path: Path) -> None:
    """
    Makes sure that the remote origin repository's address is in SSH format.

    Notes:
        If the remote's URL is in HTTP(S) format, this function will automatically convert it to SSH.

    Args:
        repo_path: Path to the Git repository to update.
    """
    logging.info("Checking remote address...")

    remote_url = _get_remote_origin_url(repo_path)

    if remote_url.startswith("git"):
        logging.info(f"Remote '{remote_url}' is already an SSH address.")
        return

    logging.warning(f"Remote '{remote_url}' is an HTTP(S) address.")

    if _repo_has_lfs_files(repo_path):
        logging.error(
            "Current repository has files tracked by Git LFS, which only works with HTTP(S) remotes.\n"
            "  Remote will not be overwritten."
        )
        raise SystemExit(1)

    logging.info("Converting remote URL into SSH format...")

    host = remote_url.split("://")[1].split("@")[-1].split("/")[0]
    user_name = remote_url.split("://")[1].split("/")[1]
    repository_name = remote_url.split("://")[1].split("/")[2]

    ssh_remote_url = f"git@{host}:{user_name}/{repository_name}"

    _set_remote_origin_url(repo_path, ssh_remote_url)
    logging.info(f"Updated remote URL: '{ssh_remote_url}'.")


def ensure_remote_is_https(repo_path: Path) -> None:
    """
    Makes sure that the remote origin repository's address is in HTTPS format.

    Notes:
        If the remote's URL is in SSH format, this function will automatically convert it to HTTPS.

    Args:
        repo_path: Path to the Git repository to update.
    """
    logging.info("Checking remote address...")

    remote_url = _get_remote_origin_url(repo_path)

    if remote_url.startswith("http"):
        if not remote_url.startswith("https"):
            logging.info("Remote URL uses HTTP. Switching to HTTPS...")
            https_remote_url = remote_url.replace("http", "https", 1)
            _set_remote_origin_url(repo_path, https_remote_url)
            logging.info(f"Updated remote URL: '{https_remote_url}'.")
        else:
            logging.info(f"Remote '{remote_url}' is an HTTPS address.")
        return

    logging.warning(f"Remote '{remote_url}' is an SSH address.")

    logging.info("Converting remote URL into HTTPS format...")

    host = remote_url.split("@")[1].split(":")[0]
    user_name = remote_url.split("@")[1].split(":")[1].split("/")[0]
    repository_name = remote_url.split("@")[1].split(":")[1].split("/")[1]

    https_remote_url = f"https://{host}/{user_name}/{repository_name}"

    _set_remote_origin_url(repo_path, https_remote_url)
    logging.info(f"Updated remote URL: '{https_remote_url}'.")
