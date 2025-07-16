#!/usr/bin/env bash

# This script wraps the setup and execution of the pyShell project.
# It ensures the Python virtual environment is created and activated,
# then runs either the shell or the test suite.
#
# Usage: ./run.sh [-t]
# -t : Run tests instead of launching the shell

set -e
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Setting up..."
    ./setup_env.sh
fi

source ".venv/bin/activate"

if [ "$1" == "-t" ]; then
    python -m unittest discover
else
    python pyShell.py
fi