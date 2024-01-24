"""
Dummy action that does nothing and is used in tests of the CI Toolkit package.
"""
import shlex

from python_ci_toolkit.actions import run_ci_action
from python_ci_toolkit.actions.datatypes import ActionOutput


def action():
    output: ActionOutput = run_ci_action("sleep", "local", args=shlex.split("--duration 10"))

    print(f"Output value of sleep action: {output.value}")
    return


if __name__ == '__main__':
    action()
