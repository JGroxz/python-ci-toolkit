from python_ci_utilities.versions import get_project_version_string


def run():
    project_root = "../"
    version = get_project_version_string(project_root)
    print(f"Project version: {version}")


if __name__ == '__main__':
    run()
