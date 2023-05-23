"""
Functions which allow to use files as persistent timestamps.
"""

import os
import time
from pathlib import Path


def reset_file_timestamp(file_path: Path):
    """
    Resets the modification timestamp of the given file.
    If the file does not exist, it will be created.

    Args:
        file_path: The path to the file.
    """

    if file_path.exists():
        assert file_path.is_file(), \
            f"File timer path '{file_path}' exists, but it is not a file."
        file_path.touch()
    else:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch(exist_ok=True)  # <- this will always update the file's modification timestamp


def get_file_timestamp(file_path: Path) -> float:
    """
    Returns the time in seconds since the last time the given file was modified.

    Args:
        file_path: The path to the file.

    Returns:
        UNIX timestamp of the last time the given file was modified.
        Returns infinity if the given path does not exist or is not a file.
    """
    if not file_path.is_file():  # <- this will still be False if the file does not exist
        return float("inf")

    file_timestamp = os.path.getmtime(file_path)
    return file_timestamp


def time_since_file_timestamp(file_path: Path) -> float:
    """
    Returns the time in seconds since the last time the given file was modified.

    Args:
        file_path: The path to the file.

    Returns:
        The time in seconds since the last time the given timer file was modified.
        Returns infinity if the given path does not exist or is not a file.
    """
    if not file_path.is_file():  # <- this will still be False if the file does not exist
        return float("inf")

    file_timestamp = get_file_timestamp(file_path)
    return time.time() - file_timestamp
