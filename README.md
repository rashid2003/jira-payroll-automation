# Payroll Management System

A comprehensive Django-based payroll management system with automated processing, REST API, and scheduled tasks.

## Features

- **Payroll Period Management**: Complete CRUD operations for payroll periods with automation support
- **Automated Payroll Processing**: Celery-based scheduled payroll runs with customizable automation rules
- **REST API**: Full REST API for payroll operations with proper permissions and authentication
- **CSV Import/Export**: Bulk operations for payroll period data management
- **Scheduled Tasks**: Background processing with Celery Beat for automated payroll runs
- **Permission System**: Role-based access control for finance, admin, and HR users
- **Data Validation**: Comprehensive validation for period overlaps, dates, and automation rules
- **Idempotent Processing**: Safe retry mechanisms and duplicate processing prevention

## 🚀 Quick Start

### 1. **Installation**
```bash
# Clone the repository
git clone <repository-url>
cd payroll-management-system

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### 2. **Start Redis (Required for Celery)**
```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or using Homebrew (macOS)
brew install redis
brew services start redis

# Or using package manager (Ubuntu/Debian)
sudo apt-get install redis-server
sudo systemctl start redis-server
```

### 3. **Start Celery Worker and Beat**
```bash
# Terminal 1: Start Celery worker
celery -A payroll_project worker --loglevel=info

# Terminal 2: Start Celery Beat scheduler
celery -A payroll_project beat --loglevel=info

# Alternative: Combined worker and beat (development only)
celery -A payroll_project worker --beat --loglevel=info
```

### 4. **Create Payroll User (Optional)**
```bash
# Create user with specific payroll permissions
python manage.py create_payroll_user
```

## API Documentation

### Base URL
```
http://localhost:8000/api/payroll/
```

### Authentication
The API uses Django REST Framework authentication. You can use:
- Session Authentication (for web interface)
- Token Authentication (for API clients)

### Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/periods/` | List all payroll periods |
| POST | `/periods/` | Create new payroll period |
| GET | `/periods/{id}/` | Get specific payroll period |
| PUT | `/periods/{id}/` | Update payroll period |
| PATCH | `/periods/{id}/` | Partially update payroll period |
| DELETE | `/periods/{id}/` | Delete payroll period |
| GET | `/periods/export-csv/` | Export periods to CSV |
| POST | `/periods/import-csv/` | Import periods from CSV |
| GET | `/periods/{id}/summary/` | Get period summary with aggregated data |
| POST | `/periods/{id}/run/` | Trigger payroll run for period |

## Detailed API Usage

### 1. List Payroll Periods

**GET** `/api/payroll/periods/`

Query parameters:
- `status`: Filter by status (`active`, `completed`, `cancelled`)
- `period_type`: Filter by type (`monthly`, `bi_weekly`, `weekly`, `custom`)
- `start_date`: Filter by start date (YYYY-MM-DD)
- `end_date`: Filter by end date (YYYY-MM-DD)
- `active_only`: Show only active periods (`true`/`false`)

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/payroll/periods/?status=active&period_type=monthly" \
  -H "Authorization: Token your-auth-token"
```

**Example Response:**
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "start_date": "2024-01-01",
      "end_date": "2024-01-31",
      "period_type": "monthly",
      "automation_enabled": true,
      "automation_rule": {
        "cron": "0 2 28 * *",
        "days_before_end": 3
      },
      "status": "active",
      "description": "January 2024 Payroll",
      "meta": {},
      "created_at": "2024-01-01T10:00:00Z",
      "updated_at": "2024-01-01T10:00:00Z",
      "is_active": true,
      "is_current": true,
      "duration_days": 31
    }
  ]
}
```

### 2. Create Payroll Period

**POST** `/api/payroll/periods/`

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/payroll/periods/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-auth-token" \
  -d '{
    "start_date": "2024-02-01",
    "end_date": "2024-02-29",
    "period_type": "monthly",
    "automation_enabled": true,
    "automation_rule": {
      "days_before_end": 5,
      "cron": "0 2 25 * *"
    },
    "description": "February 2024 Payroll",
    "status": "active"
  }'
