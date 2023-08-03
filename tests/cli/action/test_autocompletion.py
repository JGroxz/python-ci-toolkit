from python_ci_toolkit.cli.action import ActionMetadata


def test_autocompletion_list_available_actions():
    import python_ci_toolkit.cli.action as action_cli_module
    from python_ci_toolkit.cli.action import _list_available_actions

    def test():
        all_actions_metadata = _list_available_actions()
        all_actions_string = "\n".join([f"{metadata.name} – {metadata.description}" for metadata in all_actions_metadata])

        # must include all local actions
        from python_ci_toolkit.actions.retrieval.sources.local import list_actions_in_directory, LOCAL_ACTIONS_DIRECTORY
        all_local_actions = list_actions_in_directory(LOCAL_ACTIONS_DIRECTORY)
        all_local_actions_metadata = [ActionMetadata.from_action_file(p) for p in all_local_actions]


        # there must be no duplicates in the returned list
        assert len(all_actions_metadata) == len(set(all_actions_metadata)), \
            "There are duplicate actions in the list of all available actions."

    # first run to verify that the list is correct
    action_cli_module._ACTION_AUTOCOMPLETE_REMOTE_CLONE_DELAY_TIME_WINDOW = 0  # <- to avoid caching
    test()

    # run again to verify that caching does not affect the result
    action_cli_module._ACTION_AUTOCOMPLETE_REMOTE_CLONE_DELAY_TIME_WINDOW = 1000  # <- to enable caching
    test()
