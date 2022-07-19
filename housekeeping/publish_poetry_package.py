"""
Authenticates and publishes a package to the custom PyPI repository.
"""
import logging
from pathlib import Path

from python_ci_utilities.console import initialize_ci_console, ci_console
from python_ci_utilities.environment import assert_environment_variable_set
from python_ci_utilities.shell import run_shell_command
from python_ci_utilities.pip import ensure_package_installed

ENV_AWS_DOMAIN = assert_environment_variable_set("AWS_DOMAIN")
ENV_AWS_DOMAIN_OWNER = assert_environment_variable_set("AWS_DOMAIN_OWNER")
ENV_AWS_DEFAULT_REGION = assert_environment_variable_set("AWS_DEFAULT_REGION")
ENV_AWS_PYPI_REPO_NAME = assert_environment_variable_set("AWS_PYPI_REPO_NAME")


def authenticate() -> None:
    project_root = Path(__file__).parent.parent

    _, output = run_shell_command(
        command=f"aws codeartifact get-authorization-token --domain {ENV_AWS_DOMAIN} --domain-owner {ENV_AWS_DOMAIN_OWNER} --query authorizationToken --duration-seconds 3600 --output text",
        silence_output=True
    )
    pypi_token = output.strip()
    pypi_user = "aws"
    pypi_url = f"{ENV_AWS_DOMAIN}-{ENV_AWS_DOMAIN_OWNER}.d.codeartifact.{ENV_AWS_DEFAULT_REGION}.amazonaws.com/pypi/{ENV_AWS_PYPI_REPO_NAME}/"
    pypi_url_simple = f"{pypi_url}simple/"

    ci_console.print_exception(show_locals=True)

    # PIP
    run_shell_command(f"pip config set global.extra-index-url https://{pypi_user}:{pypi_token}@{pypi_url_simple}", cwd=project_root, use_wsl_on_windows=False)

    # Poetry
    run_shell_command(f"poetry config http-basic.{ENV_AWS_PYPI_REPO_NAME} {pypi_user} {pypi_token}", cwd=project_root, use_wsl_on_windows=False)
    run_shell_command(f"poetry config repositories.{ENV_AWS_PYPI_REPO_NAME} https://{pypi_user}:{pypi_token}@{pypi_url}", cwd=project_root, use_wsl_on_windows=False)


def cli():
    initialize_ci_console()

    project_root = Path(__file__).parent.parent

    ensure_package_installed("poetry")

    logging.info(f"Authenticating to PyPI repository '{ENV_AWS_PYPI_REPO_NAME}'...")

    authenticate()

    logging.info(f"Publishing package to the PYPI repository '{ENV_AWS_PYPI_REPO_NAME}'...")

    run_shell_command(f"poetry publish --repository {ENV_AWS_PYPI_REPO_NAME}", cwd=project_root, use_wsl_on_windows=False)

    logging.info(f"Package published.")


if __name__ == '__main__':
    cli()
