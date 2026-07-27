from __future__ import annotations

from configparser import ConfigParser
import io
import logging
import sys

from rich.color import ColorType
from rich.console import Console


def test_ci_toolkit_theme_uses_fixed_xterm_256_palette():
    from python_ci_toolkit.actions.logging.console import (
        _CI_TOOLKIT_RICH_THEME_FILE_PATH,
        CI_TOOLKIT_RICH_THEME,
    )

    theme_config = ConfigParser()
    theme_config.read(_CI_TOOLKIT_RICH_THEME_FILE_PATH)

    for style_name in theme_config["styles"]:
        style = CI_TOOLKIT_RICH_THEME.styles[style_name]
        for color in (style.color, style.bgcolor):
            if color is None:
                continue
            assert color.type is ColorType.EIGHT_BIT, style_name
            assert color.number is not None
            assert 16 <= color.number <= 255, style_name


def test_theme_integrates_root_logging_and_progress_styles():
    from python_ci_toolkit.actions.logging.console import CI_TOOLKIT_RICH_THEME

    expected_colors = {
        "logging.level.debug": 245,
        "logging.level.info": 75,
        "logging.level.warning": 184,
        "logging.level.error": 160,
        "logging.level.critical": 254,
        "pyci.progress": 113,
    }

    for style_name, color_number in expected_colors.items():
        color = CI_TOOLKIT_RICH_THEME.styles[style_name].color
        assert color is not None
        assert color.number == color_number

    assert (
        CI_TOOLKIT_RICH_THEME.styles["logging.level.critical"].bgcolor.number
        == 160
    )


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
        handler = root_logger.handlers[0]
        assert isinstance(
            handler.highlighter,
            logging_module._NoopHighlighter,
        )
        assert handler.keywords == []

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


def test_top_level_action_header_wraps_inside_execution_thread(monkeypatch):
    from python_ci_toolkit.actions.utils import logging as action_logging

    output = io.StringIO()
    console = Console(file=output, color_system=None, width=34)
    monkeypatch.setattr(action_logging, "get_console", lambda: console)

    action_logging.print_action_run_start(
        "action_with_a_long_name",
        "local",
        ".ci/actions/action_with_a_long_name/action_with_a_long_name.py",
        is_nested=False,
        toolkit_version="1.2.3",
        ci_environment=None,
    )

    lines = output.getvalue().splitlines()
    assert lines[0].startswith("╭─ ")
    assert all(line.startswith("│ ") for line in lines[1:-1])
    assert lines[-1] == "╰──────────╮"
    assert all(len(line) <= console.width for line in lines)


def test_top_level_action_footer_closes_on_final_wrapped_line(monkeypatch):
    from python_ci_toolkit.actions.utils import logging as action_logging

    output = io.StringIO()
    console = Console(file=output, color_system=None, width=30)
    monkeypatch.setattr(action_logging, "get_console", lambda: console)

    action_logging.print_action_run_end_success(
        "action_with_a_long_name@local",
        65.0,
        is_nested=False,
    )

    lines = output.getvalue().splitlines()
    assert lines[0] == "╭──────────╯"
    assert all(line.startswith("│ ") for line in lines[1:-1])
    assert lines[-1].startswith("╰─ ")
    assert all(len(line) <= console.width for line in lines)
