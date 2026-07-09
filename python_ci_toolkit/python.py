"""
Utility functions for working with Python modules.
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def import_module_from_file(module_name: str, file_path: Path, is_package: bool = False) -> ModuleType:
    """
    Imports a Python module with the given name from the given file path.

    Args:
        module_name: Name of the module to import.
        file_path: Path to the file where the module is stored.
        is_package: Whether the module is a package.

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location(f"{module_name}", file_path, submodule_search_locations=[] if is_package else None)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import module '{module_name}' from '{file_path}'.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{module_name}"] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if sys.modules.get(module_name) is module:
            del sys.modules[module_name]
        raise

    return module
