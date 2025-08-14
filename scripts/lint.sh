#!/bin/bash
# Run linting checks on Python code

set -e

echo "🔍 Running flake8 linting..."
uv run flake8

echo "🔍 Running mypy type checking..."
uv run mypy .

echo "✅ Linting checks complete!"