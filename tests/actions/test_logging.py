from __future__ import annotations

import io
import logging
import sys

from rich.console import Console


def test_configure_ci_logging_uses_charming_traceback(monkeypatch):
    from python_ci_toolkit.actions.logging import logging as logging_module

    output = io.StringIO()
    console = Console(
        file=output,
        force_terminal=True,
        color_system=None,
        width=160,
    )
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level
    original_excepthook = sys.excepthook

    monkeypatch.setattr(logging_module, "_logging_console", console)
    root_logger.handlers.clear()

    try:
        logging_module.configure_ci_logging("ERROR")

        assert sys.excepthook.__module__ == "charming_traceback.installation"

        logger = logging.getLogger("test.charming_traceback")
        try:
            raise RuntimeError("logged failure")
        except RuntimeError:
            logger.exception("action failed")

        rendered_output = output.getvalue()
        assert "RuntimeError: logged failure" in rendered_output
        assert '╰─▶ File "' in rendered_output
    finally:
        root_logger.handlers[:] = original_handlers
        root_logger.setLevel(original_level)
        sys.excepthook = original_excepthook
