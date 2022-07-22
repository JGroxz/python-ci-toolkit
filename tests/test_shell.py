import rich
from rich.console import Console
from rich.panel import Panel
import rich.pretty

from python_ci_toolkit.shell import run_shell_command

test_console = Console()
print = test_console.print


def run():
    aws_domain = "pyci"
    aws_domain_owner = "755432789552"
    aws_region = "eu-west-1"

    error, output = run_shell_command(
        f"aws codeartifact get-authorization-token --domain {aws_domain} --domain-owner {aws_domain_owner} --query authorizationToken --output text")

    test_command = "ls -a"
    test_cwd = "../"

    def print_run_result(run_result):
        print(Panel(rich.pretty.Pretty(run_result, expand_all=True), title=f"Result", title_align="left", border_style="light_goldenrod1"))

    print(f"Running '{test_command}' openly:", style="italic light_goldenrod1")
    result = run_shell_command(test_command, test_cwd)
    print_run_result(result)

    print()

    print(f"Running '{test_command}' silently:", style="italic light_goldenrod1")
    result = run_shell_command(test_command, test_cwd, silence_output=True)
    print_run_result(result)


if __name__ == '__main__':
    run()
