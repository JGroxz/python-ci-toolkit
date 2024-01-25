import tempfile
from pathlib import Path

from rich import print

from python_ci_toolkit.environment.paths import ci_paths


def test_project_root_directory_path():
    project_root = ci_paths.project_root

    print(f"Project root: '{project_root}'")

    assert project_root == Path(__file__).parent.parent.parent


def test_temp_directory_path():
    print(f"Python-provided temp directory: {tempfile.gettempdir()}")

    from python_ci_toolkit.environment.paths.internal import ci_temp_files_root_directory, ci_temp_files_shared_directory, ci_temp_files_projects_root_directory
    print(f"Root temp directory:      '{ci_temp_files_root_directory}'")
    print(f"Shared temp directory:    '{ci_temp_files_shared_directory}'")
    print(f"Projects temp directory:  '{ci_temp_files_projects_root_directory}'")

    from python_ci_toolkit.environment import ci_paths
    print(f"Project's temp directory: '{ci_paths.temp_files_directory}'")

    # from python_ci_toolkit.environment import ci_temp_files_directory_relative
    # print(f"Project's temp directory (relative): '{ci_temp_files_directory_relative}'")
    #
    # from python_ci_toolkit.environment import ci_project_root
    # assert ci_temp_files_directory.samefile(ci_project_root / ci_temp_files_directory_relative), \
    #     "Relative temp CI directory path does not point to the same directory as the absolute temp CI directory path."
