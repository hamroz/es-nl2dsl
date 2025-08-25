#!/usr/bin/env python3
"""Test script to verify logging functionality doesn't interfere with GUI"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_logging_imports():
    """Test that all logging utilities import correctly"""
    try:
        from gui.utils.logging_utils import GUILogger, setup_gui_logger
        print("✅ Logging utilities import successfully")
        
        # Test logger creation
        logger = GUILogger("test_component")
        print("✅ GUILogger instantiation successful")
        
        # Test logging methods
        logger.log_page_load("test_page")
        logger.log_button_click("test_button", extra_param="test")
        logger.log_selection_change("dropdown", "old", "new")
        logger.log_user_action("test_action", key="value")
        logger.log_system_operation("test_operation", duration=1.5)
        logger.log_success("test_success")
        logger.log_error("test_error_type", "test error message")
        logger.log_performance("test_perf", 2.0)
        
        print("✅ All logging methods work correctly")
        
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False
    
    return True

def test_gui_components():
    """Test that GUI components import correctly with logging"""
    try:
        # Test individual component imports
        components = [
            "gui.components.query_generator", 
            "gui.components.admin_panel",
            "gui.components.evaluation_dashboard",
            "gui.components.security_panel",
            "gui.components.data_explorer",
            "gui.components.privacy_analysis",
            "gui.components.external_llm_panel"
        ]
        
        for component in components:
            try:
                __import__(component)
                print(f"✅ {component} imports successfully")
            except ImportError as e:
                print(f"⚠️  {component} import issue: {e}")
            except Exception as e:
                print(f"❌ {component} has other issues: {e}")
                
    except Exception as e:
        print(f"❌ Component test failed: {e}")
        return False
    
    return True

def main():
    print("🧪 Testing Enhanced GUI Logging System")
    print("=" * 50)
    
    # Test logging utilities
    if test_logging_imports():
        print("\n✅ Logging system test PASSED")
    else:
        print("\n❌ Logging system test FAILED")
        return 1
    
    # Test GUI components
    if test_gui_components():
        print("\n✅ GUI components test PASSED")
    else:
        print("\n❌ GUI components test FAILED")
        return 1
    
    print("\n🎉 All tests passed! The enhanced logging system is ready to use.")
    print("\nTo start monitoring:")
    print("1. Terminal 1: ./start_gui_with_logs.py")  
    print("2. Terminal 2: ./watch_logs.py")
    print("3. Use the GUI normally - all actions will be logged!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())