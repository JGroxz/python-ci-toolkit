from .info import *
from .paths import *
from .variables import *

if ci_environment_type == CiEnvironmentType.GitHubActions:
    # GitHub Actions workspace directory belongs to a different user out-of-the-box,
    # so we have to mark it as safe to be able to run all git commands without errors.
    # See for more info: https://github.com/python-semantic-release/python-semantic-release/issues/560
    run_shell_command(f'git config --global --add safe.directory "{ci_project_root}"', silence_output=True, use_wsl_on_windows=False)
