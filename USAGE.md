# How to Use the Payroll Management System

A comprehensive guide to get started with the Payroll Management System API and automated processing.

## 🚀 Quick Setup

1. **Get the system ready:**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Run migrations
   python manage.py migrate
   
   # Create superuser
   python manage.py createsuperuser
   
   # Start Redis
   redis-server
   ```

2. **Start the services:**
   ```bash
   # Terminal 1: Django server
   python manage.py runserver
   
   # Terminal 2: Celery worker
   celery -A payroll_project worker --loglevel=info
   
   # Terminal 3: Celery beat scheduler
   celery -A payroll_project beat --loglevel=info
   ```

3. **Test it works:**
   ```bash
   curl -X GET "http://localhost:8000/api/payroll/periods/" \
     -H "Authorization: Token your-token"
   ```

## 📖 Basic API Operations

### Authentication

First, get your API token:
```bash
# Create token for your user
python manage.py shell -c "
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
user = User.objects.get(username='your_username')
token, created = Token.objects.get_or_create(user=user)
print(f'Your token: {token.key}')
"
```

### List Payroll Periods

```bash
# Get all periods
curl -X GET "http://localhost:8000/api/payroll/periods/" \
  -H "Authorization: Token your-token"

# Filter by status
curl -X GET "http://localhost:8000/api/payroll/periods/?status=active" \
  -H "Authorization: Token your-token"

# Filter by date range
curl -X GET "http://localhost:8000/api/payroll/periods/?start_date=2024-01-01&end_date=2024-12-31" \
  -H "Authorization: Token your-token"
```

### Create a New Payroll Period

```bash
curl -X POST "http://localhost:8000/api/payroll/periods/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-token" \
  -d '{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "period_type": "monthly",
    "automation_enabled": true,
    "automation_rule": {
      "days_before_end": 3
    },
    "status": "active",
    "description": "January 2024 Payroll"
  }'
```

### Update a Payroll Period

```bash
# Full update
curl -X PUT "http://localhost:8000/api/payroll/periods/1/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-token" \
  -d '{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "period_type": "monthly",
    "automation_enabled": true,
    "status": "active",
    "description": "Updated January 2024 Payroll"
  }'

# Partial update
curl -X PATCH "http://localhost:8000/api/payroll/periods/1/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-token" \
  -d '{"description": "Updated description"}'
```

### Trigger Payroll Run

```bash
curl -X POST "http://localhost:8000/api/payroll/periods/1/run/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-token" \
  -d '{
    "run_type": "full",
    "include_bonuses": true,
    "include_overtime": true,
    "notification_emails": ["finance@company.com"],
    "notes": "Regular monthly payroll"
  }'
```

### Get Period Summary

```bash
curl -X GET "http://localhost:8000/api/payroll/periods/1/summary/" \
  -H "Authorization: Token your-token"
```

## 🎯 Advanced Features

### CSV Export and Import

**Export periods to CSV:**
```bash
curl -X GET "http://localhost:8000/api/payroll/periods/export-csv/?status=active" \
  -H "Authorization: Token your-token" \
  -o payroll_periods.csv
```

**Import periods from CSV:**
```bash
curl -X POST "http://localhost:8000/api/payroll/periods/import-csv/" \
  -H "Authorization: Token your-token" \
  -F "file=@payroll_periods.csv"
```

**CSV format for import:**
```csv
Start Date,End Date,Period Type,Status,Automation Enabled,Description
2024-03-01,2024-03-31,monthly,active,Yes,March 2024 Payroll
2024-04-01,2024-04-30,monthly,active,Yes,April 2024 Payroll
```

### Automation Rules

Create periods with different automation patterns:

**Daily check at 2 AM:**
```json
{
  "automation_rule": {
    "cron": "0 2 * * *"
  }
}
```

**Run 5 days before period ends:**
```json
{
  "automation_rule": {
    "days_before_end": 5
  }
}
```

**Run on specific date:**
```json
{
  "automation_rule": {
    "run_on_date": "2024-01-28"
  }
}
```

**Combined rules with notifications:**
```json
{
  "automation_rule": {
    "days_before_end": 3,
    "cron": "0 2 28 * *",
    "notification_emails": ["finance@company.com", "hr@company.com"]
  }
}
```

## 🔧 Django Admin Interface

Access the admin interface at `http://localhost:8000/admin/` to:

- View and manage payroll periods through a web interface
- Monitor user permissions and roles
- View task execution logs
- Manage automation settings

## 📊 Monitoring and Management

### Check Celery Status

```bash
# Check active tasks
celery -A payroll_project inspect active

# Check scheduled tasks
celery -A payroll_project inspect scheduled

# Check worker statistics
celery -A payroll_project inspect stats
```

