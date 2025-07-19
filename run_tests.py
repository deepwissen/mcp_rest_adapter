#!/usr/bin/env python3
"""
Test runner script for MCPAdapters project.
Provides convenient commands to run different types of tests.
"""
import sys
import subprocess
import argparse
import os

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, shell=True, capture_output=False)
    
    if result.returncode != 0:
        print(f"❌ {description} failed with return code {result.returncode}")
        return False
    else:
        print(f"✅ {description} completed successfully")
        return True

def main():
    parser = argparse.ArgumentParser(description="Run tests for MCPAdapters")
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--coverage', action='store_true', help='Run tests with coverage report')
    parser.add_argument('--lint', action='store_true', help='Run linting checks')
    parser.add_argument('--type-check', action='store_true', help='Run type checking')
    parser.add_argument('--security', action='store_true', help='Run security scans')
    parser.add_argument('--all', action='store_true', help='Run all checks and tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--fast', action='store_true', help='Skip slow tests')
    
    args = parser.parse_args()
    
    # Set PYTHONPATH to include project root
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    success = True
    
    # If no specific test type is chosen, run all tests
    if not any([args.unit, args.integration, args.lint, args.type_check, args.security, args.all]):
        args.all = True
    
    verbose_flag = '-v' if args.verbose else ''
    fast_flag = '-m "not slow"' if args.fast else ''
    
    try:
        if args.lint or args.all:
            # Run linting
            success &= run_command(
                'flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics',
                'Linting - Critical errors check'
            )
            success &= run_command(
                'flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics',
                'Linting - Style check'
            )
        
        if args.type_check or args.all:
            # Run type checking
            success &= run_command(
                'mypy mcp_adapter/ --ignore-missing-imports',
                'Type checking'
            )
        
        if args.unit or args.all:
            # Run unit tests
            cmd = f'pytest tests/unit/ {verbose_flag} {fast_flag}'
            if args.coverage:
                cmd += ' --cov=mcp_adapter --cov=mock-services --cov-report=html --cov-report=term-missing'
            success &= run_command(cmd, 'Unit tests')
        
        if args.integration or args.all:
            # Run integration tests
            cmd = f'pytest tests/integration/ {verbose_flag} {fast_flag}'
            success &= run_command(cmd, 'Integration tests')
        
        if args.coverage and not (args.unit or args.integration):
            # Run all tests with coverage
            cmd = f'pytest tests/ {verbose_flag} {fast_flag} --cov=mcp_adapter --cov=mock-services --cov-report=html --cov-report=term-missing'
            success &= run_command(cmd, 'All tests with coverage')
        
        if args.security or args.all:
            # Run security scans
            try:
                success &= run_command(
                    'safety check',
                    'Security scan - Dependencies'
                )
            except FileNotFoundError:
                print("⚠️  Safety not installed. Install with: pip install safety")
            
            try:
                success &= run_command(
                    'bandit -r mcp_adapter/ mock-services/',
                    'Security scan - Code analysis'
                )
            except FileNotFoundError:
                print("⚠️  Bandit not installed. Install with: pip install bandit")
        
        # Summary
        print(f"\n{'='*60}")
        if success:
            print("🎉 All checks passed successfully!")
            print("📊 Coverage report available at: htmlcov/index.html")
        else:
            print("❌ Some checks failed. Please review the output above.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error running tests: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()