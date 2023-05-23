import os
import time
from pathlib import Path

from python_ci_toolkit.actions._utils._file_timestamps import reset_file_timestamp, time_since_file_timestamp, get_file_timestamp


def test_timestamp():
    TEST_TIMESTAMP_FILE_PATH = Path(__file__).parent / "output" / "test.timestamp"

    # make sure timestamp file does not exist
    TEST_TIMESTAMP_FILE_PATH.unlink(missing_ok=True)
    assert not TEST_TIMESTAMP_FILE_PATH.is_file(), \
        "The test timestamp file must not exist before the test."

    # check timestamp without file
    time_since = time_since_file_timestamp(TEST_TIMESTAMP_FILE_PATH)
    assert time_since == float("inf"), \
        "If file does not exist, time_since_file_timestamp() must return infinity."

    # create a new timestamp file
    reset_file_timestamp(TEST_TIMESTAMP_FILE_PATH)
    original_timestamp = get_file_timestamp(TEST_TIMESTAMP_FILE_PATH)
    assert TEST_TIMESTAMP_FILE_PATH.is_file(), \
        "reset_file_timestamp() must create the file if it does not exist."
    assert original_timestamp <= time.time(), \
        "After a call, reset_file_timestamp() must always return a value which is less than or equal to the current time."

    # update timestamp file
    time.sleep(0.1)
    reset_file_timestamp(TEST_TIMESTAMP_FILE_PATH)
    updated_timestamp = get_file_timestamp(TEST_TIMESTAMP_FILE_PATH)
    assert updated_timestamp > original_timestamp, \
        "After a call, reset_file_timestamp() must always return a value which is greater than the previous value."
