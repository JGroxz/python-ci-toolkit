"""
Functions for managing logging in CI environments.
"""
from __future__ import annotations

import logging
import warnings
from logging import LogRecord

from charming_traceback import Traceback as CharmingTraceback
from charming_traceback import install as install_charming_traceback
import click
import rich
import rich_click
from rich._null_file import NullFile
from rich.logging import RichHandler

from .console import _logging_console

LOG_WITH_MARKUP = dict(
    extra=dict(
        markup=True
    )
)
"""Append this to a log call to enable Rich markup in the log message."""

LOG_WITH_MARKUP_NO_HIGHLIGHTER = dict(
    extra=dict(
        markup=True,
        highlighter=None
    )
)
"""Append this to a log call to enable Rich markup in the log message, but disable Rich highlighting."""


class CharmingTracebackRichHandler(RichHandler):
    """
    Rich log handler that renders logged exceptions with Charming Traceback.
    """

    def emit(self, record: LogRecord) -> None:
        message = self.format(record)
        traceback = None
        if (
            self.rich_tracebacks
            and record.exc_info
            and record.exc_info != (None, None, None)
        ):
            exc_type, exc_value, exc_traceback = record.exc_info
            assert exc_type is not None
            assert exc_value is not None
            traceback = CharmingTraceback.from_exception(
                exc_type,
                exc_value,
                exc_traceback,
                width=self.tracebacks_width,
                code_width=self.tracebacks_code_width,
                extra_lines=self.tracebacks_extra_lines,
                theme=self.tracebacks_theme,
                word_wrap=self.tracebacks_word_wrap,
                show_locals=self.tracebacks_show_locals,
                locals_max_length=self.locals_max_length,
                locals_max_string=self.locals_max_string,
                suppress=self.tracebacks_suppress,
                max_frames=self.tracebacks_max_frames,
            )
            message = record.getMessage()
            if self.formatter:
                record.message = record.getMessage()
                formatter = self.formatter
                if hasattr(formatter, "usesTime") and formatter.usesTime():
                    record.asctime = formatter.formatTime(record, formatter.datefmt)
                message = formatter.formatMessage(record)

        message_renderable = self.render_message(record, message)
        log_renderable = self.render(
            record=record,
            traceback=traceback,
            message_renderable=message_renderable,
        )
        if isinstance(self.console.file, NullFile):
            self.handleError(record)
            return

        try:
            self.console.print(log_renderable)
        except Exception:
            self.handleError(record)


def configure_ci_logging(level: str | int = None) -> None:
    """
    Configures the root logger with Rich handler using the CI console.

    Notes:
        This call configures rich and logging module for the current CI environment and terminal type, be it Bitbucket pipelines or a local machine.
        This enables nicely formatted logs and detailed, well-readable tracebacks.

        After running this function, you can use logging.*() methods to get nicely formatted log messages in the output.

    Args:
        level: Level to set the root logger to.
    """
    # if no level provided, preserve root logger's level
    if level is None:
        level = logging.root.getEffectiveLevel()

    # ensure that level is an int
    if type(level) is str:
        level = getattr(logging, level.upper())

    # compile suppress list
    suppress_list = [click, rich_click, rich]

    # configure tracebacks
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="There is no current event loop",
            category=DeprecationWarning,
            module="charming_traceback.installation",
        )
        install_charming_traceback(
            console=_logging_console,
            show_locals=False,
            suppress=suppress_list,
        )

    # basicConfig in case logging has not been set up yet
    FORMAT = "%(message)s"
    logging.basicConfig(
        level=level,
        format=FORMAT,
        handlers=[
            CharmingTracebackRichHandler(
                console=_logging_console,
                show_path=False,
                rich_tracebacks=True,
                tracebacks_show_locals=False,
                # disable Rich markup by default to avoid character clashes when printing logs;
                # markup can still be processed on demand by explicitly adding 'extra={"markup": True}' to the log call
                markup=False,
                tracebacks_suppress=suppress_list,
            )
        ],
    )

    # override root logger's level on every call
    logging.getLogger().setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger with the specified name.
    Ensures that the logging module is configured with the default handlers for the current CI environment.
    """
    configure_ci_logging()
    return logging.getLogger(name)
