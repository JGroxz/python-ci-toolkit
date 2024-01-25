import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call():
    print()  # <- newline at the start of the logs to make them more readable
    yield


@pytest.fixture
def variable_name() -> str:
    """
    Returns:
        Name of the environment variable that is used to test environment variable access functions.
    """
    return "TEST_ENVIRONMENT_VARIABLE"