```

**Example Response:**
```json
{
  "id": 2,
  "start_date": "2024-02-01",
  "end_date": "2024-02-29",
  "period_type": "monthly",
  "automation_enabled": true,
  "automation_rule": {
    "days_before_end": 5,
    "cron": "0 2 25 * *"
  },
  "status": "active",
  "description": "February 2024 Payroll",
  "meta": {},
  "created_at": "2024-01-15T14:30:00Z",
  "updated_at": "2024-01-15T14:30:00Z",
  "is_active": true,
  "is_current": false,
  "duration_days": 29
}
```

### 3. Get Period Summary

**GET** `/api/payroll/periods/{id}/summary/`

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/payroll/periods/1/summary/" \
  -H "Authorization: Token your-auth-token"
```

**Example Response:**
```json
{
  "id": 1,
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "period_type": "monthly",
  "status": "active",
  "description": "January 2024 Payroll",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:00:00Z",
  "is_active": true,
  "is_current": true,
  "duration_days": 31,
  "total_employees": 0,
  "total_gross_pay": "0.00",
  "total_deductions": "0.00",
  "total_net_pay": "0.00",
  "average_gross_pay": "0.00"
}
```

### 4. Trigger Payroll Run

**POST** `/api/payroll/periods/{id}/run/`

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/payroll/periods/1/run/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-auth-token" \
  -d '{
    "run_type": "full",
    "include_bonuses": true,
    "include_overtime": true,
    "notification_emails": ["hr@company.com", "finance@company.com"],
    "notes": "Regular monthly payroll run"
  }'
```

**Example Response:**
```json
{
  "success": true,
  "message": "Payroll processing completed successfully",
  "period_id": 1,
  "timestamp": "2024-01-15T16:30:00Z",
  "run_parameters": {
    "run_type": "full",
    "include_bonuses": true,
    "include_overtime": true,
    "notification_emails": ["hr@company.com", "finance@company.com"],
    "notes": "Regular monthly payroll run"
  },
  "period": {
    "id": 1,
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "period_type": "Monthly"
  },
  "results": {
    "employees_processed": 0,
    "total_amount": "0.00",
    "processing_time": "0.5 seconds"
  }
}
```

### 5. CSV Export

**GET** `/api/payroll/periods/export-csv/`

Query parameters: Same as list endpoint

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/payroll/periods/export-csv/?status=active" \
  -H "Authorization: Token your-auth-token" \
  -o payroll_periods.csv
```

### 6. CSV Import

**POST** `/api/payroll/periods/import-csv/`

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/payroll/periods/import-csv/" \
  -H "Authorization: Token your-auth-token" \
  -F "file=@payroll_periods.csv"
```

**CSV Format:**
```csv
Start Date,End Date,Period Type,Status,Automation Enabled,Description
2024-03-01,2024-03-31,monthly,active,Yes,March 2024 Payroll
2024-04-01,2024-04-30,monthly,active,Yes,April 2024 Payroll
```

**Example Response:**
```json
{
  "message": "Import completed. Created: 2, Updated: 0",
  "created_count": 2,
  "updated_count": 0,
  "error_count": 0,
  "errors": []
}
```

## Scheduler Setup Instructions

### 1. Redis Configuration

The system uses Redis for task queuing and caching. Configure in `settings.py`:

```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

### 2. Celery Beat Schedule

The system includes pre-configured scheduled tasks in `settings.py`:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'auto-run-payroll': {
        'task': 'payroll.tasks.auto_run_payroll',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
        'options': {
            'expires': 3600,  # Task expires after 1 hour
        }
    },
    'cleanup-payroll-locks': {
        'task': 'payroll.tasks.cleanup_old_payroll_locks',
        'schedule': crontab(minute=0),  # Hourly
        'options': {
            'expires': 300,  # Task expires after 5 minutes
        }
    },
}
```

### 3. Production Deployment

For production environments, use a process manager like Supervisor:

**Supervisor Configuration (`/etc/supervisor/conf.d/payroll.conf`):**
```ini
[program:payroll-worker]
command=/path/to/venv/bin/celery -A payroll_project worker --loglevel=info
directory=/path/to/project
user=www-data
numprocs=2
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/payroll-worker.log

