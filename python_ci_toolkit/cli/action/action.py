from __future__ import annotations

import logging
import os
import re
import sys
from typing import List

import rich_click as click
from click import Context, Argument, Parameter
from click.shell_completion import CompletionItem

from python_ci_toolkit.cli.action.list import list_actions_command
from .find import find_actions_command, list_available_actions

ACTION_IDENTIFIER_REGEX = re.compile(r'^\w+(?:@[\w\.\/\-\+]+)?', re.UNICODE)


def _validate_action_identifier(ctx: Context, param: Argument, value: str) -> str:
    from ...actions.constants import ACTION_VERSION_SEPARATOR

    action_identifier = str(value)

    if not ACTION_IDENTIFIER_REGEX.fullmatch(value):
        possible_match = ACTION_IDENTIFIER_REGEX.match(value)

        suggestion_string = ("\n"
                             "\n"
                             f"Did you mean '{possible_match.group()}'?") if possible_match else ""

        raise click.BadParameter(
            f"'{value}'\n\n"
            f"Action identifier must be in the format ACTION_NAME[{ACTION_VERSION_SEPARATOR}ACTION_VERSION], where:\n"
            f" - ACTION_NAME can only contain alphanumeric characters and underscores.\n"
            f" - ACTION_VERSION can be either:\n"
            f"     - 'local' (for local actions)\n"
            f"     - any valid Git tag or branch name (for remote actions){suggestion_string}"
        )

    return action_identifier


def _complete_action_identifier(ctx: Context, param: Argument, incomplete: str):
    # disable logging (to avoid messages in the console during autocompletion)
    logging.root.disabled = True

    available_actions_metadata = list_available_actions()

    # filter out the actions based on the incomplete string
    filtered_actions_metadata = [a for a in available_actions_metadata if a.name.startswith(incomplete)]

    # enable logging again
    logging.root.disabled = False

    return [CompletionItem(a.name, help=a.description)
            for a in filtered_actions_metadata]


def _intercept_help_for_action(ctx: Context, param: Parameter, value: str) -> None:
    """
    Intercepts the --help option and prints the help message for the action command instead of the default one.
    """
    if not value or ctx.resilient_parsing:
        return

    logging.debug(f"Intercepted help command for action.")

    # find index of the last preceding command
    last_command = ctx.command_path.split(" ")[-1]
    last_command_index = 0
    for last_command_index, arg in enumerate(sys.argv):
        arg = str(arg)
        if (arg == last_command) or arg.endswith(f"/{last_command}"):
            break

    # find index of the help flag
    help_flag_index = 0
    for help_flag_index, arg in enumerate(sys.argv):
        arg = str(arg)
        if (arg == "--help") or (arg == "-h"):
            break

    # find index of the action identifier
    action_identifier_index = 0
    for action_identifier_index, arg in enumerate(sys.argv):
        if action_identifier_index <= last_command_index:
            # action identifier is never before the last preceding command
            continue

        arg = str(arg)
        if not arg.startswith("-"):
            break

    # check if the help flag comes after the action identifier
    if help_flag_index > action_identifier_index:
        # help flag belongs to the action itself, skip
        return
    else:
        # help flag belongs to the command
        click.echo(ctx.get_help(), color=ctx.color)
        ctx.exit()


@click.command(context_settings=dict(
    ignore_unknown_options=True,
), no_args_is_help=True)
@click.option("--debug",
              is_flag=True,
              help="Enable debug logging.",
              hidden=True)
@click.option("--list", "-l",
              is_flag=True,
              is_eager=True, callback=list_actions_command, expose_value=False,
              help="List all available actions.")
@click.option("--find", "-f",
              is_eager=True, callback=find_actions_command, expose_value=False,
              help="Find available actions based on the provided string and print them to the console.")
@click.option("--help", "-h",
              is_flag=True,
              is_eager=True, callback=_intercept_help_for_action, expose_value=False,
              help="Show this message and exit.")
@click.argument("action_identifier",
                required=1,
                type=str,
                callback=_validate_action_identifier,
                shell_complete=_complete_action_identifier)
@click.argument('action_args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def action(ctx: Context, action_identifier: str, action_args: List[str], debug: bool = False, find: str = None) -> None:
    """
    Execute CI action based on the given ACTION_IDENTIFIER.\n
    Arbitrary arguments can be passed to the action in place of ACTION_ARGS.\n
    \n
    ACTION_IDENTIFIER must be in the format ACTION_NAME[@ACTION_VERSION], where:\n
     - ACTION_NAME can only contain alphanumeric characters and underscores.\n
     - ACTION_VERSION can be either:\n
         - 'local' (for local actions)\n
         - any valid Git tag or branch name (for remote actions)\n
    \n
    Notes:\n
     - If action version is set to 'local', utility will look for the action file in '.ci/actions' folder inside your CI project's root directory.\n
     - Any arguments passed after the action name/tag will be passed to the executed action script.\n
    """

    # initialize logging
    from ...actions.logging import configure_ci_logging
    is_debug_enabled = (debug or os.environ.get("DEBUG", None))
    configure_ci_logging("DEBUG" if is_debug_enabled else "INFO")

    from ...actions import run_ci_action
    from ...actions.constants import ACTION_VERSION_SEPARATOR
    from ...actions.exceptions import ActionRuntimeError
    from ...actions.retrieval.exceptions import ActionRetrievalError

    # version can be included in the first argument, separated from the action name by a semicolon
    if ACTION_VERSION_SEPARATOR in action_identifier:
        split_by_first_colon = action_identifier.split(ACTION_VERSION_SEPARATOR, 1)
        action_name = split_by_first_colon[0]
        action_version = split_by_first_colon[1]
    else:
        action_name = action_identifier
        action_version = None

    try:
        run_ci_action(action_name, action_version, action_args)
    except (ActionRetrievalError, ActionRuntimeError) as error:
        click_error = click.ClickException(str(error))
        click_error.exit_code = error.exit_code
        raise click_error from error


if __name__ == '__main__':
    action()
