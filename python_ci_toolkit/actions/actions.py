"""
Provides functions to retrieve and run CI actions based on Python scripts.
"""

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path

from .constants import ACTION_VERSION_DEFAULT_REMOTE_STRING, ACTION_VERSION_LOCAL_STRING
from .datatypes import ActionOutput
from .exceptions import RecursiveActionError
from .events import create_action_event
from .execution import get_action_event_manager
from .logging import get_logger
from .retrieval import retrieve_ci_action_script
from .retrieval.sources.git.caching import reset_action_cache_timestamp
from .retrieval.sources.git.cloning import get_remote_action_repo
from .runtime import read_action_stack_from_environment, run_action_process
from .utils import Stopwatch
from .utils.logging import (
    get_action_display_name,
    get_action_progress_message,
    get_ci_toolkit_version,
    loading_animation,
)
from ..environment import Local, ci_paths, ci_platform
from ..environment.bootstrap import prepare_ci_project_runtime

logger = get_logger(__name__)

_running_actions_stack: list[tuple[str, str]] = read_action_stack_from_environment()
_running_action_run_ids: list[str] = []


def _is_action_running(action_name: str) -> bool:
    return any(running_action_name == action_name for running_action_name, _ in _running_actions_stack)


@dataclass(frozen=True)
class _ActionRuntimeContext:
    action_name: str
    action_version: str
    action_display_name: str
    run_id: str
    parent_run_id: str | None


@contextmanager
def _action_runtime_context(
    action_name: str,
    action_version: str | None = None,
) -> Iterator[_ActionRuntimeContext]:
    action_version = action_version or ACTION_VERSION_DEFAULT_REMOTE_STRING
    action_stack_identifier = (action_name, action_version)
    event_manager = get_action_event_manager()
    run_id = event_manager.new_run_id()
    parent_run_id = event_manager.current_run_id
    if parent_run_id is None and _running_action_run_ids:
        parent_run_id = _running_action_run_ids[-1]

    if _is_action_running(action_name):
        raise RecursiveActionError(action_name)

    _running_actions_stack.append(action_stack_identifier)
    _running_action_run_ids.append(run_id)
    try:
        yield _ActionRuntimeContext(
            action_name=action_name,
            action_version=action_version,
            action_display_name=get_action_display_name(action_name, action_version),
            run_id=run_id,
            parent_run_id=parent_run_id,
        )
    finally:
        if action_stack_identifier in _running_actions_stack:
            _running_actions_stack.remove(action_stack_identifier)
        if run_id in _running_action_run_ids:
            _running_action_run_ids.remove(run_id)


def _retrieve_action_script(runtime_context: _ActionRuntimeContext) -> tuple[Path, str]:
    logger.debug(f"Locating action '{runtime_context.action_display_name}'...")
    action_script_path, action_source = retrieve_ci_action_script(
        runtime_context.action_name,
        runtime_context.action_version,
    )
    logger.debug(f"Located action '{runtime_context.action_display_name}' at {action_source}.")
    return action_script_path, action_source


def _get_action_source_for_display(
    action_script_path: Path,
    action_source: str,
    action_version: str,
) -> str:
    if action_version != ACTION_VERSION_LOCAL_STRING:
        return action_source

    try:
        return action_script_path.relative_to(ci_paths.project_root).as_posix()
    except ValueError:
        return action_source


def _run_action_script(
    action_script_path: Path,
    runtime_context: _ActionRuntimeContext,
    args: list[str] | None,
) -> ActionOutput:
    event_manager = get_action_event_manager()
    progress_context = (
        nullcontext()
        if event_manager.is_relay
        else loading_animation(
            get_action_progress_message(runtime_context.action_display_name, "Running")
        )
    )
    with (
        progress_context,
        Stopwatch() as run_stopwatch,
    ):
        try:
            action_output = run_action_process(
                action_script_path=action_script_path,
                action_name=runtime_context.action_name,
                action_version=runtime_context.action_version,
                args=list(args or []),
                action_stack=_running_actions_stack.copy(),
                run_id=runtime_context.run_id,
            )
        except BaseException as error:
            event_manager.emit(
                create_action_event(
                    "action_finished",
                    runtime_context.run_id,
                    action_display_name=runtime_context.action_display_name,
                    status="failure",
                    duration=run_stopwatch.elapsed_time,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    exit_code=getattr(error, "exit_code", None),
                )
            )
            raise

    event_manager.emit(
        create_action_event(
            "action_finished",
            runtime_context.run_id,
            action_display_name=runtime_context.action_display_name,
            status="success",
            duration=run_stopwatch.elapsed_time,
            exit_code=action_output.exit_code,
        )
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

        get_action_event_manager().emit(
            create_action_event(
                "action_started",
                runtime_context.run_id,
                parent_run_id=runtime_context.parent_run_id,
                action_name=runtime_context.action_name,
                action_version=runtime_context.action_version,
                action_display_name=runtime_context.action_display_name,
                action_source=_get_action_source_for_display(
                    action_script_path,
                    action_source,
                    runtime_context.action_version,
                ),
                toolkit_version=get_ci_toolkit_version(),
                ci_environment=(
                    None
                    if ci_platform is Local
                    else ci_platform.name()
                ),
            )
        )

        action_output = _run_action_script(action_script_path, runtime_context, args)
        _reset_remote_action_cache_timestamp(runtime_context)
        return action_output
