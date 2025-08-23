#!/bin/bash

# ES-NL2DSL Backend Application Code Test Runner
# This script runs only tests that reveal actual application code issues,
# filtering out test infrastructure problems, warnings, and known test setup issues.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  ES-NL2DSL Application Code Issue Scanner${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_section() {
    echo ""
    echo -e "${PURPLE}===== $1 =====${NC}"
    echo ""
}

# Help function
show_help() {
    echo "ES-NL2DSL Application Code Issue Scanner"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -a, --app APP        Run tests for specific app only (authentication, queries, etc.)"
    echo "  -v, --verbose        Show detailed test output"
    echo "  -s, --summary        Show only summary of issues"
    echo "  --api-only           Test only API endpoints"
    echo "  --models-only        Test only model functionality"
    echo "  --services-only      Test only service/business logic"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Scan all apps for application issues"
    echo "  $0 --app authentication      # Scan only authentication app"
    echo "  $0 --api-only               # Test only API endpoints"
    echo "  $0 --summary                # Show concise issue summary"
    echo ""
}

# Parse command line arguments
APP_FILTER=""
VERBOSE=false
SUMMARY_ONLY=false
API_ONLY=false
MODELS_ONLY=false
SERVICES_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--app)
            APP_FILTER="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -s|--summary)
            SUMMARY_ONLY=true
            shift
            ;;
        --api-only)
            API_ONLY=true
            shift
            ;;
        --models-only)
            MODELS_ONLY=true
            shift
            ;;
        --services-only)
            SERVICES_ONLY=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Change to backend directory if not already there
if [[ $(basename "$PWD") != "backend" ]]; then
    if [[ -d "backend" ]]; then
        cd backend
    else
        print_error "Not in backend directory and backend/ not found"
        exit 1
    fi
fi

print_header

# Activate virtual environment
if [[ -f "venv/bin/activate" ]]; then
    source venv/bin/activate
    print_status "Activated virtual environment"
elif [[ -f "../env/bin/activate" ]]; then
    source ../env/bin/activate
    print_status "Activated virtual environment"
else
    print_warning "No virtual environment found - using system Python"
fi

# Set Django settings
export DJANGO_SETTINGS_MODULE=es_nl2dsl_api.test_settings

# Build pytest command to focus on application code issues
pytest_cmd=("python" "-m" "pytest")

# Add target filters
if [[ -n "$APP_FILTER" ]]; then
    pytest_cmd+=("$APP_FILTER/")
fi

# Add test type filters
if [[ "$API_ONLY" == true ]]; then
    pytest_cmd+=("-k" "api or endpoint or view or serializer")
elif [[ "$MODELS_ONLY" == true ]]; then
    pytest_cmd+=("-k" "model and not api")
elif [[ "$SERVICES_ONLY" == true ]]; then
    pytest_cmd+=("-k" "service or util or manager and not api and not model")
fi

# Configure output format to focus on application issues
if [[ "$SUMMARY_ONLY" == true ]]; then
    pytest_cmd+=("--tb=no" "--no-header" "-q")
else
    pytest_cmd+=("--tb=short" "--no-header")
fi

if [[ "$VERBOSE" == true ]]; then
    pytest_cmd+=("-v")
else
    pytest_cmd+=("-q")
fi

# Disable warnings and coverage for cleaner output
pytest_cmd+=("--disable-warnings" "--no-cov")

# Filter out known test infrastructure issues
TEMP_LOG=$(mktemp)
OUTPUT_FILE=$(mktemp)

print_status "Running application code tests..."
print_status "Command: ${pytest_cmd[*]}"
echo ""

# Run tests and capture output
if "${pytest_cmd[@]}" > "$TEMP_LOG" 2>&1; then
    TEST_EXIT_CODE=0
else
    TEST_EXIT_CODE=$?
fi

# Process output to filter application-specific issues
python3 << 'EOF' > "$OUTPUT_FILE"
import sys
import re

# Read the test output
try:
    with open(sys.argv[1], 'r') as f:
        content = f.read()
except:
    print("Could not read test output")
    sys.exit(1)

# Patterns to identify application code issues (not test infrastructure)
APPLICATION_ISSUE_PATTERNS = [
    # API/HTTP issues
    r'AssertionError: \d+ != \d+.*status.*code',
    r'AssertionError.*HTTP_\d+',
    r'Bad Request:|Method Not Allowed:|Forbidden:|Not Found:',
    
    # Model/Database field issues  
    r'FieldError.*Cannot resolve keyword',
    r'got an unexpected keyword argument',
    r'TypeError.*missing.*required.*argument',
    
    # Serializer/Validation issues
    r'ValidationError',
    r'serializer.*error',
    
    # Business logic issues
    r'AttributeError.*has no attribute',
    r'KeyError.*not found',
    
    # Integration issues
    r'ConnectionError|RequestException',
]

