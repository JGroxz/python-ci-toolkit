# AGENTS.md

## Project Intent

Python CI Toolkit is being restored as a portable Python CI/CD toolkit suitable for personal, team, and future OSS use.

Prefer portable defaults. Do not introduce assumptions about private repositories, private SSH keys, private CI runners, private package indexes, or developer machine state.

## Environment

This project uses `uv` for environment and dependency management.

Common commands:

- Lock dependencies: `uv lock`
- Install/sync dependencies: `uv sync`
- Run commands: `uv run <command>`
- Run collection: `uv run pytest --collect-only`
- Run tests: `uv run pytest`
- Build package: `uv build`

The project uses PEP 621 `[project]` metadata in `pyproject.toml` and Hatchling as the build backend. Do not reintroduce Poetry metadata or `poetry.lock` unless explicitly requested.

## Structure

This repository currently uses a flat package layout:

- Package source lives in `python_ci_toolkit/`
- Tests live in `tests/`
- Project metadata lives in `pyproject.toml`
- README lives at `README.md`

Do not migrate to `src/` layout as part of unrelated work.

## Code Style

Follow the existing straightforward Python style.

- Prefer `pathlib.Path` for filesystem paths.
- Prefer explicit, small functions over broad abstractions.
- Keep edits scoped to the issue being worked.
- Use type annotations for new or modified function signatures when practical.
- This project supports Python `>=3.10`; do not use syntax that requires newer Python versions.
- Use f-strings for string formatting, including logs.
- Keep comments rare and useful. Add a short comment when a multi-step block would otherwise hide intent.
- Preserve existing public behavior unless the task explicitly changes it.

## Imports

Use relative imports for project-internal code when editing existing package modules.

Be careful in nested packages under `python_ci_toolkit.actions`; several historical imports pointed at non-existent modules after package moves.

Current logging package location:

- `python_ci_toolkit.actions.logging`

Do not import from historical/non-existent modules such as:

- `python_ci_toolkit.logging`

After import/package changes, run:

```bash
uv run pytest --collect-only
```

## Testing

This project uses `pytest`.

Tests must be portable. They should not require:

- private Git remotes
- private SSH keys
- `~/.ssh/id_rsa`
- network access
- private CI runner images
- machine-specific cache state

For Git retrieval behavior, prefer local temporary Git repositories created with pytest fixtures over external remotes or pure mocks. This keeps coverage realistic while staying portable.

Use `tmp_path` or fixtures for filesystem state.

## CLI And Output

The current CLI stack uses `rich-click` and Rich. Continue using the existing CLI/output patterns unless there is a deliberate migration issue.

## Git And Worktree Safety

- Do not stage or commit unless explicitly instructed.
- Do not reset, checkout, or revert user changes unless explicitly instructed.
- Do not pop, drop, or apply stashes unless explicitly instructed.
- Check `git status --short --branch` before and after edits.
- Keep commits, when requested, small and semantically focused.
- Do not add agent signatures to commits.

## Agent Behavior

When a file you previously edited has been modified externally, compare the changes first. Preserve compatible user edits and build on top of the updated file.

If a task touches packaging, imports, or test collection, verify with the relevant `uv` commands before reporting success.

Track project work in Linear when the user has already assigned or referenced a Linear issue.
