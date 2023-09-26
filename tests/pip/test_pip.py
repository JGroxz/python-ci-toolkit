from python_ci_toolkit.pip import check_package_installed


def test_check_package_installed():
    """
    Tests that check_package_installed() returns True for packages that are installed and False for packages that are not.
    """
    assert check_package_installed("python-ci-toolkit"), \
        f"{check_package_installed.__name__}() must return True for packages that are installed."
    assert check_package_installed("python_ci_toolkit"), \
        f"{check_package_installed.__name__}() must return True for packages that are installed."
    assert not check_package_installed("malware"), \
        f"{check_package_installed.__name__}() must return False for packages that are not installed."

# TODO: add tests for the rest of pip module functions
