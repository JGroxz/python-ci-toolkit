"""
Private action-runtime events transported over child-process stdout.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import sys
from threading import Lock
import time
import traceback
from typing import Any, TextIO

_EVENT_FRAME_PREFIX = "::pyci-action-event-v1::"
_EVENT_PROTOCOL_VERSION = 1
_event_write_lock = Lock()


@dataclass(frozen=True)
class ActionEvent:
    kind: str
    run_id: str
    timestamp: float
    data: dict[str, Any]


def create_action_event(
    kind: str,
    run_id: str,
    *,
    timestamp: float | None = None,
    **data: Any,
) -> ActionEvent:
    return ActionEvent(
        kind=kind,
        run_id=run_id,
        timestamp=time.time() if timestamp is None else timestamp,
        data=data,
    )


def encode_event_frame(event: ActionEvent, token: str) -> str:
    payload = {
        "version": _EVENT_PROTOCOL_VERSION,
        "kind": event.kind,
        "run_id": event.run_id,
        "timestamp": event.timestamp,
        "data": event.data,
    }
    encoded_payload = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    return f"{_EVENT_FRAME_PREFIX}{token}::{encoded_payload}"


def decode_event_frame(line: str, token: str) -> ActionEvent | None:
    frame_prefix = f"{_EVENT_FRAME_PREFIX}{token}::"
    if not line.startswith(frame_prefix):
        return None

    try:
        payload = json.loads(line[len(frame_prefix):])
    except (json.JSONDecodeError, TypeError):
        return None

    if (
        not isinstance(payload, dict)
        or payload.get("version") != _EVENT_PROTOCOL_VERSION
        or not isinstance(payload.get("kind"), str)
        or not isinstance(payload.get("run_id"), str)
        or not isinstance(payload.get("timestamp"), (int, float))
        or not isinstance(payload.get("data"), dict)
    ):
        return None

    return ActionEvent(
        kind=payload["kind"],
        run_id=payload["run_id"],
        timestamp=float(payload["timestamp"]),
        data=payload["data"],
    )


def write_event_frame(
    event: ActionEvent,
    token: str,
    *,
    stream: TextIO | None = None,
) -> None:
    output_stream = stream or sys.stdout
    frame = encode_event_frame(event, token)
    with _event_write_lock:
        print(frame, file=output_stream, flush=True)


class ActionEventLogHandler(logging.Handler):
    """
    Converts child-process log records to presentation-free action events.
    """

    def __init__(
        self,
        token: str,
        run_id: str,
        *,
        stream: TextIO | None = None,
    ) -> None:
        super().__init__()
        self.token = token
        self.run_id = run_id
        self.stream = stream

    def emit(self, record: logging.LogRecord) -> None:
        try:
            exception_data = None
            if record.exc_info and record.exc_info != (None, None, None):
                exc_type, exc_value, exc_traceback = record.exc_info
                exception_data = {
                    "type": exc_type.__name__ if exc_type is not None else None,
                    "message": str(exc_value) if exc_value is not None else None,
                    "traceback": "".join(
                        traceback.format_exception(exc_type, exc_value, exc_traceback)
                    ),
                }

            event = create_action_event(
                "log",
                self.run_id,
                timestamp=record.created,
                level=record.levelno,
                level_name=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                markup=bool(getattr(record, "markup", False)),
                exception=exception_data,
            )
            write_event_frame(event, self.token, stream=self.stream)
        except Exception:
            self.handleError(record)
