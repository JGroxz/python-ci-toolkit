"""
Utility functions for managing Python PIP packages.
"""

import sys

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
    """
    error = run_shell_command(f"pip install {package_name}", silence_output=silence_pip_stdout)
    if error:
        raise RuntimeError(f"Failed to install PIP package '{package_name}'.")


def ensure_package_installed(package_name: str) -> None:
    """
    Makes sure that the given package is installed in the current Python environment.

    Args:
        package_name: Name of the package to check.
    """
    if not check_package_installed(package_name):
        install_package(package_name)
