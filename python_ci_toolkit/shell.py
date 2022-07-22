"""
Utility functions for running shell commands from Python.
"""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Tuple

from rich.style import Style
from rich.table import Table
from rich.text import Text

from .console import ci_console

SHELL_OUTPUT_PREFIX_WIDTH_MIN = 15
SHELL_OUTPUT_PREFIX_WIDTH_MAX = 30
SHELL_OUTPUT_PREFIX_STYLE = Style(color="blue")
SHELL_OUTPUT_COMMAND_STYLE = Style(color="deep_sky_blue4", italic=True)


def run_shell_command(command: str,
                      cwd: str | Path = os.getcwd(),
                      silence_output: bool = False,
                      throw_exception_on_error: bool = True,
                      use_wsl_on_windows: bool = True) -> Tuple[int, str | None]:
    """
    Executes the given command in a subprocess.

    Notes:
        If ran on a Windows machine, will use WSL for command execution.

    Args:
        command: Command to execute.
        cwd: Working directory to execute the command in. Defaults to current working directory.
        silence_output: If set to True, command output will be suppressed.
        throw_exception_on_error: If set to True (default), an exception will be thrown if the executed command exits with a non-zero exit code.
        use_wsl_on_windows: If set to True (default) and running on Windows, the provided command will be run in WSL.

    Returns:
        Command exit code.

    Raises:
        RuntimeError:
            if the executed command completes with a non-zero exit code.
    """

    if os.name == 'nt' and use_wsl_on_windows:
        # use WSL on Windows
        command = f"wsl {command}"

    args = shlex.split(command)

    captured_output = ""

    def capture_subprocess_output(pipe):
        for line in iter(pipe.readline, b''):  # b'\n'-separated lines
            decoded_line = line.decode("utf-8")

            # capture output
            nonlocal captured_output
            captured_output += decoded_line

            # print to console if not silenced
            if not silence_output:
                grid = Table.grid()
                grid.add_column(style=SHELL_OUTPUT_PREFIX_STYLE, min_width=SHELL_OUTPUT_PREFIX_WIDTH_MIN, max_width=SHELL_OUTPUT_PREFIX_WIDTH_MAX, overflow="ellipsis", no_wrap=True)
                grid.add_column(style=SHELL_OUTPUT_PREFIX_STYLE)
                grid.add_column(overflow="fold")
                grid.add_row(
                    Text(f" > shell: ") + Text(command, style=SHELL_OUTPUT_COMMAND_STYLE), " │ ", decoded_line.rstrip(" \n")
                )

                ci_console.print(grid, end="")

    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with process.stdout:
        with process.stderr:
            capture_subprocess_output(process.stdout)
            capture_subprocess_output(process.stderr)
    exitcode = process.wait()

    if (exitcode != 0) and throw_exception_on_error:
        raise RuntimeError(f"Error executing command (exit code {exitcode})\n"
                           f"    Command: {command}\n"
                           f"    Output: {captured_output}\n")

    return exitcode, captured_output
