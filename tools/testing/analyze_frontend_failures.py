#!/usr/bin/env python3
"""
Analyze React frontend test failures to identify real application code issues.
Filters out test infrastructure problems and focuses on component, logic, and integration issues.
"""

import subprocess
import sys
import re
import os
import json
from pathlib import Path

def run_frontend_tests(component_filter=None, test_type=None):
    """Run frontend tests with full output for analysis"""
    
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    if frontend_dir.exists():
        os.chdir(frontend_dir)
    
    # Check for package.json and node_modules
    if not Path("package.json").exists():
        print("❌ Not in frontend directory - package.json not found")
        return 1, ""
    
    # Build command
    cmd = ["npm", "test", "--", "--watchAll=false", "--verbose"]
    
    if component_filter:
        # Filter by specific component or path
        cmd.extend(["--testPathPattern", component_filter])
    
    if test_type:
        if test_type == "components":
            cmd.extend(["--testPathPattern", "(components|pages)"])
        elif test_type == "services":
            cmd.extend(["--testPathPattern", "services"])
        elif test_type == "contexts":
            cmd.extend(["--testPathPattern", "contexts"])
        elif test_type == "utils":
            cmd.extend(["--testPathPattern", "utils"])
    
    # Environment for test output
    env = os.environ.copy()
    env['CI'] = 'true'  # Prevent interactive mode
    
    print(f"🔍 Running frontend tests: {' '.join(cmd)}")
    print(f"📂 Working directory: {os.getcwd()}")
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "Test execution timed out"
    except Exception as e:
        return 1, f"Error running tests: {e}"

def analyze_frontend_failure(output):
    """Analyze the first frontend test failure in detail"""
    
    lines = output.split('\n')
    
    # Find first failure
    failure_info = None
    test_name = None
    error_details = []
    
    in_failure = False
    
    for i, line in enumerate(lines):
        # Look for test failure start
        if '● ' in line and ('FAIL' in line or 'fail' in line.lower()):
            if not failure_info:  # Only capture first failure
                test_name = line.strip()
                failure_info = {'test_name': test_name, 'start_line': i}
                in_failure = True
                continue
        
        # Collect error details when in failure section
        if in_failure:
            # Stop collecting at next test or summary
            if line.startswith('Test Suites:') or line.startswith('●') and i > failure_info['start_line'] + 1:
                break
            
            if line.strip():  # Non-empty lines
                error_details.append(line)
    
    if not failure_info:
        return None
    
    error_text = '\n'.join(error_details)
    
    # Categorize the failure
    categories = analyze_error_patterns(error_text, test_name)
    
    return {
        'test_name': test_name,
        'error_text': error_text,
        'categories': categories,
        'full_output': '\n'.join(lines[failure_info['start_line']:failure_info['start_line'] + 50])
    }

def analyze_error_patterns(error_text, test_name):
    """Analyze error patterns specific to React/Frontend issues"""
    
    app_issues = []
    infra_issues = []
    
    # React Component Issues
    if re.search(r'Cannot read propert(y|ies) of (undefined|null)', error_text):
        prop_match = re.search(r"Cannot read propert(?:y|ies) of (undefined|null) \(reading '(\w+)'\)", error_text)
        if prop_match:
            null_type, property_name = prop_match.groups()
            app_issues.append({
                'type': 'Undefined Property Access',
                'error': f"Accessing '{property_name}' on {null_type}",
                'fix': f"Add null check: obj?.{property_name} or obj && obj.{property_name}"
            })
    
    # React Rendering Issues
    if re.search(r'Element type is invalid|Expected a string.*for built-in', error_text):
        app_issues.append({
            'type': 'Invalid React Element',
            'error': 'Component not properly imported or defined',
            'fix': 'Check component imports and exports'
        })
    
    # Hook Issues
    if 'Invalid hook call' in error_text or 'Hooks can only be called' in error_text:
        app_issues.append({
            'type': 'React Hooks Error',
            'error': 'Hook called outside React component or in wrong context',
            'fix': 'Move hooks to component level, not inside conditions or loops'
        })
    
    # State Management Issues
    if re.search(r'Cannot read property.*of undefined.*state|state.*is not defined', error_text):
        app_issues.append({
            'type': 'State Management Error',
            'error': 'State not properly initialized or accessed',
            'fix': 'Initialize state properly and check state existence before access'
        })
    
    # API/Network Issues
    if re.search(r'Network Error|fetch.*failed|API.*error|Request failed', error_text):
        app_issues.append({
            'type': 'API/Network Error',
            'error': 'API request failed or network error',
            'fix': 'Check API endpoint, add error handling, mock API for tests'
        })
    
    # Props/PropTypes Issues
    if 'Failed prop type' in error_text or 'Invalid prop' in error_text:
        app_issues.append({
            'type': 'Props Validation Error',
            'error': 'Component received invalid props',
            'fix': 'Check prop types and ensure correct props are passed'
        })
    
    # Event Handler Issues
    if re.search(r'.*is not a function.*onClick|.*is not a function.*onChange|.*is not a function.*onSubmit', error_text):
        handler_match = re.search(r'(\w+) is not a function', error_text)
        if handler_match:
            handler_name = handler_match.group(1)
            app_issues.append({
                'type': 'Event Handler Error',
                'error': f"'{handler_name}' is not a function",
                'fix': f"Define {handler_name} function or check if prop is passed correctly"
            })
    
    # Material-UI/Component Library Issues
    if re.search(r'Material-UI|MUI.*theme|useTheme.*undefined', error_text):
        app_issues.append({
            'type': 'UI Library Error',
            'error': 'Material-UI theme or component error',
            'fix': 'Ensure ThemeProvider is properly set up and components are imported correctly'
        })
    
    # Authentication Context Issues
    if 'useAuth' in error_text or 'AuthContext' in error_text:
        app_issues.append({
            'type': 'Authentication Context Error',
            'error': 'Authentication context not available or improperly used',
            'fix': 'Wrap component with AuthProvider or mock auth context in tests'
        })
    
    # Routing Issues
    if 'useNavigate' in error_text or 'useLocation' in error_text or 'Router' in error_text:
        app_issues.append({
            'type': 'React Router Error',
            'error': 'Router hooks used outside Router context',
            'fix': 'Wrap component with Router in tests or check routing setup'
        })
    
    # Test Infrastructure Issues (to ignore)
    if re.search(r'Module not found.*__mocks__|Jest.*configuration|setupTests', error_text):
        infra_issues.append('Test configuration or mock setup issue')
    
    if re.search(r'SyntaxError.*import|Cannot resolve module|Module parse failed', error_text):
        infra_issues.append('Module resolution or build configuration issue')
    
    if 'ReferenceError: document is not defined' in error_text:
        infra_issues.append('DOM environment not properly set up in test')
    
    # WebSocket/Real-time Issues (specific to your app)
    if 'WebSocket' in error_text or 'socket' in error_text.lower():
        app_issues.append({
            'type': 'WebSocket Connection Error',
            'error': 'WebSocket connection failed or not properly mocked',
            'fix': 'Mock WebSocket in tests or check real-time connection setup'
        })
    
    return {
        'app_issues': app_issues,
        'infra_issues': infra_issues
    }

