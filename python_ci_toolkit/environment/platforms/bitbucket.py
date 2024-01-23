import os
from pathlib import Path

from .base import CiPlatform


class BitbucketPipelines(CiPlatform):
    """
    Integration for Bitbucket Pipelines.
    """

    @classmethod
    def is_current(cls) -> bool:
        return bool(os.environ.get("BITBUCKET_PIPELINE_UUID"))

    @classmethod
    def name(cls) -> str:
        return "Bitbucket Pipelines"

    @classmethod
    def supports_multiline_envvars(cls) -> bool:
        return False

    @classmethod
    def get_ci_project_root(cls) -> Path:
        return Path(os.environ.get("BITBUCKET_CLONE_DIR"))
