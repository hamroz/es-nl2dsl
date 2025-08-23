#!/usr/bin/env python3
"""
React Frontend Issue Scanner and Fixer

This script identifies real React/frontend application code issues and provides specific fix recommendations.
Filters out test infrastructure problems and focuses on component, hook, state, and integration issues.
"""

import subprocess
import sys
import re
import os
import json
from pathlib import Path

def run_all_frontend_tests(component_filter=None, test_type=None):
    """Run all frontend tests and capture failures"""
    
    frontend_dir = Path(__file__).parent / "frontend"
    if frontend_dir.exists():
        os.chdir(frontend_dir)
    
    if not Path("package.json").exists():
        print("❌ Not in frontend directory - package.json not found")
        return 1, ""
    
    # Build comprehensive test command
    cmd = ["npm", "test", "--", "--watchAll=false", "--verbose", "--coverage=false"]
    
    if component_filter:
        cmd.extend(["--testPathPattern", component_filter])
    
    if test_type:
        type_patterns = {
            "components": "(components|pages)",
            "services": "services",
            "contexts": "contexts", 
            "utils": "utils",
            "hooks": "hooks"
        }
        if test_type in type_patterns:
            cmd.extend(["--testPathPattern", type_patterns[test_type]])
    
    env = os.environ.copy()
    env['CI'] = 'true'
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "Test execution timed out (180s)"
    except Exception as e:
        return 1, f"Error running tests: {e}"

def extract_frontend_issues(output):
    """Extract real application code issues from frontend test output"""
    
    lines = output.split('\n')
    issues = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for test failure markers
        if '● ' in line and ('FAIL' in line or 'Error' in line or 'fail' in line.lower()):
            test_name = line.strip().replace('● ', '')
            
            # Collect error details from next lines
            j = i + 1
            error_lines = []
            
            while j < len(lines) and j < i + 100:  # Look ahead max 100 lines
                error_line = lines[j]
                
                # Stop at next test or summary
                if error_line.startswith('● ') or error_line.startswith('Test Suites:'):
                    break
                
                error_lines.append(error_line)
                j += 1
            
            error_text = '\n'.join(error_lines)
            
            # Analyze this specific error
            analyzed_issues = analyze_specific_error(test_name, error_text)
            issues.extend(analyzed_issues)
        
        i += 1
    
    return issues

def analyze_specific_error(test_name, error_text):
    """Analyze a specific error and categorize it"""
    
    issues = []
    
    # React Component Errors
    if re.search(r'Cannot read propert(y|ies) of (undefined|null)', error_text):
        prop_matches = re.findall(r"Cannot read propert(?:y|ies) of (undefined|null) \(reading '(\w+)'\)", error_text)
        for null_type, prop in prop_matches:
            issues.append({
                'test': test_name,
                'type': 'Null/Undefined Access',
                'error': f"Accessing '{prop}' on {null_type}",
                'severity': 'HIGH',
                'fix_suggestion': f"Add null check: obj?.{prop} or check if obj exists before accessing {prop}",
                'code_example': f"// Before: obj.{prop}\n// After: obj?.{prop} || defaultValue"
            })
    
    # React Element/Component Issues
    if re.search(r'Element type is invalid|Expected a string.*for built-in', error_text):
        issues.append({
            'test': test_name,
            'type': 'Invalid React Element',
            'error': 'Component not properly imported/exported',
            'severity': 'HIGH', 
            'fix_suggestion': 'Check component import/export statements and component definition',
            'code_example': '// Check: import Component from "./Component"\n// Or: import { Component } from "./Component"'
        })
    
    # Hook Errors
    if 'Invalid hook call' in error_text or 'Hooks can only be called' in error_text:
        issues.append({
            'test': test_name,
            'type': 'React Hooks Violation',
            'error': 'Hook called outside component or in wrong context',
            'severity': 'HIGH',
            'fix_suggestion': 'Move hooks to component level, not inside conditions, loops, or nested functions',
            'code_example': '// Wrong: if(condition) { useState() }\n// Right: const [state] = useState(); if(condition) { ... }'
        })
    
    # State Management Errors
    if re.search(r'Cannot read property.*state|state.*is not defined|state.*undefined', error_text):
        issues.append({
            'test': test_name,
            'type': 'State Management Error',
            'error': 'State not properly initialized or accessed',
            'severity': 'MEDIUM',
            'fix_suggestion': 'Initialize state with proper default values and check state before access',
            'code_example': 'const [state, setState] = useState(initialValue)'
        })
    
    # Event Handler Errors
    event_match = re.search(r'(\w+) is not a function.*onClick|(\w+) is not a function.*onChange|(\w+) is not a function.*onSubmit', error_text)
    if event_match:
        handler_name = event_match.group(1) or event_match.group(2)
        issues.append({
            'test': test_name,
            'type': 'Event Handler Error',
            'error': f"'{handler_name}' is not a function",
            'severity': 'MEDIUM',
            'fix_suggestion': f'Define {handler_name} function or check if it\'s passed as prop correctly',
            'code_example': f'const {handler_name} = () => {{ /* handler logic */ }}'
        })
    
    # API/Async Errors
    if re.search(r'Network Error|fetch.*failed|API.*error|Request failed|Promise.*rejected', error_text):
        issues.append({
            'test': test_name,
            'type': 'API/Network Error',
            'error': 'API request failed or async operation error',
            'severity': 'MEDIUM',
            'fix_suggestion': 'Add proper error handling for API calls and mock API responses in tests',
            'code_example': 'try { const data = await api.call() } catch(error) { handleError(error) }'
        })
    
    # Context Errors
    if re.search(r'useAuth.*undefined|AuthContext.*undefined|useContext.*undefined', error_text):
        issues.append({
            'test': test_name,
            'type': 'Context Provider Missing',
            'error': 'Component using context outside of provider',
            'severity': 'HIGH',
            'fix_suggestion': 'Wrap component with appropriate Provider or mock context in tests',
            'code_example': '// In test: wrapper component with <AuthProvider><Component /></AuthProvider>'
        })
    
    # Router Errors
    if re.search(r'useNavigate|useLocation|useParams.*undefined|Router.*not found', error_text):
        issues.append({
            'test': test_name,
            'type': 'React Router Error',
            'error': 'Router hooks used outside Router context',
            'severity': 'MEDIUM',
            'fix_suggestion': 'Wrap component with Router in tests or check routing setup',
            'code_example': '// In test: <BrowserRouter><Component /></BrowserRouter>'
        })
    
    # Material-UI/Theme Errors
    if re.search(r'Material-UI|MUI.*theme|useTheme.*undefined|theme.*not defined', error_text):
        issues.append({
            'test': test_name,
            'type': 'UI Theme Error',
            'error': 'Material-UI theme not available',
            'severity': 'MEDIUM',
            'fix_suggestion': 'Ensure ThemeProvider wraps component or mock theme in tests',
            'code_example': '// <ThemeProvider theme={theme}><Component /></ThemeProvider>'
        })
    
    # Props/PropTypes Errors
    if re.search(r'Failed prop type|Invalid prop.*supplied', error_text):
        issues.append({
            'test': test_name,
            'type': 'Props Validation Error',
            'error': 'Component received invalid props',
            'severity': 'LOW',
            'fix_suggestion': 'Check prop types and ensure correct props are passed',
            'code_example': 'Component.propTypes = { prop: PropTypes.string.isRequired }'
        })
    
    # WebSocket/Real-time Errors (specific to your app)
    if re.search(r'WebSocket.*failed|socket.*error|WebSocket.*undefined', error_text):
        issues.append({
            'test': test_name,
            'type': 'WebSocket Connection Error',
            'error': 'WebSocket connection failed',
            'severity': 'MEDIUM',
            'fix_suggestion': 'Mock WebSocket connections in tests or check WebSocket setup',
            'code_example': '// Mock: jest.mock("./websocket", () => ({ connect: jest.fn() }))'
        })
    
    return issues

