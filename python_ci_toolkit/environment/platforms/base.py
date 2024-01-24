from abc import ABC, abstractmethod
from pathlib import Path

from rich.console import Console
from rich.theme import Theme


class CiPlatform(ABC):
    """
    Base class for CI platform integrations.
    """

    @classmethod
    @abstractmethod
    def is_current(cls) -> bool:
        """
        Returns:
            True if the current CI platform is the one this class is implemented for, False otherwise.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """
        Returns:
            Pretty name of this CI platform.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def supports_multiline_envvars(cls) -> bool:
        """
        Returns:
            True if the current CI platform supports multiline environment variables, False otherwise.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def get_ci_project_root(cls) -> Path:
        """
        Returns:
            Absolute path to the root directory of the current CI project.
        """
        raise NotImplementedError()

    # event callbacks

    @classmethod
    @abstractmethod
    def on_patch_rich_console(cls, console: Console, default_theme: Theme) -> Console:
        """
        Callback that is called when Rich Console is being patched for the current CI environment.

        Notes:
            Use this to modify the properties of the Rich Console instance used for CI Toolkit's logging output.
            Optionally, create a new Rich Console instance to use instead of the default one and return it.

        Args:
            console: Rich Console instance to patch.
            default_theme: Default CI Toolkit's Rich theme.

        Returns:
            Rich Console instance to use for CI Toolkit's logging output.
        """
        return console
