# Payroll System Permissions & Validation

This document describes the role-based permissions system and validation features implemented in the payroll system.

## Overview

The payroll system implements a comprehensive role-based access control (RBAC) system that ensures only authorized users can create payroll periods and run payroll operations. The system also includes robust validation to prevent date overlaps and duplicate periods.

## Role-Based Access Control

### User Roles

The system supports five user roles:

1. **Employee** (`employee`) - Default role with minimal permissions
2. **Manager** (`manager`) - Basic management permissions
3. **HR** (`hr`) - Human resources with view-all permissions
4. **Finance** (`finance`) - Financial operations permissions
5. **Admin** (`admin`) - Full system administration permissions

### Automatic Permission Assignment

When users are assigned finance or admin roles, they automatically receive the following permissions:
- `can_create_periods = True`
- `can_run_payroll = True`
- `can_view_all_periods = True`

HR users automatically receive:
- `can_view_all_periods = True`

### Manual Permission Override

For any role, individual permissions can be manually granted:
- `can_create_periods` - Allows creating new payroll periods
- `can_run_payroll` - Allows triggering payroll runs
- `can_view_all_periods` - Allows viewing all payroll periods

## DRF Permission Classes

### PayrollPeriodPermissions

Main permission class for `PayrollPeriodViewSet`:

- **GET requests** (list, retrieve): Finance, Admin, HR, or users with `can_view_all_periods`
- **POST requests** (create): Finance, Admin, or users with `can_create_periods`
- **PUT/PATCH/DELETE requests** (update, destroy): Finance or Admin only

### CanCreatePayrollPeriods

Specific permission for creating payroll periods:
- Finance users
- Admin users
- Any user with `can_create_periods = True`

### CanRunPayroll

Specific permission for running payroll operations:
- Finance users
- Admin users
- Any user with `can_run_payroll = True`

### CanViewAllPeriods

Specific permission for viewing all periods:
- Finance users
- Admin users
- HR users
- Any user with `can_view_all_periods = True`

### IsFinanceOrAdmin

Strict permission requiring Finance or Admin role:
- Finance users only
- Admin users only

## API Endpoints & Permissions

### PayrollPeriod CRUD Operations

| Endpoint | Method | Permission Required |
|----------|---------|-------------------|
| `/api/payroll/periods/` | GET | CanViewAllPeriods |
| `/api/payroll/periods/` | POST | CanCreatePayrollPeriods |
| `/api/payroll/periods/{id}/` | GET | CanViewAllPeriods |
| `/api/payroll/periods/{id}/` | PUT/PATCH | IsFinanceOrAdmin |
| `/api/payroll/periods/{id}/` | DELETE | IsFinanceOrAdmin |
| `/api/payroll/periods/export-csv/` | GET | IsFinanceOrAdmin |
| `/api/payroll/periods/import-csv/` | POST | IsFinanceOrAdmin |

### Summary & Payroll Run Operations

| Endpoint | Method | Permission Required |
|----------|---------|-------------------|
| `/api/payroll/periods/{id}/summary/` | GET | CanViewAllPeriods |
| `/api/payroll/periods/{id}/run/` | POST | CanRunPayroll |

## Validation Features

### Date Overlap Prevention

The system prevents overlapping periods of the same type:

```python
# Prevents creating periods like:
# Period 1: Jan 1-31 (monthly)
# Period 2: Jan 15 - Feb 15 (monthly) ❌ OVERLAP
```

**Validation Logic:**
- Checks for periods where `start_date <= new_end_date` AND `end_date >= new_start_date`
- Only applies to periods of the same `period_type`
- Excludes the current instance when updating

### Period Uniqueness

Prevents exact duplicate periods:

```python
# Prevents creating identical periods:
# Period 1: Jan 1-31 (monthly)
# Period 2: Jan 1-31 (monthly) ❌ DUPLICATE
```

### Automation Rule Validation

Validates JSON automation rules:

**Valid Rule Formats:**
```json
{
  "cron": "0 0 25 * *",
  "days_before_end": 3,
  "run_on_date": "2024-01-25"
}
```

**Validation Rules:**
- Must be valid JSON object
- Must contain at least one of: `cron`, `days_before_end`, `run_on_date`
- `run_on_date` must be in YYYY-MM-DD format
- `days_before_end` must be non-negative integer

### Date Range Validation

- `end_date` must be after `start_date`
- `start_date` cannot be in the past for new periods
- Payroll cannot be run for periods that have ended

## Usage Examples

### Creating a User with Permissions

```python
from django.contrib.auth.models import User
from payroll.models import UserProfile

# Create user
user = User.objects.create_user(
    username='finance_user',
    email='finance@company.com',
    password='secure_password'
)

# Get the automatically created profile
profile = user.userprofile
profile.role = 'finance'  # This will auto-set permissions
profile.department = 'Finance'
profile.employee_id = 'FIN001'
profile.save()
```

### Manual Permission Assignment

```python
# Grant specific permissions to a manager
profile = user.userprofile
profile.role = 'manager'
profile.can_create_periods = True  # Manual override
profile.save()
```

### API Authentication

```python
# Using Token Authentication
headers = {
    'Authorization': 'Token your_auth_token_here',
    'Content-Type': 'application/json'
}

# Create a period (requires finance/admin or can_create_periods)
response = requests.post(
    'http://localhost:8000/api/payroll/periods/',
    json={
        'start_date': '2024-01-01',
        'end_date': '2024-01-31',
        'period_type': 'monthly',
        'description': 'January 2024 Payroll'
    },
    headers=headers
)
```

## Error Messages

### Permission Denied

```json
{
  "detail": "You don't have permission to create payroll periods. Only Finance/Admin roles or users with explicit permissions can create periods."
}
```

### Date Overlap

```json
{
  "start_date": [
    "This period overlaps with existing Monthly period (2024-01-01 to 2024-01-31)."
  ]
}
```

### Duplicate Period

```json
{
  "start_date": [
    "A Monthly period with these exact dates already exists."
  ]
}
```

## Database Models

### UserProfile Model

```python
class UserProfile(BaseModel):
    user = OneToOneField(User, on_delete=CASCADE)
    role = CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    department = CharField(max_length=100, blank=True, null=True)
    employee_id = CharField(max_length=50, blank=True, null=True, unique=True)
    can_create_periods = BooleanField(default=False)
    can_run_payroll = BooleanField(default=False)
    can_view_all_periods = BooleanField(default=False)
```

### PayrollPeriod Model Constraints

```python
class Meta:
    constraints = [
        CheckConstraint(
            check=Q(end_date__gte=F('start_date')),
            name='payroll_period_end_after_start'
        )
    ]
```

## Migration Commands

```bash
# Create and apply migrations for the new models
python manage.py makemigrations payroll
python manage.py migrate

# Create a superuser for admin access
python manage.py createsuperuser
```

## Testing

The system includes comprehensive validation at multiple levels:

1. **Model Level** - `clean()` method validation
2. **Serializer Level** - DRF serializer validation
3. **View Level** - Permission class enforcement
4. **Database Level** - Constraint validation

## Security Considerations

- All endpoints require authentication
- Permissions are checked at the view level
- Model validation prevents data integrity issues
- Admin interface respects user roles
- Sensitive operations (create/update/delete) require elevated permissions

## Future Enhancements

Potential improvements to consider:

1. **Department-based permissions** - Users can only access periods for their department
2. **Time-based permissions** - Permissions that expire or are date-bound
3. **Approval workflows** - Multi-step approval process for payroll runs
4. **Audit logging** - Track all permission-sensitive operations
5. **Permission inheritance** - Hierarchical permission structures
