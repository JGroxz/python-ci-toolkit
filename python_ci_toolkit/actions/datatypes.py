from dataclasses import dataclass
from typing import Any


@dataclass
class ActionRunResult:
    """
    Represents the result of a CI action run.
    """
    exception: BaseException = None

    @property
    def is_successful(self) -> bool:
        """
        True if the action run was successful, False otherwise.
        """
        no_exceptions = self.exception is None
        clean_exit = isinstance(self.exception, SystemExit) and self.exception.code == 0

        return no_exceptions or clean_exit
