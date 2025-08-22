#!/usr/bin/env python3
"""
Quick test script to verify core ES-NL2DSL functionality is restored
"""

import requests
import json
import time
import sys
from pathlib import Path

def test_django_backend():
    """Test if Django backend is responding"""
    try:
        response = requests.get('http://localhost:8000/api/v1/', timeout=5)
        return response.status_code == 200
    except:
        return False

def test_query_generation():
    """Test the core query generation functionality"""
    try:
        # Test data
        test_prompt = "Find malicious events from July 4th 2017"
        
        # Create query generation request
        data = {
            'prompt': test_prompt,
            'method': 'constrained',
            'index': 'logs_net',
            'model': 'llama3.1:latest'
        }
        
        # Send request to Django backend
        response = requests.post(
            'http://localhost:8000/api/v1/queries/',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code != 202:
            print(f"❌ Query generation request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
        result = response.json()
        task_id = result.get('task_id')
        
        print(f"✅ Query generation started (Task ID: {task_id})")
        
        # Poll for completion (give it time for the Celery task)
        max_attempts = 30
        for attempt in range(max_attempts):
            check_response = requests.get(f'http://localhost:8000/api/v1/queries/{task_id}/')
            
            if check_response.status_code == 200:
                status_data = check_response.json()
                status = status_data.get('status')
                
                print(f"Attempt {attempt + 1}: Status = {status}")
                
                if status == 'completed':
                    print("✅ Query generation completed successfully!")
                    if 'query' in status_data:
                        print(f"✅ Generated DSL query present")
                        return True
                    else:
                        print("❌ No DSL query in response")
                        return False
                elif status == 'failed':
                    error = status_data.get('error_message', 'Unknown error')
                    print(f"❌ Query generation failed: {error}")
                    return False
                    
            time.sleep(2)
            
        print("❌ Query generation timed out")
        return False
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def test_src_scripts():
    """Test that the original src scripts still work"""
    try:
        import subprocess
        import tempfile
        
        # Test the generate_constrained.py script directly
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Find malicious events from 2017-07-04")
            prompt_file = f.name
        
        cmd = [
            sys.executable, 
            'src/generate_constrained.py',
            '--prompt', prompt_file,
            '--task-id', 'test-001', 
            '--output-dir', '/tmp',
            '--model', 'llama3.1:latest'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd='.')
        
        Path(prompt_file).unlink(missing_ok=True)
        
        if result.returncode == 0:
            print("✅ Original src/generate_constrained.py script works")
            return True
        else:
            print(f"❌ Original script failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Script test error: {e}")
        return False

def main():
    print("🧪 Testing ES-NL2DSL Core Functionality")
    print("======================================")
    
    # Test 1: Django Backend
    print("\n1. Testing Django Backend...")
    if not test_django_backend():
        print("❌ Django backend is not responding")
        print("   Make sure to run: ./start_system.sh")
        sys.exit(1)
    print("✅ Django backend is responding")
    
    # Test 2: Original Scripts (should still work)
    print("\n2. Testing Original Scripts...")
    if not test_src_scripts():
        print("❌ Original scripts not working")
        print("   Check Ollama installation and models")
        return False
    
    # Test 3: Core Query Generation (integrated)
    print("\n3. Testing Integrated Query Generation...")
    if not test_query_generation():
        print("❌ Core query generation not working")
        print("   Check Celery worker and Redis connection")
        return False
    
    print("\n🎉 All Tests Passed!")
    print("===============================")
    print("✅ Django backend responding")
    print("✅ Original scripts working") 
    print("✅ Integrated query generation working")
    print("✅ Migration architect feedback RESOLVED")
    print("\nThe ES-NL2DSL system is now fully functional!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)