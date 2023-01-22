import logging

import click as vanilla_click
import rich_click as click
from rich.traceback import install

from .action import action
from .autocompletion import autocompletion

# configuring rich-click
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.MAX_WIDTH = 80
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option()
@click.option("--debug",
              is_flag=True,
              help="Enable debug logging.")
def cli(debug: bool = False) -> None:
    """
    Tool to streamline the use of Python scripts in CI/CD automation.
    """

    # initialize logging
    from python_ci_toolkit.logging import configure_ci_logging
    configure_ci_logging("DEBUG" if debug else "INFO")


# Register CLI commands
cli.add_command(autocompletion)
cli.add_command(action)

if __name__ == '__main__':
    cli()
