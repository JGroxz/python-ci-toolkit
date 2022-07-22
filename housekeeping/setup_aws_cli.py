"""
Generates configuration file to authenticate AWS CLI installed on our CI runner image.
"""
import logging
import os
from pathlib import Path

from python_ci_toolkit.console import initialize_ci_console
from python_ci_toolkit.environment import assert_environment_variable_set

AWS_CONFIG_FOLDER_PATH = "~/.aws/"
AWS_CREDENTIALS_FILE_NAME = "credentials"
AWS_CONFIG_FILE_NAME = "config"

ENV_AWS_CI_ACCESS_KEY_ID = assert_environment_variable_set("AWS_CI_ACCESS_KEY_ID")
ENV_AWS_CI_SECRET_ACCESS_KEY = assert_environment_variable_set("AWS_CI_SECRET_ACCESS_KEY")
ENV_AWS_DEFAULT_REGION = assert_environment_variable_set("AWS_DEFAULT_REGION")


def write_to_file(file_path: Path, contents: str):
    with open(file_path, "w") as file:
        file.write(contents)


def cli():
    initialize_ci_console()

    logging.info("Generating AWS CLI configuration file...")

    # expand path as needed
    global AWS_CONFIG_FOLDER_PATH
    AWS_CONFIG_FOLDER_PATH = Path(AWS_CONFIG_FOLDER_PATH).expanduser()

    # create directories
    if not AWS_CONFIG_FOLDER_PATH.exists():
        os.makedirs(AWS_CONFIG_FOLDER_PATH)

    # write credentials
    file_contents = (f"[default]\n"
                     f"aws_access_key_id={ENV_AWS_CI_ACCESS_KEY_ID}\n"
                     f"aws_secret_access_key={ENV_AWS_CI_SECRET_ACCESS_KEY}\n")
    file_path = Path(AWS_CONFIG_FOLDER_PATH, AWS_CREDENTIALS_FILE_NAME)
    write_to_file(file_path, file_contents)
    logging.info(f"Wrote credentials to '{file_path}'.")

    # write config
    file_contents = (f"[default]\n"
                     f"region={ENV_AWS_DEFAULT_REGION}\n"
                     f"output=json\n")
    file_path = Path(AWS_CONFIG_FOLDER_PATH, AWS_CONFIG_FILE_NAME)
    write_to_file(file_path, file_contents)
    logging.info(f"Wrote config to '{file_path}'.")

    logging.info(f"AWS CLI configuration files generated.")


if __name__ == '__main__':
    cli()
