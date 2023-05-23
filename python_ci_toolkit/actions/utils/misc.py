"""
Miscellaneous utility functions of the actions package.
"""
import hashlib

from ..utils.stopwatch import Stopwatch
from ...logging import get_logger

logger = get_logger(__name__)


def log_execution_time(func):
    """Utility decorator to time the execution of functions."""

    def wrapped(*args, **kwargs):
        with Stopwatch() as sw:
            result = func(*args, **kwargs)

        logger.debug(f"Function '{func.__name__}()' took {sw.elapsed_time_ms:.0f} ms to execute.")
        return result

    return wrapped


def hash_string(string: str) -> str:
    """
    Returns a hash of the given string.
    """
    return hashlib.md5(string.encode()).hexdigest()
