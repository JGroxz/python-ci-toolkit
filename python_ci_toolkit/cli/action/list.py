from click import Context, Argument
from rich import print, box
from rich.panel import Panel
from rich.table import Table

from python_ci_toolkit.cli.action.find import ActionMetadata, list_available_actions


def print_available_actions(actions_metadata: list[ActionMetadata]) -> None:
    """
    Prints the given list of actions metadata to the console.
    """
    # panel title
    title = f"Available CI actions ({len(actions_metadata)} in total)"

    # prepare display grid
    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(header="Name", style="green")
    grid.add_column(header="Description")

    for metadata in actions_metadata:
        grid.add_row(
            metadata.name,
            metadata.description,
        )
    panel_content = grid

    # print panel
    panel = Panel(
        panel_content,
        box=box.ROUNDED, border_style="blue",
        title=title, title_align="left",
        expand=False, highlight=False
    )

    print(panel)


def list_actions_command(ctx: Context, param: Argument, value: str) -> None:
    if not value or ctx.resilient_parsing:
        return

    from python_ci_toolkit.actions.utils.logging import loading_animation
    with loading_animation(f"Listing available actions"):
        matches = list_available_actions()

    print_available_actions(matches)

    # print a tip about how to use the action
    a_lot_of_actions = len(matches) > 10
    if a_lot_of_actions:
        # print a tip about searching for actions
        root_command_name = ctx.command_path
        find_flag = "--find"
        panel_content = f"Use [yellow]'{root_command_name} {find_flag}'[/] to filter available actions by their name or description."
        title = "💡Tip"
        panel = Panel(
            panel_content,
            box=box.ROUNDED, border_style="yellow",
            title=title, title_align="left",
            expand=True, width=80, highlight=False
        )
        print(panel)

    ctx.exit(0)
