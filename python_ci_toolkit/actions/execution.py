"""
Central coordination and rendering for action execution events.
"""

from __future__ import annotations

from datetime import datetime
import logging
import os
import secrets
import shutil
from threading import Lock

import rich
from rich.text import Text

from .events import (
    ActionEvent,
    create_action_event,
    decode_event_frame,
    write_event_frame,
)
from .protocol import (
    PYCI_INTERNAL_ACTION_RUN_ID_ENV_VAR,
    PYCI_INTERNAL_EVENT_TOKEN_ENV_VAR,
    PYCI_INTERNAL_ROOT_COLUMNS_ENV_VAR,
    PYCI_INTERNAL_ROOT_LINES_ENV_VAR,
)
from .utils import Stopwatch
from .utils.logging import (
    _ACTION_VISUAL_THREAD_OFFSET,
    print_action_run_end_failure,
    print_action_run_end_success,
    print_action_run_start,
)

_MINIMUM_CHILD_TERMINAL_WIDTH = 20
_NESTED_THREAD_INDENT = 1


def _read_positive_environment_integer(name: str) -> int | None:
    value = os.environ.get(name)
    if value is None:
        return None
    try:
        parsed_value = int(value)
    except ValueError:
        return None
    return parsed_value if parsed_value > 0 else None


class ExecutionFlowRenderer:
    """
    Owns all terminal decoration for an action execution tree.
    """

    def __init__(self) -> None:
        self._run_depths: dict[str, int] = {}
        self._console = rich.get_console()

    def render(self, event: ActionEvent) -> None:
        if event.kind == "action_started":
            self._render_action_started(event)
        elif event.kind == "action_finished":
            self._render_action_finished(event)
        elif event.kind in {"log", "stream"}:
            self._render_output(event)

    def _render_action_started(self, event: ActionEvent) -> None:
        parent_run_id = event.data.get("parent_run_id")
        parent_depth = self._run_depths.get(parent_run_id, -1)
        depth = parent_depth + 1
        self._run_depths[event.run_id] = depth

        print_action_run_start(
            str(event.data["action_name"]),
            str(event.data["action_version"]),
            str(event.data["action_source"]),
            is_nested=(depth > 0),
            nesting_depth=depth,
            toolkit_version=str(event.data["toolkit_version"]),
            ci_environment=str(event.data["ci_environment"]),
        )

    def _render_action_finished(self, event: ActionEvent) -> None:
        depth = self._run_depths.get(event.run_id, 0)
        action_display_name = str(event.data["action_display_name"])
        duration = float(event.data.get("duration", 0.0))
        status = event.data.get("status")

        if status == "success":
            print_action_run_end_success(
                action_display_name,
                duration,
                is_nested=(depth > 0),
                nesting_depth=depth,
            )
        else:
            print_action_run_end_failure(
                action_display_name,
                duration,
                str(event.data.get("error_type") or "ActionProcessError"),
                is_nested=(depth > 0),
                nesting_depth=depth,
            )
        self._run_depths.pop(event.run_id, None)

    def _render_output(self, event: ActionEvent) -> None:
        depth = self._run_depths.get(event.run_id, 0)
        if event.kind == "log":
            level_name = str(event.data.get("level_name") or logging.getLevelName(
                int(event.data.get("level", logging.INFO))
            ))
            message = str(event.data.get("message", ""))
            if event.data.get("markup"):
                try:
                    message_text = Text.from_markup(message)
                except Exception:
                    message_text = Text(message)
            else:
                message_text = Text(message)

            exception = event.data.get("exception")
            if isinstance(exception, dict) and exception.get("traceback"):
                message_text.append("\n")
                message_text.append(str(exception["traceback"]), style="dim")
            style = self._level_style(int(event.data.get("level", logging.INFO)))
        else:
            stream = str(event.data.get("stream", "stdout"))
            level_name = stream.upper()
            message_text = Text.from_ansi(str(event.data.get("text", "")))
            style = "red" if stream == "stderr" else None

        self._print_threaded_text(
            timestamp=event.timestamp,
            level_name=level_name,
            message=message_text,
            depth=depth,
            message_style=style,
        )

    def _print_threaded_text(
        self,
        *,
        timestamp: float,
        level_name: str,
        message: Text,
        depth: int,
        message_style: str | None,
    ) -> None:
        thread_column = (
            _ACTION_VISUAL_THREAD_OFFSET
            + 1
            + (depth * _NESTED_THREAD_INDENT)
        )
        timestamp_text = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
        prefix_value = f"{timestamp_text} {level_name[:8]:<8}"
        if len(prefix_value) > thread_column:
            prefix_value = prefix_value[:thread_column]
        prefix_value = prefix_value.ljust(thread_column)

        available_width = max(self._console.width - thread_column - 2, 1)
        wrapped_lines = message.wrap(
            self._console,
            available_width,
            overflow="fold",
            no_wrap=False,
        )
        if not wrapped_lines:
            wrapped_lines.append(Text())

        for line in wrapped_lines:
            rendered_line = Text(prefix_value, style="dim")
            rendered_line.append("│", style="pyci.flair_dark")
            rendered_line.append(" ")
            rendered_line.append_text(line)
            self._console.print(
                rendered_line,
                style=message_style,
                overflow="crop",
                no_wrap=True,
                highlight=False,
            )

    @staticmethod
    def _level_style(level: int) -> str | None:
        if level >= logging.CRITICAL:
            return "pyci.critical"
        if level >= logging.ERROR:
            return "red"
        if level >= logging.WARNING:
            return "yellow"
        return None


