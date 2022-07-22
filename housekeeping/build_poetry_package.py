"""
Builds a Poetry package from the current project.
"""
import logging

from python_ci_toolkit.console import initialize_ci_console
from python_ci_toolkit.environment import ci_project_root
from python_ci_toolkit.pip import ensure_package_installed
from python_ci_toolkit.shell import run_shell_command


def cli():
    initialize_ci_console()

    ensure_package_installed("poetry")

    logging.info("Starting Poetry build...")

    run_shell_command("poetry build", cwd=ci_project_root, use_wsl_on_windows=False)

    logging.info("Poetry build completed.")


if __name__ == '__main__':
    cli()
