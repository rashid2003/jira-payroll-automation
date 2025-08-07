"""
Comprehensive tests for PayrollPeriod model and related functionality.

This test module covers:
- CRUD operations for PayrollPeriod
- Salary calculations accuracy with edge cases
- Automation trigger testing (mocked Celery)
- Summary endpoint totals validation
"""

import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, Mock

from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from payroll.models import PayrollPeriod, UserProfile
from payroll.services.payroll_processor import PayrollProcessor, PayrollProcessorError
from payroll.tasks import auto_run_payroll, process_payroll_period


class PayrollPeriodModelTestCase(TestCase):
    """Test cases for PayrollPeriod model CRUD operations and validation."""
    
    def setUp(self):
        """Set up test data."""
        self.today = timezone.now().date()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_create_payroll_period_success(self):
        """Test successful creation of payroll period."""
        period = PayrollPeriod.objects.create(
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            status='active',
            description='Test monthly period'
        )
        
        self.assertEqual(period.start_date, self.today)
        self.assertEqual(period.end_date, self.today + timedelta(days=30))
        self.assertEqual(period.period_type, 'monthly')
        self.assertEqual(period.status, 'active')
        self.assertFalse(period.automation_enabled)
        self.assertEqual(period.duration_days, 31)
        
    def test_create_period_with_automation(self):
        """Test creating period with automation enabled."""
        automation_rule = {'days_before_end': 3}
        period = PayrollPeriod.objects.create(
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            automation_enabled=True,
            automation_rule=automation_rule,
            status='active'
        )
        
        self.assertTrue(period.automation_enabled)
        self.assertEqual(period.automation_rule, automation_rule)
        
    def test_period_validation_end_before_start(self):
        """Test validation error when end date is before start date."""
        with self.assertRaises(ValidationError) as context:
            period = PayrollPeriod(
                start_date=self.today + timedelta(days=10),
                end_date=self.today,
                period_type='monthly'
            )
            period.clean()
            
        self.assertIn('end_date', context.exception.message_dict)
        
    def test_period_validation_overlapping_periods(self):
        """Test validation error for overlapping periods of same type."""
        # Create first period
        PayrollPeriod.objects.create(
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            status='active'
        )
        
        # Try to create overlapping period
        with self.assertRaises(ValidationError) as context:
            period = PayrollPeriod(
                start_date=self.today + timedelta(days=15),
                end_date=self.today + timedelta(days=45),
                period_type='monthly'
            )
            period.clean()
            
        self.assertIn('start_date', context.exception.message_dict)
        self.assertIn('overlaps', str(context.exception.message_dict['start_date']))
        
    def test_period_validation_duplicate_periods(self):
        """Test validation error for duplicate periods."""
        # Create first period
        PayrollPeriod.objects.create(
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            status='active'
        )
        
        # Try to create duplicate period
        with self.assertRaises(ValidationError) as context:
            period = PayrollPeriod(
                start_date=self.today,
                end_date=self.today + timedelta(days=30),
                period_type='monthly'
            )
            period.clean()
            
        self.assertIn('start_date', context.exception.message_dict)
        self.assertIn('already exists', str(context.exception.message_dict['start_date']))
        
    def test_automation_rule_validation_invalid_format(self):
        """Test validation of automation rule format."""
        with self.assertRaises(ValidationError) as context:
            period = PayrollPeriod(
                start_date=self.today,
                end_date=self.today + timedelta(days=30),
                automation_rule="invalid_string"  # Should be dict
            )
            period.clean()
            
        self.assertIn('automation_rule', context.exception.message_dict)
        
    def test_automation_rule_validation_invalid_keys(self):
        """Test validation of automation rule keys."""
        with self.assertRaises(ValidationError) as context:
            period = PayrollPeriod(
                start_date=self.today,
                end_date=self.today + timedelta(days=30),
                automation_rule={'invalid_key': 'value'}
            )
            period.clean()
            
        self.assertIn('automation_rule', context.exception.message_dict)
        
    def test_update_payroll_period(self):
        """Test updating an existing payroll period."""
        period = PayrollPeriod.objects.create(
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            status='active'
        )
        
        # Update the period
        period.description = "Updated description"
        period.status = 'completed'
        period.save()
        
        period.refresh_from_db()
        self.assertEqual(period.description, "Updated description")
        self.assertEqual(period.status, 'completed')
        
    def test_delete_payroll_period(self):
        """Test deleting a payroll period."""
        period = PayrollPeriod.objects.create(
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            status='active'
        )
        period_id = period.id
        
        period.delete()
        
        with self.assertRaises(PayrollPeriod.DoesNotExist):
            PayrollPeriod.objects.get(id=period_id)
            
    def test_period_properties(self):
        """Test computed properties of payroll period."""
        # Test is_active
        active_period = PayrollPeriod.objects.create(
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            status='active'
        )
        self.assertTrue(active_period.is_active)
        
        # Test is_current
        current_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=5),
            end_date=self.today + timedelta(days=25),
            period_type='monthly',
            status='active'
        )
        self.assertTrue(current_period.is_current)
        
        # Test duration_days
        self.assertEqual(active_period.duration_days, 31)


