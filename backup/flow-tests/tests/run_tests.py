#!/usr/bin/env python3
"""
Test runner script for PoyMoyMir Telegram bot end-to-end tests.
"""

import sys
import os
from pathlib import Path
import subprocess
import argparse

# Add the flow directory to the path
FLOW_DIR = Path(__file__).parent.parent / "flow"
sys.path.insert(0, str(FLOW_DIR))

def install_dependencies():
    """Install test dependencies."""
    print("Installing test dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "tests/requirements.txt"])
        print("✅ Test dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install test dependencies: {e}")
        return False

def run_tests(coverage=False, verbose=False):
    """Run the test suite."""
    print("Running PoyMoyMir Telegram bot tests...")
    
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest", "tests/"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=flow", "--cov-report=term-missing"])
    
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
        if result.returncode == 0:
            print("✅ All tests passed!")
            return True
        else:
            print("❌ Some tests failed!")
            return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def run_specific_test(test_name, verbose=False):
    """Run a specific test by name."""
    print(f"Running specific test: {test_name}")
    
    cmd = [sys.executable, "-m", "pytest", "-k", test_name]
    
    if verbose:
        cmd.append("-v")
    
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
        if result.returncode == 0:
            print("✅ Test passed!")
            return True
        else:
            print("❌ Test failed!")
            return False
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

def main():
    """Main function to parse arguments and run tests."""
    parser = argparse.ArgumentParser(description="Run PoyMoyMir Telegram bot tests")
    parser.add_argument("--install-deps", action="store_true", help="Install test dependencies")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--test", "-t", help="Run specific test by name")
    
    args = parser.parse_args()
    
    # Install dependencies if requested
    if args.install_deps:
        if not install_dependencies():
            sys.exit(1)
    
    # Run tests
    if args.test:
        success = run_specific_test(args.test, args.verbose)
    else:
        success = run_tests(args.coverage, args.verbose)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()