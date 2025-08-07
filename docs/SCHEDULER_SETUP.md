# Scheduler Setup Guide

This guide provides detailed instructions for setting up and configuring the automated payroll scheduler using Celery and Redis.

## Overview

The Payroll Management System uses Celery for task queuing and Redis as a message broker. The scheduler automatically processes payroll periods based on their automation rules.

## Architecture

```
┌─────────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Django Web App    │    │  Celery Worker  │    │  Celery Beat    │
│                     │    │                 │    │   Scheduler     │
│  - REST API         │    │  - Task Exec    │    │  - Cron Jobs    │
│  - Admin Interface  │────│  - Payroll Proc │    │  - Triggers     │
│  - User Interface   │    │  - Error Handle │    │  - Monitoring   │
└─────────────────────┘    └─────────────────┘    └─────────────────┘
           │                         │                         │
           │                         │                         │
           └─────────────────────────┼─────────────────────────┘
                                     │
                          ┌─────────────────┐
                          │      Redis      │
                          │                 │
                          │  - Message Q    │
                          │  - Result Store │
                          │  - Cache        │
                          └─────────────────┘
```

## Prerequisites

### System Requirements

- Python 3.8+
- Django 4.2+
- Redis 6.0+
- Celery 5.3+

### Installation

1. **Install Redis**

   **Ubuntu/Debian:**
   ```bash
   sudo apt update
   sudo apt install redis-server
   sudo systemctl start redis-server
   sudo systemctl enable redis-server
   ```

   **CentOS/RHEL:**
   ```bash
   sudo yum install epel-release
   sudo yum install redis
   sudo systemctl start redis
   sudo systemctl enable redis
   ```

   **macOS:**
   ```bash
   brew install redis
   brew services start redis
   ```

   **Docker:**
   ```bash
   docker run -d --name redis -p 6379:6379 redis:alpine
   ```

2. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify Redis Connection**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

## Configuration

### 1. Django Settings

Update `payroll_project/settings.py`:

```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Task retry settings
CELERY_TASK_DEFAULT_RETRY_DELAY = 60  # 1 minute
CELERY_TASK_MAX_RETRIES = 3

# Task timeout settings
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
CELERY_TASK_TIME_LIMIT = 600       # 10 minutes

# Cache configuration for task idempotency
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'payroll_cache',
        'TIMEOUT': 300,  # 5 minutes default timeout
    }
}

# Scheduled tasks configuration
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'auto-run-payroll': {
        'task': 'payroll.tasks.auto_run_payroll',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
        'options': {
            'expires': 3600,  # Task expires after 1 hour if not executed
        }
    },
    'cleanup-payroll-locks': {
        'task': 'payroll.tasks.cleanup_old_payroll_locks',
        'schedule': crontab(minute=0),  # Run hourly
        'options': {
            'expires': 300,  # Task expires after 5 minutes if not executed
        }
    },
}
```

### 2. Environment Variables

Create a `.env` file for environment-specific settings:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_URL=redis://localhost:6379/1

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Logging
CELERY_LOG_LEVEL=INFO
DJANGO_LOG_LEVEL=INFO

# Email Configuration (for notifications)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Default notification email
DEFAULT_PAYROLL_EMAIL=finance@yourcompany.com
```

### 3. Celery App Configuration

The `payroll_project/celery.py` file is already configured:

```python
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payroll_project.settings')

app = Celery('payroll_project')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed Django apps
app.autodiscover_tasks()

