#!/usr/bin/env bash

# Usage: ./setup_env.sh
# This script creates a Python virtual environment in .venv and installs requirements.

set -e

VENV_NAME=".venv"

PYTHON_BIN=$(command -v python3)

if [ -z "$PYTHON_BIN" ]; then
    echo "python3 not found. Please install Python 3."
    exit 1
fi

if [ ! -d "$VENV_NAME" ]; then
    echo "Creating virtual environment ($VENV_NAME)..."
    "$PYTHON_BIN" -m venv "$VENV_NAME"
fi

source "$VENV_NAME/bin/activate"
pip install --upgrade pip
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

echo "=========================="
echo "Environment setup complete."
echo "=========================="
echo -e " - To \033[0;32mactivate\033[0m the environment, run: source $VENV_NAME/bin/activate"
echo -e " - To \033[0;31mdeactivate\033[0m the environment, simply run: deactivate"