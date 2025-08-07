# Payroll Automation Scheduler

This document explains how to use the automated payroll processing system built with Celery Beat and Django.

## Overview

The payroll automation system provides:
- **Scheduled Processing**: Automatically runs payroll based on configurable rules
- **Idempotency**: Ensures payroll periods aren't processed multiple times
- **Error Handling**: Robust error handling with retry logic
- **Manual Control**: Management commands for testing and manual processing

## Components

### 1. Celery Beat Task: `auto_run_payroll()`

The main periodic task that:
1. Queries `PayrollPeriod` objects with `automation_enabled=True` and `status='active'`
2. Checks if periods are due for processing using `is_due_for_automation()` 
3. Calls `PayrollProcessor.run_payroll()` for eligible periods
4. Ensures idempotency using Redis cache locks

### 2. PayrollPeriod Model Enhancements

New fields and methods:
- `automation_enabled`: Boolean flag to enable/disable automation
- `automation_rule`: JSON field storing automation rules
- `is_due_for_automation()`: Method to check if period is due for processing

### 3. Automation Rules

The `automation_rule` JSON field supports:

```json
// Run on a specific date
{"run_on_date": "2024-01-25"}

// Run N days before period end date  
{"days_before_end": 3}

// Custom cron expression (handled by Celery Beat)
{"cron": "0 0 25 * *"}
```

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Redis Server

```bash
# Ubuntu/Debian
sudo systemctl start redis

# macOS with Homebrew
brew services start redis

# Docker
docker run -d --name redis -p 6379:6379 redis:alpine
```

### 3. Run Django Migrations

```bash
python manage.py migrate
```

### 4. Start Celery Worker

```bash
celery -A payroll_project worker --loglevel=info
```

### 5. Start Celery Beat Scheduler

```bash
celery -A payroll_project beat --loglevel=info
```

## Configuration

### Default Schedule

By default, `auto_run_payroll()` runs daily at 2:00 AM:

```python
CELERY_BEAT_SCHEDULE = {
    'auto-run-payroll': {
        'task': 'payroll.tasks.auto_run_payroll',
        'schedule': crontab(hour=2, minute=0),
        'options': {
            'expires': 3600,  # 1 hour expiration
        }
    },
}
```

### Customizing Schedule

To change the schedule, modify `settings.py`:

```python
# Run every hour
'schedule': crontab(minute=0)

# Run twice daily
'schedule': crontab(hour=[2, 14], minute=0)

# Run on weekdays only
'schedule': crontab(hour=2, minute=0, day_of_week='1-5')
```

## Usage Examples

### 1. Creating an Automated Payroll Period

```python
from payroll.models import PayrollPeriod
from datetime import date, timedelta

# Monthly payroll that runs 3 days before end date
period = PayrollPeriod.objects.create(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31), 
    period_type='monthly',
    automation_enabled=True,
    automation_rule={'days_before_end': 3},
    status='active'
)

# Bi-weekly payroll that runs on specific date
period = PayrollPeriod.objects.create(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 14),
    period_type='bi_weekly', 
    automation_enabled=True,
    automation_rule={'run_on_date': '2024-01-12'},
    status='active'
)
```

### 2. Manual Testing

```bash
# Test full automation (synchronous)
python manage.py run_payroll_automation

# Test specific period
python manage.py run_payroll_automation --period-id 1

# Force processing regardless of rules
python manage.py run_payroll_automation --period-id 1 --force

# Run asynchronously through Celery
python manage.py run_payroll_automation --async
```

### 3. Monitoring

```python
# Check which periods are due for automation
from payroll.models import PayrollPeriod

due_periods = [
    p for p in PayrollPeriod.objects.filter(
        automation_enabled=True, 
        status='active'
    ) 
    if p.is_due_for_automation()
]

print(f"Periods due for automation: {len(due_periods)}")
```

## Idempotency & Safety

### Cache-Based Locking

The system uses Redis cache to prevent duplicate processing:

```python
cache_key = f"payroll_processing_{period.id}"
if cache.get(cache_key):
    # Already being processed, skip
    return

# Set lock with 1 hour expiration  
cache.set(cache_key, True, timeout=3600)
```

### Status Checking

Multiple levels of status checking:
1. Only processes periods with `status='active'`
2. Skips periods already marked as `'completed'`
3. Validates period exists before processing

### Error Handling

- **Retry Logic**: Failed tasks retry up to 3 times with exponential backoff
- **Isolation**: Each period processes independently  
- **Logging**: Comprehensive logging for debugging
- **Cleanup**: Hourly cleanup task removes stale locks

## Monitoring & Troubleshooting

### Celery Monitoring

```bash
# Check active tasks
celery -A payroll_project inspect active

# Check scheduled tasks
celery -A payroll_project inspect scheduled

# Check worker stats
celery -A payroll_project inspect stats
```

### Django Logs

```python
import logging
logger = logging.getLogger('payroll.tasks')

# Check recent automation runs
# Logs are written with INFO level for successful runs
# ERROR level for failures
```

### Redis Monitoring

```bash
# Connect to Redis CLI
redis-cli

# Check current locks
KEYS payroll_cache:payroll_processing_*

# Check cache usage
INFO memory
```

## Production Considerations

### 1. High Availability

- Run multiple Celery workers for redundancy
- Use Redis Sentinel or Cluster for cache high availability
- Monitor worker health and restart failed workers

### 2. Scaling

- Use separate queues for payroll tasks: `CELERY_TASK_ROUTES`
- Scale workers based on payroll volume
- Consider using Celery Flower for monitoring

### 3. Security

- Use Redis AUTH in production
- Encrypt Redis connections with TLS
- Limit Redis access to application servers only

### 4. Backup & Recovery

- Backup Redis data regularly
- Have rollback procedures for failed payroll runs
- Test automation in staging environment first

## Troubleshooting

### Common Issues

**Task not running:**
- Check Celery Beat is running
- Verify Redis connectivity  
- Check task is properly registered

**Duplicate processing:**
- Check Redis cache is working
- Verify lock cleanup task is running
- Look for worker failures that don't release locks

**Performance issues:**
- Monitor worker memory usage
- Check Redis performance
- Consider task optimization for large employee counts

**Missing periods:**
- Verify automation rules are correct
- Check period status is 'active'
- Confirm `automation_enabled=True`

### Debug Commands

```bash
# Test Redis connection
python -c "from django.core.cache import cache; print(cache.get('test') or 'OK')"

# Test task registration  
celery -A payroll_project inspect registered

# Test specific automation rule
python manage.py shell
>>> from payroll.models import PayrollPeriod
>>> period = PayrollPeriod.objects.get(id=1)
>>> period.is_due_for_automation()
```

## API Integration

For programmatic control:

```python
from payroll.tasks import auto_run_payroll, run_payroll_for_period

# Queue automation task
task = auto_run_payroll.delay()
print(f"Task ID: {task.id}")

# Check task status
result = task.get(timeout=10)
print(f"Result: {result}")

# Process specific period
task = run_payroll_for_period.delay(period_id=1, force=False)
```

This automation system provides a robust, scalable solution for automated payroll processing with comprehensive error handling and monitoring capabilities.
