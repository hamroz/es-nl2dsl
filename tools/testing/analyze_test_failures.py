#!/usr/bin/env python3
"""
Analyze test failures to identify real application code issues.
"""

import subprocess
import sys
import re
import os
from pathlib import Path

def run_tests_with_full_output(app_filter=None):
    """Run tests with full traceback to analyze"""
    
    backend_dir = Path(__file__).parent.parent.parent / "backend"
    if backend_dir.exists():
        os.chdir(backend_dir)
    
    venv_python = Path("venv/bin/python")
    if not venv_python.exists():
        print("❌ Virtual environment not found")
        return 1, ""
    
    cmd = [
        str(venv_python), "-m", "pytest", 
        "--tb=long",  # Full traceback for analysis
        "--disable-warnings", 
        "--no-cov",
        "-x",  # Stop on first failure for detailed analysis
        "-v"
    ]
    
    if app_filter:
        cmd.append(f"{app_filter}/")
    
    env = os.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = 'es_nl2dsl_api.test_settings'
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, f"Error: {e}"

def analyze_first_failure(output):
    """Analyze the first failure in detail"""
    
    lines = output.split('\n')
    
    # Find the failure section
    failure_start = -1
    test_name = None
    
    for i, line in enumerate(lines):
        if 'FAILURES' in line:
            failure_start = i
            break
        elif 'FAILED' in line and '::' in line:
            test_name = line.split('FAILED ')[1].split(' ')[0]
    
    if failure_start == -1:
        return None
    
    # Extract the failure details
    failure_lines = lines[failure_start:failure_start + 100]  # Next 100 lines
    failure_text = '\n'.join(failure_lines)
    
    # Categorize the failure
    categories = []
    
    if re.search(r'AssertionError: \d+ != \d+', failure_text):
        status_match = re.search(r'AssertionError: (\d+) != (\d+)', failure_text)
        if status_match:
            actual, expected = status_match.groups()
            categories.append(f"HTTP Status Code Issue: Got {actual}, expected {expected}")
    
    if 'FieldError' in failure_text and 'Cannot resolve keyword' in failure_text:
        field_match = re.search(r"Cannot resolve keyword '(\w+)'", failure_text)
        if field_match:
            categories.append(f"Model Field Issue: Field '{field_match.group(1)}' doesn't exist")
    
    if 'TypeError' in failure_text and 'unexpected keyword argument' in failure_text:
        arg_match = re.search(r"unexpected keyword argument '(\w+)'", failure_text)
        if arg_match:
            categories.append(f"Method Signature Issue: Unexpected argument '{arg_match.group(1)}'")
    
    if 'AttributeError' in failure_text and 'has no attribute' in failure_text:
        attr_match = re.search(r"'(\w+)' object has no attribute '(\w+)'", failure_text)
        if attr_match:
            obj_type, attr_name = attr_match.groups()
            categories.append(f"Missing Attribute: {obj_type} missing '{attr_name}' attribute/method")
    
    if 'Bad Request:' in failure_text or 'Method Not Allowed:' in failure_text:
        categories.append("HTTP Request Issue: Check URL patterns and view methods")
    
    # Check for database/infrastructure issues
    infra_issues = []
    
    if 'database table is locked' in failure_text:
        infra_issues.append("Database concurrency issue (test infrastructure)")
    
    if 'UNIQUE constraint failed' in failure_text:
        infra_issues.append("Database constraint violation (test data isolation)")
    
    if 'GeoIP' in failure_text:
        infra_issues.append("GeoIP configuration missing (test setup)")
    
    return {
        'test_name': test_name,
        'app_issues': categories,
        'infra_issues': infra_issues,
        'full_traceback': failure_text
    }

def main():
    app_filter = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("🔍 DETAILED FAILURE ANALYSIS")
    print("="*50)
    
    if app_filter:
        print(f"📍 Analyzing app: {app_filter}")
    
    print("⏳ Running tests (stopping on first failure)...")
    exit_code, output = run_tests_with_full_output(app_filter)
    
    if exit_code == 0:
        print("🎉 All tests passed!")
        return 0
    
    analysis = analyze_first_failure(output)
    
    if not analysis:
        print("❌ Could not analyze failure")
        return 1
    
    print(f"\n📋 Test: {analysis['test_name']}")
    print()
    
    if analysis['app_issues']:
        print("🐛 APPLICATION CODE ISSUES:")
        for issue in analysis['app_issues']:
            print(f"   • {issue}")
        print()
    
    if analysis['infra_issues']:
        print("🔧 INFRASTRUCTURE ISSUES:")
        for issue in analysis['infra_issues']:
            print(f"   • {issue}")
        print()
    
    if not analysis['app_issues'] and not analysis['infra_issues']:
        print("❓ UNcategorized ISSUE:")
        # Show key error lines
        for line in analysis['full_traceback'].split('\n'):
            if any(keyword in line for keyword in ['Error:', 'AssertionError:', 'TypeError:', 'AttributeError:']):
                print(f"   {line.strip()}")
    
    print("\n" + "="*50)
    print("💡 RECOMMENDATIONS:")
    
    if analysis['app_issues']:
        print("1. Fix the application code issues listed above")
        print("2. Check your Django models, views, and URL configuration")
        print("3. Verify API endpoint implementations and method signatures")
    elif analysis['infra_issues']:
        print("1. These appear to be test infrastructure issues")
        print("2. Consider using test fixtures and better data isolation")
        print("3. The application code is likely correct")
    else:
        print("1. Review the full traceback below for clues")
        print("2. This may be a complex integration issue")
    
    if '--full' in sys.argv:
        print("\n🔍 FULL TRACEBACK:")
        print("-" * 50)
        print(analysis['full_traceback'])
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())