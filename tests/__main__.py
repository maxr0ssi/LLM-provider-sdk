#!/usr/bin/env python3
"""
Test runner for steer-llm-sdk.

This module allows running the test suite using:
    python -m tests

It provides the same functionality as running pytest directly.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """Run the test suite using pytest."""
    try:
        import pytest
    except ImportError:
        print("Error: pytest is not installed.")
        print("Please install it with: pip install pytest pytest-asyncio pytest-cov")
        return 1
    
    # Get the tests directory
    tests_dir = Path(__file__).parent
    
    # Default pytest arguments
    args = [
        str(tests_dir),  # Run all tests in this directory
        "-v",            # Verbose output
        "--tb=short",    # Short traceback format
    ]
    
    # Add any command line arguments passed to the module
    if len(sys.argv) > 1:
        # Replace the tests directory with user-provided arguments
        args = sys.argv[1:]
    
    # Run pytest with the specified arguments
    exit_code = pytest.main(args)
    
    # Print summary based on exit code
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code: {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())