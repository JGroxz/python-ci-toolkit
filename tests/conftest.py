import pytest


@pytest.fixture
def variable_name() -> str:
    """
    Returns:
        Name of the environment variable that is used to test environment variable access functions.
    """
    return "TEST_ENVIRONMENT_VARIABLE"
