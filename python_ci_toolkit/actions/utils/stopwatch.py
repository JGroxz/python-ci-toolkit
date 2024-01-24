from __future__ import annotations

import contextlib
import time
from types import TracebackType
from typing import Type


class Stopwatch(contextlib.AbstractContextManager):
    """
    A context manager that measures the time elapsed between its creation and its exit.
    """

    _start_time: float
    _duration: float | None = None

    def __enter__(self) -> Stopwatch:
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, __exc_type: Type[BaseException] | None, __exc_value: BaseException | None, __traceback: TracebackType | None) -> bool | None:
        self._duration = time.perf_counter() - self._start_time

        if __exc_value is not None:
            raise __exc_value

        return None

    @property
    def elapsed_time(self) -> float:
        """
        Returns the elapsed time in seconds.

        Notes:
            If inside the context, returns the time elapsed since the context's creation.
            If the context has already exited, returns the time elapsed between the context's creation and its exit.
        """
        if self._duration is None:
            return time.perf_counter() - self._start_time
        else:
            return self._duration

    @property
    def elapsed_time_ms(self) -> float:
        """
        Returns the elapsed time in milliseconds.

        Notes:
            If inside the context, returns the time elapsed since the context's creation.
            If the context has already exited, returns the time elapsed between the context's creation and its exit.
        """
        return self.elapsed_time * 1000

    @property
    def elapsed_time_pretty(self) -> str:
        """
        Returns the elapsed time as a pretty string.
        """
        return self.format_time_pretty(self.elapsed_time)

    @staticmethod
    def format_time_pretty(seconds: float) -> str:
        """
        Returns the given time in a pretty string format.

        Args:
            seconds: Time in seconds.
        """
        milliseconds = seconds * 1000
        microseconds = seconds * 1000000

        if seconds >= 3600:
            return f"{seconds / 3600:.0f} h {seconds % 3600 / 60:.0f} min {seconds % 60:.1f} s"
        if seconds >= 60:
            return f"{seconds / 60:.0f} min {seconds % 60:.1f} s"
        if seconds >= 1:
            return f"{seconds:.1f} s"
        elif seconds * 1000 >= 1:
            return f"{milliseconds:.0f} ms"
        else:
            return f"{microseconds:.0f} µs"
