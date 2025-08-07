# Payroll Period Tests

This directory contains comprehensive tests for the PayrollPeriod functionality, covering all requirements from Step 9 of the project plan.

## Test Coverage

### `test_payroll_period.py`

#### 1. CRUD Operations (`PayrollPeriodModelTestCase`, `PayrollPeriodAPITestCase`)
- **Create**: Test successful creation of payroll periods with various configurations
- **Read**: Test retrieving single and multiple payroll periods via API
- **Update**: Test updating payroll period fields via API and model methods  
- **Delete**: Test deletion with business rules (cannot delete completed periods)

#### 2. Salary Calculations Accuracy with Edge Cases (`SalaryCalculationTestCase`)
- **Basic Calculations**: Test standard salary calculations with deductions, taxes, insurance
- **Zero Salary**: Test handling of employees with zero base salary
- **High Deductions**: Test edge case where deductions exceed gross salary (negative net pay)
- **Mocked Processing**: Test complete payroll processor workflow with mocked dependencies

#### 3. Automation Trigger Testing (`PayrollPeriodAutomationTestCase`, `PayrollPeriodCeleryTaskTestCase`)
- **Days Before End**: Test automation based on `days_before_end` rule
- **Specific Date**: Test automation based on `run_on_date` rule  
- **Cron Rules**: Test automation with cron expressions
- **Mocked Celery Tasks**: Test `auto_run_payroll` and `process_payroll_period` tasks
- **Cache Locking**: Test idempotency with cache-based locks
- **Error Handling**: Test graceful error handling in automated processing

#### 4. Summary Endpoint Totals (`PayrollPeriodAPITestCase`)
- **Summary Structure**: Test summary endpoint returns correct data structure
- **Aggregated Totals**: Test calculation of total employees, gross pay, deductions, net pay
- **Averages**: Test calculation of average pay amounts
- **Non-existent Periods**: Test 404 handling for invalid period IDs

## Additional Test Classes

### `PayrollPeriodFilterTestCase`
- Tests API filtering by status, period type, active status
- Tests query parameter handling

### `PayrollPeriodEdgeCaseTestCase`  
- Tests error conditions and edge cases
- Leap year handling, single-day periods
- Invalid automation rules
- PayrollProcessor error scenarios

### `PayrollTestUtils`
- Utility methods for creating test data
- Helper functions for test setup

## Running the Tests

### Prerequisites
1. Django environment set up with all dependencies installed
2. Database configured and migrated
3. Redis/Cache backend configured for cache-related tests

### Running All Tests
```bash
python manage.py test payroll.tests.test_payroll_period
```

### Running Specific Test Classes
```bash
# CRUD operations only
python manage.py test payroll.tests.test_payroll_period.PayrollPeriodModelTestCase

# Salary calculations only  
python manage.py test payroll.tests.test_payroll_period.SalaryCalculationTestCase

# Automation tests only
python manage.py test payroll.tests.test_payroll_period.PayrollPeriodAutomationTestCase

# API tests only
python manage.py test payroll.tests.test_payroll_period.PayrollPeriodAPITestCase
```

### Running with Verbose Output
```bash
python manage.py test payroll.tests.test_payroll_period -v 2
```

## Test Dependencies and Mocking

The tests use extensive mocking to avoid dependencies on external services:

- **PayrollProcessor**: Mocked to test calculation logic without requiring actual employee data
- **Celery Tasks**: Mocked to test automation logic without requiring Celery workers  
- **Calculation Functions**: Mocked to test specific calculation scenarios
- **Cache**: Uses Django's cache framework for locking tests
- **Database**: Uses Django's test database with transaction rollback

## Key Test Patterns

### Model Validation Testing
```python
with self.assertRaises(ValidationError) as context:
    period = PayrollPeriod(invalid_data)
    period.clean()
self.assertIn('field_name', context.exception.message_dict)
```

### API Endpoint Testing  
```python
response = self.client.post('/payroll/periods/', data, format='json')
self.assertEqual(response.status_code, status.HTTP_201_CREATED)
```

### Mock-based Calculation Testing
```python
@patch('payroll.services.payroll_processor.calculate_deductions')
def test_calculation(self, mock_deductions):
    mock_deductions.return_value = Decimal('500.00')
    # Test calculation logic
```

### Celery Task Testing
```python
@patch('payroll.tasks.process_payroll_period')
def test_automation(self, mock_process):
    result = auto_run_payroll()
    mock_process.assert_called_once_with(period_id)
```

## Expected Test Results

When all tests pass, you should see output similar to:
```
test_create_payroll_period_success ... ok
test_period_validation_overlapping_periods ... ok
test_is_due_for_automation_days_before_end ... ok
test_basic_salary_calculation ... ok
test_summary_endpoint ... ok
...

Ran 45 tests in 2.5s
OK
```

## Notes

- Tests are designed to be independent and can run in any order
- Database state is reset between tests using Django's TestCase
- Cache is cleared before each test that uses caching functionality  
- All external dependencies are mocked to ensure reliable, fast test execution
- Tests cover both positive cases (expected behavior) and negative cases (error conditions)
