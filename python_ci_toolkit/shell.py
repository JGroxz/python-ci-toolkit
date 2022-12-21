"""
Utility functions for running shell commands from Python.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Tuple

from rich.style import Style
from rich.table import Table
from rich.text import Text

SHELL_OUTPUT_PREFIX_WIDTH_MIN = 15
SHELL_OUTPUT_PREFIX_WIDTH_MAX = 26
SHELL_OUTPUT_PREFIX_STYLE = Style(color="blue")
SHELL_OUTPUT_COMMAND_STYLE = Style(color="deep_sky_blue4", italic=True)
SHELL_OUTPUT_STDERR_STYLE = Style(color="red")

ci_console = None


def run_shell_command(command: str,
                      cwd: str | Path = os.getcwd(),
                      silence_output: bool = False,
                      raw_output: bool = False,
                      throw_exception_on_error: bool = True,
                      use_wsl_on_windows: bool = True) -> Tuple[int, str]:
    """
    Executes the given command in a subprocess.

    Notes:
        If ran on a Windows machine, will use WSL for command execution.

    Args:
        command: Command to execute.
        cwd: Working directory to execute the command in. Defaults to current working directory.
        silence_output: If set to True, command output will be suppressed.
        raw_output: If set to True, the output from the executed command will be printed as is.
            If set to False, the output will be printed with pretty Rich formatting through ci_console.
            Has effect only with 'silence_output' set to False.
        throw_exception_on_error: If set to True (default), an exception will be thrown if the executed command exits with a non-zero exit code.
        use_wsl_on_windows: If set to True (default) and running on Windows, the provided command will be run in WSL.

    Returns:
        Command exit code and captured output (list of lines).

    Raises:
        RuntimeError:
            if the executed command completes with a non-zero exit code.
    """

    # lazy-initialize CI console if using pretty output
    global ci_console
    if (not silence_output) and (not raw_output) and (ci_console is None):
        from .console import ci_console as c
        ci_console = c

    # use WSL if required on Windows
    if os.name == "nt" and use_wsl_on_windows:
        command = f"wsl {command}"

    # print header if using pretty output
    if (not silence_output) and (not raw_output):
        header = Text("Running shell command:", style=SHELL_OUTPUT_PREFIX_STYLE) + " " + Text(f"{command}",
                                                                                              style=SHELL_OUTPUT_COMMAND_STYLE)
        ci_console.print(header)

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
                    print(decoded_line)
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
                    ci_console.print(grid, end="")
                lock.release()

    # run the shell command and capture its output
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with process.stdout, process.stderr:
        # we read stdout and stderr in threads to be able to print live logs from both streams concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(capture_subprocess_output, process.stdout)
            executor.submit(capture_subprocess_output, process.stderr, stderr=True)
            executor.shutdown(wait=True)
    exitcode = process.wait()

    if (exitcode != 0) and throw_exception_on_error:
        if silence_output:
            output_string = (f"  Output:\n"
                             f"    ↓ ↓ ↓ Command output start ↓ ↓ ↓\n"
                             f"{''.join(captured_output)}\n"
                             f"    ↑ ↑ ↑  Command output end  ↑ ↑ ↑\n")
        else:
            output_string = "  Output of the command can be seen before the stacktrace above."

        raise RuntimeError(f"Error executing command (exit code {exitcode})\n"
                           f"  Command:\n"
                           f"    {command}\n"
                           f"{output_string}")

    return exitcode, captured_output
