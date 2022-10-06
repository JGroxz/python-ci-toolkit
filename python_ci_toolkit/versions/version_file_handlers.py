"""
This file defines logic for handling different types of version files.
"""
import dataclasses
import json
from typing import List

import toml
from semver import VersionInfo


@dataclasses.dataclass
class VersionFileHandler:
    file_name: str

    def read_version(self, file_contents: str) -> VersionInfo:
        raise NotImplementedError

    def update_version(self, file_contents: str, new_version: VersionInfo) -> str:
        raise NotImplementedError


@dataclasses.dataclass
class PyProjectVersionFileHandler(VersionFileHandler):
    """
    Handler for pyproject.toml used in Poetry projects.
    """
    file_name: str = "pyproject.toml"

    def read_version(self, file_contents: str) -> VersionInfo:
        from .versions import parse_semantic_version
        project_config = toml.loads(file_contents)
        version = project_config.get("tool").get("poetry").get("version")
        return parse_semantic_version(version)

    def update_version(self, file_contents: str, new_version: VersionInfo) -> str:
        project_config = toml.loads(file_contents)
        version_string = f"{new_version}"
        self._set_nested_dict_key(project_config, ["tool", "poetry", "version"], version_string)
        return toml.dumps(project_config)

    def _set_nested_dict_key(self, dictionary, keys, value):
        for key in keys[:-1]:
            dictionary = dictionary.setdefault(key, {})
        dictionary[keys[-1]] = value


@dataclasses.dataclass
class PackageJsonVersionFileHandler(VersionFileHandler):
    """
    Handler for package.json used in Node projects.
    """
    file_name: str = "package.json"

    def read_version(self, file_contents: str) -> VersionInfo:
        from .versions import parse_semantic_version
        project_config = json.loads(file_contents)
        version_string = project_config.get("version")
        return parse_semantic_version(version_string)

    def update_version(self, file_contents: str, new_version: VersionInfo) -> str:
        project_config = json.loads(file_contents)
        version_string = f"{new_version}"
        project_config.set("version", version_string)
        return json.dumps(project_config)


@dataclasses.dataclass
class PlainTextVersionFileHandler(VersionFileHandler):
    """
    Handler plain text version files (which contain version string as the first line in the file).
    """
    file_name: str = "VERSION"

    def read_version(self, file_contents: str) -> VersionInfo:
        from .versions import parse_semantic_version
        first_line = file_contents.strip("\n")
        return parse_semantic_version(first_line)

    def update_version(self, file_contents: str, new_version: VersionInfo) -> str:
        return f"{new_version}"


VERSION_FILE_HANDLERS: List[VersionFileHandler] = [
    PyProjectVersionFileHandler(),
    PackageJsonVersionFileHandler(),
    PlainTextVersionFileHandler("VERSION"),
    PlainTextVersionFileHandler("version.txt")
]
"""
List of version file handlers used by python-ci-toolkit to parse version files in the projects.
"""
