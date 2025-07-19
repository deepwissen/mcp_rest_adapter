#!/usr/bin/env python3
"""
Validate that all test files are properly structured and can be imported.
"""
import os
import sys
import importlib.util
from pathlib import Path

def validate_test_file(file_path):
    """Validate a single test file."""
    try:
        spec = importlib.util.spec_from_file_location("test_module", file_path)
        if spec is None:
            return False, f"Could not load spec for {file_path}"
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check for test classes or functions
        test_items = [name for name in dir(module) if name.startswith('test_') or name.startswith('Test')]
        
        if not test_items:
            return False, f"No test classes or functions found in {file_path}"
        
        return True, f"✅ {file_path.name} - {len(test_items)} test items found"
        
    except Exception as e:
        return False, f"❌ {file_path.name} - Error: {e}"

def main():
    """Main validation function."""
    project_root = Path(__file__).parent
    test_dir = project_root / "tests"
    
    if not test_dir.exists():
        print("❌ Tests directory not found")
        return 1
    
    # Add project root to Python path
    sys.path.insert(0, str(project_root))
    
    print("🔍 Validating test files...")
    print("=" * 60)
    
    total_files = 0
    passed_files = 0
    
    # Find all test files
    for test_file in test_dir.rglob("test_*.py"):
        total_files += 1
        success, message = validate_test_file(test_file)
        print(message)
        if success:
            passed_files += 1
    
    print("=" * 60)
    print(f"📊 Validation Results: {passed_files}/{total_files} files passed")
    
    if passed_files == total_files:
        print("🎉 All test files are valid!")
        return 0
    else:
        print("❌ Some test files have issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())