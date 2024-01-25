"""
Automatically bumps python-ci-toolkit's version dependency in python-ci-containers repository.

https://bitbucket.org/pyci/python-ci-containers/src/main/
"""

import os
import re
from pathlib import Path

from git import Repo

from python_ci_toolkit.actions import get_action_logger
from python_ci_toolkit.environment import retrieve_environment_variable, ci_paths
from python_ci_toolkit.git import delete_git_repo
from python_ci_toolkit.git import get_default_ssh_private_key, git_ssh_credentials
from python_ci_toolkit.versions import versions

logger = get_action_logger(__name__)

PYTHON_CI_PUSH_SSH_PRIVATE_KEY = retrieve_environment_variable(
    "PYTHON_CI_PUSH_SSH_PRIVATE_KEY",
    usage_explanation="An SSH private key with read and write access to the python-ci-containers repository is required to update it.",
    fallback=get_default_ssh_private_key
)

PYTHON_CI_CONTAINERS_REPO_URL = "git@github.com:pyci/python-ci-runner.git"
TEMP_REPO_CLONE_PATH = ci_paths.temp_files_directory / "python-ci-containers-clone"
TOOLKIT_VERSION_DEFINITION_REGEX = re.compile('(python-ci-toolkit==".*")', flags=re.UNICODE)


def clone_python_ci_containers_repo() -> Repo:
    # Recreate the temporary directory
    if TEMP_REPO_CLONE_PATH.exists():
        delete_git_repo(TEMP_REPO_CLONE_PATH)
    os.makedirs(TEMP_REPO_CLONE_PATH, exist_ok=True)

    repo = Repo.clone_from(PYTHON_CI_CONTAINERS_REPO_URL, TEMP_REPO_CLONE_PATH)

    return repo


def update_self_dependency_version_in_dockerfile(containers_repo: Repo) -> None:
    # Read Dockerfile
    containers_repo_root = Path(containers_repo.working_tree_dir)
    dockerfile_path = containers_repo_root / "Dockerfile"
    with dockerfile_path.open("r") as file:
        content = file.read()

    # Get current toolkit version string
    current_toolkit_version = versions.read_project_version(ci_paths.project_root)
    current_toolkit_version_string = f'python-ci-toolkit=="{current_toolkit_version}"'

    # Replace toolkit version with the current one everywhere in the Dockerfile
    matches = TOOLKIT_VERSION_DEFINITION_REGEX.findall(content)
    logger.info(f"Found {len(matches)} occurrence(s) of version string to replace in the Dockerfile.")
    for match in matches:
        # Check if version has to be updated
        version_to_be_replaced = versions.parse_semantic_version(match.split('"')[1].replace(".dev", "-dev"))
        if version_to_be_replaced >= current_toolkit_version:
            logger.info(f"Toolkit version used in the Dockerfile ('{version_to_be_replaced}') is not older than current one ('{current_toolkit_version}').\n"
                        f"  No need to update the containers repo.")
            raise SystemExit(0)

        # Update version
        content = content.replace(match, current_toolkit_version_string)

    # Write back to file
    with dockerfile_path.open("w") as file:
        file.write(content)
    logger.info(f"Updated toolkit dependency to '{current_toolkit_version_string}' in '{dockerfile_path}'.")

    # Commit Dockerfile change
    containers_repo.git.add("Dockerfile")
    containers_repo.git.commit(m=f"Update python-ci-toolkit version to {current_toolkit_version}")
    logger.info("Committed toolkit version update.")

    # Bump version (patch)
    containers_version = versions.read_project_version(containers_repo_root)
    new_containers_version = containers_version.bump_patch()
    versions.write_project_version(containers_repo_root, new_containers_version)

    # Commit and tag version file change
    containers_repo.git.add("VERSION")
    containers_repo.git.commit(m=f"Bump version to {new_containers_version}")
    containers_repo.create_tag(f"v{new_containers_version}", message=f"Tag generated after the update of python-ci-toolkit dependency to v{current_toolkit_version}")
    logger.info("Bumped patch version of python-ci-containers and committed.")


def action() -> None:
    current_toolkit_version = versions.read_project_version(ci_paths.project_root)
    if current_toolkit_version.prerelease:
        logger.info(f"Currently checked out toolkit version ('{current_toolkit_version}') is a pre-release.\n"
                    f"  No need to update the containers repo.")
        raise SystemExit(0)

    with git_ssh_credentials(PYTHON_CI_PUSH_SSH_PRIVATE_KEY):
        logger.info("Cloning containers repo...")
        containers_repo = clone_python_ci_containers_repo()
        logger.info("Repo cloned.")

        containers_repo.git.config("user.name", "PyCI Bot")
        containers_repo.git.config("user.email", "automation@pyci.dev")
        logger.info("Set Git config in the containers repo.")

        containers_repo.git.checkout("main")
        logger.info("Checked out 'main'.")

        logger.info("Updating self-dependency in the repo's Dockerfile...")
        update_self_dependency_version_in_dockerfile(containers_repo)
        logger.info("Self-dependency updated.")

        logger.info("Pushing commits and tags...")
        containers_repo.git.push()
        containers_repo.git.push(tags=True)
        logger.info("Done.")


if __name__ == '__main__':
    action()
