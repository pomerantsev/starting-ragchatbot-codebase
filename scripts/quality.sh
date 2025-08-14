#!/bin/bash
# Run all code quality checks

set -e

echo "🚀 Running comprehensive code quality checks..."
echo ""

echo "📋 Step 1: Format code"
./scripts/format.sh
echo ""

echo "📋 Step 2: Run linting"
./scripts/lint.sh
echo ""

echo "📋 Step 3: Run tests"
echo "🧪 Running tests..."
uv run pytest backend/tests/ -v

echo ""
echo "🎉 All quality checks passed!"