"""
Simple action for testing your python-ci-toolkit installation.
"""

from python_ci_toolkit.actions.actions import get_action_logger

logger = get_action_logger(__name__)


def cli() -> None:
    logger.info("Hello World! 🌸")


if __name__ == '__main__':
    cli()
