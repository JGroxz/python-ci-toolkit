"""
Miscellaneous utility functions of the actions package.
"""
import hashlib
import time

from ..logging import get_logger

logger = get_logger(__name__)


def timeit(func):
    """Utility decorator to time the execution of functions."""

    def wrapped(*args, **kwargs):
        start = time.perf_counter()

        result = func(*args, **kwargs)

        duration = time.perf_counter() - start
        logger.debug(f"Function '{func.__name__}()' took {duration * 1000:.0f} ms to execute.")
        return result

    return wrapped


def hash_string(string: str) -> str:
    """
    Returns a hash of the given string.
    """
    return hashlib.md5(string.encode()).hexdigest()
