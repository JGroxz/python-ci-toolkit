from semver import VersionInfo

from python_ci_toolkit.versions import get_project_version_from_file, get_latest_pypi_package_version, get_all_available_pypi_package_versions, parse_semantic_version


def test_project_version():
    project_root = "../"
    version = get_project_version_from_file(project_root)
    print(f"Project version: {version}")


def test_latest():
    test_package = "pip"
    latest_pip_version = get_latest_pypi_package_version(test_package)
    print(f"Latest available version of {test_package}: {latest_pip_version}")


def test_version_parsing():
    version_strings = [
        "0.0.0",
        "0.0.1",
        "0.1.0",
        "1.1.0",
        "0.0.0-dev",
        "0.0.1-dev",
        "0.1.0-dev",
        "1.0.0-dev",
        "v0.0.0-dev",
        "v0.0.1-dev",
        "v0.1.0-dev",
        "v1.0.0-dev.1",
    ]

    for version_string in version_strings:
        version = parse_semantic_version(version_string)
        VersionInfo
        print(f"{version_string} -> {version}")


if __name__ == '__main__':
    test_project_version()
    # test_latest()
    test_version_parsing()
