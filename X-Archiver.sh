#!/bin/bash

# X-Archiver Execution Script
# This script ensures the Python virtual environment is set up and runs the application.

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"

# 1. Check if virtual environment exists, create if not
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment."
        exit 1
    fi
fi

# 2. Upgrade pip and install/update dependencies
echo "Ensuring dependencies are installed..."
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null
"$VENV_DIR/bin/pip" install -r requirements.txt > /dev/null

# 3. Ensure Playwright browsers are installed
echo "Checking Playwright browsers..."
"$VENV_DIR/bin/playwright" install chromium > /dev/null

# 4. Run the main application with passed arguments
echo "Starting X-Archiver..."
echo "------------------------------------------"
"$VENV_DIR/bin/python" main.py "$@"
echo "------------------------------------------"
echo "Done."
