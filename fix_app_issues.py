#!/usr/bin/env python3
"""
Application Code Issue Fixer for ES-NL2DSL Backend

This script identifies real application code issues and provides specific fix recommendations.
"""

import subprocess
import sys
import re
import os
from pathlib import Path
import json

def run_all_tests(app_filter=None):
    """Run all tests and capture failures"""
    
    backend_dir = Path(__file__).parent / "backend"
    if backend_dir.exists():
        os.chdir(backend_dir)
    
    venv_python = Path("venv/bin/python")
    if not venv_python.exists():
        print("❌ Virtual environment not found")
        return 1, ""
    
    cmd = [
        str(venv_python), "-m", "pytest", 
        "--tb=short",
        "--disable-warnings", 
        "--no-cov",
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

def extract_app_issues(output):
    """Extract real application code issues from test output"""
    
    lines = output.split('\n')
    issues = []
    current_test = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for failed test
        if line.startswith('FAILED') and '::' in line:
            current_test = line.replace('FAILED ', '').split(' ')[0]
            
            # Look for the actual error in next few lines
            j = i + 1
            while j < len(lines) and j < i + 50:  # Look ahead max 50 lines
                error_line = lines[j]
                
                # HTTP status code issues
                status_match = re.search(r'AssertionError: (\d+) != (\d+)', error_line)
                if status_match:
                    actual, expected = status_match.groups()
                    issues.append({
                        'test': current_test,
                        'type': 'HTTP Status Code',
                        'error': f"Expected {expected}, got {actual}",
                        'description': get_status_description(actual, expected),
                        'fix_suggestion': get_status_fix_suggestion(actual, expected)
                    })
                    break
                
                # Field errors
                if 'FieldError' in error_line and 'Cannot resolve keyword' in error_line:
                    field_match = re.search(r"Cannot resolve keyword '(\w+)'.*Choices are: (.+)", error_line)
                    if field_match:
                        missing_field, available_fields = field_match.groups()
                        issues.append({
                            'test': current_test,
                            'type': 'Model Field Error',
                            'error': f"Field '{missing_field}' doesn't exist",
                            'description': f"Available fields: {available_fields}",
                            'fix_suggestion': get_field_fix_suggestion(missing_field, available_fields)
                        })
                        break
                
                # Method signature issues
                if 'TypeError' in error_line and 'unexpected keyword argument' in error_line:
                    arg_match = re.search(r"unexpected keyword argument '(\w+)'", error_line)
                    if arg_match:
                        bad_arg = arg_match.group(1)
                        issues.append({
                            'test': current_test,
                            'type': 'Method Signature Error',
                            'error': f"Method doesn't accept argument '{bad_arg}'",
                            'description': 'Method signature mismatch between test and implementation',
                            'fix_suggestion': f"Either remove '{bad_arg}' from test call or add it to method definition"
                        })
                        break
                
                # Missing attributes/methods
                if 'AttributeError' in error_line and 'has no attribute' in error_line:
                    attr_match = re.search(r"'(\w+)' object has no attribute '(\w+)'", error_line)
                    if attr_match:
                        obj_type, missing_attr = attr_match.groups()
                        issues.append({
                            'test': current_test,
                            'type': 'Missing Attribute/Method',
                            'error': f"{obj_type} missing '{missing_attr}'",
                            'description': f"The {obj_type} class doesn't have the {missing_attr} attribute or method",
                            'fix_suggestion': f"Add '{missing_attr}' method/property to {obj_type} class"
                        })
                        break
                
                # Property setter issues
                if 'property' in error_line and 'has no setter' in error_line:
                    issues.append({
                        'test': current_test,
                        'type': 'Property Setter Error',
                        'error': 'Property has no setter',
                        'description': 'Trying to set a read-only property',
                        'fix_suggestion': 'Add setter to property or modify test to not set this property'
                    })
                    break
                
                j += 1
        
        i += 1
    
    return issues

def get_status_description(actual, expected):
    """Get description for HTTP status code issues"""
    status_meanings = {
        '200': 'OK - Success',
        '201': 'Created - Resource created successfully',
        '400': 'Bad Request - Invalid data or missing required fields',
        '401': 'Unauthorized - Authentication required',
        '403': 'Forbidden - Permission denied',
        '404': 'Not Found - Resource or endpoint not found',
        '405': 'Method Not Allowed - Wrong HTTP method for endpoint',
        '500': 'Internal Server Error - Server-side error'
    }
    
    actual_desc = status_meanings.get(actual, f'Status {actual}')
    expected_desc = status_meanings.get(expected, f'Status {expected}')
    
    return f"Got: {actual_desc}, Expected: {expected_desc}"

def get_status_fix_suggestion(actual, expected):
    """Get fix suggestion for HTTP status code issues"""
    if actual == '400' and expected == '201':
        return "Check request data validation. Likely missing required fields or invalid data format."
    elif actual == '405' and expected == '200':
        return "Check URL patterns and view methods. Wrong HTTP method or missing endpoint."
    elif actual == '404':
        return "Check URL routing. Endpoint might not exist or URL pattern incorrect."
    elif actual == '403' and expected in ['200', '201']:
        return "Check permissions and authentication. User might not have required permissions."
    else:
        return f"Debug why endpoint returns {actual} instead of {expected}"

def get_field_fix_suggestion(missing_field, available_fields):
    """Get fix suggestion for field errors"""
    available = available_fields.split(', ')
    
    # Look for similar field names
    similar = []
    for field in available:
        if missing_field.lower() in field.lower() or field.lower() in missing_field.lower():
            similar.append(field)
    
    if similar:
        return f"Use '{similar[0]}' instead of '{missing_field}' (similar available field)"
    else:
        return f"Add '{missing_field}' field to model or use one of: {available_fields}"

def generate_fix_summary(issues, app_filter):
    """Generate a summary of fixes needed"""
    
    print("\n" + "="*60)
    print("🔧 APPLICATION CODE ISSUES TO FIX")
    print("="*60)
    
    if not issues:
        print("🎉 No application code issues found!")
        print("   All test failures appear to be infrastructure or test setup related.")
        return
    
    print(f"Found {len(issues)} application code issues in {app_filter or 'all apps'}:")
    print()
    
    # Group by type
    by_type = {}
    for issue in issues:
        issue_type = issue['type']
        if issue_type not in by_type:
            by_type[issue_type] = []
        by_type[issue_type].append(issue)
    
    for issue_type, type_issues in by_type.items():
        print(f"📋 {issue_type} Issues ({len(type_issues)})")
        print("-" * 40)
        
        for i, issue in enumerate(type_issues, 1):
            print(f"{i}. Test: {issue['test']}")
            print(f"   Error: {issue['error']}")
            print(f"   Fix: {issue['fix_suggestion']}")
            if 'description' in issue:
                print(f"   Details: {issue['description']}")
            print()
    
    print("💡 PRIORITY ORDER:")
    priority = [
        "HTTP Status Code",
        "Model Field Error", 
        "Method Signature Error",
        "Missing Attribute/Method",
        "Property Setter Error"
    ]
    
    for p in priority:
        if p in by_type:
            print(f"1. Fix {p} issues first ({len(by_type[p])} issues)")
            break
    
    print("\n🚀 NEXT STEPS:")
    print("1. Fix issues in the priority order above")
    print("2. Run tests after each fix to verify")
    print("3. Use: python3 analyze_test_failures.py <app> --full for detailed tracebacks")

def main():
    """Main function"""
    app_filter = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("🔍 ES-NL2DSL APPLICATION CODE ISSUE ANALYZER")
    print("="*50)
    
    if app_filter:
        print(f"📍 Analyzing app: {app_filter}")
    else:
        print("📍 Analyzing all apps")
    
    print("⏳ Running all tests to identify issues...")
    
    exit_code, output = run_all_tests(app_filter)
    
    if exit_code == 0:
        print("🎉 All tests passed! No issues to fix.")
        return 0
    
    print("📊 Analyzing test failures...")
    issues = extract_app_issues(output)
    
    generate_fix_summary(issues, app_filter)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())