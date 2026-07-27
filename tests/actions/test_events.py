from __future__ import annotations

import io
import logging

from rich.console import Console
from rich.text import Text

from python_ci_toolkit.actions.events import (
    ActionEventLogHandler,
    create_action_event,
    decode_event_frame,
    encode_event_frame,
)
from python_ci_toolkit.actions.execution import ActionEventManager
from python_ci_toolkit.actions.execution import ExecutionFlowRenderer


def test_event_frame_round_trip_preserves_multiline_unicode_payload():
    event = create_action_event(
        "stream",
        "child-run",
        timestamp=123.5,
        stream="stdout",
        text="first line\nžluťoučký",
    )

    frame = encode_event_frame(event, "private-token")

    assert "\n" not in frame
    assert decode_event_frame(frame, "private-token") == event
    assert decode_event_frame(frame, "different-token") is None


def test_event_log_handler_preserves_log_semantics_and_traceback():
    output = io.StringIO()
    handler = ActionEventLogHandler(
        "private-token",
        "action-run",
        stream=output,
    )
    logger = logging.Logger("test.action")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    try:
        raise ValueError("broken action")
    except ValueError:
        logger.exception("action failed")

    event = decode_event_frame(output.getvalue().strip(), "private-token")

    assert event is not None
    assert event.kind == "log"
    assert event.run_id == "action-run"
    assert event.data["level"] == logging.ERROR
    assert event.data["level_name"] == "ERROR"
    assert event.data["logger_name"] == "test.action"
    assert event.data["message"] == "action failed"
    assert event.data["exception"]["type"] == "ValueError"
    assert "ValueError: broken action" in event.data["exception"]["traceback"]


def test_child_terminal_dimensions_account_for_renderer_prefix():
    manager = ActionEventManager()
    manager.root_columns = 120
    manager.root_lines = 40

    top_level_environment = manager.child_environment("top-run", depth=0)
    nested_environment = manager.child_environment("nested-run", depth=1)

    assert top_level_environment["COLUMNS"] == "107"
    assert nested_environment["COLUMNS"] == "106"
    assert top_level_environment["LINES"] == "40"
    assert top_level_environment["TERMINAL_WIDTH"] == "107"
    assert top_level_environment["PYCI_INTERNAL_EVENT_TOKEN"] == manager.token
    assert top_level_environment["PYCI_INTERNAL_ACTION_RUN_ID"] == "top-run"


def test_execution_line_dims_only_its_prefix():
    prefix = Text()
    prefix.append(" 00:01.2 ", style="dim")
    prefix.append("i", style="pyci.log.info")
    prefix.append(" ")
    rendered_line = ExecutionFlowRenderer._assemble_threaded_line(
        prefix,
        Text("action output"),
        None,
    )

    dim_spans = [span for span in rendered_line.spans if span.style == "dim"]
    assert rendered_line.plain == " 00:01.2 i │ action output"
    assert len(dim_spans) == 1
    assert dim_spans[0].start == 0
    assert dim_spans[0].end == len(" 00:01.2 ")
    assert dim_spans[0].end < rendered_line.plain.index("action output")


def test_execution_level_markers_remain_distinct_without_color():
    assert ExecutionFlowRenderer._level_marker(logging.DEBUG) == (
        "·",
        "pyci.log.debug",
        None,
    )
    assert ExecutionFlowRenderer._level_marker(logging.INFO) == (
        "i",
        "pyci.log.info",
        None,
    )
    assert ExecutionFlowRenderer._level_marker(logging.WARNING) == (
        "!",
        "pyci.log.warning",
        None,
    )
    assert ExecutionFlowRenderer._level_marker(logging.ERROR) == (
        "×",
        "pyci.log.error",
        None,
    )
    assert ExecutionFlowRenderer._level_marker(logging.CRITICAL) == (
        "×",
        "pyci.log.critical",
        "pyci.log.critical_padding",
    )