[program:payroll-beat]
command=/path/to/venv/bin/celery -A payroll_project beat --loglevel=info
directory=/path/to/project
user=www-data
numprocs=1
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/payroll-beat.log
```

### 4. Monitoring Tasks

Monitor Celery tasks using Flower:

```bash
# Install Flower
pip install flower

# Start monitoring
celery -A payroll_project flower

# Access web interface at http://localhost:5555
```

### 5. Custom Automation Rules

Payroll periods support flexible automation rules:

```python
# Days before period end
{
    "days_before_end": 3
}

# Specific date
{
    "run_on_date": "2024-01-28"
}

# Cron expression
{
    "cron": "0 2 28 * *"  # 28th of every month at 2 AM
}

# Combined rules
{
    "days_before_end": 5,
    "cron": "0 2 25 * *",
    "notification_emails": ["finance@company.com"]
}
```

## Manual Task Execution

### Run Payroll for Specific Period
```bash
python manage.py shell -c "
from payroll.tasks import run_payroll_for_period
result = run_payroll_for_period.delay(period_id=1, force=True)
print(result.get())
"
```

### Check Task Status
```bash
# Using Django shell
python manage.py shell -c "
from celery.result import AsyncResult
result = AsyncResult('task-id-here')
print(f'Status: {result.status}')
print(f'Result: {result.result}')
"
```

## Error Handling and Validation

### Common Error Responses

**Validation Error (400):**
```json
{
  "error": "Invalid payroll run parameters",
  "details": {
    "period_id": ["Payroll period with ID 999 does not exist."]
  }
}
```

**Processing Error (422):**
```json
{
  "error": "Payroll processing failed",
  "details": "Period is not in active status",
  "period_id": 1
}
```

**Server Error (500):**
```json
{
  "error": "Unexpected error during payroll run",
  "details": "Database connection failed",
  "period_id": 1
}
```

## Permissions

The system implements role-based access control:

- **Finance Users**: Full access to all operations
- **Admin Users**: Full access to all operations
- **HR Users**: View access and ability to run payroll
- **Regular Users**: Limited access based on specific permissions

### Permission Classes Used:
- `PayrollPeriodPermissions`: General CRUD permissions
- `CanRunPayroll`: Permission to trigger payroll runs
- `CanViewAllPeriods`: Permission to view all periods and summaries
- `IsFinanceOrAdmin`: Finance and admin only operations

## Development

### Running Tests
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test payroll

# Run with coverage
pip install coverage
coverage run manage.py test
coverage report
```

### Database Migrations
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Check migration status
python manage.py showmigrations
```

## Troubleshooting

### 1. Redis Connection Issues
```bash
# Check Redis status
redis-cli ping

# Check Redis logs
tail -f /var/log/redis/redis-server.log
```

### 2. Celery Worker Not Processing Tasks
```bash
# Check worker status
celery -A payroll_project inspect active

# Purge queue
celery -A payroll_project purge

# Restart worker
pkill -f "celery worker"
celery -A payroll_project worker --loglevel=info
```

### 3. Permission Denied Errors
```bash
# Create user with proper permissions
python manage.py create_payroll_user --username finance_user --role finance

# Check user permissions
python manage.py shell -c "
from django.contrib.auth.models import User
user = User.objects.get(username='finance_user')
print(user.get_all_permissions())
"
```

### 4. Task Lock Issues
```bash
# Clear stuck locks
python manage.py shell -c "
from django.core.cache import cache
# Clear all locks (use carefully)
cache.delete_many([key for key in cache.keys() if key.startswith('payroll_processing_')])
"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
