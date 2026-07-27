"""
CLI command for adding autocompletion for this tool to the current shell.
"""
import os
import re
import shutil
from pathlib import Path

import rich
import rich_click as click  # type: ignore
from click import Context, UsageError
from rich import print  # type: ignore
from rich.theme import Theme

AUTOCOMPLETION_COMMANDS_FILE_NAME = "autocompletion_commands"
AUTOCOMPLETION_COMMANDS_FILE_PATH = Path(__file__).parent / AUTOCOMPLETION_COMMANDS_FILE_NAME

CURRENT_SHELL_PATH = Path(os.environ.get("SHELL", ""))
CURRENT_SHELL_NAME = CURRENT_SHELL_PATH.name.lower()

RICH_THEME = Theme({
    "shell": "color(44)",
    "command": "color(184)",
    "path": "color(40)",
})


@click.command(hidden=True, no_args_is_help=True)
@click.pass_context
@click.option("--generate", "-g",
              is_flag=True,
              help=f"Generate autocompletion scripts for this CLI.")
@click.option("--install/--uninstall", "-i/-u",
              default=None,
              help=f"Add or remove autocompletion for this CLI in {CURRENT_SHELL_NAME} ({CURRENT_SHELL_PATH}).\n"
                   f"This will update the corresponding shell files of the current user.")
def autocompletion(ctx: Context, generate: bool, install: bool) -> None:
    """
    Manage autocompletion for this CLI.
    """
    with rich.get_console().use_theme(RICH_THEME):
        # get command name from context
        command_name_from_context = ctx.find_root().info_name

        # get command name(s) from file
        command_names_from_file = read_command_names_from_file(AUTOCOMPLETION_COMMANDS_FILE_PATH)

        # merge all command names
        command_names = sorted(list(set(command_names_from_file + [command_name_from_context])))

        # manage autocompletion for each command
        for command_name in command_names:
            manage_autocompletion_for_command(command_name, generate, install)


def read_command_names_from_file(file_path: Path) -> list[str]:
    """
    Reads the list of command names line-by-line from the given file.

    Notes:
        This will ignore invalid lines (empty lines, lines containing only whitespace etc.).

    Args:
        file_path: Path to the file to read the command names from.

    Returns:
        List of command names.
    """
    if not AUTOCOMPLETION_COMMANDS_FILE_PATH.exists():
        # no file – no command names
        return []

    command_names = []
    valid_command_name_regex = re.compile(r"(^\w[\w-]+$)")  # only letters, numbers, underscores and dashes

    with file_path.open("r") as file:
        for line in file.readlines():
            command_name = line.strip()
            is_valid_command_name = valid_command_name_regex.match(command_name)
            if is_valid_command_name:
                command_names.append(command_name)

    return command_names


def manage_autocompletion_for_command(command_name: str, generate: bool, install: bool) -> None:
    """
    Manages autocompletion for the given Click command.

    Args:
        command_name: Name of the command to manage autocompletion for.
        generate: If True, autocompletion scripts will be generated.
        install: If True, autocompletion will be installed to the current shell RC file; if False, it will be uninstalled.
    """

    # get autocompletion script info for current shell
    autocompletion_scripts_directory_path = Path(__file__).parent / "autocompletion_scripts"
    current_autocompletion_script_path = (autocompletion_scripts_directory_path / f".{command_name}-complete.{CURRENT_SHELL_NAME}")

    if generate or install:
        generate_autocompletion_script(CURRENT_SHELL_NAME, command_name, current_autocompletion_script_path)

    managing_installation = install is not None
    if managing_installation:
        if CURRENT_SHELL_NAME in ("bash", "zsh"):
            manage_installation_for_bash_or_zsh(
                command_name, Path.home(), current_autocompletion_script_path, CURRENT_SHELL_NAME, install
            )
        elif CURRENT_SHELL_NAME == "fish":
            manage_installation_for_fish(
                command_name, Path.home(), current_autocompletion_script_path, install
            )
        else:
            raise UsageError("This command only supports installing autocompletion for bash, zsh and fish shells. "
                             f"Current shell is {CURRENT_SHELL_NAME} ({CURRENT_SHELL_PATH}).")


