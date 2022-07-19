"""
Builds a Poetry package from the current project.
"""
import logging
from pathlib import Path

from python_ci_utilities.console import initialize_ci_console
from python_ci_utilities.shell import run_shell_command
from python_ci_utilities.pip import ensure_package_installed


def cli():
    initialize_ci_console()

    project_root = Path(__file__).parent.parent

    ensure_package_installed("poetry")

    logging.info("Starting Poetry build...")

    run_shell_command("poetry build", cwd=project_root, use_wsl_on_windows=False)

    logging.info("Poetry build completed.")


if __name__ == '__main__':
    cli()
