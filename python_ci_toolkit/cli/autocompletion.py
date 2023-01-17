"""
CLI command for adding autocompletion for this tool to the current shell.
"""
import shutil
from pathlib import Path

from click import Context, UsageError

import rich_click as click  # type: ignore
import os
from rich import print  # type: ignore
import sys

AUTOCOMPLETION_COMMAND_BASE_NAME = "pyci-annotation-utilities"

CURRENT_SHELL_PATH = Path(os.environ.get("SHELL", ""))
CURRENT_SHELL_NAME = CURRENT_SHELL_PATH.name.lower()


@click.command(hidden=True)
@click.pass_context
@click.option("--generate", "-g",
              is_flag=True,
              help=f"Generate autocompletion scripts for this CLI.")
@click.option("--install/--uninstall",
              default=None,
              help=f"Add or remove autocompletion for this CLI in {CURRENT_SHELL_NAME} ({CURRENT_SHELL_PATH}).\n"
                   f"This will update the corresponding shell files of the current user.")
def autocompletion(ctx: Context, generate: bool, install: bool) -> None:
    # if none of the flags are passed, show help
    if not any(ctx.params.values()) and (install is None):
        ctx.get_help()
        sys.exit()

    # get autocompletion script info for current shell
    autocompletion_scripts_directory_path = Path(__file__).parent / "autocompletion_scripts"
    root_command_name = ctx.find_root().info_name
    current_autocompletion_script_path = (autocompletion_scripts_directory_path
                                          / f".{root_command_name}-complete.{CURRENT_SHELL_NAME}")

    if generate or install:
        generate_autocompletion_script(CURRENT_SHELL_NAME, root_command_name, current_autocompletion_script_path)

    managing_installation = install is not None
    if managing_installation:
        if CURRENT_SHELL_NAME in ("bash", "zsh"):
            manage_installation_for_bash_or_zsh(
                root_command_name, Path.home(), current_autocompletion_script_path, CURRENT_SHELL_NAME, install
            )
        elif CURRENT_SHELL_NAME == "fish":
            manage_installation_for_fish(
                root_command_name, Path.home(), current_autocompletion_script_path, install
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
    print(f':sparkles: Generated [cyan]{shell_type}[/] completion file at "{output_path}".')


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
            print(f":zzz: Autocompletion for [cyan]{command_name}[/] is already installed in your "
                  f"[cyan]{rc_file_path.name}[/] file. Skipping.")
            sys.exit()

        # Add entry to the user's rc file
        with rc_file_path.open("a+") as file:
            file.write(f"{autocompletion_string}")

        print(f":white_check_mark: Added [cyan]{command_name}[/] autocompletion entry from your "
              f"[cyan]{rc_file_path.name}[/] file.")
    else:
        if autocompletion_string not in rc_file_content:
            print(f":zzz: There is no autocompletion for [cyan]{command_name}[/] installed in your "
                  f"[cyan]{rc_file_path.name}[/] file. Skipping.")
            sys.exit()

        # Remove entry from the user's rc file
        rc_file_content = rc_file_content.replace(autocompletion_string, "")
        with rc_file_path.open("w") as file:
            file.write(rc_file_content)

        print(f":white_check_mark: Removed [cyan]{command_name}[/] autocompletion entry from your "
              f"[cyan]{rc_file_path.name}[/] file.")


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

        print(f":white_check_mark: Added [cyan]{command_name}[/] autocompletion script to your [cyan]fish[/] config "
              f"directory.")
    else:
        if not destination_path.exists():
            print(f":zzz: Autocompletion for [cyan]{command_name}[/] is not present in your fish config directory. "
                  f"Skipping.")
            sys.exit()

        # Remove autocompletion script from fish config directory
        destination_path.unlink()

        print(f":white_check_mark: Removed [cyan]{command_name}[/] autocompletion script from your [cyan]fish[/] "
              f"config directory.")
