import tempfile
from pathlib import Path

ci_temp_files_root_directory: Path = Path(tempfile.gettempdir()) / "python-ci-toolkit" / "temp"
"""
Common root directory of all temporary file directories used by the toolkit.

Notes:
    For internal use only.
"""

ci_temp_files_shared_directory = ci_temp_files_root_directory / "shared"
"""
Common root directory of all temporary file directories used by the toolkit.

Notes:
    For internal use only.
"""

ci_temp_files_projects_root_directory = ci_temp_files_root_directory / "project-specific"
"""
Common root directory of all project-specific temporary file directories used by the toolkit.

Notes:
    For internal use only.
"""
