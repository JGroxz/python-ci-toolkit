"""
Convenience function for running shell commands from Python.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from comrun import CommandRunner
from comrun.datatypes import CommandResult as ComrunCommandResult
import rich
from rich.style import Style
from rich.table import Table
from rich.text import Text

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
    command: str
    """Command that was executed."""
    exit_code: int
    """Exit code of the command."""
    output: str
    """Captured output of the command."""

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
    def output_lines(self) -> list[str]:
        """
        Captured command output split into lines.
        """
        return self.output.splitlines()

    @property
    def output_stripped(self) -> str:
        """
        Captured command output with leading and trailing whitespaces and newlines removed.
        """
        return self.output.strip(" \n")

    @property
    def output_value(self) -> str | None:
        """
        Similar to output_stripped, but returns None if the stripped output is an empty string.

        Notes:
            Useful when the output of the command is expected to be a single-line string which has to be used in further logic.
        """
        stripped = self.output_stripped

        return stripped if (stripped != "") else None


def run_shell_command(command: str,
                      cwd: str | Path = os.getcwd(),
                      raw_output: bool = False,
                      silence_output: bool = False,
                      raise_on_error: bool = True,
                      use_wsl_on_windows: bool = True) -> ShellCommandResult:
    """
    Executes the given command in a subprocess.

    Notes:
        If run on a Windows machine, will use WSL for command execution.

    Args:
        command: Command to execute.
        cwd: Working directory to execute the command in. Defaults to current working directory.
        raw_output: If set to True, the output from the executed command will be printed as is.
            If set to False, the output will be printed with pretty formatting through the global Rich Console.
            Has effect only with 'silence_output' set to False.
        silence_output: If set to True, command output will be suppressed.
        raise_on_error: If set to True (default), an exception will be thrown if the executed command exits with a non-zero exit code.
        use_wsl_on_windows: If set to True (default) and running on Windows, the provided command will be run in WSL.

    Returns:
        Command result with exit code and captured output.

    Raises:
        RuntimeError:
            if the executed command completes with a non-zero exit code.
    """

    # lazy-initialize CI console if using pretty output
    global _output_console
    if (not silence_output) and (_output_console is None):
        _output_console = rich.get_console()

    # print header if using pretty output
    if (not silence_output) and (not raw_output):
        header = Text("Running shell command:", style=SHELL_OUTPUT_PREFIX_STYLE) + " " + Text(f"{command}",
                                                                                              style=SHELL_OUTPUT_COMMAND_STYLE)
        _output_console.print(header)

    # display only the first line of the command (for pretty output)
    command_display_string = command.splitlines()[0]

    def print_command_output_line(line: str, stream: str, _) -> None:
        if raw_output:
            _output_console.print(line, highlight=False)
            return

        grid = Table.grid()
        grid.add_column(style=SHELL_OUTPUT_PREFIX_STYLE, min_width=SHELL_OUTPUT_PREFIX_WIDTH_MIN,
                        max_width=SHELL_OUTPUT_PREFIX_WIDTH_MAX, overflow="ellipsis", no_wrap=True)
        grid.add_column(style=SHELL_OUTPUT_PREFIX_STYLE)
        grid.add_column(overflow="fold")
        grid.add_row(
            Text(f" > shell: ") + Text(command_display_string, style=SHELL_OUTPUT_COMMAND_STYLE), " │ ",
            (line if stream == "stdout" else Text(line, style=SHELL_OUTPUT_STDERR_STYLE))
        )
        # noinspection PyUnresolvedReferences
        _output_console.print(grid, end="")

    runner = CommandRunner(
        cwd=cwd,
        quiet=silence_output,
        check=False,
        wsl=use_wsl_on_windows,
        on_line=print_command_output_line,
    )
    result = _convert_comrun_result(runner(command))

    if result.is_failed and raise_on_error:
        if silence_output:
            output_string = (f"  Output:\n"
                             f"    ↓ ↓ ↓ Command output start ↓ ↓ ↓\n"
                             f"{result.output}\n"
                             f"    ↑ ↑ ↑  Command output end  ↑ ↑ ↑\n")
        else:
            output_string = "  Output of the command can be seen before the stacktrace above."

        raise RuntimeError(f"Error executing command (exit code {result.exit_code})\n"
                           f"  Command:\n"
                           f"    {command}\n"
                           f"{output_string}")

    # print header if using pretty output
    if (not silence_output) and (not raw_output):
        header = (
                Text(f"Shell command finished:", style=SHELL_OUTPUT_PREFIX_STYLE) + " "
                + Text(f"{command}", style=SHELL_OUTPUT_COMMAND_STYLE) + " "
                + Text(f"(exit code {result.exit_code})", style=SHELL_OUTPUT_PREFIX_STYLE)
        )
        _output_console.print(header)

    return result


def _convert_comrun_result(result: ComrunCommandResult) -> ShellCommandResult:
    return ShellCommandResult(
        command=result.command,
        exit_code=result.exit_code,
        output=result.output.text,
    )
