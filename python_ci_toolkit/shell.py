"""
Convenience function for running shell commands from Python.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
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
_UNSET = object()


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


@dataclass(frozen=True)
class ShellCommandRunner:
    """
    Preconfigured shell command runner that preserves PyCI's shell result contract.
    """
    cwd: str | Path | None = None
    raw_output: bool = False
    quiet: bool = False
    check: bool = True
    wsl: bool = True

    def with_options(
        self,
        *,
        cwd: str | Path | None | object = _UNSET,
        raw_output: bool | object = _UNSET,
        quiet: bool | object = _UNSET,
        check: bool | object = _UNSET,
        wsl: bool | object = _UNSET,
    ) -> "ShellCommandRunner":
        updates = {}
        if cwd is not _UNSET:
            updates["cwd"] = cwd
        if raw_output is not _UNSET:
            updates["raw_output"] = raw_output
        if quiet is not _UNSET:
            updates["quiet"] = quiet
        if check is not _UNSET:
            updates["check"] = check
        if wsl is not _UNSET:
            updates["wsl"] = wsl

        return replace(self, **updates) if updates else self

    def __call__(
        self,
        command: str,
        *,
        cwd: str | Path | None | object = _UNSET,
        raw_output: bool | object = _UNSET,
        quiet: bool | object = _UNSET,
        check: bool | object = _UNSET,
        wsl: bool | object = _UNSET,
    ) -> ShellCommandResult:
        return self.run(
            command,
            cwd=cwd,
            raw_output=raw_output,
            quiet=quiet,
            check=check,
            wsl=wsl,
        )

    def run(
        self,
        command: str,
        *,
        cwd: str | Path | None | object = _UNSET,
        raw_output: bool | object = _UNSET,
        quiet: bool | object = _UNSET,
        check: bool | object = _UNSET,
        wsl: bool | object = _UNSET,
    ) -> ShellCommandResult:
        return _run_shell_command(
            command=command,
            cwd=self.cwd if cwd is _UNSET else cwd,
            raw_output=self.raw_output if raw_output is _UNSET else raw_output,
            quiet=self.quiet if quiet is _UNSET else quiet,
            check=self.check if check is _UNSET else check,
            wsl=self.wsl if wsl is _UNSET else wsl,
        )


shell_command_runner = ShellCommandRunner()
quiet_shell_command_runner = ShellCommandRunner(quiet=True, wsl=False)
probe_shell_command_runner = ShellCommandRunner(quiet=True, check=False, wsl=False)


def run_shell_command(
    command: str,
    cwd: str | Path | None = None,
    raw_output: bool = False,
    quiet: bool = False,
    check: bool = True,
    wsl: bool = True,
) -> ShellCommandResult:
    """
    Executes the given command in a subprocess.

    Notes:
        If run on a Windows machine, will use WSL for command execution.

    Args:
        command: Command to execute.
        cwd: Working directory to execute the command in. Defaults to current working directory.
        raw_output: If set to True, the output from the executed command will be printed as is.
            If set to False, the output will be printed with pretty formatting through the global Rich Console.
            Has effect only with 'quiet' set to False.
        quiet: If set to True, command output will be suppressed.
        check: If set to True (default), an exception will be thrown if the executed command exits with a non-zero exit code.
        wsl: If set to True (default) and running on Windows, the provided command will be run in WSL.

    Returns:
        Command result with exit code and captured output.

    Raises:
        RuntimeError:
            if the executed command completes with a non-zero exit code.
    """
    return shell_command_runner(
        command,
        cwd=cwd,
        raw_output=raw_output,
        quiet=quiet,
        check=check,
        wsl=wsl,
    )


def _run_shell_command(
    command: str,
    cwd: str | Path | None,
    raw_output: bool,
    quiet: bool,
    check: bool,
    wsl: bool,
) -> ShellCommandResult:
    # lazy-initialize CI console if using pretty output
    global _output_console
    if (not quiet) and (_output_console is None):
        _output_console = rich.get_console()

    # print header if using pretty output
    if (not quiet) and (not raw_output):
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
        quiet=quiet,
        check=False,
        wsl=wsl,
        on_line=print_command_output_line,
    )
    result = _convert_comrun_result(runner(command))

    if result.is_failed and check:
        if quiet:
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
    if (not quiet) and (not raw_output):
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