class PayrollPeriodAutomationTestCase(TestCase):
    """Test cases for payroll period automation functionality."""
    
    def setUp(self):
        """Set up test data for automation tests."""
        cache.clear()
        self.today = timezone.now().date()
        
    def test_is_due_for_automation_days_before_end(self):
        """Test automation trigger based on days before end date."""
        # Period due for automation (3 days before end)
        due_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=3),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'days_before_end': 3},
            status='active'
        )
        self.assertTrue(due_period.is_due_for_automation())
        
        # Period not due yet (more than 3 days before end)
        not_due_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=10),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'days_before_end': 3},
            status='active'
        )
        self.assertFalse(not_due_period.is_due_for_automation())
        
    def test_is_due_for_automation_specific_date(self):
        """Test automation trigger for specific run date."""
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
        period.automation_rule = {
            'run_on_date': (self.today + timedelta(days=1)).strftime('%Y-%m-%d')
        }
        period.save()
        self.assertFalse(period.is_due_for_automation())
        
    def test_is_due_for_automation_cron_rule(self):
        """Test automation trigger with cron rule."""
        period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=30),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'cron': '0 0 25 * *'},
            status='active'
        )
        # Cron rule should return True when called from task
        self.assertTrue(period.is_due_for_automation())
        
    def test_automation_disabled_period(self):
        """Test that disabled automation periods are not triggered."""
        period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=3),
            period_type='monthly',
            automation_enabled=False,
            automation_rule={'days_before_end': 3},
            status='active'
        )
        self.assertFalse(period.is_due_for_automation())
        
    def test_automation_inactive_status(self):
        """Test that non-active periods are not triggered."""
        period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=3),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'days_before_end': 3},
            status='completed'
        )
        self.assertFalse(period.is_due_for_automation())


