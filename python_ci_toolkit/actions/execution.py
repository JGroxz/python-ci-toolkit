"""
Central coordination and rendering for action execution events.
"""

from __future__ import annotations

import logging
import os
import secrets
import shutil
from threading import Lock

import rich
from rich.ansi import AnsiDecoder
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
        self._stream_decoders: dict[tuple[str, str], AnsiDecoder] = {}
        self._root_started_at: float | None = None
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
        if depth == 0:
            self._root_started_at = event.timestamp
        ci_environment = event.data.get("ci_environment")

        print_action_run_start(
            str(event.data["action_name"]),
            str(event.data["action_version"]),
            str(event.data["action_source"]),
            is_nested=(depth > 0),
            nesting_depth=depth,
            toolkit_version=str(event.data["toolkit_version"]),
            ci_environment=(
                ci_environment
                if isinstance(ci_environment, str)
                else None
            ),
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
        for decoder_key in [
            key for key in self._stream_decoders if key[0] == event.run_id
        ]:
            self._stream_decoders.pop(decoder_key)
        self._run_depths.pop(event.run_id, None)
        if depth == 0:
            self._root_started_at = None

    def _render_output(self, event: ActionEvent) -> None:
        depth = self._run_depths.get(event.run_id, 0)
        if event.kind == "log":
            level = int(event.data.get("level", logging.INFO))
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
            style = self._level_style(level)
            marker, marker_style, marker_padding_style = self._level_marker(level)
        else:
            stream = str(event.data.get("stream", "stdout"))
            message_text = self._decode_stream_text(
                event.run_id,
                stream,
                str(event.data.get("text", "")),
            )
            style = None
            marker, marker_style, marker_padding_style = (
                ("»", "pyci.log.stderr", None)
                if stream == "stderr"
                else ("›", "pyci.log.stdout", None)
            )

        self._print_threaded_text(
            elapsed=max(
                event.timestamp - (
                    self._root_started_at
                    if self._root_started_at is not None
                    else event.timestamp
                ),
                0.0,
            ),
            message=message_text,
            depth=depth,
            message_style=style,
            marker=marker,
            marker_style=marker_style,
            marker_padding_style=marker_padding_style,
        )

    def _decode_stream_text(
        self,
        run_id: str,
        stream: str,
        text: str,
    ) -> Text:
        decoder = self._stream_decoders.setdefault(
            (run_id, stream),
            AnsiDecoder(),
        )
        decoded_text = Text()
        for carriage_return_segment in text.split("\r"):
            decoded_text = decoder.decode_line(carriage_return_segment)
        return decoded_text

    def _print_threaded_text(
        self,
        *,
        elapsed: float,
        message: Text,
        depth: int,
        message_style: str | None,
        marker: str,
        marker_style: str,
        marker_padding_style: str | None,
    ) -> None:
        thread_column = _ACTION_VISUAL_THREAD_OFFSET + 1
        elapsed_text = self._format_elapsed_time(elapsed)
        prefix = self._build_output_prefix(
            elapsed_text,
            marker,
            marker_style,
            marker_padding_style,
        )

        available_width = max(
            self._console.width
            - thread_column
            - (depth * _NESTED_THREAD_INDENT)
            - 2,
            1,
        )
        wrapped_lines = message.wrap(
            self._console,
            available_width,
            overflow="fold",
            no_wrap=False,
        )
        if not wrapped_lines:
            wrapped_lines.append(Text())

        for line in wrapped_lines:
            rendered_line = self._assemble_threaded_line(
                prefix,
                line,
                message_style,
                depth,
            )
            self._console.print(
                rendered_line,
                overflow="crop",
                no_wrap=True,
                highlight=False,
            )

    @staticmethod
    def _format_elapsed_time(elapsed: float) -> str:
        total_tenths = max(int(elapsed * 10), 0)
        total_seconds = total_tenths // 10
        if total_seconds < 3600:
            minutes, second_tenths = divmod(total_tenths, 600)
            seconds, tenths = divmod(second_tenths, 10)
            elapsed_text = f"{minutes:02d}:{seconds:02d}.{tenths}"
        elif total_seconds < 100 * 3600:
            hours, remaining_seconds = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remaining_seconds, 60)
            elapsed_text = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            days, remaining_seconds = divmod(total_seconds, 24 * 3600)
            hours, remaining_seconds = divmod(remaining_seconds, 3600)
            minutes = remaining_seconds // 60
            if days < 100:
                elapsed_text = f"{days}d{hours:02d}:{minutes:02d}"
            elif days <= 9999:
                elapsed_text = f"{days}d{hours:02d}h"
            else:
                elapsed_text = ">9999d"
        return elapsed_text.rjust(8)

    @staticmethod
    def _build_output_prefix(
        elapsed_time: str,
        marker: str,
        marker_style: str,
        marker_padding_style: str | None,
    ) -> Text:
        prefix = Text()
        prefix.append(elapsed_time, style="dim")
        if marker_padding_style is None:
            prefix.append(" ")
            prefix.append(marker, style=marker_style)
            prefix.append(" ")
        else:
            prefix.append("▐", style=marker_padding_style)
            prefix.append(marker, style=marker_style)
            prefix.append("▌", style=marker_padding_style)
        return prefix

    @staticmethod
    def _assemble_threaded_line(
        prefix: Text,
        message: Text,
        message_style: str | None,
        nesting_depth: int = 0,
    ) -> Text:
        rendered_line = Text()
        rendered_line.append_text(prefix)
        rendered_line.append(
            "│" * nesting_depth,
            style="pyci.flair_dark_dim",
        )
        rendered_line.append("│", style="pyci.flair_dark")
        rendered_line.append(" ")
        message_start = len(rendered_line)
        rendered_line.append_text(message)
        if message_style is not None:
            rendered_line.stylize_before(message_style, message_start)
        return rendered_line

    @staticmethod
    def _level_style(level: int) -> str | None:
        if level >= logging.CRITICAL:
            return "pyci.status.failure"
        if level >= logging.ERROR:
            return "pyci.error"
        if level >= logging.WARNING:
            return "pyci.log.warning"
        return None

    @staticmethod
    def _level_marker(level: int) -> tuple[str, str, str | None]:
        if level >= logging.CRITICAL:
            return "×", "pyci.log.critical", "pyci.log.critical_padding"
        if level >= logging.ERROR:
            return "×", "pyci.log.error", None
        if level >= logging.WARNING:
            return "!", "pyci.log.warning", None
        if level >= logging.INFO:
            return "i", "pyci.log.info", None
        return "·", "pyci.log.debug", None


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