class ActionEventManager:
    """
    Renders events in the root process and relays them in action processes.
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        current_run_id: str | None = None,
        renderer: ExecutionFlowRenderer | None = None,
    ) -> None:
        environment_token = os.environ.get(PYCI_INTERNAL_EVENT_TOKEN_ENV_VAR)
        environment_run_id = os.environ.get(PYCI_INTERNAL_ACTION_RUN_ID_ENV_VAR)
        self.token = token or environment_token or secrets.token_hex(16)
        self.current_run_id = (
            current_run_id if current_run_id is not None else environment_run_id
        )
        self.is_relay = bool(
            (environment_token or token)
            and (environment_run_id or current_run_id)
        )
        self._renderer = renderer or ExecutionFlowRenderer()
        self._lock = Lock()

        terminal_size = shutil.get_terminal_size(
            fallback=(self._renderer._console.width, self._renderer._console.height)
        )
        self.root_columns = (
            _read_positive_environment_integer(PYCI_INTERNAL_ROOT_COLUMNS_ENV_VAR)
            or terminal_size.columns
        )
        self.root_lines = (
            _read_positive_environment_integer(PYCI_INTERNAL_ROOT_LINES_ENV_VAR)
            or terminal_size.lines
        )

    def new_run_id(self) -> str:
        return secrets.token_hex(12)

    def emit(self, event: ActionEvent) -> None:
        with self._lock:
            if self.is_relay:
                write_event_frame(event, self.token)
            else:
                self._renderer.render(event)

    def accept_child_line(
        self,
        line: str,
        stream: str,
        child_run_id: str,
    ) -> ActionEvent:
        event = decode_event_frame(line, self.token)
        if event is None:
            event = create_action_event(
                "stream",
                child_run_id,
                stream=stream,
                text=line,
            )
        self.emit(event)
        return event

    def child_environment(self, run_id: str, depth: int) -> dict[str, str]:
        content_width = max(
            self.root_columns
            - (_ACTION_VISUAL_THREAD_OFFSET + 3)
            - (depth * _NESTED_THREAD_INDENT),
            _MINIMUM_CHILD_TERMINAL_WIDTH,
        )
        return {
            PYCI_INTERNAL_EVENT_TOKEN_ENV_VAR: self.token,
            PYCI_INTERNAL_ACTION_RUN_ID_ENV_VAR: run_id,
            PYCI_INTERNAL_ROOT_COLUMNS_ENV_VAR: str(self.root_columns),
            PYCI_INTERNAL_ROOT_LINES_ENV_VAR: str(self.root_lines),
            "COLUMNS": str(content_width),
            "LINES": str(self.root_lines),
            "TERMINAL_WIDTH": str(content_width),
        }


_action_event_manager: ActionEventManager | None = None


def get_action_event_manager() -> ActionEventManager:
    global _action_event_manager
    if _action_event_manager is None:
        _action_event_manager = ActionEventManager()
    return _action_event_manager


def get_event_output(event: ActionEvent) -> tuple[str, str] | None:
    if event.kind == "stream":
        return (
            str(event.data.get("stream", "stdout")),
            str(event.data.get("text", "")),
        )
    if event.kind != "log":
        return None

    text = str(event.data.get("message", ""))
    exception = event.data.get("exception")
    if isinstance(exception, dict) and exception.get("traceback"):
        text = f"{text}\n{exception['traceback']}".rstrip("\n")
    return "stdout", text
