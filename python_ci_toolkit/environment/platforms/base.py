from abc import ABC, abstractmethod
from pathlib import Path


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
