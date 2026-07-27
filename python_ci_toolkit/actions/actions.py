"""
Provides functions to retrieve and run CI actions based on Python scripts.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .constants import ACTION_VERSION_DEFAULT_REMOTE_STRING, ACTION_VERSION_LOCAL_STRING
from .datatypes import ActionOutput
from .exceptions import RecursiveActionError
from .logging import get_logger
from .retrieval import retrieve_ci_action_script
from .retrieval.sources.git.caching import reset_action_cache_timestamp
from .retrieval.sources.git.cloning import get_remote_action_repo
from .runtime import read_action_stack_from_environment, run_action_process
from .utils import Stopwatch
from .utils.logging import (
    get_action_display_name,
    get_action_progress_message,
    loading_animation,
    print_action_run_end_failure,
    print_action_run_end_success,
    print_action_run_start,
)
from ..environment.bootstrap import prepare_ci_project_runtime

logger = get_logger(__name__)

_running_actions_stack: list[tuple[str, str]] = read_action_stack_from_environment()


def _is_action_running(action_name: str) -> bool:
    return any(running_action_name == action_name for running_action_name, _ in _running_actions_stack)


@dataclass(frozen=True)
class _ActionRuntimeContext:
    action_name: str
    action_version: str
    action_display_name: str
    is_nested: bool


@contextmanager
def _action_runtime_context(
    action_name: str,
    action_version: str | None = None,
) -> Iterator[_ActionRuntimeContext]:
    action_version = action_version or ACTION_VERSION_DEFAULT_REMOTE_STRING
    action_stack_identifier = (action_name, action_version)

    if _is_action_running(action_name):
        raise RecursiveActionError(action_name)

    _running_actions_stack.append(action_stack_identifier)
    try:
        yield _ActionRuntimeContext(
            action_name=action_name,
            action_version=action_version,
            action_display_name=get_action_display_name(action_name, action_version),
            is_nested=(len(_running_actions_stack) > 1),
        )
    finally:
        if action_stack_identifier in _running_actions_stack:
            _running_actions_stack.remove(action_stack_identifier)


def _retrieve_action_script(runtime_context: _ActionRuntimeContext) -> tuple[Path, str]:
    logger.debug(f"Locating action '{runtime_context.action_display_name}'...")
    action_script_path, action_source = retrieve_ci_action_script(
        runtime_context.action_name,
        runtime_context.action_version,
    )
    logger.debug(f"Located action '{runtime_context.action_display_name}' at {action_source}.")
    return action_script_path, action_source


def _run_action_script(
    action_script_path: Path,
    runtime_context: _ActionRuntimeContext,
    args: list[str] | None,
) -> ActionOutput:
    with (
        loading_animation(get_action_progress_message(runtime_context.action_display_name, "Running")),
        Stopwatch() as run_stopwatch,
    ):
        try:
            action_output = run_action_process(
                action_script_path=action_script_path,
                action_name=runtime_context.action_name,
                action_version=runtime_context.action_version,
                args=list(args or []),
                action_stack=_running_actions_stack.copy(),
            )
        except BaseException as error:
            print_action_run_end_failure(
                runtime_context.action_display_name,
                run_stopwatch,
                error,
                runtime_context.is_nested,
            )
            raise

    print_action_run_end_success(
        runtime_context.action_display_name,
        run_stopwatch,
        runtime_context.is_nested,
    )
    return action_output


def _reset_remote_action_cache_timestamp(runtime_context: _ActionRuntimeContext) -> None:
    if runtime_context.action_version == ACTION_VERSION_LOCAL_STRING:
        return

    action_repo = get_remote_action_repo()
    if action_repo is None:
        return

    reset_action_cache_timestamp(
        action_repo,
        runtime_context.action_name,
        runtime_context.action_version,
    )


def run_ci_action(
    action_name: str,
    action_version: str | None = None,
    args: list[str] | None = None,
) -> ActionOutput:
    """
    Execute a CI action in an isolated subprocess.

    Nested actions resolve versions using the same rules as top-level actions
    and communicate through ActionOutput rather than Python return values.
    """
    prepare_ci_project_runtime()

    with _action_runtime_context(action_name, action_version) as runtime_context:
        action_script_path, action_source = _retrieve_action_script(runtime_context)

        print_action_run_start(
            runtime_context.action_name,
            runtime_context.action_version,
            action_source,
            runtime_context.is_nested,
        )

        action_output = _run_action_script(action_script_path, runtime_context, args)
        _reset_remote_action_cache_timestamp(runtime_context)
        return action_output
