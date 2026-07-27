# Python CI Toolkit

Collection of tools useful in our CI/CD pipelines based on Python.

```bash
pip install --upgrade python-ci-toolkit
```

## Development

This project uses `uv` for dependency management and local commands.

```bash
uv sync
uv run pytest
uv build
```

The GitHub Actions workflows in this repository use public GitHub-hosted runners
and do not require private runner images or private reusable workflow
repositories.

## Action Sources

PyCI can run local actions from `.ci/actions` without any remote repository
configuration.

Remote action repositories are optional and disabled by default. To enable
remote actions for a project, configure `.ci/pyci.toml`:

```toml
[actions]
remote_repository = "https://github.com/example/python-ci-actions.git"
```

`PYTHON_CI_ACTIONS_GIT_REPO_URL` can be used as a CI-time override and takes
precedence over `.ci/pyci.toml`.

### Remote Repository Authentication

| Remote URL type | PyCI behavior |
| --- | --- |
| HTTPS | No PyCI-managed credentials; Git uses public access or configured credential helpers. |
| Local path/file URL | No PyCI-managed credentials; Git reads from the local repository. |
| SSH | No PyCI-managed credentials; Git uses ambient SSH configuration such as an agent, deploy key, or user SSH config. |

PyCI does not manage remote repository credentials directly. Configure Git or
SSH authentication in the current environment before invoking PyCI; the
configured remote action repository must already be fetchable by Git.

## Action Runtime

Actions run in isolated uv subprocesses. An action can declare dependencies in
an adjacent `requirements.txt`; those packages are available to that action
without being installed into PyCI's environment or the caller's project.

Action entrypoints continue to use an `action()` function. Return values do not
cross the subprocess boundary. Write small structured outputs as JSON through
the `set_action_output` helper:

```python
from python_ci_toolkit.actions import set_action_output


def action() -> None:
    set_action_output("artifact_path", "dist/package.whl")
    set_action_output("metadata", {"publish": True})
```

Callers receive those values through `ActionOutput.values`. Each invocation
also exposes the JSON output file path as `PYCI_ACTION_OUTPUT`.

See [`docs/architecture/isolated-action-runtime.md`](docs/architecture/isolated-action-runtime.md)
for the process, failure, nesting, and cache contracts.
