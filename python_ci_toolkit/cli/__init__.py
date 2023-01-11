import logging

import click as vanilla_click
import rich_click as click
from rich.logging import RichHandler
from rich.traceback import install

from .autocompletion import autocompletion

# configuring rich-click
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.MAX_WIDTH = 80
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option()
def cli() -> None:
    # initialize logging

    install(show_locals=False, suppress=[click, vanilla_click])

    logs_format = "%(message)s"
    logging.basicConfig(
        level="INFO",
        format=logs_format,
        handlers=[
            RichHandler(
                show_path=False,
                tracebacks_show_locals=False,
                markup=False
            )
        ]
    )


# Register CLI commands
cli.add_command(autocompletion)

if __name__ == '__main__':
    cli()
