"""
Tests for payroll automation functionality.
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from payroll.models import PayrollPeriod
from payroll.tasks import auto_run_payroll, process_payroll_period


class PayrollAutomationTestCase(TestCase):
    
    def setUp(self):
        """Set up test data"""
        cache.clear()  # Clear cache before each test
        
        # Create test periods
        self.today = timezone.now().date()
        
        # Period due for automation (3 days before end)
        self.due_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=3),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'days_before_end': 3},
            status='active'
        )
        
        # Period not due yet  
        self.not_due_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=10), 
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'days_before_end': 3},
            status='active'
        )
        
        # Period with automation disabled
        self.disabled_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=3),
            period_type='monthly', 
            automation_enabled=False,
            automation_rule={'days_before_end': 3},
            status='active'
        )
        
        # Already completed period
        self.completed_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=60),
            end_date=self.today - timedelta(days=30),
            period_type='monthly',
            automation_enabled=True, 
            automation_rule={'days_before_end': 3},
            status='completed'
        )
    
    def test_is_due_for_automation_days_before_end(self):
        """Test automation rule: days_before_end"""
        self.assertTrue(self.due_period.is_due_for_automation())
        self.assertFalse(self.not_due_period.is_due_for_automation())
        self.assertFalse(self.disabled_period.is_due_for_automation())
        self.assertFalse(self.completed_period.is_due_for_automation())
    
    def test_is_due_for_automation_specific_date(self):
        """Test automation rule: run_on_date"""
        period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'run_on_date': self.today.strftime('%Y-%m-%d')},
            status='active'
        )
        
        self.assertTrue(period.is_due_for_automation())
        
        # Test with different date
        period.automation_rule = {'run_on_date': (self.today + timedelta(days=1)).strftime('%Y-%m-%d')}
        period.save()
        self.assertFalse(period.is_due_for_automation())
    
    def test_is_due_for_automation_cron_rule(self):
        """Test automation rule: cron (always returns True when called from task)"""
        period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'cron': '0 0 25 * *'},
            status='active'
        )
        
        # Cron rule returns True when called (Celery Beat handles timing)
        self.assertTrue(period.is_due_for_automation())
    
    @patch('payroll.tasks.process_payroll_period')
    def test_auto_run_payroll_processes_due_periods(self, mock_process):
        """Test that auto_run_payroll processes only due periods"""
        mock_process.return_value = {'status': 'completed', 'period_id': self.due_period.id}
        
        result = auto_run_payroll()
        
        # Should process only the due period
        self.assertEqual(result['processed_count'], 1)
        self.assertEqual(result['skipped_count'], 0)
        self.assertEqual(result['failed_count'], 0)
        
        mock_process.assert_called_once_with(self.due_period.id)
    
    @patch('payroll.tasks.PayrollProcessor')
    def test_process_payroll_period_success(self, mock_processor_class):
        """Test successful payroll processing"""
        mock_processor = MagicMock()
        mock_processor.run_payroll.return_value = {'employees_processed': 10}
        mock_processor_class.return_value = mock_processor
        
        result = process_payroll_period(self.due_period.id)
        
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['period_id'], self.due_period.id)
        mock_processor.run_payroll.assert_called_once_with(self.due_period.id)
    
    def test_process_payroll_period_already_completed(self):
        """Test processing already completed period"""
        result = process_payroll_period(self.completed_period.id)
        
        self.assertEqual(result['status'], 'already_completed')
        self.assertEqual(result['period_id'], self.completed_period.id)
    
    def test_process_payroll_period_not_found(self):
        """Test processing non-existent period"""
        from payroll.services.payroll_processor import PayrollProcessorError
        
        with self.assertRaises(PayrollProcessorError):
            process_payroll_period(99999)
    
    @patch('payroll.tasks.process_payroll_period')
    def test_auto_run_payroll_with_cache_lock(self, mock_process):
        """Test that cache lock prevents duplicate processing"""
        # Set cache lock
        cache.set(f"payroll_processing_{self.due_period.id}", True, timeout=3600)
        
        result = auto_run_payroll()
        
        # Should skip the period due to lock
        self.assertEqual(result['processed_count'], 0)
        self.assertEqual(result['skipped_count'], 1)
        self.assertEqual(result['skipped_periods'][0]['reason'], 'Already processing')
        
        mock_process.assert_not_called()
    
    @patch('payroll.tasks.process_payroll_period')
    def test_auto_run_payroll_handles_errors(self, mock_process):
        """Test error handling in auto_run_payroll"""
        mock_process.side_effect = Exception("Processing failed")
        
        result = auto_run_payroll()
        
        # Should handle the error gracefully
        self.assertEqual(result['processed_count'], 0)
        self.assertEqual(result['failed_count'], 1)
        self.assertIn('Processing failed', result['failed_periods'][0]['error'])
    
    def test_automation_rule_validation(self):
        """Test validation of automation rules"""
        from django.core.exceptions import ValidationError
        
        # Valid rules should not raise exceptions
        valid_rules = [
            {'days_before_end': 3},
            {'run_on_date': '2024-01-25'},
            {'cron': '0 0 25 * *'},
        ]
        
        for rule in valid_rules:
            period = PayrollPeriod(
                start_date=self.today,
                end_date=self.today + timedelta(days=30),
                automation_rule=rule
            )
            # Should not raise exception
            period.clean()
        
        # Invalid rule should raise exception
        period = PayrollPeriod(
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            automation_rule={'invalid_key': 'value'}
        )
        
        with self.assertRaises(ValidationError):
            period.clean()


class PayrollAutomationIntegrationTestCase(TestCase):
    """Integration tests that test the full automation flow"""
    
    def setUp(self):
        cache.clear()
    
    @patch('payroll.services.payroll_processor.PayrollProcessor.run_payroll')
    def test_end_to_end_automation(self, mock_run_payroll):
        """Test complete automation flow"""
        mock_run_payroll.return_value = {
            'employees_processed': 5,
            'total_gross_amount': '50000.00'
        }
        
        # Create a period due for automation
        today = timezone.now().date()
        period = PayrollPeriod.objects.create(
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=2),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'days_before_end': 2},
            status='active'
        )
        
        # Run automation
        result = auto_run_payroll()
        
        # Verify results
        self.assertEqual(result['processed_count'], 1)
        self.assertEqual(result['failed_count'], 0)
        
        # Verify PayrollProcessor was called
        mock_run_payroll.assert_called_once_with(period.id)
        
        # Verify period status (would be updated by PayrollProcessor in real scenario)
        period.refresh_from_db()
        # Note: Status change depends on PayrollProcessor implementation
