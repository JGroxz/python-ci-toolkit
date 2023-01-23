"""
Utility functions for working with Python modules.
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def import_module_from_file(module_name: str, file_path: Path) -> ModuleType:
    """
    Imports a Python module with the given name from the given file path.

    Args:
        module_name: Name of the module to import.
        file_path: Path to the file where the module is stored.

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location(f"{module_name}", file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{module_name}"] = module
    spec.loader.exec_module(module)

    return module
