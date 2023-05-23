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
    def elapsed_time_str(self) -> str:
        """
        Returns the elapsed time as a pretty string.
        """
        if self.elapsed_time >= 1:
            return f"{self.elapsed_time:.3f} s"
        else:
            return f"{self.elapsed_time_ms:.0f} ms"
