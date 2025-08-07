#!/usr/bin/env python
"""Test runner with coverage reporting"""

import sys
import subprocess
import os


def run_tests():
    """Run all tests with coverage"""
    
    print("=" * 60)
    print("Running Dynamic Orchestrator MCP Tests")
    print("=" * 60)
    
    # Install test dependencies if needed
    print("\n📦 Installing test dependencies...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", 
        "pytest", "pytest-asyncio", "pytest-cov", "pytest-mock"
    ], check=False)
    
    # Run tests with coverage
    print("\n🧪 Running tests with coverage...")
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-report=html:coverage_report",
        "--tb=short"
    ])
    
    if result.returncode == 0:
        print("\n✅ All tests passed!")
        print("📊 Coverage report generated in coverage_report/index.html")
    else:
        print("\n❌ Some tests failed. Check the output above.")
        sys.exit(1)
    
    # Run example scenarios
    print("\n🎯 Running example scenarios...")
    result = subprocess.run([
        sys.executable, "examples/example_scenarios.py"
    ])
    
    if result.returncode == 0:
        print("\n✅ Example scenarios completed successfully!")
    else:
        print("\n⚠️ Example scenarios had issues.")
    
    print("\n" + "=" * 60)
    print("Test suite completed!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()