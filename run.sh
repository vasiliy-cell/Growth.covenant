#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Use the project venv's Python (it has numpy/torch). The system Mac has no
# bare `python`, only `python3`, and that one lacks the deps.
PY="./.venv/bin/python3"

echo "Do you want to run tests? (y/n)"
read -p "Enter choice: " run_tests_choice

if [ "$run_tests_choice" = "y" ] || [ "$run_tests_choice" = "Y" ]; then
    echo "🧪 Running tests..."
    $PY -m pytest

    if [ $? -ne 0 ]; then
        echo "❌ Tests failed. Aborting run."
        exit 1
    fi

    echo "✅ Tests passed."
else
    echo "⏩ Skipping tests."
fi
# ----------------------------------

echo ""
echo "Choose run mode:"
echo "1) Normal run"
echo "2) Visualized run"
echo ""

read -p "Enter choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    echo "Starting normal run..."
    $PY src/run.py

elif [ "$choice" = "2" ]; then
    echo "Starting visualized run..."
    $PY src/visualized_run.py

else
    echo "❌ Invalid choice. Exiting."
    exit 1
fi