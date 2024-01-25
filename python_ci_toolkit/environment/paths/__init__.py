from .core import CiPaths
from .caches import purge_temporary_files

ci_paths = CiPaths()

__all__ = [
    "ci_paths",
]
