#!/bin/bash

# ES-NL2DSL Backend Test Runner
# Comprehensive script to run Django backend tests with coverage reporting

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
RUN_COVERAGE=true
RUN_PARALLEL=false
KEEP_DB=false
VERBOSE=false
APP_FILTER=""
TEST_FILTER=""
HTML_REPORT=false
FAST_MODE=false

# Print usage
usage() {
    echo "ES-NL2DSL Backend Test Runner"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -f, --fast           Run tests without coverage (faster)"
    echo "  -p, --parallel       Run tests in parallel"
    echo "  -k, --keepdb         Keep test database between runs"
    echo "  -v, --verbose        Verbose output"
    echo "  -h, --html           Generate HTML coverage report"
    echo "  -a, --app APP        Run tests for specific app only"
    echo "  -t, --test PATTERN   Run tests matching pattern"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                             # Run all tests with coverage"
    echo "  $0 --fast                      # Run all tests without coverage"
    echo "  $0 --parallel --keepdb         # Fast parallel execution"
    echo "  $0 --app queries               # Run only queries app tests"
    echo "  $0 --test authentication       # Run authentication tests"
    echo "  $0 --html                      # Generate HTML coverage report"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--fast)
            FAST_MODE=true
            RUN_COVERAGE=false
            shift
            ;;
        -p|--parallel)
            RUN_PARALLEL=true
            shift
            ;;
        -k|--keepdb)
            KEEP_DB=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--html)
            HTML_REPORT=true
            shift
            ;;
        -a|--app)
            APP_FILTER="$2"
            shift 2
            ;;
        -t|--test)
            TEST_FILTER="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    # Check Python
    if ! command_exists python3; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check if we're in the right directory (should be run from scripts/testing/)
    if [ ! -f "../../backend/manage.py" ]; then
        print_error "Please run this script from scripts/testing/ directory"
        print_error "Expected path: ../../backend/manage.py"
        print_error "Current directory: $(pwd)"
        exit 1
    fi
    
    # Check virtual environment in backend directory
    if [ ! -d "../../backend/venv" ] && [ ! -d "../../backend/env" ] && [ ! -d "../../env" ]; then
        print_warning "No virtual environment found. Creating in backend directory..."
        cd ../../backend
        python3 -m venv venv
        cd -
    fi
    
    # Activate virtual environment
    if [ -d "../../backend/venv" ]; then
        source ../../backend/venv/bin/activate
        print_status "Activated virtual environment: ../../backend/venv"
    elif [ -d "../../backend/env" ]; then
        source ../../backend/env/bin/activate  
        print_status "Activated virtual environment: ../../backend/env"
    elif [ -d "../../env" ]; then
        source ../../env/bin/activate
        print_status "Activated virtual environment: ../../env"
    fi
    
    # Check Django
    if ! python -c "import django" 2>/dev/null; then
        print_error "Django is not installed. Installing dependencies..."
        pip install -r ../../backend/requirements.txt
    fi
    
    # Check test dependencies
    local missing_deps=""
    
    if ! python -c "import pytest" 2>/dev/null; then
        missing_deps="$missing_deps pytest"
    fi
    
    if ! python -c "import pytest_django" 2>/dev/null; then
        missing_deps="$missing_deps pytest-django"
    fi
    
    if ! python -c "import pytest_cov" 2>/dev/null; then
        missing_deps="$missing_deps pytest-cov"
    fi
    
    if ! python -c "import factory" 2>/dev/null; then
        missing_deps="$missing_deps factory-boy"
    fi
    
    if ! python -c "import responses" 2>/dev/null; then
        missing_deps="$missing_deps responses"
    fi
    
    if ! python -c "import freezegun" 2>/dev/null; then
        missing_deps="$missing_deps freezegun"
    fi
    
    if ! python -c "import model_bakery" 2>/dev/null; then
        missing_deps="$missing_deps model-bakery"
    fi
    
    if [ ! -z "$missing_deps" ]; then
        print_warning "Installing missing test dependencies:$missing_deps"
        pip install $missing_deps
    fi
    
    print_success "All dependencies are available"
}