### Manual Task Execution

```bash
# Run payroll for specific period
python manage.py shell -c "
from payroll.tasks import run_payroll_for_period
result = run_payroll_for_period.delay(period_id=1, force=True)
print(result.get())
"

# Check automation eligibility
python manage.py shell -c "
from payroll.models import PayrollPeriod
period = PayrollPeriod.objects.get(id=1)
print(f'Due for automation: {period.is_due_for_automation()}')
"
```

### Monitor with Flower

```bash
# Install and start Flower
pip install flower
celery -A payroll_project flower

# Access monitoring at http://localhost:5555
```

## 🛠️ Management Commands

### Create Payroll User with Permissions

```bash
# Interactive creation
python manage.py create_payroll_user

# With parameters
python manage.py create_payroll_user --username finance_user --role finance --email finance@company.com
```

### Run Automation Tasks Manually

```bash
# Run the automated payroll check
python manage.py shell -c "
from payroll.tasks import auto_run_payroll
result = auto_run_payroll.delay()
print(result.get())
"
```

## 🔒 Permissions and Access Control

The system uses role-based access control:

**Finance Role:**
- Full access to all operations
- Can create, update, delete periods
- Can run payroll and export data

**HR Role:**
- Can view periods and summaries
- Can run payroll
- Cannot create or delete periods

**Admin Role:**
- Full system access
- User management
- System configuration

**Regular User:**
- Limited access based on specific permissions

## 📋 Common Workflows

### Monthly Payroll Setup

1. **Create monthly periods for the year:**
   ```bash
   # Create script or use API to create 12 monthly periods
   curl -X POST "http://localhost:8000/api/payroll/periods/" \
     -H "Content-Type: application/json" \
     -H "Authorization: Token your-token" \
     -d '{
       "start_date": "2024-01-01",
       "end_date": "2024-01-31", 
       "period_type": "monthly",
       "automation_enabled": true,
       "automation_rule": {
         "cron": "0 2 28 * *"
       },
       "status": "active"
     }'
   ```

2. **Enable automation for automatic processing**
3. **Monitor through admin interface or API**

### Bi-weekly Payroll Setup

1. **Create bi-weekly periods:**
   ```bash
   curl -X POST "http://localhost:8000/api/payroll/periods/" \
     -H "Content-Type: application/json" \
     -H "Authorization: Token your-token" \
     -d '{
       "start_date": "2024-01-01",
       "end_date": "2024-01-14",
       "period_type": "bi_weekly", 
       "automation_enabled": true,
       "automation_rule": {
         "cron": "0 2 * * 5"
       },
       "status": "active"
     }'
   ```

### Emergency Payroll Run

```bash
# Force run payroll immediately
curl -X POST "http://localhost:8000/api/payroll/periods/1/run/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-token" \
  -d '{
    "run_type": "full",
    "notes": "Emergency payroll run - bonus payments"
  }'
```

## 🚨 Troubleshooting

### Common Issues

**Authentication errors:**
```bash
# Check if token is valid
curl -X GET "http://localhost:8000/api/payroll/periods/" \
  -H "Authorization: Token your-token" -v
```

**Period validation errors:**
```bash
# Periods cannot overlap - check existing periods first
curl -X GET "http://localhost:8000/api/payroll/periods/?start_date=2024-01-01&end_date=2024-01-31"
```

**Celery not processing tasks:**
```bash
# Check if Redis is running
redis-cli ping

# Check worker status
celery -A payroll_project inspect ping
```

**Permission denied:**
```bash
# Check user permissions
python manage.py shell -c "
from django.contrib.auth.models import User
user = User.objects.get(username='your_username')
print(user.get_all_permissions())
"
```

### Health Check Script

Create a simple health check:

```bash
#!/bin/bash
# health_check.sh

echo "Checking Payroll System Health..."

# Check Django
if curl -s http://localhost:8000/admin/login/ > /dev/null; then
    echo "✅ Django is running"
else
    echo "❌ Django is not responding"
fi

# Check Redis
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is running"
else
    echo "❌ Redis is not responding"
fi

# Check Celery
if celery -A payroll_project inspect ping > /dev/null 2>&1; then
    echo "✅ Celery worker is running"
else
    echo "❌ Celery worker is not responding"
fi

echo "Health check complete."
```

## 📚 Additional Resources

- **Full API Documentation:** See `docs/API.md` for complete endpoint reference
- **Scheduler Setup:** See `docs/SCHEDULER_SETUP.md` for detailed configuration
- **Django Admin:** Access at `/admin/` for web-based management
- **API Browser:** Access at `/api/payroll/` for browsable API interface

---

That's the essential guide to using the Payroll Management System! For more advanced usage and configuration, refer to the complete documentation in the `docs/` directory.