class PayrollPeriodCeleryTaskTestCase(TestCase):
    """Test cases for Celery task automation with mocking."""
    
    def setUp(self):
        """Set up test data for Celery task tests."""
        cache.clear()
        self.today = timezone.now().date()
        
        # Create test periods
        self.due_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=3),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'days_before_end': 3},
            status='active'
        )
        
        self.not_due_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=10),
            period_type='monthly',
            automation_enabled=True,
            automation_rule={'days_before_end': 3},
            status='active'
        )
        
    @patch('payroll.tasks.process_payroll_period')
    def test_auto_run_payroll_processes_due_periods(self, mock_process):
        """Test that auto_run_payroll processes only due periods."""
        mock_process.return_value = {
            'status': 'completed', 
            'period_id': self.due_period.id
        }
        
        result = auto_run_payroll()
        
        # Should process only the due period
        self.assertEqual(result['processed_count'], 1)
        self.assertEqual(result['skipped_count'], 0)
        self.assertEqual(result['failed_count'], 0)
        
        mock_process.assert_called_once_with(self.due_period.id)
        
    @patch('payroll.tasks.PayrollProcessor')
    def test_process_payroll_period_success(self, mock_processor_class):
        """Test successful payroll processing task."""
        mock_processor = MagicMock()
        mock_processor.run_payroll.return_value = {'employees_processed': 10}
        mock_processor_class.return_value = mock_processor
        
        result = process_payroll_period(self.due_period.id)
        
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['period_id'], self.due_period.id)
        mock_processor.run_payroll.assert_called_once_with(self.due_period.id)
        
    @patch('payroll.tasks.process_payroll_period')
    def test_auto_run_payroll_with_cache_lock(self, mock_process):
        """Test cache lock prevents duplicate processing."""
        # Set cache lock
        cache.set(f"payroll_processing_{self.due_period.id}", True, timeout=3600)
        
        result = auto_run_payroll()
        
        # Should skip the period due to lock
        self.assertEqual(result['processed_count'], 0)
        self.assertEqual(result['skipped_count'], 1)
        self.assertEqual(
            result['skipped_periods'][0]['reason'], 
            'Already processing'
        )
        
        mock_process.assert_not_called()
        
    @patch('payroll.tasks.process_payroll_period')
    def test_auto_run_payroll_handles_errors(self, mock_process):
        """Test error handling in auto_run_payroll."""
        mock_process.side_effect = Exception("Processing failed")
        
        result = auto_run_payroll()
        
        # Should handle the error gracefully
        self.assertEqual(result['processed_count'], 0)
        self.assertEqual(result['failed_count'], 1)
        self.assertIn(
            'Processing failed', 
            result['failed_periods'][0]['error']
        )


