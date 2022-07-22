from python_ci_toolkit.versions import get_project_version_from_file, get_latest_pypi_package_version, get_all_available_pypi_package_versions


def run():
    project_root = "../"
    version = get_project_version_from_file(project_root)
    print(f"Project version: {version}")


def test_latest():
    test_package = "pip"
    latest_pip_version = get_latest_pypi_package_version(test_package)
    print(f"Latest available version of {test_package}: {latest_pip_version}")


if __name__ == '__main__':
    run()
    test_latest()
