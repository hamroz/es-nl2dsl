#!/usr/bin/env python3
"""
Simple React Frontend Issue Finder

Quick tool to identify application code issues vs test infrastructure problems in React tests.
"""

import subprocess
import sys
import re
import os
from pathlib import Path

def run_frontend_tests(component_filter=None):
    """Run frontend tests and capture output"""
    
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    if frontend_dir.exists():
        os.chdir(frontend_dir)
    
    if not Path("package.json").exists():
        print("❌ Not in frontend directory")
        return 1, ""
    
    cmd = ["npm", "test", "--", "--watchAll=false", "--coverage=false"]
    
    if component_filter:
        cmd.extend(["--testPathPattern", component_filter])
    
    env = os.environ.copy()
    env['CI'] = 'true'
    
    print(f"🔍 Running frontend tests: {' '.join(cmd)}")
    print(f"📂 Working directory: {os.getcwd()}")
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, f"Error: {e}"

def categorize_frontend_failures(output):
    """Categorize frontend test failures"""
    
    # Patterns for React/Frontend application issues
    app_issue_patterns = [
        r'Cannot read propert(y|ies) of (undefined|null)',  # Null/undefined access
        r'Element type is invalid',  # Invalid React elements
        r'Invalid hook call',  # Hook violations
        r'Hooks can only be called',  # Hook context errors
        r'.*is not a function.*onClick|.*is not a function.*onChange',  # Event handler errors
        r'useAuth.*undefined|AuthContext.*undefined',  # Context errors
        r'useNavigate.*undefined|useLocation.*undefined',  # Router errors
        r'Network Error|fetch.*failed|API.*error',  # API errors
        r'Material-UI.*theme|useTheme.*undefined',  # Theme errors
        r'Failed prop type|Invalid prop',  # Props errors
        r'WebSocket.*failed|socket.*error',  # WebSocket errors
    ]
    
    # Patterns to ignore (test infrastructure)
    ignore_patterns = [
        r'Module not found.*__mocks__',  # Mock setup
        r'Jest.*configuration',  # Jest config
        r'setupTests',  # Test setup
        r'SyntaxError.*import',  # Build issues  
        r'Cannot resolve module',  # Module resolution
        r'ReferenceError: document is not defined',  # DOM environment
        r'JSDOM.*error',  # JSDOM issues
        r'Transform.*failed',  # Build transform issues
    ]
    
    lines = output.split('\n')
    
    # Extract test summary
    summary_match = re.search(r'Tests:.*?(\d+) failed.*?(\d+) passed', output)
    total_failed = int(summary_match.group(1)) if summary_match else 0
    total_passed = int(summary_match.group(2)) if summary_match else 0
    
    # Find application issues
    app_issues = []
    current_test = None
    current_error = []
    
    for line in lines:
        if '● ' in line and ('FAIL' in line or 'Error' in line):
            # Process previous test
            if current_test and current_error:
                error_text = '\n'.join(current_error)
                if is_frontend_app_issue(error_text, app_issue_patterns, ignore_patterns):
                    app_issues.append({
                        'test': current_test,
                        'error': error_text[:200] + '...' if len(error_text) > 200 else error_text
                    })
            
            # Start new test
            current_test = line.strip().replace('● ', '')
            current_error = []
        
        elif current_test and line.strip():
            current_error.append(line)
            
            # Stop at next test or summary
            if 'Test Suites:' in line or line.startswith('●'):
                break
    
    # Process last test
    if current_test and current_error:
        error_text = '\n'.join(current_error)
        if is_frontend_app_issue(error_text, app_issue_patterns, ignore_patterns):
            app_issues.append({
                'test': current_test,
                'error': error_text[:200] + '...' if len(error_text) > 200 else error_text
            })
    
    return {
        'total_failed': total_failed,
        'total_passed': total_passed,
        'app_issues': app_issues,
        'infrastructure_issues': total_failed - len(app_issues)
    }

def is_frontend_app_issue(error_text, app_patterns, ignore_patterns):
    """Check if error is a frontend application issue"""
    
    # First check if it should be ignored
    for pattern in ignore_patterns:
        if re.search(pattern, error_text, re.IGNORECASE):
            return False
    
    # Then check if it's an application issue
    for pattern in app_patterns:
        if re.search(pattern, error_text, re.IGNORECASE):
            return True
    
    return False

def print_frontend_results(results):
    """Print categorized frontend results"""
    
    print("="*60)
    print("🎨 REACT FRONTEND ISSUES ANALYSIS") 
    print("="*60)
    print(f"📊 Total Tests: {results['total_passed'] + results['total_failed']}")
    print(f"✅ Passed: {results['total_passed']}")
    print(f"❌ Failed: {results['total_failed']}")
    print(f"🐛 React App Issues: {len(results['app_issues'])}")
    print(f"🔧 Test Infrastructure Issues: {results['infrastructure_issues']}")
    print()
    
    if not results['app_issues']:
        print("🎉 No React application code issues found!")
        print("   All failures appear to be test infrastructure problems.")
        return
    
    print("🔍 REACT APPLICATION ISSUES TO FIX:")
    print()
    
    for i, issue in enumerate(results['app_issues'], 1):
        print(f"--- ISSUE #{i} ---")
        print(f"📍 Test: {issue['test']}")
        
        # Extract key error info
        error_lines = issue['error'].split('\n')
        key_error = None
        
        for line in error_lines:
            if any(keyword in line for keyword in [
                'Cannot read', 'Element type', 'Invalid hook', 'is not a function',
                'undefined', 'Network Error', 'Failed prop'
            ]):
                key_error = line.strip()
                break
        
        if key_error:
            print(f"🚨 Error: {key_error}")
        
        print()

def main():
    """Main function"""
    
    component_filter = sys.argv[1] if len(sys.argv) > 1 else None
    
    if component_filter:
        print(f"🎯 Focusing on: {component_filter}")
    else:
        print("🎯 Analyzing all React components")
    
    # Run tests
    exit_code, output = run_frontend_tests(component_filter)
    
    # Analyze results
    results = categorize_frontend_failures(output)
    
    # Print results
    print_frontend_results(results)
    
    # Debug output if requested
    if '--debug' in sys.argv and not results['app_issues']:
        print("\n🔍 DEBUG: Sample failure patterns found:")
        lines = output.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ['error', 'failed', 'cannot', 'undefined', 'invalid']):
                print(f"   {line}")
        print()
    
    # Recommendations
    print("💡 NEXT STEPS:")
    if results['app_issues']:
        print("1. Fix the React application issues listed above")
        print("2. Focus on component logic, state management, and prop handling")
        print("3. Use: python3 analyze_frontend_failures.py <component> --full for details")
        print("4. Check component imports, hooks usage, and context providers")
    else:
        print("1. Your React application code looks good!")
        print("2. Focus on fixing test configuration and mock setup")
        print("3. Check Jest configuration, test utilities, and mock files")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())