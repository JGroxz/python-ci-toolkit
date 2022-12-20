"""
Utility functions for managing Python PIP packages.
"""
import io
from pathlib import Path

import pkg_resources

from .shell import run_shell_command


def check_package_installed(package_name: str) -> bool:
    """
    Checks if the given PIP package is installed in the current Python environment.

    Args:
        package_name: Name of the package to check.

    Returns:
        True if the package is installed, False otherwise.
    """

    try:
        pkg_resources.require(package_name)
    except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as e:
        return False

    return True


def install_package(package_name: str, silence_pip_stdout: bool = False) -> None:
    """
    Installs the given requirement in the current Python environment using PIP.

    Args:
        package_name: Name of the package to install.
        silence_pip_stdout: If set to True, PIP installation logs will not be sent to stdout.

    Raises:
        RuntimeError if package installation fails.
    """
    error, _ = run_shell_command(f"pip install {package_name}", silence_output=silence_pip_stdout, use_wsl_on_windows=False)
    if error:
        raise RuntimeError(f"Failed to install PIP package '{package_name}'.")


def ensure_package_installed(package_name: str, silence_pip_stdout: bool = False) -> None:
    """
    Makes sure that the given package is installed in the current Python environment.

    Args:
        package_name: Name of the package to check.
        silence_pip_stdout: If set to True, PIP installation logs will not be sent to stdout.

    Raises:
        RuntimeError if package installation fails.
    """
    if not check_package_installed(package_name):
        install_package(package_name, silence_pip_stdout)


def ensure_requirements_installed(requirements_file_path: Path, silence_pip_stdout: bool = False) -> None:
    """
    Makes sure that the packages in the given requirements file are installed in the current Python environment.

    Args:
        requirements_file_path: Path to the requirements.txt file to install the requirements from.
        silence_pip_stdout: If set to True, PIP installation logs will not be sent to stdout.

    Raises:
        FileNotFoundError if the given requirements file does not exist.
        RuntimeError if any package installation fails.
    """
    if not requirements_file_path.exists():
        raise FileNotFoundError(f"Cannot install requirements from file '{requirements_file_path}' because the file does not exist.")

    with io.open(requirements_file_path, "r") as file:
        lines = file.readlines()

    for line in lines:
        ensure_package_installed(line, silence_pip_stdout)
