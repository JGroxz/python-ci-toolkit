# Isolated Action Runtime

## Status

This document defines the target action runtime introduced by OS-43.

## Process Boundary

PyCI actions run in subprocesses. The parent PyCI process remains responsible
for action retrieval, runtime preparation, progress reporting, and translating
the child process result into PyCI datatypes and errors.

The child process uses the same Python version and PyCI version as the parent.
It receives the action's dependencies in a fresh uv environment:

```text
uv run --isolated --no-project \
  --python <parent-python> \
  <exact-pyci-runtime> \
  [--with-requirements <action-directory>/requirements.txt] \
  --module python_ci_toolkit.actions.bootstrap \
  <action-script> <action-name> <action-version> [action-arguments...]
```

The bootstrap imports the action module and calls its `action()` entrypoint.
Click entrypoints continue to run with `standalone_mode=False`.

## Dependency Declarations

An adjacent `requirements.txt` remains the supported action dependency
declaration in the first isolated runtime version. PyCI does not install those
requirements into its own interpreter or the caller's project environment.

PEP 723 metadata and action-local `pyproject.toml` files are not part of this
version. They can be evaluated later without changing the process boundary.

The isolated environment contains both the action requirements and the exact
PyCI runtime. Dependency conflicts between those two sets fail resolution
without changing the parent environment.

## Environment And Caching

`uv run --isolated` creates a fresh ephemeral environment for each action
invocation. PyCI does not maintain a second persistent environment cache.
Package downloads, built distributions, and resolver data use uv's normal
cache.

A future persistent environment cache would need a key containing at least:

- cache schema version
- Python implementation and version
- PyCI runtime identity
- dependency declaration contents
- resolver-affecting configuration

Action source or Git ref changes do not invalidate a dependency environment
unless they change one of those inputs.

## Action Arguments

The child receives the requested action arguments through `sys.argv`:

```python
[action_name, *action_arguments]
```

Nested actions use the same rule. The active action stack is propagated to
child processes so recursive action calls remain blocked.

## Structured Outputs

Each invocation receives a unique output file path through:

```text
PYCI_ACTION_OUTPUT
```

The file contains one UTF-8 JSON object. The object must have string keys and
JSON-compatible values. An action may write it directly or call
`set_action_output(name, value)`.

Example:

```json
{
  "version": "0.34.0",
  "artifact_path": "dist/python_ci_toolkit-0.34.0.whl"
}
```

The parent parses the file after a successful child exit. Invalid JSON or a
non-object top-level value is an action runtime error.

Large values remain workspace files or CI artifacts. The output object should
contain paths or metadata for those files instead of their contents.

## Result Contract

Successful execution returns an `ActionOutput` containing:

- parsed JSON values
- exit code
- captured stdout
- captured stderr

The Python value returned by `action()` is ignored. Arbitrary Python objects do
not cross the process boundary.

The bootstrap writes a separate internal result envelope. It distinguishes:

- successful action completion
- a missing `action()` entrypoint
- an exception raised while importing or running the action
- `SystemExit`

If uv or the bootstrap fails before producing that envelope, the parent raises
an isolated runtime startup error. Child exception types are not reconstructed
in the parent; action failures become structured `ActionProcessError`
instances.

## Nested Actions

`run_ci_action(...)` remains available inside an action because the exact PyCI
runtime is installed in every child environment. A nested action receives its
own isolated environment and `PYCI_ACTION_OUTPUT` file.

Nested actions communicate through `ActionOutput`, logs, exit status, and
workspace files. Parent actions cannot receive arbitrary Python return values
or catch the child's original exception type.

## Compatibility

Preserved:

- `action()` entrypoints
- Click-wrapped action entrypoints
- action command-line arguments
- adjacent `requirements.txt` files
- imports from `python_ci_toolkit`
- local and remote action retrieval
- nested `run_ci_action(...)` calls
- live stdout and stderr

Changed:

- requirements no longer mutate the current Python environment
- action modules no longer share process-global state with the caller
- `action()` return values are ignored
- `ActionOutput.value` is replaced by `ActionOutput.values`
- child exceptions cross the boundary as PyCI runtime errors

## Trust Boundary

Isolation protects dependency and process state; it is not a security sandbox.
Actions remain trusted executable code with access to inherited credentials,
the project workspace, and the network unless the surrounding CI environment
restricts them.