def generate_frontend_fix_summary(issues, filter_info):
    """Generate a comprehensive fix summary for frontend issues"""
    
    print("\n" + "="*60)
    print("🎨 REACT FRONTEND ISSUES TO FIX")
    print("="*60)
    
    if not issues:
        print("🎉 No React application code issues found!")
        print("   All test failures appear to be infrastructure or test setup related.")
        return
    
    print(f"Found {len(issues)} frontend application issues:")
    if filter_info:
        print(f"Filter: {filter_info}")
    print()
    
    # Group by severity and type
    by_severity = {'HIGH': [], 'MEDIUM': [], 'LOW': []}
    by_type = {}
    
    for issue in issues:
        severity = issue.get('severity', 'MEDIUM')
        issue_type = issue['type']
        
        by_severity[severity].append(issue)
        if issue_type not in by_type:
            by_type[issue_type] = []
        by_type[issue_type].append(issue)
    
    # Show by severity
    for severity in ['HIGH', 'MEDIUM', 'LOW']:
        if by_severity[severity]:
            severity_emoji = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}
            print(f"{severity_emoji[severity]} {severity} PRIORITY ({len(by_severity[severity])} issues)")
            print("-" * 50)
            
            for issue in by_severity[severity]:
                print(f"📍 {issue['type']}: {issue['error']}")
                print(f"   Test: {issue['test']}")
                print(f"   💡 Fix: {issue['fix_suggestion']}")
                if 'code_example' in issue:
                    print(f"   📝 Example:")
                    for line in issue['code_example'].split('\n'):
                        print(f"      {line}")
                print()
    
    print("📋 ISSUE SUMMARY BY TYPE:")
    print("-" * 30)
    for issue_type, type_issues in by_type.items():
        count = len(type_issues)
        print(f"• {issue_type}: {count} issue{'s' if count != 1 else ''}")
    
    print("\n🚀 RECOMMENDED FIX ORDER:")
    print("1. Fix HIGH priority issues first (Component errors, Hooks, Context)")
    print("2. Then MEDIUM priority (State, Events, API, Router)")  
    print("3. Finally LOW priority (Props validation)")
    print()
    print("🔧 NEXT STEPS:")
    print("1. Fix issues in the priority order above")
    print("2. Run tests after each fix: npm test")
    print("3. Use: python3 analyze_frontend_failures.py <component> --full for details")
    print("4. Focus on one component/area at a time for systematic fixing")

def main():
    """Main function"""
    
    component_filter = None
    test_type = None
    
    # Parse arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ['components', 'services', 'contexts', 'utils', 'hooks']:
            test_type = arg
        else:
            component_filter = arg
    
    print("🎨 REACT FRONTEND ISSUE ANALYZER")
    print("="*50)
    
    filter_info = None
    if component_filter:
        filter_info = f"Component/Path: {component_filter}"
        print(f"📍 Analyzing component/path: {component_filter}")
    elif test_type:
        filter_info = f"Test Type: {test_type}"
        print(f"📍 Analyzing test type: {test_type}")
    else:
        print("📍 Analyzing all frontend tests")
    
    print("⏳ Running all tests to identify issues...")
    
    exit_code, output = run_all_frontend_tests(component_filter, test_type)
    
    if exit_code == 0:
        print("🎉 All frontend tests passed! No issues to fix.")
        return 0
    
    print("📊 Analyzing test failures...")
    issues = extract_frontend_issues(output)
    
    generate_frontend_fix_summary(issues, filter_info)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())