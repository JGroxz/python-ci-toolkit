#!/usr/bin/env bash
# Script used to test and demonstrate real-time logging of run_shell_command() function.

>&1 echo "started"

sleep 1

>&2 echo "error"

sleep 1

>&1 echo "normal log"

sleep 1

>&1 echo "another normal log"

sleep 1

>&2 echo "another error"

sleep 1

>&1 echo "completed"