# Optional: Configure additional settings
app.conf.update(
    worker_prefetch_multiplier=1,  # Disable prefetching for better distribution
    task_acks_late=True,           # Acknowledge tasks after completion
    worker_disable_rate_limits=True,
)
```

## Running the Scheduler

### Development Environment

1. **Start Redis**
   ```bash
   # If not already running
   redis-server
   ```

2. **Start Django Development Server**
   ```bash
   python manage.py runserver
   ```

3. **Start Celery Worker** (new terminal)
   ```bash
   celery -A payroll_project worker --loglevel=info
   ```

4. **Start Celery Beat Scheduler** (new terminal)
   ```bash
   celery -A payroll_project beat --loglevel=info
   ```

5. **Combined Worker + Beat** (alternative for development)
   ```bash
   celery -A payroll_project worker --beat --loglevel=info
   ```

### Production Environment

#### Using Supervisor (Recommended)

1. **Install Supervisor**
   ```bash
   # Ubuntu/Debian
   sudo apt install supervisor
   
   # CentOS/RHEL
   sudo yum install supervisor
   ```

2. **Create Supervisor Configuration**
   
   Create `/etc/supervisor/conf.d/payroll.conf`:

   ```ini
   [program:payroll-worker]
   command=/path/to/venv/bin/celery -A payroll_project worker --loglevel=info --concurrency=4
   directory=/path/to/payroll-project
   user=www-data
   numprocs=1
   stdout_logfile=/var/log/payroll-worker.log
   stderr_logfile=/var/log/payroll-worker-error.log
   autostart=true
   autorestart=true
   startsecs=10
   stopwaitsecs=600
   killasgroup=true
   environment=PATH="/path/to/venv/bin",DJANGO_SETTINGS_MODULE="payroll_project.settings"

   [program:payroll-beat]
   command=/path/to/venv/bin/celery -A payroll_project beat --loglevel=info --pidfile=/var/run/celerybeat.pid
   directory=/path/to/payroll-project
   user=www-data
   numprocs=1
   stdout_logfile=/var/log/payroll-beat.log
   stderr_logfile=/var/log/payroll-beat-error.log
   autostart=true
   autorestart=true
   startsecs=10
   stopwaitsecs=10
   killasgroup=true
   environment=PATH="/path/to/venv/bin",DJANGO_SETTINGS_MODULE="payroll_project.settings"

   [group:payroll]
   programs=payroll-worker,payroll-beat
   priority=999
   ```

3. **Start Services**
   ```bash
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl start payroll:*
   ```

4. **Check Status**
   ```bash
   sudo supervisorctl status payroll:*
   ```

#### Using Systemd

1. **Create Worker Service**
   
   Create `/etc/systemd/system/payroll-worker.service`:

   ```ini
   [Unit]
   Description=Payroll Celery Worker
   After=network.target redis.service

   [Service]
   Type=forking
   User=www-data
   Group=www-data
   EnvironmentFile=/path/to/payroll-project/.env
   WorkingDirectory=/path/to/payroll-project
   ExecStart=/path/to/venv/bin/celery -A payroll_project worker --detach --loglevel=info --logfile=/var/log/payroll-worker.log --pidfile=/var/run/payroll-worker.pid
   ExecStop=/path/to/venv/bin/celery -A payroll_project control shutdown
   ExecReload=/bin/kill -s HUP $MAINPID
   PIDFile=/var/run/payroll-worker.pid
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

2. **Create Beat Service**
   
   Create `/etc/systemd/system/payroll-beat.service`:

   ```ini
   [Unit]
   Description=Payroll Celery Beat
   After=network.target redis.service

   [Service]
   Type=simple
   User=www-data
   Group=www-data
   EnvironmentFile=/path/to/payroll-project/.env
   WorkingDirectory=/path/to/payroll-project
   ExecStart=/path/to/venv/bin/celery -A payroll_project beat --loglevel=info --logfile=/var/log/payroll-beat.log --pidfile=/var/run/payroll-beat.pid
   PIDFile=/var/run/payroll-beat.pid
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and Start Services**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable payroll-worker payroll-beat
   sudo systemctl start payroll-worker payroll-beat
   ```

#### Using Docker

1. **Create Docker Compose File**
   
   Create `docker-compose.yml`:

   ```yaml
   version: '3.8'
   services:
     redis:
       image: redis:alpine
       ports:
         - "6379:6379"
       command: redis-server --appendonly yes
       volumes:
         - redis_data:/data

     db:
       image: postgres:13
       environment:
         POSTGRES_DB: payroll
         POSTGRES_USER: payroll
         POSTGRES_PASSWORD: password
       volumes:
         - postgres_data:/var/lib/postgresql/data

     web:
       build: .
       ports:
         - "8000:8000"
       depends_on:
         - db
         - redis
       environment:
         - DJANGO_SETTINGS_MODULE=payroll_project.settings
         - CELERY_BROKER_URL=redis://redis:6379/0
       volumes:
         - .:/code
       command: python manage.py runserver 0.0.0.0:8000

     worker:
       build: .
       depends_on:
         - db
         - redis
       environment:
         - DJANGO_SETTINGS_MODULE=payroll_project.settings
         - CELERY_BROKER_URL=redis://redis:6379/0
       volumes:
         - .:/code
       command: celery -A payroll_project worker --loglevel=info

     beat:
       build: .
       depends_on:
         - db
         - redis
       environment:
         - DJANGO_SETTINGS_MODULE=payroll_project.settings
         - CELERY_BROKER_URL=redis://redis:6379/0
       volumes:
         - .:/code
       command: celery -A payroll_project beat --loglevel=info

   volumes:
     redis_data:
     postgres_data:
   ```

