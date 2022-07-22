"""
Authenticates and publishes a package to the custom PyPI repository.
"""
import logging
from pathlib import Path

import toml

from python_ci_toolkit.console import initialize_ci_console
from python_ci_toolkit.environment import assert_environment_variable_set
from python_ci_toolkit.pip import ensure_package_installed
from python_ci_toolkit.shell import run_shell_command
from python_ci_toolkit.versions import get_latest_pypi_package_version, get_project_version_from_file

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

    # PIP
    run_shell_command(f"pip config set global.extra-index-url https://{pypi_user}:{pypi_token}@{pypi_url_simple}", cwd=project_root, use_wsl_on_windows=False)

    # Poetry
    run_shell_command(f"poetry config http-basic.{ENV_AWS_PYPI_REPO_NAME} {pypi_user} {pypi_token}", cwd=project_root, use_wsl_on_windows=False)
    run_shell_command(f"poetry config repositories.{ENV_AWS_PYPI_REPO_NAME} https://{pypi_url}", cwd=project_root, use_wsl_on_windows=False)


def publish() -> None:
    project_root = Path(__file__).parent.parent

    package_name = get_poetry_project_package_name()

    latest_version = get_latest_pypi_package_version(package_name)
    local_version = get_project_version_from_file(project_root)

    # check if we need to publish by comparing our local version to the latest one in the remote repo
    if latest_version == local_version:
        logging.info(f"Version '{latest_version}' of '{package_name}' already exists in the target repository '{ENV_AWS_PYPI_REPO_NAME}'. Will not publish.")
        return
    if latest_version > local_version:
        logging.warning(f"Local version of the package '{package_name}' ('{local_version}') is lower than the latest version in the target repository '{ENV_AWS_PYPI_REPO_NAME}' ('{latest_version}').\n"
                        f"    Something could be wrong. Please check the CI logic.")
        exit(1)

    run_shell_command(f"poetry publish --repository {ENV_AWS_PYPI_REPO_NAME}", cwd=project_root, use_wsl_on_windows=False)


def get_poetry_project_package_name() -> str:
    project_root = Path(__file__).parent.parent

    pyproject_toml_path = Path(project_root, "pyproject.toml")
    if not pyproject_toml_path.exists():
        logging.error(f"'pyproject.toml' was not found in the project root folder ('{project_root}').\n"
                      f"    Make sure you are trying to publish a poetry project.")
        exit(1)

    with open(pyproject_toml_path, "r") as file:
        contents = file.read()
        project_config = toml.loads(contents)
        package_name = project_config.get("tool").get("poetry").get("name")

    return package_name


def cli():
    initialize_ci_console()

    ensure_package_installed("poetry")

    logging.info(f"Authenticating to PyPI repository '{ENV_AWS_PYPI_REPO_NAME}'...")

    authenticate()

    logging.info(f"Publishing package to the PYPI repository '{ENV_AWS_PYPI_REPO_NAME}'...")

    publish()

    logging.info(f"Done.")


if __name__ == '__main__':
    cli()
