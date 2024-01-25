"""
Utility functions related to Git repositories.
"""
from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path


def delete_git_repo(repo_path: Path) -> None:
    """
    Deletes Git repository in the given folder.

    Notes:
        Deleting Git directory requires special treatment, because a normal shutil.rmtree() call can fail
        because of certain files in .git directory which get marked as read-only when cloning.

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
