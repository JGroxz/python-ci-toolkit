import rich
from rich.console import Console
from rich.panel import Panel

from python_ci_toolkit.shell import run_shell_command

test_console = Console()
print = test_console.print  # type: ignore


def run():
    """
    Use this to see both stdout and stderr output being printed to the console when using run_shell_command().
    """

    test_command = f"bash tests/files/shell/slow_print.sh"
    test_cwd = "../../"

    def print_run_result(run_result):
        print(Panel(rich.pretty.Pretty(run_result, expand_all=True), title=f"Result", title_align="left", border_style="light_goldenrod1"))

    print(f"Running '{test_command}' openly:", style="italic light_goldenrod1")
    result = run_shell_command(test_command, test_cwd)
    print_run_result(result)

    print()

    print(f"Running '{test_command}' silently:", style="italic light_goldenrod1")
    result = run_shell_command(test_command, test_cwd, quiet=True)
    print_run_result(result)


if __name__ == '__main__':
    run()