# Set up test environment
setup_test_environment() {
    print_status "Setting up test environment..."
    
    # Create necessary directories (in project root)
    mkdir -p ../artifacts/exports
    mkdir -p ../artifacts/generated
    mkdir -p ../artifacts/results
    
    # Set Django settings
    export DJANGO_SETTINGS_MODULE=es_nl2dsl_api.test_settings
    
    # Let pytest-django handle database setup automatically
    print_status "Test database will be managed by pytest-django"
    
    print_success "Test environment ready"
}

# Run the tests
run_tests() {
    print_status "Starting Django backend tests..."
    
    # Build pytest command
    local pytest_cmd="pytest"
    local pytest_args=""
    
    # Add coverage options
    if [ "$RUN_COVERAGE" = true ]; then
        pytest_args="$pytest_args --cov=."
        pytest_args="$pytest_args --cov-report=term-missing"
        pytest_args="$pytest_args --cov-fail-under=75"
        
        if [ "$HTML_REPORT" = true ]; then
            pytest_args="$pytest_args --cov-report=html:htmlcov"
        fi
    fi
    
    # Add parallel execution
    if [ "$RUN_PARALLEL" = true ]; then
        pytest_args="$pytest_args -n auto"
    fi
    
    # Add database options
    if [ "$KEEP_DB" = true ]; then
        pytest_args="$pytest_args --reuse-db"
    fi
    
    # Add verbose output
    if [ "$VERBOSE" = true ]; then
        pytest_args="$pytest_args -v"
    fi
    
    # Add app filter
    if [ ! -z "$APP_FILTER" ]; then
        pytest_args="$pytest_args $APP_FILTER/"
    fi
    
    # Add test pattern filter
    if [ ! -z "$TEST_FILTER" ]; then
        pytest_args="$pytest_args -k $TEST_FILTER"
    fi
    
    # Skip slow tests in fast mode is disabled for now to avoid shell quoting issues
    
    # Add common options
    pytest_args="$pytest_args --tb=short"
    pytest_args="$pytest_args --disable-warnings"
    pytest_args="$pytest_args --create-db"
    
    # Run the tests
    print_status "Executing: $pytest_cmd $pytest_args"
    echo ""
    
    if $pytest_cmd $pytest_args; then
        print_success "All tests passed!"
        return 0
    else
        print_error "Some tests failed!"
        return 1
    fi
}

# Show coverage report
show_coverage_report() {
    if [ "$RUN_COVERAGE" = true ] && [ "$HTML_REPORT" = true ]; then
        if [ -f "htmlcov/index.html" ]; then
            print_success "HTML coverage report generated: htmlcov/index.html"
            print_status "Open htmlcov/index.html in your browser to view detailed coverage"
            
            # Try to open in browser (macOS)
            if command_exists open; then
                print_status "Opening coverage report in browser..."
                open htmlcov/index.html
            fi
        fi
    fi
}

# Clean up function
cleanup() {
    print_status "Cleaning up test artifacts..."
    
    # Clean up generated test files
    rm -rf artifacts/exports/test_*
    rm -rf artifacts/generated/eval_*
    
    print_status "Cleanup completed"
}

# Main execution
main() {
    echo ""
    echo "======================================"
    echo "  ES-NL2DSL Backend Test Runner"
    echo "======================================"
    echo ""
    
    # Check dependencies and setup
    check_dependencies
    
    # Change to backend directory for the rest of the operations
    cd backend
    
    setup_test_environment
    
    # Run tests
    local exit_code=0
    
    if run_tests; then
        print_success "Test execution completed successfully"
        show_coverage_report
    else
        print_error "Test execution failed"
        exit_code=1
    fi
    
    # Always cleanup
    cleanup
    
    echo ""
    if [ $exit_code -eq 0 ]; then
        print_success "Backend tests completed successfully!"
    else
        print_error "Backend tests failed!"
    fi
    echo ""
    
    return $exit_code
}

# Handle interrupts
trap 'print_warning "Tests interrupted by user"; cleanup; exit 1' INT TERM

# Run main function
main "$@"