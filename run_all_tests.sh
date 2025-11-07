#!/bin/bash
# Test runner script with coverage

export ANTHROPIC_API_KEY=test_key

echo "Running full test suite with coverage..."
echo "========================================"

python3 -m pytest tests/ -v --cov=src --cov-report=term-missing --tb=short

echo ""
echo "Test run complete!"

