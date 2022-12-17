"""
This file defines logic for handling different types of version files.
"""
import dataclasses
import json
from pathlib import Path
from typing import Dict

import toml
from semver import VersionInfo


@dataclasses.dataclass
class VersionFileHandler:

    def read_version(self, file_path: Path) -> VersionInfo:
        with open(file_path, "r") as file:
            contents = file.read()
            return self._read_version_from_file_contents(contents)

    def write_version(self, file_path: Path, new_version: VersionInfo) -> None:
        with open(file_path, "r+") as file:
            contents = file.read()
            updated_contents = self._update_version_from_file_contents(contents, new_version)
            file.seek(0)
            file.truncate()
            file.write(updated_contents)

    def _read_version_from_file_contents(self, file_contents: str) -> VersionInfo:
        raise NotImplementedError

    def _update_version_from_file_contents(self, file_contents: str, new_version: VersionInfo) -> str:
        raise NotImplementedError


@dataclasses.dataclass
class PyProjectVersionFileHandler(VersionFileHandler):
    """
    Handler for pyproject.toml used in Poetry projects.
    """

    def _read_version_from_file_contents(self, file_contents: str) -> VersionInfo:
        from .versions import parse_semantic_version
        project_config = toml.loads(file_contents)
        version = project_config.get("tool").get("poetry").get("version")
        return parse_semantic_version(version)

    def _update_version_from_file_contents(self, file_contents: str, new_version: VersionInfo) -> str:
        project_config = toml.loads(file_contents)
        version_string = f"{new_version}"
        self._set_nested_dict_key(project_config, ["tool", "poetry", "version"], version_string)
        return toml.dumps(project_config)

    @staticmethod
    def _set_nested_dict_key(dictionary, keys, value):
        for key in keys[:-1]:
            dictionary = dictionary.setdefault(key, {})
        dictionary[keys[-1]] = value


@dataclasses.dataclass
class PackageJsonVersionFileHandler(VersionFileHandler):
    """
    Handler for package.json used in Node projects.
    """

    def _read_version_from_file_contents(self, file_contents: str) -> VersionInfo:
        from .versions import parse_semantic_version
        project_config = json.loads(file_contents)
        version_string = project_config.get("version")
        return parse_semantic_version(version_string)

    def _update_version_from_file_contents(self, file_contents: str, new_version: VersionInfo) -> str:
        project_config = json.loads(file_contents)
        version_string = f"{new_version}"
        project_config.setdefault("version", version_string)
        return json.dumps(project_config, indent=2)


@dataclasses.dataclass
class PlainTextVersionFileHandler(VersionFileHandler):
    """
    Handler for plain text version files (which contain version string as the first line in the file).
    """

    def _read_version_from_file_contents(self, file_contents: str) -> VersionInfo:
        from .versions import parse_semantic_version
        first_line = file_contents.strip("\n")
        return parse_semantic_version(first_line)

    def _update_version_from_file_contents(self, file_contents: str, new_version: VersionInfo) -> str:
        return f"{new_version}"


VERSION_FILE_HANDLERS: Dict[str, VersionFileHandler] = {
    "pyproject.toml": PyProjectVersionFileHandler(),
    "package.json": PackageJsonVersionFileHandler(),
    "VERSION": PlainTextVersionFileHandler(),
    "version.txt": PlainTextVersionFileHandler()
}
"""
Dictionary which matches version file names with respective file handlers.
Used by python-ci-toolkit to parse version files in the projects.
"""
