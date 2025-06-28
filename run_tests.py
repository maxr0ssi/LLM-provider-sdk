#!/usr/bin/env python
"""Test runner for Steer LLM SDK."""

import sys
import subprocess
import argparse


def main():
    """Run tests with various options."""
    parser = argparse.ArgumentParser(description="Run Steer LLM SDK tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    parser.add_argument("--parallel", "-n", type=int, help="Run tests in parallel")
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd = ["pytest"]
    
    # Add markers
    markers = []
    if args.unit:
        markers.append("unit")
    if args.integration:
        markers.append("integration")
    if args.fast:
        markers.append("not slow")
    
    if markers:
        cmd.extend(["-m", " and ".join(markers)])
    
    # Add verbosity
    if args.verbose:
        cmd.append("-vv")
    
    # Add coverage
    if args.coverage:
        cmd.extend([
            "--cov=steer_llm_sdk",
            "--cov-report=term-missing",
            "--cov-report=html"
        ])
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])
    
    # Run tests
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=".")
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())