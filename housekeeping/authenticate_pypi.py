"""
Adds custom registry to PIP and Poetry configurations.
"""
from pathlib import Path

from python_ci_utilities.console import initialize_ci_console
from python_ci_utilities.environment import assert_environment_variable_set
from python_ci_utilities.pip import ensure_package_installed
from python_ci_utilities.shell import run_shell_command

ENV_AWS_DOMAIN = assert_environment_variable_set("AWS_DOMAIN")
ENV_AWS_DOMAIN_OWNER = assert_environment_variable_set("AWS_DOMAIN_OWNER")
ENV_AWS_DEFAULT_REGION = assert_environment_variable_set("AWS_DEFAULT_REGION")
ENV_AWS_PYPI_REPO_NAME = assert_environment_variable_set("AWS_PYPI_REPO_NAME")


def cli():
    initialize_ci_console()

    ensure_package_installed("poetry")




if __name__ == '__main__':
    cli()