class SalaryCalculationTestCase(TestCase):
    """Test cases for salary calculations with edge cases."""
    
    def setUp(self):
        """Set up test data for salary calculations."""
        self.user = User.objects.create_user(
            username='employee1',
            email='employee1@example.com',
            password='testpass123'
        )
        self.today = timezone.now().date()
        self.period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today,
            period_type='monthly',
            status='active'
        )
        
    @patch('payroll.services.payroll_processor.calculate_deductions')
    @patch('payroll.services.payroll_processor.calculate_taxes')
    @patch('payroll.services.payroll_processor.calculate_insurance')
    def test_basic_salary_calculation(self, mock_insurance, mock_taxes, mock_deductions):
        """Test basic salary calculation workflow."""
        # Mock calculation functions
        mock_deductions.return_value = Decimal('500.00')
        mock_taxes.return_value = Decimal('1000.00')
        mock_insurance.return_value = Decimal('200.00')
        
        processor = PayrollProcessor()
        
        # Mock the employee compensation collation
        with patch.object(processor, '_collate_employee_compensation') as mock_collate:
            mock_collate.return_value = {
                'base_salary': Decimal('5000.00'),
                'bonuses': Decimal('500.00'),
                'overtime': Decimal('300.00'),
                'gross_salary': Decimal('5800.00')
            }
            
            with patch.object(processor, '_update_employee_salary') as mock_update:
                with patch.object(processor, '_create_payroll_payment') as mock_payment:
                    # Run the employee processing
                    processor._process_employee_payroll(self.user, self.period)
                    
                    # Verify calculations were called
                    mock_deductions.assert_called_once_with(Decimal('5800.00'), self.user.id)
                    mock_taxes.assert_called_once_with(Decimal('5800.00'), self.user.id)
                    mock_insurance.assert_called_once_with(Decimal('5800.00'), self.user.id)
                    
                    # Verify net salary calculation (gross - deductions - taxes - insurance)
                    expected_net = Decimal('5800.00') - Decimal('500.00') - Decimal('1000.00') - Decimal('200.00')
                    # Check if update_employee_salary was called with correct net salary
                    args = mock_update.call_args[0]
                    self.assertEqual(args[4], expected_net)  # net_salary parameter
                    
    @patch('payroll.services.payroll_processor.calculate_deductions')
    @patch('payroll.services.payroll_processor.calculate_taxes')
    @patch('payroll.services.payroll_processor.calculate_insurance')
    def test_zero_salary_calculation(self, mock_insurance, mock_taxes, mock_deductions):
        """Test salary calculation with zero base salary."""
        mock_deductions.return_value = Decimal('0.00')
        mock_taxes.return_value = Decimal('0.00')
        mock_insurance.return_value = Decimal('0.00')
        
        processor = PayrollProcessor()
        
        with patch.object(processor, '_collate_employee_compensation') as mock_collate:
            mock_collate.return_value = {
                'base_salary': Decimal('0.00'),
                'bonuses': Decimal('0.00'),
                'overtime': Decimal('0.00'),
                'gross_salary': Decimal('0.00')
            }
            
            with patch.object(processor, '_update_employee_salary') as mock_update:
                with patch.object(processor, '_create_payroll_payment'):
                    processor._process_employee_payroll(self.user, self.period)
                    
                    # Net salary should be 0.00
                    args = mock_update.call_args[0]
                    self.assertEqual(args[4], Decimal('0.00'))
                    
    @patch('payroll.services.payroll_processor.calculate_deductions')
    @patch('payroll.services.payroll_processor.calculate_taxes')
    @patch('payroll.services.payroll_processor.calculate_insurance')
    def test_high_deductions_calculation(self, mock_insurance, mock_taxes, mock_deductions):
        """Test salary calculation with high deductions (edge case)."""
        # Deductions higher than gross salary
        mock_deductions.return_value = Decimal('3000.00')
        mock_taxes.return_value = Decimal('2000.00')
        mock_insurance.return_value = Decimal('1000.00')
        
        processor = PayrollProcessor()
        
        with patch.object(processor, '_collate_employee_compensation') as mock_collate:
            mock_collate.return_value = {
                'base_salary': Decimal('5000.00'),
                'bonuses': Decimal('0.00'),
                'overtime': Decimal('0.00'),
                'gross_salary': Decimal('5000.00')
            }
            
            with patch.object(processor, '_update_employee_salary') as mock_update:
                with patch.object(processor, '_create_payroll_payment'):
                    processor._process_employee_payroll(self.user, self.period)
                    
                    # Net salary should be negative
                    expected_net = Decimal('5000.00') - Decimal('6000.00')  # -1000.00
                    args = mock_update.call_args[0]
                    self.assertEqual(args[4], expected_net)
                    
    def test_payroll_processor_full_run_mock(self):
        """Test complete payroll processor run with mocked employees."""
        with patch.object(PayrollProcessor, '_get_active_employees') as mock_employees:
            # Mock active employees
            mock_employees.return_value = [self.user]
            
            with patch.object(PayrollProcessor, '_process_employee_payroll') as mock_process:
                with patch.object(PayrollProcessor, '_complete_period') as mock_complete:
                    processor = PayrollProcessor()
                    result = processor.run_payroll(self.period.id)
                    
                    # Verify the processing flow
                    mock_employees.assert_called_once()
                    mock_process.assert_called_once_with(self.user, self.period)
                    mock_complete.assert_called_once_with(self.period)
                    
                    # Check result structure
                    self.assertIn('period_id', result)
                    self.assertIn('processed_employees', result)
                    self.assertIn('total_gross_amount', result)
                    self.assertEqual(result['period_id'], self.period.id)