def test_elapsed_time_format_stays_aligned_across_long_action_durations():
    assert ExecutionFlowRenderer._format_elapsed_time(0.0) == " 00:00.0"
    assert ExecutionFlowRenderer._format_elapsed_time(65.39) == " 01:05.3"
    assert ExecutionFlowRenderer._format_elapsed_time(3599.99) == " 59:59.9"
    assert ExecutionFlowRenderer._format_elapsed_time(3600.0) == " 1:00:00"
    assert ExecutionFlowRenderer._format_elapsed_time(45296.0) == "12:34:56"
    assert ExecutionFlowRenderer._format_elapsed_time(360000.0) == " 4d04:00"


def test_critical_marker_uses_existing_prefix_space_for_half_block_padding():
    marker = ExecutionFlowRenderer._level_marker(logging.CRITICAL)
    prefix = ExecutionFlowRenderer._build_output_prefix(" 00:01.2", *marker)

    assert prefix.plain == " 00:01.2▐×▌"
    assert len(prefix) == len(" 00:01.2 × ")


def test_nested_execution_line_dims_ancestor_threads():
    prefix = Text()
    prefix.append(" 00:01.2 ", style="dim")
    prefix.append("i", style="pyci.log.info")
    prefix.append(" ")
    rendered_line = ExecutionFlowRenderer._assemble_threaded_line(
        prefix,
        Text("nested output"),
        None,
        nesting_depth=2,
    )

    ancestor_spans = [
        span
        for span in rendered_line.spans
        if span.style == "pyci.flair_dark_dim"
    ]
    active_thread_spans = [
        span
        for span in rendered_line.spans
        if span.style == "pyci.flair_dark"
    ]

    assert rendered_line.plain == " 00:01.2 i │││ nested output"
    assert len(ancestor_spans) == 1
    assert ancestor_spans[0].start == len(prefix)
    assert ancestor_spans[0].end == len(prefix) + 2
    assert len(active_thread_spans) == 1
    assert active_thread_spans[0].start == len(prefix) + 2
    assert active_thread_spans[0].end == len(prefix) + 3


def test_explicit_log_markup_overrides_message_severity_not_marker():
    from python_ci_toolkit.actions.logging.console import CI_TOOLKIT_RICH_THEME

    console = Console(
        color_system="256",
        theme=CI_TOOLKIT_RICH_THEME,
    )
    prefix = ExecutionFlowRenderer._build_output_prefix(
        " 00:01.2",
        *ExecutionFlowRenderer._level_marker(logging.ERROR),
    )
    rendered_line = ExecutionFlowRenderer._assemble_threaded_line(
        prefix,
        Text.from_markup("[color(40)]expected failure[/] ordinary failure"),
        "pyci.error",
    )

    marker_offset = rendered_line.plain.index("×")
    marked_message_offset = rendered_line.plain.index("expected failure")
    ordinary_message_offset = rendered_line.plain.index("ordinary failure")

    assert (
        rendered_line.get_style_at_offset(console, marker_offset).color.number
        == 160
    )
    assert (
        rendered_line.get_style_at_offset(
            console,
            marked_message_offset,
        ).color.number
        == 40
    )
    assert (
        rendered_line.get_style_at_offset(
            console,
            ordinary_message_offset,
        ).color.number
        == 160
    )


def test_stream_ansi_style_continues_across_lines():
    renderer = ExecutionFlowRenderer()
    renderer._console = Console(color_system="256")

    first_line = renderer._decode_stream_text(
        "action-run",
        "stdout",
        "\x1b[38;5;75mfirst",
    )
    second_line = renderer._decode_stream_text(
        "action-run",
        "stdout",
        "second",
    )
    reset_line = renderer._decode_stream_text(
        "action-run",
        "stdout",
        "\x1b[0mplain",
    )

    assert first_line.get_style_at_offset(renderer._console, 0).color.number == 75
    assert second_line.get_style_at_offset(renderer._console, 0).color.number == 75
    assert reset_line.get_style_at_offset(renderer._console, 0).color is None


def test_stream_carriage_return_updates_render_only_latest_value():
    renderer = ExecutionFlowRenderer()
    renderer._console = Console(color_system="256")

    rendered_update = renderer._decode_stream_text(
        "action-run",
        "stdout",
        "\x1b[38;5;184m10%\r20%\r30%",
    )

    assert rendered_update.plain == "30%"
    assert (
        rendered_update.get_style_at_offset(renderer._console, 0).color.number
        == 184
    )
