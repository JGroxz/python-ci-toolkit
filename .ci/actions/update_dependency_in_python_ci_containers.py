"""
Custom CI action that automatically bumps python-ci-toolkit's version dependency in python-ci-containers repository.
"""
import logging
from pathlib import Path

from python_ci_toolkit.console import initialize_ci_console


def clone_python_ci_containers_repo() -> Path:
    return Path("")


def create_feature_branch() -> None:
    pass


def update_self_dependency_version_in_dockerfile(containers_repo_root: Path) -> None:
    # TODO: patch Dockerfile
    pass


def merge_feature_into_main() -> None:
    pass


def push_containers_repo() -> None:
    pass


def cli() -> None:

    initialize_ci_console()

    logging.warning("Not implemented yet.")

    containers_repo_root = clone_python_ci_containers_repo()

    create_feature_branch()

    update_self_dependency_version_in_dockerfile(containers_repo_root)

    merge_feature_into_main()

    push_containers_repo()


if __name__ == '__main__':
    cli()