2. **Create Dockerfile**
   
   ```dockerfile
   FROM python:3.9-slim

   WORKDIR /code

   COPY requirements.txt /code/
   RUN pip install -r requirements.txt

   COPY . /code/

   CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
   ```

3. **Start Services**
   ```bash
   docker-compose up -d
   ```

## Automation Rules Configuration

### Rule Types

The system supports three types of automation rules:

#### 1. Days Before End
Trigger payroll processing a specified number of days before the period ends.

```python
automation_rule = {
    "days_before_end": 5
}
```

#### 2. Specific Date
Run payroll on a specific date.

```python
automation_rule = {
    "run_on_date": "2024-01-28"
}
```

#### 3. Cron Expression
Use cron syntax for complex scheduling.

```python
automation_rule = {
    "cron": "0 2 28 * *"  # 28th of every month at 2 AM
}
```

#### 4. Combined Rules
Use multiple rule types together.

```python
automation_rule = {
    "days_before_end": 5,
    "cron": "0 2 * * *",  # Daily at 2 AM
    "notification_emails": ["finance@company.com", "hr@company.com"]
}
```

### Common Cron Patterns

| Pattern | Description |
|---------|-------------|
| `0 2 * * *` | Daily at 2:00 AM |
| `0 2 * * 1` | Every Monday at 2:00 AM |
| `0 2 1 * *` | First day of every month at 2:00 AM |
| `0 2 15 * *` | 15th day of every month at 2:00 AM |
| `0 2 28 * *` | 28th day of every month at 2:00 AM |
| `0 2 */2 * *` | Every other day at 2:00 AM |
| `0 2 * * 1,3,5` | Monday, Wednesday, Friday at 2:00 AM |

### Creating Automation Rules via API

```bash
# Create period with automation
curl -X POST "http://localhost:8000/api/payroll/periods/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-token" \
  -d '{
    "start_date": "2024-02-01",
    "end_date": "2024-02-29",
    "period_type": "monthly",
    "automation_enabled": true,
    "automation_rule": {
      "days_before_end": 3,
      "cron": "0 2 * * *",
      "notification_emails": ["finance@company.com"]
    },
    "status": "active",
    "description": "February 2024 Payroll"
  }'
```

## Monitoring and Maintenance

### 1. Celery Flower (Web-based Monitoring)

Install and run Flower for real-time monitoring:

```bash
# Install Flower
pip install flower

# Start Flower
celery -A payroll_project flower

# Access web interface at http://localhost:5555
```

### 2. Command Line Monitoring

```bash
# Check active tasks
celery -A payroll_project inspect active

# Check scheduled tasks
celery -A payroll_project inspect scheduled

# Check worker statistics
celery -A payroll_project inspect stats

# Purge all tasks
celery -A payroll_project purge
```

### 3. Log Monitoring

Monitor log files for errors and task execution:

```bash
# Follow worker logs
tail -f /var/log/payroll-worker.log

# Follow beat logs
tail -f /var/log/payroll-beat.log

# Search for errors
grep -i error /var/log/payroll-worker.log
```

### 4. Health Checks

Create a health check script:

```bash
#!/bin/bash
# health_check.sh

# Check Redis
redis-cli ping > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ Redis is running"
else
    echo "❌ Redis is not responding"
    exit 1
fi

# Check Celery Worker
celery -A payroll_project inspect ping > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Celery worker is running"
else
    echo "❌ Celery worker is not responding"
    exit 1
fi

# Check Beat scheduler (if running as separate process)
if pgrep -f "celery.*beat" > /dev/null; then
    echo "✅ Celery beat is running"
else
    echo "❌ Celery beat is not running"
    exit 1
fi

echo "✅ All services are healthy"
```

