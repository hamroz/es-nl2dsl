#!/usr/bin/env python3
"""
Comprehensive Django Test Runner for ES-NL2DSL Backend

This script provides a unified way to run all Django tests with proper setup,
coverage reporting, and various testing options.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --fast             # Run tests without coverage
    python run_tests.py --unit             # Run only unit tests
    python run_tests.py --integration      # Run only integration tests
    python run_tests.py --app queries      # Run tests for specific app
    python run_tests.py --coverage-html    # Generate HTML coverage report
    python run_tests.py --parallel         # Run tests in parallel
    python run_tests.py --keepdb           # Keep test database for faster reruns
"""

import os
import sys
import argparse
import subprocess
import django
from pathlib import Path
from django.core.management import execute_from_command_line
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'es_nl2dsl_api.test_settings')
django.setup()


class TestRunner:
    """Comprehensive test runner for Django backend"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.coverage_config = self.base_dir / '.coveragerc'
        self.htmlcov_dir = self.base_dir / 'htmlcov'
        
    def create_coverage_config(self):
        """Create coverage configuration file"""
        config_content = """
[run]
source = .
omit = 
    */venv/*
    */env/*
    */migrations/*
    manage.py
    */settings/*
    */test*.py
    */tests/*
    */conftest.py
    */wsgi.py
    */asgi.py
    */urls.py
    */apps.py
    */admin.py
    */factories.py
    __pycache__/*
    .coverage*
    htmlcov/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    class Meta:
    if settings.DEBUG

[html]
directory = htmlcov
"""
        with open(self.coverage_config, 'w') as f:
            f.write(config_content.strip())
    
    def run_pytest_tests(self, args):
        """Run tests using pytest"""
        pytest_args = ['pytest']
        
        # Add coverage if requested
        if not args.fast:
            pytest_args.extend([
                '--cov=.',
                '--cov-config', str(self.coverage_config),
                '--cov-report=term-missing',
                '--cov-fail-under=80'
            ])
            
            if args.coverage_html:
                pytest_args.extend(['--cov-report=html'])
        
        # Add parallel execution if requested
        if args.parallel:
            pytest_args.extend(['-n', 'auto'])
        
        # Add test markers
        if args.unit:
            pytest_args.extend(['-m', 'unit'])
        elif args.integration:
            pytest_args.extend(['-m', 'integration'])
        elif args.api:
            pytest_args.extend(['-m', 'api'])
        elif args.slow:
            pytest_args.extend(['-m', 'slow'])
        elif args.fast:
            pytest_args.extend(['-m', 'not slow'])
        
        # Add specific app if requested
        if args.app:
            pytest_args.append(f'{args.app}/tests.py')
        
        # Add keepdb for faster reruns
        if args.keepdb:
            pytest_args.extend(['--reuse-db'])
        
        # Add verbose output if requested
        if args.verbose:
            pytest_args.extend(['-v'])
        
        # Add specific test patterns
        if args.pattern:
            pytest_args.extend(['-k', args.pattern])
        
        print(f"Running: {' '.join(pytest_args)}")
        result = subprocess.run(pytest_args, cwd=self.base_dir)
        return result.returncode
    
    def run_django_tests(self, args):
        """Run tests using Django's test runner"""
        django_args = ['test']
        
        # Add specific app if requested
        if args.app:
            django_args.append(args.app)
        
        # Add parallel execution if requested
        if args.parallel:
            django_args.extend(['--parallel', 'auto'])
        
        # Add keepdb for faster reruns
        if args.keepdb:
            django_args.extend(['--keepdb'])
        
        # Add verbose output if requested
        if args.verbose:
            django_args.extend(['--verbosity', '2'])
        
        print(f"Running Django tests: {' '.join(django_args)}")
        execute_from_command_line(['manage.py'] + django_args)
    
    def setup_test_environment(self):
        """Set up test environment"""
        # Create necessary directories
        os.makedirs(self.base_dir / 'artifacts' / 'exports', exist_ok=True)
        os.makedirs(self.base_dir / 'artifacts' / 'generated', exist_ok=True)
        
        # Create coverage config
        self.create_coverage_config()
        
        print("Test environment set up successfully")
    
    def check_dependencies(self):
        """Check if test dependencies are installed"""
        try:
            import pytest
            import pytest_django
            import pytest_cov
            import factory
            import responses
            import freezegun
        except ImportError as e:
            print(f"Missing test dependency: {e}")
            print("Please install test dependencies:")
            print("pip install pytest pytest-django pytest-cov pytest-xdist factory-boy responses freezegun model-bakery")
            sys.exit(1)
    
    def run_specific_tests(self, args):
        """Run specific test categories"""
        if args.models:
            return self.run_pytest_tests(argparse.Namespace(
                **vars(args), pattern='*Model*Test'
            ))
        elif args.views:
            return self.run_pytest_tests(argparse.Namespace(
                **vars(args), pattern='*View*Test or *API*Test'
            ))
        elif args.serializers:
            return self.run_pytest_tests(argparse.Namespace(
                **vars(args), pattern='*Serializer*Test'
            ))
        elif args.tasks:
            return self.run_pytest_tests(argparse.Namespace(
                **vars(args), pattern='*Task*Test'
            ))
        elif args.auth:
            return self.run_pytest_tests(argparse.Namespace(
                **vars(args), app='authentication'
            ))
        elif args.queries:
            return self.run_pytest_tests(argparse.Namespace(
                **vars(args), app='queries'
            ))
        elif args.evaluation:
            return self.run_pytest_tests(argparse.Namespace(
                **vars(args), app='evaluation'
            ))
        else:
            return self.run_pytest_tests(args)
    
    def show_coverage_report(self):
        """Display coverage report summary"""
        if self.htmlcov_dir.exists():
            index_file = self.htmlcov_dir / 'index.html'
            if index_file.exists():
                print(f"\nHTML Coverage report available at: {index_file}")
                print("Open in browser to see detailed coverage information")
    
    def cleanup_test_artifacts(self):
        """Clean up test artifacts"""
        artifacts_to_clean = [
            self.base_dir / 'artifacts' / 'exports',
            self.base_dir / 'artifacts' / 'generated',
        ]
        
        for artifact_dir in artifacts_to_clean:
            if artifact_dir.exists():
                for file in artifact_dir.glob('*'):
                    if file.is_file():
                        file.unlink()
        
        print("Test artifacts cleaned up")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Comprehensive Django Test Runner for ES-NL2DSL Backend',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests with coverage
  python run_tests.py --fast             # Run all tests without coverage
  python run_tests.py --unit             # Run only unit tests
  python run_tests.py --integration      # Run only integration tests
  python run_tests.py --app queries      # Run tests for queries app
  python run_tests.py --auth             # Run authentication tests
  python run_tests.py --models           # Run only model tests
  python run_tests.py --views            # Run only view/API tests
  python run_tests.py --parallel --keepdb # Fast parallel execution
  python run_tests.py --coverage-html    # Generate HTML coverage report
  python run_tests.py --pattern "Query*" # Run tests matching pattern
        """
    )
    
    # Test execution options
    parser.add_argument('--fast', action='store_true',
                       help='Run tests without coverage reporting')
    parser.add_argument('--parallel', action='store_true',
                       help='Run tests in parallel')
    parser.add_argument('--keepdb', action='store_true',
                       help='Keep test database between runs')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    # Test filtering options
    parser.add_argument('--unit', action='store_true',
                       help='Run only unit tests')
    parser.add_argument('--integration', action='store_true',
                       help='Run only integration tests')
    parser.add_argument('--api', action='store_true',
                       help='Run only API tests')
    parser.add_argument('--slow', action='store_true',
                       help='Run slow tests')
    parser.add_argument('--pattern', type=str,
                       help='Run tests matching pattern')
    
    # App-specific options
    parser.add_argument('--app', type=str,
                       help='Run tests for specific app')
    parser.add_argument('--auth', action='store_true',
                       help='Run authentication tests')
    parser.add_argument('--queries', action='store_true',
                       help='Run queries app tests')
    parser.add_argument('--evaluation', action='store_true',
                       help='Run evaluation app tests')
    
    # Component-specific options
    parser.add_argument('--models', action='store_true',
                       help='Run only model tests')
    parser.add_argument('--views', action='store_true',
                       help='Run only view/API tests')
    parser.add_argument('--serializers', action='store_true',
                       help='Run only serializer tests')
    parser.add_argument('--tasks', action='store_true',
                       help='Run only task tests')
    
    # Coverage options
    parser.add_argument('--coverage-html', action='store_true',
                       help='Generate HTML coverage report')
    parser.add_argument('--coverage-xml', action='store_true',
                       help='Generate XML coverage report')
    
    # Test runner options
    parser.add_argument('--django', action='store_true',
                       help='Use Django test runner instead of pytest')
    parser.add_argument('--setup', action='store_true',
                       help='Set up test environment only')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up test artifacts')
    parser.add_argument('--check-deps', action='store_true',
                       help='Check test dependencies')
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Handle special commands
    if args.setup:
        runner.setup_test_environment()
        return 0
    
    if args.cleanup:
        runner.cleanup_test_artifacts()
        return 0
    
    if args.check_deps:
        runner.check_dependencies()
        print("All test dependencies are available")
        return 0
    
    # Check dependencies before running tests
    runner.check_dependencies()
    
    # Set up test environment
    runner.setup_test_environment()
    
    try:
        # Run tests
        if args.django:
            exit_code = runner.run_django_tests(args)
        else:
            exit_code = runner.run_specific_tests(args)
        
        # Show coverage report if generated
        if not args.fast and args.coverage_html:
            runner.show_coverage_report()
        
        return exit_code
        
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        return 1
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())