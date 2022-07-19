"""
Builds a Poetry package from the current project.
"""
import logging
from pathlib import Path

from python_ci_utilities.console import initialize_ci_console
from python_ci_utilities.environment import assert_environment_variable_set
from python_ci_utilities.shell import run_shell_command
from python_ci_utilities.pip import ensure_package_installed

ENV_AWS_PYPI_REPO_NAME = assert_environment_variable_set("AWS_PYPI_REPO_NAME")


def cli():
    initialize_ci_console()

    project_root = Path(__file__).parent.parent

    ensure_package_installed("poetry")

    logging.info(f"Publishing package to the PYPI repository '{ENV_AWS_PYPI_REPO_NAME}'...")

    run_shell_command(f"poetry publish --repository {ENV_AWS_PYPI_REPO_NAME}", cwd=project_root, use_wsl_on_windows=False)

    logging.info(f"Package published.")


if __name__ == '__main__':
    cli()