def get_fix_priority(issue_type):
    """Get fix priority for different issue types"""
    priority_map = {
        'Undefined Property Access': 1,
        'Invalid React Element': 1,
        'React Hooks Error': 1,
        'State Management Error': 2,
        'Event Handler Error': 2,
        'API/Network Error': 3,
        'Authentication Context Error': 3,
        'React Router Error': 3,
        'Props Validation Error': 4,
        'UI Library Error': 4,
        'WebSocket Connection Error': 4,
    }
    return priority_map.get(issue_type, 5)

def main():
    """Main function"""
    component_filter = None
    test_type = None
    
    # Parse arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['components', 'services', 'contexts', 'utils']:
            test_type = sys.argv[1]
        else:
            component_filter = sys.argv[1]
    
    print("🔍 REACT FRONTEND FAILURE ANALYSIS")
    print("="*50)
    
    if component_filter:
        print(f"📍 Analyzing component/path: {component_filter}")
    elif test_type:
        print(f"📍 Analyzing test type: {test_type}")
    else:
        print("📍 Analyzing all frontend tests")
    
    print("⏳ Running tests (stopping on first failure)...")
    
    exit_code, output = run_frontend_tests(component_filter, test_type)
    
    if exit_code == 0:
        print("🎉 All frontend tests passed!")
        return 0
    
    analysis = analyze_frontend_failure(output)
    
    if not analysis:
        print("❌ Could not analyze failure - no clear failure pattern found")
        if '--debug' in sys.argv:
            print("\n🔍 DEBUG: Raw output:")
            print("-" * 30)
            print(output[:2000])  # First 2000 chars
        return 1
    
    print(f"\n📋 Test: {analysis['test_name']}")
    print()
    
    if analysis['categories']['app_issues']:
        print("🐛 APPLICATION CODE ISSUES:")
        
        # Sort by priority
        sorted_issues = sorted(
            analysis['categories']['app_issues'],
            key=lambda x: get_fix_priority(x['type'])
        )
        
        for issue in sorted_issues:
            print(f"   • {issue['type']}: {issue['error']}")
            print(f"     💡 Fix: {issue['fix']}")
        print()
    
    if analysis['categories']['infra_issues']:
        print("🔧 INFRASTRUCTURE ISSUES:")
        for issue in analysis['categories']['infra_issues']:
            print(f"   • {issue}")
        print()
    
    if not analysis['categories']['app_issues'] and not analysis['categories']['infra_issues']:
        print("❓ UNCATEGORIZED ISSUE:")
        # Show key error lines
        for line in analysis['error_text'].split('\n'):
            if any(keyword in line.lower() for keyword in ['error:', 'failed:', 'cannot', 'undefined', 'null']):
                print(f"   {line.strip()}")
        print()
    
    print("="*50)
    print("💡 RECOMMENDATIONS:")
    
    if analysis['categories']['app_issues']:
        print("1. Fix the application code issues listed above")
        print("2. Focus on high-priority issues first (Undefined access, Invalid elements, Hooks)")
        print("3. Add proper null checks and error boundaries")
        print("4. Ensure proper component lifecycle and state management")
    elif analysis['categories']['infra_issues']:
        print("1. These appear to be test infrastructure issues")
        print("2. Check test configuration, mocks, and setup files")
        print("3. The component code is likely correct")
    else:
        print("1. Review the error details below for clues")
        print("2. This may be a complex integration or configuration issue")
    
    if '--full' in sys.argv:
        print("\n🔍 FULL ERROR OUTPUT:")
        print("-" * 50)
        print(analysis['full_output'])
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())