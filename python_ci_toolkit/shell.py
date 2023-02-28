"""
Utility functions for running shell commands from Python.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from rich.style import Style
from rich.table import Table
from rich.text import Text

_IS_ON_WINDOWS = (os.name == "nt")

SHELL_OUTPUT_PREFIX_WIDTH_MIN = 15
SHELL_OUTPUT_PREFIX_WIDTH_MAX = 26
SHELL_OUTPUT_PREFIX_STYLE = Style(color="blue")
SHELL_OUTPUT_COMMAND_STYLE = Style(color="deep_sky_blue4", italic=True)
SHELL_OUTPUT_STDERR_STYLE = Style(color="red")

_output_console = None


@dataclass
class ShellCommandResult:
    """
    Result of executing a shell command.
    """
    exit_code: int
    """Exit code of the command."""
    output: str
    """Captured raw output of the command."""

    @property
    def is_successful(self) -> bool:
        """
        Returns True if the command completed successfully (exit code is 0), False otherwise.
        """
        return self.exit_code == 0

    @property
    def is_failed(self) -> bool:
        """
        Returns True if the command failed (exit code is non-zero), False otherwise.
        """
        return not self.is_successful

    @property
    def output_stripped(self) -> str:
        """
        Captured output of the command with leading and trailing whitespaces and newlines removed.
        """
        return self.output.strip()

    @property
    def output_lines(self) -> list[str]:
        """
        Captured output of the command split into lines.
        """
        return self.output.splitlines()


def run_shell_command(command: str,
                      cwd: str | Path = os.getcwd(),
                      raw_output: bool = False,
                      silence_output: bool = False,
                      raise_on_error: bool = True,
                      use_wsl_on_windows: bool = True) -> ShellCommandResult:
    """
    Executes the given command in a subprocess.

    Notes:
        If ran on a Windows machine, will use WSL for command execution.

    Args:
        command: Command to execute.
        cwd: Working directory to execute the command in. Defaults to current working directory.
        raw_output: If set to True, the output from the executed command will be printed as is.
            If set to False, the output will be printed with pretty Rich formatting through ci_output_console.
            Has effect only with 'silence_output' set to False.
        silence_output: If set to True, command output will be suppressed.
        raise_on_error: If set to True (default), an exception will be thrown if the executed command exits with a non-zero exit code.
        use_wsl_on_windows: If set to True (default) and running on Windows, the provided command will be run in WSL.

    Returns:
        Command exit code and captured output (list of lines).

    Raises:
        RuntimeError:
            if the executed command completes with a non-zero exit code.
    """

    # lazy-initialize CI console if using pretty output
    global _output_console
    if (not silence_output) and (_output_console is None):
        from .logging import ci_output_console
        _output_console = ci_output_console

    # use WSL if required on Windows
    if _IS_ON_WINDOWS and use_wsl_on_windows:
        command = f"wsl {command}"

    # print header if using pretty output
    if (not silence_output) and (not raw_output):
        header = Text("Running shell command:", style=SHELL_OUTPUT_PREFIX_STYLE) + " " + Text(f"{command}",
                                                                                              style=SHELL_OUTPUT_COMMAND_STYLE)
        _output_console.print(header)

    # prepare command args
    args = shlex.split(command)

    captured_output = ""

    # lock is required to prints from stdout- and stderr-reading threads from interfering with each other
    # (if 'silence_output' is set to False)
    lock = threading.Lock()

    # helper function for handling the executed shell command's output
    def capture_subprocess_output(pipe, stderr: bool = False):
        for line in iter(pipe.readline, b''):  # b'\n'-separated lines
            decoded_line = line.decode("utf-8")

            # capture output
            nonlocal captured_output
            captured_output += decoded_line

            # print to console if not silenced
            if not silence_output:
                lock.acquire()
                decoded_line = decoded_line.rstrip(" \n")
                if raw_output:
                    _output_console.print(decoded_line)
                else:
                    grid = Table.grid()
                    grid.add_column(style=SHELL_OUTPUT_PREFIX_STYLE, min_width=SHELL_OUTPUT_PREFIX_WIDTH_MIN,
                                    max_width=SHELL_OUTPUT_PREFIX_WIDTH_MAX, overflow="ellipsis", no_wrap=True)
                    grid.add_column(style=SHELL_OUTPUT_PREFIX_STYLE)
                    grid.add_column(overflow="fold")
                    grid.add_row(
                        Text(f" > shell: ") + Text(command, style=SHELL_OUTPUT_COMMAND_STYLE), " │ ",
                        (decoded_line if (not stderr) else Text(decoded_line, style=SHELL_OUTPUT_STDERR_STYLE))
                    )
                    # noinspection PyUnresolvedReferences
                    _output_console.print(grid, end="")
                lock.release()

    # run the shell command and capture its output
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with process.stdout, process.stderr:
        # we read stdout and stderr in threads to be able to print live logs from both streams concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(capture_subprocess_output, process.stdout)
            executor.submit(capture_subprocess_output, process.stderr, stderr=True)
            executor.shutdown(wait=True)
    exit_code = process.wait()

    if (exit_code != 0) and raise_on_error:
        if silence_output:
            output_string = (f"  Output:\n"
                             f"    ↓ ↓ ↓ Command output start ↓ ↓ ↓\n"
                             f"{''.join(captured_output)}\n"
                             f"    ↑ ↑ ↑  Command output end  ↑ ↑ ↑\n")
        else:
            output_string = "  Output of the command can be seen before the stacktrace above."

        raise RuntimeError(f"Error executing command (exit code {exit_code})\n"
                           f"  Command:\n"
                           f"    {command}\n"
                           f"{output_string}")

    return ShellCommandResult(
        exit_code=exit_code,
        output=captured_output
    )