## Troubleshooting

### Common Issues

#### 1. Redis Connection Errors

```bash
# Check Redis status
sudo systemctl status redis-server

# Check Redis configuration
redis-cli config get "*"

# Test connection
redis-cli ping
```

#### 2. Celery Worker Not Processing Tasks

```bash
# Check worker status
celery -A payroll_project inspect active

# Restart worker
sudo supervisorctl restart payroll-worker

# Check for stuck tasks
celery -A payroll_project inspect reserved
```

#### 3. Beat Scheduler Not Running Tasks

```bash
# Check beat configuration
celery -A payroll_project beat --dry-run

# Check scheduled tasks
python manage.py shell -c "
from django_celery_beat.models import PeriodicTask
for task in PeriodicTask.objects.all():
    print(f'{task.name}: {task.enabled}')
"
```

#### 4. Task Lock Issues

```bash
# Clear processing locks
python manage.py shell -c "
from django.core.cache import cache
keys = cache.keys('payroll_processing_*')
if keys:
    cache.delete_many(keys)
    print(f'Cleared {len(keys)} locks')
else:
    print('No locks found')
"
```

#### 5. Memory Issues

```bash
# Monitor memory usage
celery -A payroll_project inspect memdump

# Restart workers if needed
sudo supervisorctl restart payroll-worker
```

### Performance Tuning

#### 1. Worker Concurrency

```bash
# Adjust worker concurrency based on CPU cores
celery -A payroll_project worker --concurrency=4

# Auto-scale workers
celery -A payroll_project worker --autoscale=10,3
```

#### 2. Task Routing

Configure task routing for better performance:

```python
# settings.py
CELERY_TASK_ROUTES = {
    'payroll.tasks.auto_run_payroll': {'queue': 'payroll'},
    'payroll.tasks.process_payroll_period': {'queue': 'processing'},
}
```

#### 3. Result Backend Optimization

```python
# settings.py
CELERY_RESULT_EXPIRES = 3600  # Results expire after 1 hour
CELERY_RESULT_COMPRESSION = 'gzip'
```

## Security Considerations

### 1. Redis Security

```bash
# Configure Redis authentication
# In /etc/redis/redis.conf:
requirepass your-secure-password

# Bind to localhost only
bind 127.0.0.1
```

### 2. Task Security

```python
# settings.py
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_IGNORE_RESULT = False
CELERY_TASK_STORE_ERRORS_EVEN_IF_IGNORED = True
```

### 3. Network Security

- Use firewall rules to restrict Redis access
- Use SSL/TLS for Redis connections in production
- Isolate Celery workers in private network

## Backup and Recovery

### 1. Redis Data Backup

```bash
# Create backup
redis-cli BGSAVE

# Copy backup file
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb
```

### 2. Task Queue Recovery

```bash
# Save current queue state
celery -A payroll_project inspect reserved > task_backup.json

# Restore after recovery
# Manual intervention required to requeue tasks
```

### 3. Database Backup

```bash
# PostgreSQL backup
pg_dump payroll_db > payroll_backup_$(date +%Y%m%d).sql

# SQLite backup
cp db.sqlite3 db_backup_$(date +%Y%m%d).sqlite3
```

## Scaling Considerations

### Horizontal Scaling

1. **Multiple Workers**
   ```bash
   # Run workers on multiple servers
   celery -A payroll_project worker --hostname=worker1@server1
   celery -A payroll_project worker --hostname=worker2@server2
   ```

2. **Redis Clustering**
   - Use Redis Cluster for high availability
   - Configure Celery for Redis Sentinel

3. **Load Balancing**
   - Use nginx for API load balancing
   - Distribute workers across multiple servers

### Vertical Scaling

1. **Increase Worker Resources**
   - More CPU cores for worker processes
   - More RAM for task processing
   - SSD storage for better I/O

2. **Optimize Task Performance**
   - Use database connection pooling
   - Implement task result caching
   - Minimize task payload size

This completes the comprehensive scheduler setup guide for the Payroll Management System.
