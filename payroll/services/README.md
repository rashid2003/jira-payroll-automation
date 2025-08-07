# PayrollProcessor Service

## Overview

The PayrollProcessor service handles the complete payroll processing workflow for a given payroll period. It provides a comprehensive solution for processing employee salaries, bonuses, overtime, deductions, taxes, and insurance calculations.

## Features

- **Complete Payroll Workflow**: Handles end-to-end payroll processing
- **Employee Management**: Fetches active employees automatically
- **Compensation Calculation**: Collates salary, bonuses, and overtime
- **Deduction Processing**: Applies taxes, deductions, and insurance using existing helpers
- **Payment Creation**: Creates PayrollPayment records linked to the period
- **Status Management**: Marks periods as completed with summary logging
- **Error Handling**: Robust error handling with detailed logging
- **Transaction Safety**: Uses database transactions for data integrity

## Usage

### Basic Usage

```python
from payroll.services.payroll_processor import run_payroll

# Process payroll for a specific period
summary = run_payroll(period_id=1)
print(summary)
```

### Advanced Usage with Class

```python
from payroll.services.payroll_processor import PayrollProcessor

processor = PayrollProcessor()
try:
    summary = processor.run_payroll(period_id=1)
    print(f"Processed {summary['processed_employees']} employees")
    print(f"Total net amount: ${summary['total_net_amount']}")
except PayrollProcessorError as e:
    print(f"Processing failed: {e}")
```

## Requirements

### Models Required

The service expects the following models to exist in `payroll.models`:

- `PayrollPeriod`: Main period model (already exists)
- `EmployeeSalary`: Employee salary records
- `PayrollPayment`: Payment records
- `Deduction`: Deduction configurations
- `Tax`: Tax configurations  
- `Insurance`: Insurance configurations
- `Bonus`: Bonus records
- `Overtime`: Overtime records

### Helper Functions Required

The service expects these helper functions in `payroll.utils.calculators`:

- `calculate_deductions(gross_salary, employee_id)`: Calculate deductions
- `calculate_taxes(gross_salary, employee_id)`: Calculate taxes
- `calculate_insurance(gross_salary, employee_id)`: Calculate insurance
- `calculate_net_salary(gross, deductions, taxes, insurance)`: Calculate net salary

### Fallback Behavior

If the required models or helper functions don't exist, the service includes:

- **Placeholder Models**: Mock classes for missing models
- **Default Calculations**: Basic tax calculation (20% rate) and zero deductions/insurance
- **Graceful Degradation**: Continues processing with warnings logged

## API Reference

### `run_payroll(period_id: int) -> Dict`

Main function to process payroll for a period.

**Parameters:**
- `period_id`: ID of the PayrollPeriod to process

**Returns:**
- Dictionary with processing summary including:
  - `processed_employees`: Number of employees processed
  - `total_gross_amount`: Total gross salary amount
  - `total_net_amount`: Total net salary amount
  - `total_deductions`: Total deductions applied
  - `total_taxes`: Total taxes applied
  - `total_insurance`: Total insurance applied
  - `processing_errors`: Number of processing errors
  - `error_details`: List of error messages
  - `completed_at`: Processing completion timestamp
  - `status`: Final period status

**Raises:**
- `PayrollProcessorError`: If processing fails

### PayrollProcessor Class

#### Methods

- `run_payroll(period_id)`: Main processing method
- `_get_payroll_period(period_id)`: Validates and retrieves period
- `_get_active_employees()`: Fetches active employee list
- `_process_employee_payroll(employee, period)`: Processes single employee
- `_collate_employee_compensation(employee, period)`: Collects compensation data
- `_calculate_all_deductions(gross_salary, employee_id)`: Calculates deductions
- `_update_employee_salary(...)`: Updates EmployeeSalary record
- `_create_payroll_payment(...)`: Creates PayrollPayment record
- `_complete_period(period)`: Marks period as completed
- `_generate_summary(period)`: Generates processing summary

## Processing Workflow

1. **Validation**: Validates PayrollPeriod exists and is active
2. **Employee Fetch**: Retrieves all active employees
3. **For Each Employee**:
   - Collates base salary, bonuses, overtime
   - Calculates deductions, taxes, insurance
   - Computes net salary
   - Updates/creates EmployeeSalary record
   - Creates PayrollPayment record
4. **Completion**: Marks period as completed
5. **Summary**: Logs and returns processing summary

## Error Handling

- **Database Transactions**: All operations wrapped in atomic transactions
- **Individual Employee Errors**: Continues processing other employees if one fails
- **Detailed Logging**: Comprehensive logging at INFO, DEBUG, and ERROR levels
- **Custom Exceptions**: Uses `PayrollProcessorError` for specific failures
- **Summary Reporting**: Includes error count and details in final summary

## Configuration

### Logging

Configure Django logging to capture PayrollProcessor logs:

```python
LOGGING = {
    'loggers': {
        'payroll.services.payroll_processor': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### Employee Filtering

Modify `_get_active_employees()` method to customize employee selection:

```python
def _get_active_employees(self):
    return User.objects.filter(
        is_active=True,
        employee_profile__status='active',
        employee_profile__department__isnull=False,
        # Add your custom filters here
    ).select_related('employee_profile').prefetch_related('employee_profile__department')
```

## Testing

Use the included test function for development:

```python
from payroll.services.payroll_processor import test_payroll_processor

# Test with period ID 1
result = test_payroll_processor()
```

**Note**: Remove `test_payroll_processor()` function in production deployment.

## Security Considerations

- All database operations use Django ORM for SQL injection protection
- Transaction rollback ensures data integrity on failures
- Employee access is restricted to active users only
- Detailed audit trail through comprehensive logging

## Performance Optimization

- Uses `select_related()` and `prefetch_related()` for efficient queries
- Processes employees in single database transaction
- Aggregates bonus/overtime data efficiently
- Minimal database roundtrips per employee

## Future Enhancements

Potential improvements for future versions:

- **Batch Processing**: Process employees in batches for very large organizations
- **Async Processing**: Use Celery for background processing
- **Email Notifications**: Send completion notifications to HR
- **Approval Workflow**: Add approval steps before marking period complete
- **Audit Trail**: Enhanced audit logging with user tracking
- **Custom Calculators**: Plugin system for custom calculation rules
