from __future__ import annotations

import io
import logging

from python_ci_toolkit.actions.events import (
    ActionEventLogHandler,
    create_action_event,
    decode_event_frame,
    encode_event_frame,
)
from python_ci_toolkit.actions.execution import ActionEventManager


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

    assert top_level_environment["COLUMNS"] == "90"
    assert nested_environment["COLUMNS"] == "89"
    assert top_level_environment["LINES"] == "40"
    assert top_level_environment["TERMINAL_WIDTH"] == "90"
    assert top_level_environment["PYCI_INTERNAL_EVENT_TOKEN"] == manager.token
    assert top_level_environment["PYCI_INTERNAL_ACTION_RUN_ID"] == "top-run"
