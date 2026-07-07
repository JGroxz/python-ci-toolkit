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
