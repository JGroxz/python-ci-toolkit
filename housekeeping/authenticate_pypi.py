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

    project_root = Path(__file__).parent.parent

    _, output = run_shell_command(
        command=f"aws codeartifact get-authorization-token --domain {ENV_AWS_DOMAIN} --domain-owner {ENV_AWS_DOMAIN_OWNER} --query authorizationToken --duration-seconds 3600 --output text",
        silence_output=True
    )
    pypi_token = output.strip()
    pypi_user = "aws"
    pypi_url = f"{ENV_AWS_DOMAIN}-{ENV_AWS_DOMAIN_OWNER}.d.codeartifact.{ENV_AWS_DEFAULT_REGION}.amazonaws.com/pypi/{ENV_AWS_PYPI_REPO_NAME}/simple/"

    # PIP
    run_shell_command(f"pip config set global.extra-index-url https://{pypi_user}:{pypi_token}@{pypi_url}", cwd=project_root, use_wsl_on_windows=False)

    # Poetry
    run_shell_command(f"poetry config http-basic.{ENV_AWS_PYPI_REPO_NAME} {pypi_user} {pypi_token}", cwd=project_root, use_wsl_on_windows=False)
    run_shell_command(f"poetry config repositories.{ENV_AWS_PYPI_REPO_NAME} https://{pypi_url}", cwd=project_root, use_wsl_on_windows=False)


if __name__ == '__main__':
    cli()
