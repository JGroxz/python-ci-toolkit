"""
Utility functions for running shell commands from Python.
"""
from __future__ import annotations

import os
import shlex
import subprocess
from typing import Tuple

import rich
from rich.style import Style
from rich.table import Table
from rich.text import Text

SHELL_OUTPUT_PREFIX_WIDTH_MIN = 15
SHELL_OUTPUT_PREFIX_WIDTH_MAX = 30
SHELL_OUTPUT_PREFIX_STYLE = Style(color="blue")


def run_shell_command(command: str, cwd: str = os.getcwd(), silence_output: bool = False) -> Tuple[int, str | None]:
    """
    Executes the given command in a subprocess.

    Notes:
        If ran on a Windows machine, will use WSL for command execution.

    Args:
        command: Command to execute.
        cwd: Working directory to execute the command in. Defaults to current working directory.
        silence_output: If set to True, command output will be suppressed.

    Returns:
        Command exit code.
    """

    if os.name == 'nt':
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
                    Text(f" > shell: {command}"), " │ ", decoded_line.strip()
                )

                rich.print(grid, end="")

    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with process.stdout:
        with process.stderr:
            capture_subprocess_output(process.stdout)
            capture_subprocess_output(process.stderr)
    exitcode = process.wait()

    return exitcode, captured_output
