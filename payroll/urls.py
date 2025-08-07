"""
URL configuration for payroll app.

This module defines URL patterns for payroll period management:
- CRUD operations for payroll periods
- Payroll run functionality
- Period summary and reporting
- CSV import/export operations
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import payroll_period_views

# Create router for ViewSet-based views
router = DefaultRouter()
router.register(r'periods', payroll_period_views.PayrollPeriodViewSet, basename='payrollperiod')

# Define app-specific URL patterns
app_name = 'payroll'

urlpatterns = [
    # Include router URLs for basic CRUD operations
    # This provides:
    # - GET    /periods/                     -> list (index)
    # - POST   /periods/                     -> create
    # - GET    /periods/<int:id>/            -> retrieve
    # - PUT    /periods/<int:id>/            -> update
    # - PATCH  /periods/<int:id>/            -> partial_update
    # - DELETE /periods/<int:id>/            -> destroy
    # - GET    /periods/export-csv/          -> export_csv
    # - POST   /periods/import-csv/          -> import_csv
    path('', include(router.urls)),
    
    # Additional custom endpoints for specific operations
    path('periods/<int:period_id>/run/', payroll_period_views.PayrollRunAPIView.as_view(), name='payroll-run'),
    path('periods/<int:period_id>/summary/', payroll_period_views.SummaryAPIView.as_view(), name='period-summary'),
]
