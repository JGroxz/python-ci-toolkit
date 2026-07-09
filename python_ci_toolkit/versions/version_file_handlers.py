"""
This file defines logic for handling different types of version files.
"""
import dataclasses
import json
from pathlib import Path
from typing import Dict

import tomlkit
from semver import VersionInfo


@dataclasses.dataclass
class VersionFileHandler:
    """
    Base class for version file handlers.
    """

    def read_version(self, file_path: Path) -> VersionInfo:
        """
        Reads the version from the given file.

        Args:
            file_path: Path to the file to read the version from.

        Returns:
            VersionInfo read from the file.
        """
        contents = file_path.read_text(encoding="utf-8")
        return self._read_version_from_file_contents(contents)

    def write_version(self, file_path: Path, new_version: VersionInfo) -> None:
        """
        Writes the given version to the given file.

        Args:
            file_path: Path to the file to write the version to.
            new_version: Version to write to the file.
        """

        contents = file_path.read_text(encoding="utf-8")
        updated_contents = self._update_version_from_file_contents(contents, new_version)
        file_path.write_text(updated_contents, encoding="utf-8")

    def _read_version_from_file_contents(self, file_contents: str) -> VersionInfo:
        raise NotImplementedError

    def _update_version_from_file_contents(self, file_contents: str, new_version: VersionInfo) -> str:
        raise NotImplementedError


@dataclasses.dataclass
class PyProjectVersionFileHandler(VersionFileHandler):
    """
    Handler for pyproject.toml files.

    PEP 621 project metadata is preferred. Legacy Poetry metadata is still
    supported so PyCI can inspect older repositories during migration.
    """
    PEP_621_VERSION_PATH = ("project", "version")
    POETRY_VERSION_PATH = ("tool", "poetry", "version")

    def _read_version_from_file_contents(self, file_contents: str) -> VersionInfo:
        from .versions import parse_semantic_version
        project_config = tomlkit.parse(file_contents)
        version = self._get_nested_dict_key(project_config, self.PEP_621_VERSION_PATH)
        if version is None:
            version = self._get_nested_dict_key(project_config, self.POETRY_VERSION_PATH)
        if version is None:
            raise ValueError("Could not find project version in 'pyproject.toml'.")
        return parse_semantic_version(str(version))

    def _update_version_from_file_contents(self, file_contents: str, new_version: VersionInfo) -> str:
        project_config = tomlkit.parse(file_contents)
        version_string = f"{new_version}"
        if self._get_nested_dict_key(project_config, self.PEP_621_VERSION_PATH) is not None:
            self._set_nested_dict_key(project_config, self.PEP_621_VERSION_PATH, version_string)
        elif self._get_nested_dict_key(project_config, self.POETRY_VERSION_PATH) is not None:
            self._set_nested_dict_key(project_config, self.POETRY_VERSION_PATH, version_string)
        else:
            self._set_nested_dict_key(project_config, self.PEP_621_VERSION_PATH, version_string)
        return project_config.as_string()

    @staticmethod
    def _get_nested_dict_key(dictionary, keys):
        for key in keys:
            if not isinstance(dictionary, dict):
                return None
            dictionary = dictionary.get(key)
            if dictionary is None:
                return None
        return dictionary

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
        project_config["version"] = version_string
        return json.dumps(project_config, indent=2)


@dataclasses.dataclass
class PlainTextVersionFileHandler(VersionFileHandler):
    """
    Handler for plain text version files (which contain version string as the first line in the file).
    """

    def _read_version_from_file_contents(self, file_contents: str) -> VersionInfo:
        from .versions import parse_semantic_version
        lines = file_contents.splitlines()
        first_line = lines[0] if lines else ""
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
