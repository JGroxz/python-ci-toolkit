"""
Utility functions for running shell commands from Python.
"""

import os
import shlex
import subprocess


def run_shell_command(command: str, cwd: str = os.getcwd(), silence_output: bool = False) -> int:
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
    args = shlex.split(command)
    process = subprocess.Popen(args, stdout=(subprocess.DEVNULL if silence_output else subprocess.PIPE), cwd=cwd)
    return_code = process.wait()

    return return_code
