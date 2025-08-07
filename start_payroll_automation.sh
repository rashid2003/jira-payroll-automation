#!/bin/bash

# Payroll Automation Startup Script
# This script helps start all necessary services for the payroll automation system

set -e  # Exit on any error

echo "🚀 Starting Payroll Automation System..."

# Check if Redis is running
echo "📡 Checking Redis connection..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Please start Redis first:"
    echo "   - Ubuntu/Debian: sudo systemctl start redis"
    echo "   - macOS: brew services start redis"
    echo "   - Docker: docker run -d --name redis -p 6379:6379 redis:alpine"
    exit 1
fi
echo "✅ Redis is running"

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: No virtual environment detected. Consider using a virtual environment."
fi

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run Django migrations
echo "🔄 Running Django migrations..."
python manage.py migrate

# Check Django configuration
echo "🧪 Testing Django configuration..."
python manage.py check

# Test Redis cache connection
echo "🧪 Testing Redis cache connection..."
python -c "from django.core.cache import cache; cache.set('test', 'ok'); print('✅ Cache working')"

# Create log directory
mkdir -p logs

echo ""
echo "🎯 System is ready! To start the services:"
echo ""
echo "Terminal 1 - Start Celery Worker:"
echo "  celery -A payroll_project worker --loglevel=info --logfile=logs/celery_worker.log"
echo ""
echo "Terminal 2 - Start Celery Beat Scheduler:"
echo "  celery -A payroll_project beat --loglevel=info --logfile=logs/celery_beat.log"
echo ""
echo "Terminal 3 - Start Django Development Server (optional):"
echo "  python manage.py runserver"
echo ""
echo "📋 Management Commands:"
echo "  # Test automation manually"
echo "  python manage.py run_payroll_automation"
echo ""
echo "  # Process specific period"
echo "  python manage.py run_payroll_automation --period-id 1"
echo ""
echo "  # Force process regardless of rules"
echo "  python manage.py run_payroll_automation --period-id 1 --force"
echo ""
echo "  # Run tests"
echo "  python manage.py test payroll.tests_automation"
echo ""
echo "📖 See PAYROLL_AUTOMATION.md for detailed documentation"
echo ""
echo "🎉 Ready to automate payroll processing!"
