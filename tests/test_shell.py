import os
from pathlib import Path

import pytest

from python_ci_toolkit.shell import run_shell_command

IS_ON_WINDOWS = (os.name == "nt")


def test_exit_codes():
    assert not IS_ON_WINDOWS, \
        "This test is not tested on Windows (yet)."

    # test a valid command with zero exit code
    command = "true" if (not IS_ON_WINDOWS) else "exit /b 0"
    result = run_shell_command(command, raise_on_error=False)

    assert result.is_successful, \
        f"Command '{command}' must successfully execute with exit code 0."

    # test a valid command with non-zero exit code (without raising an exception
    command = "false" if not IS_ON_WINDOWS else "exit /b 42"
    excepted_exit_code = 1
    result = run_shell_command(command, raise_on_error=False)

    assert result.is_failed, \
        f"Command '{command}' must fail with non-zero exit code."
    assert result.exit_code == excepted_exit_code, \
        f"Command '{command}' must fail with exit code {excepted_exit_code}."

    # test a valid command with non-zero exit code (with raise_on_error)
    with pytest.raises(RuntimeError):
        run_shell_command(command, raise_on_error=True)


def test_cwd():
    """Test that the working directory is being set correctly when running a shell command."""

    # current working directory
    command = "pwd"
    result = run_shell_command("pwd")

    assert result.is_successful, \
        f"Command '{command}' must successfully execute."
    assert result.output_stripped == os.getcwd(), \
        f"Working directory is not correct."

    # custom working directory
    custom_cwd = str(Path(__file__).parent)
    result = run_shell_command(command, cwd=custom_cwd)

    assert result.is_successful, \
        f"Command '{command}' must successfully execute."
    assert result.output_stripped == custom_cwd, \
        f"Custom working directory is not correct."


def test_output():
    """Test that a valid shell command is executed correctly."""

    test_echo_message_lines = [
        "The cake is a lie.",
        "But this test is not.",
    ]
    test_echo_message = "\n".join(test_echo_message_lines)

    command = f"echo '{test_echo_message}'"
    result = run_shell_command(command, use_wsl_on_windows=True)

    assert result.is_successful, \
        f"Command '{command}' must successfully execute."
    assert result.output_stripped == test_echo_message, \
        f"Stripped captured output of the command is not correct."
    assert result.output_lines == test_echo_message_lines, \
        f"Captured output of the command split into lines is not correct."


def test_invalid_command():
    # test an invalid command (it must raise an exception even if raise_on_error is False)
    invalid_command = "invalid_command_that_doesnt_exist --with-invalid-option and-invalid-argument"
    with pytest.raises(FileNotFoundError):
        run_shell_command(invalid_command, raise_on_error=False)
