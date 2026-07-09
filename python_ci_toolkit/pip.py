"""
Utility functions for managing Python PIP packages.
"""
import pkgutil
import sys
from pathlib import Path

from .shell import quiet_shell_command_runner


def check_package_installed(package_name: str) -> bool:
    """
    Checks if the given PIP package is installed in the current Python environment.

    Args:
        package_name: Name of the package to check.

    Returns:
        True if the package is installed, False otherwise.
    """
    package_name = package_name.replace("-", "_")
    return package_name in (entry.name for entry in pkgutil.iter_modules())


def install_package(package_name: str, quiet: bool = False) -> None:
    """
    Installs the given requirement in the current Python environment using PIP.

    Args:
        package_name: Name of the package to install.
            Can contain version specifiers, e.g. "python-ci-toolkit>=0.1.0".
        quiet: If set to True, PIP installation logs will not be sent to stdout.

    Raises:
        RuntimeError if package installation fails.
    """
    current_python_executable = Path(sys.executable)
    result = quiet_shell_command_runner(
        f"'{current_python_executable}' -m pip install {package_name}",
        quiet=quiet,
    )
    if result.is_failed:
        raise RuntimeError(f"Failed to install PIP package '{package_name}'.")


def ensure_package_installed(package_name: str, quiet: bool = False) -> None:
    """
    Makes sure that the given package is installed in the current Python environment.

    Args:
        package_name: Name of the package to check.
        quiet: If set to True, PIP installation logs will not be sent to stdout.

    Raises:
        RuntimeError if package installation fails.
    """
    if check_package_installed(package_name):
        return

    install_package(package_name, quiet)


def ensure_requirements_installed(requirements_file_path: Path, quiet: bool = False) -> None:
    """
    Makes sure that the packages in the given requirements file are installed in the current Python environment.

    Args:
        requirements_file_path: Path to the requirements.txt file to install the requirements from.
        quiet: If set to True, PIP installation logs will not be sent to stdout.

    Raises:
        FileNotFoundError if the given requirements file does not exist.
        RuntimeError if any package installation fails.
    """
    if not requirements_file_path.exists():
        raise FileNotFoundError(f"Cannot install requirements from file '{requirements_file_path}' because the file does not exist.")

    with requirements_file_path.open("r") as file:
        lines = file.readlines()
        lines = [line.strip() for line in lines]
        # remove empty lines and comments
        lines = [line for line in lines
                 if (len(line) > 0) and (not line.startswith("#"))]

    for line in lines:
        ensure_package_installed(line, quiet)