def generate_autocompletion_script(shell_type: str, command_name: str, output_path: Path) -> None:
    """
    Generates autocompletion scripts for the given shell type in the given location.

    Args:
        shell_type: Type of the shell to generate the scripts for (bash, zsh, fish etc.).
        command_name: Name of the command nto generate autocompletions for.
        output_path: Path to the output script file.
    """
    os.makedirs(output_path.parent, exist_ok=True)

    command_name_upper_snake = command_name.upper().replace("-", "_")
    os.system(f'_{command_name_upper_snake}_COMPLETE={shell_type}_source {command_name} > "{output_path}"')

    word = "Generated" if output_path.exists() else "Re-generated"
    print(f':sparkles: {word} [shell]{shell_type}[/] completion file for command [command]{command_name}[/] at "{output_path}".')


def manage_installation_for_bash_or_zsh(
        command_name: str,
        user_home_path: Path,
        autocomplete_path: Path,
        shell_type: str = CURRENT_SHELL_NAME,
        install: bool = True
) -> None:
    """
    Installs or uninstalls autocompletions for bash or zsh shells.

    Args:
        command_name: Name of the CLI tool.
        user_home_path: Path to the home directory of the user for whom to install the autocompletions.
        autocomplete_path: Path to the autocompletion script.
        shell_type: Type of the shell (bash or zsh).
        install: If True, autocompletion will be installed; if False, it will be uninstalled.
    """
    assert shell_type in ("bash", "zsh")

    rc_file_path = user_home_path / f".{shell_type}rc"
    autocompletion_string = (f'\n# Autocompletion for {command_name}\n'
                             f'. "{autocomplete_path}"\n')

    with rc_file_path.open("r") as file:
        rc_file_content = file.read()

    if install:
        if autocompletion_string in rc_file_content:
            print(f":zzz: Autocompletion for [command]{command_name}[/] is already installed in your "
                  f"[path]{rc_file_path.name}[/] file. Skipping.")
            return

        # Add entry to the user's rc file
        with rc_file_path.open("a+") as file:
            file.write(f"{autocompletion_string}")

        print(f":white_check_mark: Added [command]{command_name}[/] autocompletion entry from your "
              f"[path]{rc_file_path.name}[/] file.")
    else:
        if autocompletion_string not in rc_file_content:
            print(f":zzz: There is no autocompletion for [command]{command_name}[/] installed in your "
                  f"[path]{rc_file_path.name}[/] file. Skipping.")
            return

        # Remove entry from the user's rc file
        rc_file_content = rc_file_content.replace(autocompletion_string, "")
        with rc_file_path.open("w") as file:
            file.write(rc_file_content)

        print(f":white_check_mark: Removed [command]{command_name}[/] autocompletion entry from your "
              f"[path]{rc_file_path.name}[/] file.")


def manage_installation_for_fish(
        command_name: str,
        user_home_path: Path,
        autocomplete_path: Path,
        install: bool = True
) -> None:
    """
    Installs or uninstalls autocompletions for fish shell.

    Args:
        command_name: Name of the CLI tool.
        user_home_path: Path to the home directory of the user for whom to install the autocompletions.
        autocomplete_path: Path to the autocompletion script.
        install: If True, autocompletion will be installed; if False, it will be uninstalled.
    """
    destination_path = user_home_path / f".config/fish/completions/{command_name}.fish"

    if install:
        # Add autocompletion script to fish config directory
        shutil.copyfile(
            autocomplete_path,
            destination_path,
        )

        print(f":white_check_mark: Added [command]{command_name}[/] autocompletion script to your [shell]fish[/] config "
              f"directory.")
    else:
        if not destination_path.exists():
            print(f":zzz: Autocompletion for [command]{command_name}[/] is not present in your fish config directory. "
                  f"Skipping.")
            return

        # Remove autocompletion script from fish config directory
        destination_path.unlink()

        print(f":white_check_mark: Removed [command]{command_name}[/] autocompletion script from your [shell]fish[/] "
              f"config directory.")
