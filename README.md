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
precedence over `.ci/pyci.toml`. For SSH remote URLs, provide
`PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY` or rely on the local default SSH key only
after explicitly configuring an SSH action repository.
