from pathlib import Path


def test_autocompletion_lists_local_actions_without_remote_config(monkeypatch):
    from python_ci_toolkit.cli.action.find import ActionMetadata, list_available_actions
    from python_ci_toolkit.actions.retrieval.sources.local import list_actions_in_directory, LOCAL_ACTIONS_DIRECTORY

    monkeypatch.delenv("PYTHON_CI_ACTIONS_GIT_REPO_URL", raising=False)

    all_actions_metadata = list_available_actions(cache_timeout=0)
    all_local_actions = list_actions_in_directory(LOCAL_ACTIONS_DIRECTORY)
    all_local_actions_metadata = [
        ActionMetadata(f"{metadata.name}@local", f"[local] {metadata.description}")
        for metadata in [ActionMetadata.from_action_file(p) for p in all_local_actions]
    ]

    assert all_actions_metadata == sorted(all_local_actions_metadata)


def test_autocompletion_list_available_actions(remote_actions_git_repo: Path):
    from python_ci_toolkit.cli.action.find import ActionMetadata, list_available_actions

    def test(cache_timeout: float):
        all_actions_metadata = list_available_actions(cache_timeout=cache_timeout)
        all_actions_string = "\n".join([f"{metadata.name} – {metadata.description}" for metadata in all_actions_metadata])

        # must include all local actions
        from python_ci_toolkit.actions.retrieval.sources.local import list_actions_in_directory, LOCAL_ACTIONS_DIRECTORY
        all_local_actions = list_actions_in_directory(LOCAL_ACTIONS_DIRECTORY)
        all_local_actions_metadata = [
            ActionMetadata(f"{metadata.name}@local", f"[local] {metadata.description}")
            for metadata in [ActionMetadata.from_action_file(p) for p in all_local_actions]
        ]

        for metadata in all_local_actions_metadata:
            assert metadata in all_actions_metadata, \
                f"Expected to find local action '{metadata.name}', but it was missing:\n{all_actions_string}"

        expected_remote_action = ActionMetadata("hello_world", "[remote] Remote hello world action.")
        assert expected_remote_action in all_actions_metadata, \
            f"Expected to find remote action '{expected_remote_action.name}' from '{remote_actions_git_repo}', but it was missing:\n{all_actions_string}"

        # there must be no duplicates in the returned list
        assert len(all_actions_metadata) == len(set(all_actions_metadata)), \
            "There are duplicate actions in the list of all available actions."

    # first run to verify that the list is correct
    test(cache_timeout=0)

    # run again to verify that caching does not affect the result
    test(cache_timeout=1000)
