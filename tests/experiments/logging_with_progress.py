import logging
import time

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress


def run():
    console = Console()

    FORMAT = "%(message)s"
    logging.basicConfig(
        level="INFO",
        format=FORMAT,
        handlers=[
            RichHandler(
                console=console,
                show_path=False,
                tracebacks_show_locals=False,
                # disable Rich markup by default to avoid character clashes when printing logs;
                # markup can still be processed on demand by explicitly adding 'extra={"markup": True}' to the log call
                markup=False
            )
        ]
    )

    with Progress(console=console, transient=True) as progress:
        progress.add_task("Testing...", total=None)
        time.sleep(1)
        logging.info("hello")
        time.sleep(1)
        logging.info("I'm trying")
        console.print("Aasdasdasda")
        time.sleep(1)
        logging.info(" to ")
        console.print("asdasDASDaDAdsadasd")
        time.sleep(1)
        logging.info("brake ")
        time.sleep(1)
        logging.info("stuff")
        time.sleep(1)


if __name__ == '__main__':
    run()