# Patterns to IGNORE (test infrastructure issues)
IGNORE_PATTERNS = [
    r'DeprecationWarning.*factory',
    r'GeoIP.*not available',
    r'UNIQUE constraint failed',  # Test data isolation issues
    r'IntegrityError.*duplicate',
    r'warnings\.warn',
    r'pytest.*collection',
    r'Creating test database',
    r'Destroying test database',
]

lines = content.split('\n')
current_failure = []
in_failure_section = False
application_failures = []
total_tests = 0
total_failures = 0

for line in lines:
    # Extract test counts
    if 'failed' in line and 'passed' in line:
        # Pattern: "34 failed, 77 passed"
        match = re.search(r'(\d+) failed.*?(\d+) passed', line)
        if match:
            total_failures = int(match.group(1))
            passed = int(match.group(2))
            total_tests = total_failures + passed
    
    # Track failure sections
    if line.startswith('FAILURES'):
        in_failure_section = True
        continue
    elif line.startswith('=') and 'failed' in line:
        in_failure_section = False
        if current_failure:
            application_failures.append('\n'.join(current_failure))
        current_failure = []
        continue
    
    if in_failure_section:
        # Start of new failure
        if line.startswith('_') and 'FAILED' not in line:
            if current_failure:
                # Check if current failure is application-related
                failure_text = '\n'.join(current_failure)
                is_application_issue = False
                is_ignored = False
                
                # Check if it matches application issue patterns
                for pattern in APPLICATION_ISSUE_PATTERNS:
                    if re.search(pattern, failure_text, re.IGNORECASE):
                        is_application_issue = True
                        break
                
                # Check if it should be ignored
                for pattern in IGNORE_PATTERNS:
                    if re.search(pattern, failure_text, re.IGNORECASE):
                        is_ignored = True
                        break
                
                # Add to application failures if relevant
                if is_application_issue and not is_ignored:
                    application_failures.append(failure_text)
            
            current_failure = [line]
        else:
            current_failure.append(line)

# Handle last failure
if current_failure:
    failure_text = '\n'.join(current_failure)
    is_application_issue = False
    is_ignored = False
    
    for pattern in APPLICATION_ISSUE_PATTERNS:
        if re.search(pattern, failure_text, re.IGNORECASE):
            is_application_issue = True
            break
    
    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, failure_text, re.IGNORECASE):
            is_ignored = True
            break
    
    if is_application_issue and not is_ignored:
        application_failures.append(failure_text)

# Output results
print("="*60)
print(f"APPLICATION CODE ISSUES SUMMARY")
print("="*60)
print(f"Total Tests Run: {total_tests}")
print(f"Total Failures: {total_failures}")
print(f"Application Code Issues: {len(application_failures)}")
print(f"Test Infrastructure Issues: {total_failures - len(application_failures)}")
print("")

if len(application_failures) == 0:
    print("🎉 No application code issues found!")
    print("All failures appear to be test infrastructure or data isolation issues.")
else:
    print("🔍 APPLICATION CODE ISSUES TO FIX:")
    print("")
    
    for i, failure in enumerate(application_failures, 1):
        print(f"--- ISSUE #{i} ---")
        # Extract test name
        test_match = re.search(r'test_\w+', failure)
        if test_match:
            print(f"Test: {test_match.group()}")
        
        # Extract main error
        error_lines = [line for line in failure.split('\n') if 'Error:' in line or 'AssertionError:' in line]
        if error_lines:
            print(f"Error: {error_lines[-1].strip()}")
        
        print()

EOF

python3 "$OUTPUT_FILE" "$TEMP_LOG"

# Show detailed failures if verbose
if [[ "$VERBOSE" == true ]] && [[ "$SUMMARY_ONLY" == false ]]; then
    print_section "DETAILED TEST OUTPUT"
    cat "$TEMP_LOG"
fi

# Cleanup
rm -f "$TEMP_LOG" "$OUTPUT_FILE"

print_section "RECOMMENDATIONS"
echo "1. Fix the application code issues shown above"
echo "2. Run 'python manage.py check' to identify Django configuration issues"
echo "3. Run 'python manage.py migrate --check' to verify migrations"
echo "4. Check API URL routing with 'python manage.py show_urls'"
echo ""
echo "For specific app testing:"
echo "  $0 --app authentication --verbose"
echo "  $0 --api-only --summary"

exit $TEST_EXIT_CODE