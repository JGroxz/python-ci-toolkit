"""
Simple action for testing your python-ci-toolkit installation.
"""
import logging

import click

from python_ci_toolkit.actions.actions import get_action_logger

logger = get_action_logger(__name__)


@click.command
@click.option("--shout",
              is_flag=True)
def cli(shout: bool) -> None:

    logger.debug("Initiating the realm-greeting procedure...")

    message = "Hello World"

    if shout:
        logger.critical(f"{message.upper()}!!! 🔥")
    else:
        logger.info(f"{message}! 🌸")


if __name__ == '__main__':
    cli()
