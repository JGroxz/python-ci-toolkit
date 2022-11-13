import os
import sys

from python_ci_toolkit import actions, python


def test_run_action_git() -> None:
    os.environ["SECRETS_FILE_NAME"] = "secrets"

    print(sys.argv)
    sys.argv.append("build_dockers:action/build_dockers")
    actions.actions.cli()


def test_run_action_local() -> None:
    sys.argv.append("build_dockers:local")
    actions.actions.cli()


if __name__ == '__main__':
    test_run_action_git()
    # test_run_action_local()
    # test_build_dockers()
