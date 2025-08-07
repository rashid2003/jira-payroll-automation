"""
Simple test to validate imports are working correctly.
"""

def test_imports():
    """Test that all required modules can be imported."""
    try:
        # Test Django imports
        from django.test import TestCase
        from django.contrib.auth.models import User
        from django.utils import timezone
        
        # Test REST framework imports
        from rest_framework.test import APITestCase
        from rest_framework import status
        
        # Test payroll app imports
        from payroll.models import PayrollPeriod, UserProfile
        from payroll.services.payroll_processor import PayrollProcessor, PayrollProcessorError
        from payroll.tasks import auto_run_payroll, process_payroll_period
        
        print("All imports successful!")
        return True
        
    except ImportError as e:
        print(f"Import error: {e}")
        return False

if __name__ == "__main__":
    test_imports()
