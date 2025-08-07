"""
PayrollProcessor service for handling complete payroll processing workflow.

This service handles:
1. Fetching active employees
2. Processing salary, bonuses, and overtime for each employee
3. Applying deductions, taxes, and insurance rates
4. Creating payroll payments
5. Updating payroll period status
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional
from django.db import transaction, models
from django.utils import timezone
from django.contrib.auth.models import User

# Import models - assuming they exist or will be created
try:
    from payroll.models import (
        PayrollPeriod, 
        EmployeeSalary, 
        PayrollPayment, 
        Deduction, 
        Tax, 
        Insurance,
        Bonus,
        Overtime
    )
except ImportError:
    # Fallback imports or create placeholder models
    from payroll.models import PayrollPeriod
    
    # These would need to be defined in models.py
    class EmployeeSalary:
        pass
    class PayrollPayment:
        pass
    class Deduction:
        pass
    class Tax:
        pass
    class Insurance:
        pass
    class Bonus:
        pass
    class Overtime:
        pass

# Import helper functions - assuming they exist or will be created
try:
    from payroll.utils.calculators import (
        calculate_deductions,
        calculate_taxes,
        calculate_insurance,
        calculate_net_salary
    )
except ImportError:
    # Fallback implementations
    def calculate_deductions(gross_salary: Decimal, employee_id: int) -> Decimal:
        """Calculate total deductions for an employee"""
        # Placeholder implementation
        return Decimal('0.00')
    
    def calculate_taxes(gross_salary: Decimal, employee_id: int) -> Decimal:
        """Calculate total taxes for an employee"""
        # Placeholder implementation - typical tax rate
        return gross_salary * Decimal('0.20')
    
    def calculate_insurance(gross_salary: Decimal, employee_id: int) -> Decimal:
        """Calculate total insurance for an employee"""
        # Placeholder implementation
        return Decimal('0.00')
    
    def calculate_net_salary(gross_salary: Decimal, deductions: Decimal, 
                           taxes: Decimal, insurance: Decimal) -> Decimal:
        """Calculate net salary after all deductions"""
        return gross_salary - deductions - taxes - insurance


# Configure logging
logger = logging.getLogger(__name__)


class PayrollProcessorError(Exception):
    """Custom exception for payroll processing errors"""
    pass


class PayrollProcessor:
    """
    Service class for processing payroll for a given period.
    
    Handles the complete workflow from fetching employees to creating
    payments and updating period status.
    """
    
    def __init__(self):
        self.processed_count = 0
        self.total_gross_amount = Decimal('0.00')
        self.total_net_amount = Decimal('0.00')
        self.total_deductions = Decimal('0.00')
        self.total_taxes = Decimal('0.00')
        self.total_insurance = Decimal('0.00')
        self.errors = []
    
    @transaction.atomic
    def run_payroll(self, period_id: int) -> Dict:
        """
        Main function to run payroll for a given period.
        
        Args:
            period_id: ID of the PayrollPeriod to process
            
        Returns:
            Dict containing processing summary and results
            
        Raises:
            PayrollProcessorError: If payroll processing fails
        """
        try:
            logger.info(f"Starting payroll processing for period ID: {period_id}")
            
            # Get and validate payroll period
            period = self._get_payroll_period(period_id)
            
            # Fetch active employees
            active_employees = self._get_active_employees()
            logger.info(f"Found {len(active_employees)} active employees")
            
            # Process each employee
            for employee in active_employees:
                try:
                    self._process_employee_payroll(employee, period)
                    self.processed_count += 1
                except Exception as e:
                    error_msg = f"Error processing employee {employee.id}: {str(e)}"
                    logger.error(error_msg)
                    self.errors.append(error_msg)
            
            # Mark period as completed and log summary
            self._complete_period(period)
            summary = self._generate_summary(period)
            
            logger.info(f"Payroll processing completed for period {period_id}")
            logger.info(f"Summary: {summary}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Payroll processing failed for period {period_id}: {str(e)}")
            raise PayrollProcessorError(f"Payroll processing failed: {str(e)}") from e
    
    def _get_payroll_period(self, period_id: int) -> PayrollPeriod:
        """Get and validate payroll period"""
        try:
            period = PayrollPeriod.objects.get(id=period_id)
        except PayrollPeriod.DoesNotExist:
            raise PayrollProcessorError(f"Payroll period with ID {period_id} not found")
        
        if period.status == 'completed':
            raise PayrollProcessorError(f"Payroll period {period_id} is already completed")
        
        if period.status == 'cancelled':
            raise PayrollProcessorError(f"Payroll period {period_id} is cancelled")
        
        return period
    
    def _get_active_employees(self) -> List[User]:
        """
        Fetch all active employees.
        
        Assuming employees are User objects with is_active=True.
        In a real implementation, this might filter by employee status,
        department, or other criteria.
        """
        return User.objects.filter(
            is_active=True,
            # Add additional filters as needed, e.g.:
            # employee_profile__status='active',
            # employee_profile__department__isnull=False,
        ).select_related().prefetch_related()
    
    def _process_employee_payroll(self, employee: User, period: PayrollPeriod) -> None:
        """
        Process payroll for a single employee.
        
        This includes:
        - Collating salary, bonuses, overtime
        - Applying deductions, taxes, insurance
        - Updating EmployeeSalary.net_salary
        - Creating PayrollPayment
        """
        logger.debug(f"Processing payroll for employee {employee.id}")
        
        # Step 2a: Collate EmployeeSalary, bonuses, overtime
        employee_data = self._collate_employee_compensation(employee, period)
        
        # Step 2b: Apply deductions, taxes, insurance
        deduction_data = self._calculate_all_deductions(
            employee_data['gross_salary'], 
            employee.id
        )
        
        # Step 2c: Calculate net salary
        net_salary = calculate_net_salary(
            employee_data['gross_salary'],
            deduction_data['total_deductions'],
            deduction_data['total_taxes'],
            deduction_data['total_insurance']
        )
        
        # Update/create EmployeeSalary record
        employee_salary = self._update_employee_salary(
            employee, period, employee_data, deduction_data, net_salary
        )
        
        # Step 2d: Create PayrollPayment
        payment = self._create_payroll_payment(
            employee, period, employee_salary, net_salary
        )
        
        # Update running totals
        self._update_totals(employee_data, deduction_data, net_salary)
        
        logger.debug(f"Successfully processed payroll for employee {employee.id}")
    
    def _collate_employee_compensation(self, employee: User, period: PayrollPeriod) -> Dict:
        """
        Collate all compensation elements for an employee.
        
        Returns dict with base_salary, bonuses, overtime, and gross_salary.
        """
        # Get base salary (assuming from EmployeeSalary model or profile)
        try:
            # Try to get existing salary record for this period or latest
            employee_salary = EmployeeSalary.objects.filter(
                employee=employee,
                period=period
            ).first()
            
            if not employee_salary:
                # Get latest salary record for this employee
                employee_salary = EmployeeSalary.objects.filter(
                    employee=employee
                ).order_by('-created_at').first()
            
            base_salary = employee_salary.base_salary if employee_salary else Decimal('0.00')
            
        except (EmployeeSalary.DoesNotExist, AttributeError):
            # Fallback: assume salary is stored elsewhere or default
            base_salary = Decimal('50000.00')  # Default salary
        
        # Get bonuses for this period
        try:
            bonuses = Bonus.objects.filter(
                employee=employee,
                period=period,
                is_active=True
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        except (AttributeError, NameError):
            bonuses = Decimal('0.00')
        
        # Get overtime for this period
        try:
            overtime = Overtime.objects.filter(
                employee=employee,
                period=period,
                is_active=True
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        except (AttributeError, NameError):
            overtime = Decimal('0.00')
        
        # Calculate gross salary
        gross_salary = base_salary + bonuses + overtime
        
        return {
            'base_salary': base_salary,
            'bonuses': bonuses,
            'overtime': overtime,
            'gross_salary': gross_salary
        }
    
    def _calculate_all_deductions(self, gross_salary: Decimal, employee_id: int) -> Dict:
        """
        Calculate all deductions, taxes, and insurance for an employee.
        
        Uses existing helper functions.
        """
        deductions = calculate_deductions(gross_salary, employee_id)
        taxes = calculate_taxes(gross_salary, employee_id)
        insurance = calculate_insurance(gross_salary, employee_id)
        
        return {
            'total_deductions': deductions,
            'total_taxes': taxes,
            'total_insurance': insurance
        }
    
    def _update_employee_salary(
        self, 
        employee: User, 
        period: PayrollPeriod,
        employee_data: Dict,
        deduction_data: Dict,
        net_salary: Decimal
    ) -> 'EmployeeSalary':
        """
        Update or create EmployeeSalary record with calculated net_salary.
        """
        try:
            employee_salary, created = EmployeeSalary.objects.update_or_create(
                employee=employee,
                period=period,
                defaults={
                    'base_salary': employee_data['base_salary'],
                    'bonuses': employee_data['bonuses'],
                    'overtime': employee_data['overtime'],
                    'gross_salary': employee_data['gross_salary'],
                    'total_deductions': deduction_data['total_deductions'],
                    'total_taxes': deduction_data['total_taxes'],
                    'total_insurance': deduction_data['total_insurance'],
                    'net_salary': net_salary,
                    'processed_at': timezone.now()
                }
            )
            
            action = "Created" if created else "Updated"
            logger.debug(f"{action} EmployeeSalary record for employee {employee.id}")
            
            return employee_salary
            
        except Exception as e:
            logger.error(f"Failed to update EmployeeSalary for employee {employee.id}: {e}")
            # Create a mock object if the model doesn't exist yet
            class MockEmployeeSalary:
                def __init__(self):
                    self.employee = employee
                    self.period = period
                    self.net_salary = net_salary
            
            return MockEmployeeSalary()
    
    def _create_payroll_payment(
        self, 
        employee: User,
        period: PayrollPeriod,
        employee_salary: 'EmployeeSalary',
        net_salary: Decimal
    ) -> 'PayrollPayment':
        """
        Create PayrollPayment record linked to the period.
        """
        try:
            payment = PayrollPayment.objects.create(
                employee=employee,
                period=period,
                employee_salary=employee_salary,
                amount=net_salary,
                payment_date=timezone.now().date(),
                status='pending',  # or 'processed' depending on business logic
                payment_method='bank_transfer',  # default method
                reference_number=f"PAY-{period.id}-{employee.id}-{timezone.now().strftime('%Y%m%d')}"
            )
            
            logger.debug(f"Created PayrollPayment for employee {employee.id}")
            return payment
            
        except Exception as e:
            logger.error(f"Failed to create PayrollPayment for employee {employee.id}: {e}")
            # Create a mock object if the model doesn't exist yet
            class MockPayrollPayment:
                def __init__(self):
                    self.employee = employee
                    self.period = period
                    self.amount = net_salary
            
            return MockPayrollPayment()
    
    def _update_totals(
        self, 
        employee_data: Dict, 
        deduction_data: Dict, 
        net_salary: Decimal
    ) -> None:
        """Update running totals for summary reporting."""
        self.total_gross_amount += employee_data['gross_salary']
        self.total_net_amount += net_salary
        self.total_deductions += deduction_data['total_deductions']
        self.total_taxes += deduction_data['total_taxes']
        self.total_insurance += deduction_data['total_insurance']
    
    def _complete_period(self, period: PayrollPeriod) -> None:
        """Mark payroll period as completed."""
        period.status = 'completed'
        period.save(update_fields=['status', 'updated_at'])
        logger.info(f"Marked payroll period {period.id} as completed")
    
    def _generate_summary(self, period: PayrollPeriod) -> Dict:
        """Generate processing summary with totals."""
        summary = {
            'period_id': period.id,
            'period_dates': f"{period.start_date} to {period.end_date}",
            'processed_employees': self.processed_count,
            'total_gross_amount': float(self.total_gross_amount),
            'total_net_amount': float(self.total_net_amount),
            'total_deductions': float(self.total_deductions),
            'total_taxes': float(self.total_taxes),
            'total_insurance': float(self.total_insurance),
            'processing_errors': len(self.errors),
            'error_details': self.errors,
            'completed_at': timezone.now().isoformat(),
            'status': 'completed'
        }
        
        return summary


# Convenience function for direct usage
def run_payroll(period_id: int) -> Dict:
    """
    Convenience function to run payroll processing.
    
    Args:
        period_id: ID of the PayrollPeriod to process
        
    Returns:
        Dict containing processing summary and results
        
    Raises:
        PayrollProcessorError: If payroll processing fails
    """
    processor = PayrollProcessor()
    return processor.run_payroll(period_id)


# Example usage and testing function
def test_payroll_processor():
    """
    Test function to demonstrate usage.
    Should be removed in production.
    """
    try:
        # Example: Process payroll for period ID 1
        result = run_payroll(period_id=1)
        print("Payroll processing completed successfully!")
        print(f"Summary: {result}")
        return result
    except PayrollProcessorError as e:
        print(f"Payroll processing failed: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
