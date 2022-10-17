from pathlib import Path

from python_ci_toolkit.environment import get_project_root_directory_path


def run():
    project_root = get_project_root_directory_path()

    assert project_root == Path(__file__).parent.parent


if __name__ == '__main__':
    run()
