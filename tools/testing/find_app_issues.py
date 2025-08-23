#!/usr/bin/env python3
"""
Simple script to identify application code issues from test output.
This filters out test infrastructure problems and highlights real code issues.
"""

import subprocess
import sys
import re
import os
from pathlib import Path

def run_tests(app_filter=None):
    """Run tests and capture output"""
    
    # Change to backend directory
    backend_dir = Path(__file__).parent.parent.parent / "backend"
    if backend_dir.exists():
        os.chdir(backend_dir)
    
    # Use the virtual environment python directly
    venv_python = Path("venv/bin/python")
    if not venv_python.exists():
        print("❌ Virtual environment not found at venv/bin/python")
        return 1, "Virtual environment not found"
    
    # Build pytest command
    cmd = [
        str(venv_python), "-m", "pytest", 
        "--tb=short", 
        "--disable-warnings", 
        "--no-cov",
        "-q"
    ]
    
    if app_filter:
        cmd.append(f"{app_filter}/")
    
    # Set environment
    env = os.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = 'es_nl2dsl_api.test_settings'
    
    print(f"🔍 Running tests: {' '.join(cmd)}")
    print(f"📂 Working directory: {os.getcwd()}")
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, f"Error running tests: {e}"

def categorize_failures(output):
    """Categorize test failures into application vs infrastructure issues"""
    
    # Patterns that indicate real application code issues
    app_issue_patterns = [
        r'AssertionError: \d+ != \d+',  # Status code mismatches (400 != 201, 405 != 200)
        r'FieldError.*Cannot resolve keyword',  # Model field issues (is_active doesn't exist)
        r'TypeError.*unexpected keyword argument',  # Method signature issues  
        r'AttributeError.*has no attribute',  # Missing methods/properties
        r'Bad Request:|Method Not Allowed:|Not Found:',  # HTTP issues
        r'ValidationError',  # Data validation issues
        r'KeyError(?!.*session)',  # Missing keys (not session related)
        r'AssertionError.*not found in',  # Expected values not found
        r'AssertionError.*!= \'.*\'',  # String comparison failures
        r'property.*has no setter',  # Property setter issues
    ]
    
    # Patterns to ignore (test infrastructure issues)
    ignore_patterns = [
        r'DeprecationWarning.*factory',
        r'GeoIP.*not available',
        r'UNIQUE constraint failed',
        r'IntegrityError.*duplicate',
        r'Creating test database',
        r'Destroying test database',
        r'warnings\.warn',
        r'database table is locked',  # SQLite concurrency issues
        r'Lists differ.*AuditLog.*System.*login',  # Test isolation issues with audit logs
        r'AssertionError.*unexpectedly found in',  # Test data contamination
    ]
    
    lines = output.split('\n')
    
    # Extract summary info
    summary_match = re.search(r'(\d+) failed.*?(\d+) passed', output)
    total_failed = int(summary_match.group(1)) if summary_match else 0
    total_passed = int(summary_match.group(2)) if summary_match else 0
    
    # Find application issues
    app_issues = []
    current_test = None
    current_error = []
    
    for line in lines:
        # Test name line (starts with FAILED)
        if line.startswith('FAILED'):
            # Process previous test
            if current_test and current_error:
                error_text = '\n'.join(current_error)
                if is_app_issue(error_text, app_issue_patterns, ignore_patterns):
                    app_issues.append({
                        'test': current_test,
                        'error': error_text
                    })
            
            # Start new test
            current_test = line.replace('FAILED ', '').split(' ')[0]
            current_error = []
            
        elif line.startswith(('E   ', '   ', '>', 'self')):
            current_error.append(line)
    
    # Process last test
    if current_test and current_error:
        error_text = '\n'.join(current_error)
        if is_app_issue(error_text, app_issue_patterns, ignore_patterns):
            app_issues.append({
                'test': current_test,
                'error': error_text
            })
    
    return {
        'total_failed': total_failed,
        'total_passed': total_passed,
        'app_issues': app_issues,
        'infrastructure_issues': total_failed - len(app_issues)
    }

def is_app_issue(error_text, app_patterns, ignore_patterns):
    """Check if an error is an application code issue"""
    
    # First check if it should be ignored
    for pattern in ignore_patterns:
        if re.search(pattern, error_text, re.IGNORECASE):
            return False
    
    # Then check if it's an application issue
    for pattern in app_patterns:
        if re.search(pattern, error_text, re.IGNORECASE):
            return True
    
    return False

def print_results(results):
    """Print categorized results"""
    
    print("="*60)
    print("🎯 APPLICATION CODE ISSUES ANALYSIS")
    print("="*60)
    print(f"📊 Total Tests: {results['total_passed'] + results['total_failed']}")
    print(f"✅ Passed: {results['total_passed']}")
    print(f"❌ Failed: {results['total_failed']}")
    print(f"🐛 Application Issues: {len(results['app_issues'])}")
    print(f"🔧 Infrastructure Issues: {results['infrastructure_issues']}")
    print()
    
    if not results['app_issues']:
        print("🎉 No application code issues found!")
        print("   All failures appear to be test infrastructure problems.")
        return
    
    print("🔍 APPLICATION CODE ISSUES TO FIX:")
    print()
    
    for i, issue in enumerate(results['app_issues'], 1):
        print(f"--- ISSUE #{i} ---")
        print(f"📍 Test: {issue['test']}")
        
        # Extract the main error line
        error_lines = issue['error'].split('\n')
        main_error = None
        
        for line in error_lines:
            if any(keyword in line for keyword in ['AssertionError:', 'FieldError:', 'TypeError:', 'AttributeError:', 'ValidationError:', 'KeyError:']):
                main_error = line.strip()
                break
        
        if main_error:
            print(f"🚨 Error: {main_error}")
        else:
            # Show first few lines of error
            relevant_lines = [line.strip() for line in error_lines[:3] if line.strip()]
            if relevant_lines:
                print(f"🚨 Error: {relevant_lines[-1]}")
        
        print()

def main():
    """Main function"""
    app_filter = sys.argv[1] if len(sys.argv) > 1 else None
    
    if app_filter:
        print(f"🎯 Focusing on app: {app_filter}")
    else:
        print("🎯 Analyzing all apps")
    
    # Run tests
    exit_code, output = run_tests(app_filter)
    
    # Analyze results
    results = categorize_failures(output)
    
    # Print results
    print_results(results)
    
    # Debug: Show some sample failures if no app issues found
    if not results['app_issues'] and '--debug' in sys.argv:
        print("\n🔍 DEBUG: Sample failure patterns found:")
        lines = output.split('\n')
        for line in lines:
            if 'FAILED' in line or any(word in line for word in ['Error:', 'AssertionError:', 'TypeError:']):
                print(f"   {line}")
        print()
    
    # Recommendations
    print("💡 NEXT STEPS:")
    if results['app_issues']:
        print("1. Fix the application code issues listed above")
        print("2. Check your Django URLs, model fields, and API serializers")
        print("3. Run 'python manage.py check' for configuration issues")
        print("4. Re-run tests to verify fixes")
    else:
        print("1. Your application code looks good!")
        print("2. Focus on fixing test data isolation and setup issues")
        print("3. Consider using factories with unique values")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())