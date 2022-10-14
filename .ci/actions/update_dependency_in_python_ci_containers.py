"""
Custom CI action that automatically bumps python-ci-toolkit version dependency in python-ci-containers repository.
"""
import logging

from python_ci_toolkit.console import initialize_ci_console


def cli() -> None:

    initialize_ci_console()

    logging.warning("Not implemented yet.")


if __name__ == '__main__':
    cli()