class PayrollPeriodAPITestCase(APITestCase):
    """Test cases for PayrollPeriod API endpoints including summary."""
    
    def setUp(self):
        """Set up test data for API tests."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create user profile with permissions
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.role = 'finance'
        self.profile.save()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.today = timezone.now().date()
        self.period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today,
            period_type='monthly',
            status='active'
        )
        
    def test_create_period_via_api(self):
        """Test creating payroll period via API."""
        data = {
            'start_date': (self.today + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (self.today + timedelta(days=31)).strftime('%Y-%m-%d'),
            'period_type': 'monthly',
            'status': 'active',
            'description': 'API created period'
        }
        
        response = self.client.post('/payroll/periods/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['period_type'], 'monthly')
        self.assertEqual(response.data['description'], 'API created period')
        
    def test_list_periods_via_api(self):
        """Test listing payroll periods via API."""
        response = self.client.get('/payroll/periods/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.period.id)
        
    def test_retrieve_period_via_api(self):
        """Test retrieving single payroll period via API."""
        response = self.client.get(f'/payroll/periods/{self.period.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.period.id)
        self.assertEqual(response.data['period_type'], 'monthly')
        
    def test_update_period_via_api(self):
        """Test updating payroll period via API."""
        data = {
            'description': 'Updated description',
            'status': 'completed'
        }
        
        response = self.client.patch(f'/payroll/periods/{self.period.id}/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Updated description')
        self.assertEqual(response.data['status'], 'completed')
        
    def test_delete_period_via_api(self):
        """Test deleting payroll period via API."""
        response = self.client.delete(f'/payroll/periods/{self.period.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify period was deleted
        with self.assertRaises(PayrollPeriod.DoesNotExist):
            PayrollPeriod.objects.get(id=self.period.id)
            
    def test_cannot_delete_completed_period(self):
        """Test that completed periods cannot be deleted."""
        self.period.status = 'completed'
        self.period.save()
        
        response = self.client.delete(f'/payroll/periods/{self.period.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    @patch('payroll.views.payroll_period_views.SummaryAPIView._calculate_period_summary')
    def test_summary_endpoint(self, mock_calculate):
        """Test summary endpoint with totals."""
        # Mock the summary calculation
        mock_calculate.return_value = {
            'total_employees': 5,
            'total_gross_pay': '25000.00',
            'total_deductions': '5000.00',
            'total_net_pay': '20000.00',
            'average_gross_pay': '5000.00',
            'processed_at': None,
            'processing_status': 'pending',
            'payment_count': 0,
        }
        
        response = self.client.get(f'/payroll/periods/{self.period.id}/summary/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify summary data structure
        self.assertIn('id', response.data)
        self.assertIn('total_employees', response.data)
        self.assertIn('total_gross_pay', response.data)
        self.assertIn('total_deductions', response.data)
        self.assertIn('total_net_pay', response.data)
        self.assertIn('average_gross_pay', response.data)
        
        # Verify calculated values
        self.assertEqual(response.data['total_employees'], 5)
        self.assertEqual(response.data['total_gross_pay'], '25000.00')
        self.assertEqual(response.data['total_net_pay'], '20000.00')
        
    def test_summary_endpoint_nonexistent_period(self):
        """Test summary endpoint with non-existent period."""
        response = self.client.get('/payroll/periods/99999/summary/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    @patch('payroll.views.payroll_period_views.PayrollProcessor')
    def test_payroll_run_endpoint(self, mock_processor_class):
        """Test payroll run endpoint."""
        # Mock processor
        mock_processor = MagicMock()
        mock_processor.run_payroll.return_value = {
            'processed_employees': 10,
            'total_gross_amount': 50000.00,
            'status': 'completed'
        }
        mock_processor_class.return_value = mock_processor
        
        data = {
            'run_type': 'full',
            'include_bonuses': True,
            'include_overtime': True,
            'notes': 'Test payroll run'
        }
        
        response = self.client.post(f'/payroll/periods/{self.period.id}/run/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('result', response.data)
        self.assertIn('run_parameters', response.data)
        self.assertIn('period', response.data)
        
        # Verify processor was called
        mock_processor.run_payroll.assert_called_once_with(self.period.id)
        
    def test_payroll_run_invalid_period(self):
        """Test payroll run with invalid period."""
        data = {'run_type': 'full'}
        
        response = self.client.post('/payroll/periods/99999/run/', data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PayrollPeriodFilterTestCase(APITestCase):
    """Test cases for API filtering and querying."""
    
    def setUp(self):
        """Set up test data for filtering tests."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Set up user permissions
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.role = 'finance'
        self.profile.save()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.today = timezone.now().date()
        
        # Create test periods
        self.active_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today,
            period_type='monthly',
            status='active'
        )
        
        self.completed_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=60),
            end_date=self.today - timedelta(days=30),
            period_type='monthly',
            status='completed'
        )
        
        self.weekly_period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=7),
            end_date=self.today,
            period_type='weekly',
            status='active'
        )
        
    def test_filter_by_status(self):
        """Test filtering periods by status."""
        response = self.client.get('/payroll/periods/?status=active')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # active and weekly periods
        
        response = self.client.get('/payroll/periods/?status=completed')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
    def test_filter_by_period_type(self):
        """Test filtering periods by type."""
        response = self.client.get('/payroll/periods/?period_type=monthly')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # monthly periods
        
        response = self.client.get('/payroll/periods/?period_type=weekly')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
    def test_filter_active_only(self):
        """Test filtering for active periods only."""
        response = self.client.get('/payroll/periods/?active_only=true')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return only active periods (not completed)
        for period in response.data['results']:
            self.assertEqual(period['status'], 'active')


