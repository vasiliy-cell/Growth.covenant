#!/bin/bash

echo "🧪 Running tests..."
pytest

if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Aborting run."
    exit 1
fi

echo "✅ Tests passed."

echo ""
echo "Choose run mode:"
echo "1) Normal run"
echo "2) Visualized run"
echo ""

read -p "Enter choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    echo "Starting normal run..."
    python src/run.py

elif [ "$choice" = "2" ]; then
    echo "Starting visualized run..."
    python src/visualized_run.py

else
    echo "❌ Invalid choice. Exiting."
    exit 1
fi