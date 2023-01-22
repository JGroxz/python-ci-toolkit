"""
Simple action for testing your python-ci-toolkit installation.
"""
import logging

from python_ci_toolkit.console import initialize_ci_console


def cli() -> None:
    initialize_ci_console()
    logging.info("Hello World! 🌸")


if __name__ == '__main__':
    cli()