class PayrollPeriodEdgeCaseTestCase(TestCase):
    """Test cases for edge cases and error conditions."""
    
    def setUp(self):
        """Set up test data for edge case tests."""
        self.today = timezone.now().date()
        
    def test_payroll_processor_error_handling(self):
        """Test PayrollProcessor error handling."""
        # Test with non-existent period
        processor = PayrollProcessor()
        
        with self.assertRaises(PayrollProcessorError) as context:
            processor.run_payroll(99999)
            
        self.assertIn('not found', str(context.exception))
        
    def test_payroll_processor_completed_period(self):
        """Test processing already completed period."""
        period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today,
            period_type='monthly',
            status='completed'
        )
        
        processor = PayrollProcessor()
        
        with self.assertRaises(PayrollProcessorError) as context:
            processor.run_payroll(period.id)
            
        self.assertIn('already completed', str(context.exception))
        
    def test_payroll_processor_cancelled_period(self):
        """Test processing cancelled period."""
        period = PayrollPeriod.objects.create(
            start_date=self.today - timedelta(days=30),
            end_date=self.today,
            period_type='monthly',
            status='cancelled'
        )
        
        processor = PayrollProcessor()
        
        with self.assertRaises(PayrollProcessorError) as context:
            processor.run_payroll(period.id)
            
        self.assertIn('cancelled', str(context.exception))
        
    def test_leap_year_period_calculation(self):
        """Test period calculations with leap year dates."""
        # February 2024 (leap year)
        leap_start = date(2024, 2, 1)
        leap_end = date(2024, 2, 29)
        
        period = PayrollPeriod.objects.create(
            start_date=leap_start,
            end_date=leap_end,
            period_type='monthly',
            status='active'
        )
        
        # Should handle 29 days correctly
        self.assertEqual(period.duration_days, 29)
        
    def test_single_day_period(self):
        """Test period with same start and end date."""
        period = PayrollPeriod.objects.create(
            start_date=self.today,
            end_date=self.today,
            period_type='custom',
            status='active'
        )
        
        self.assertEqual(period.duration_days, 1)
        
    def test_automation_rule_edge_cases(self):
        """Test automation rule edge cases."""
        # Test with invalid date format
        period = PayrollPeriod(
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            automation_enabled=True,
            automation_rule={'run_on_date': 'invalid-date'}
        )
        
        # Should not crash, just return False
        self.assertFalse(period.is_due_for_automation())
        
        # Test with negative days_before_end
        period.automation_rule = {'days_before_end': -5}
        period.save()
        
        # Should handle gracefully
        self.assertFalse(period.is_due_for_automation())


# Test utilities and helpers
class PayrollTestUtils:
    """Utility methods for payroll testing."""
    
    @staticmethod
    def create_test_period(start_offset=-30, end_offset=0, **kwargs):
        """Create a test payroll period with default values."""
        today = timezone.now().date()
        defaults = {
            'start_date': today + timedelta(days=start_offset),
            'end_date': today + timedelta(days=end_offset),
            'period_type': 'monthly',
            'status': 'active'
        }
        defaults.update(kwargs)
        return PayrollPeriod.objects.create(**defaults)
        
    @staticmethod
    def create_test_user(username='testuser', role='employee'):
        """Create a test user with specified role."""
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='testpass123'
        )
        profile = UserProfile.objects.get(user=user)
        profile.role = role
        profile.save()
        return user
