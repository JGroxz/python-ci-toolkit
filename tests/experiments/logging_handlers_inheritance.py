from __future__ import annotations

import logging

from rich import print


# from rich.console import Console
# from rich.logging import RichHandler


def run():
    """Trying to figure out how to correctly set up loggers in Python."""

    def print_logger_info(name: str | None):
        logger = logging.getLogger(name)
        print(f"({logger.propagate}) {logger.handlers} {logger.parent} -> {logger}")
        logger.info(f"log from logger '{name}'")

    print("[red]Before:")

    print_logger_info(None)
    print_logger_info("root.boobs")
    print_logger_info("root.boobs.tits")
    print_logger_info(__name__)

    logging.getLogger().level = 500
    # FORMAT = "%(message)s"
    # logging.basicConfig(
    #     level="INFO",
    #     format=FORMAT,
    #     handlers=[
    #         RichHandler(
    #             console=Console(),
    #             show_path=False,
    #             tracebacks_show_locals=False,
    #             # disable Rich markup by default to avoid character clashes when printing logs;
    #             # markup can still be processed on demand by explicitly adding 'extra={"markup": True}' to the log call
    #             markup=False,
    #             omit_repeated_times=False
    #         )
    #     ],
    #     force=True,
    # )

    print("[red]After:")

    print_logger_info(None)
    print_logger_info("root.boobs")
    print_logger_info("root.boobs.tits")
    print_logger_info(__name__)

    # print(root_logger_before == root_logger_after)
    # print(child_logger_before == child_logger_after)


if __name__ == '__main__':
    run()
