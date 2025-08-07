"""
PayrollPeriod Views Module

This module contains all API views for payroll period management:
- PayrollPeriodViewSet: Full CRUD operations for payroll periods
- SummaryAPIView: GET /payroll/periods/{id}/summary for aggregated data
- PayrollRunAPIView: POST /payroll/periods/{id}/run to trigger payroll processing
- CSV export/import endpoints for data management
"""

import csv
import io
import logging
from typing import Any, Dict

from django.db.models import QuerySet, Sum, Count, Avg, F, Q
from django.http import HttpResponse, Http404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated

from ..models import PayrollPeriod
from ..serializers.payroll_period import (
    PayrollPeriodSerializer,
    PayrollPeriodSummarySerializer,
    PayrollRunSerializer
)
from ..services.payroll_processor import PayrollProcessor, PayrollProcessorError
from ..permissions import (
    PayrollPeriodPermissions,
    CanRunPayroll,
    CanViewAllPeriods,
    IsFinanceOrAdmin
)

logger = logging.getLogger(__name__)


class PayrollPeriodViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet for PayrollPeriod CRUD operations.
    
    Provides:
    - list: GET /payroll/periods/ - List all payroll periods
    - create: POST /payroll/periods/ - Create new payroll period
    - retrieve: GET /payroll/periods/{id}/ - Get specific payroll period
    - update: PUT /payroll/periods/{id}/ - Update payroll period
    - partial_update: PATCH /payroll/periods/{id}/ - Partially update payroll period
    - destroy: DELETE /payroll/periods/{id}/ - Delete payroll period
    - export_csv: GET /payroll/periods/export_csv/ - Export periods to CSV
    - import_csv: POST /payroll/periods/import_csv/ - Import periods from CSV
    
    Permissions:
    - List/Retrieve: Finance, Admin, HR, or users with can_view_all_periods
    - Create: Finance, Admin, or users with can_create_periods
    - Update/Delete: Finance or Admin only
    - Export/Import: Finance or Admin only
    """
    
    queryset = PayrollPeriod.objects.all()
    serializer_class = PayrollPeriodSerializer
    permission_classes = [PayrollPeriodPermissions]
    
    def get_queryset(self) -> QuerySet[PayrollPeriod]:
        """
        Optionally filter the queryset based on query parameters.
        """
        queryset = PayrollPeriod.objects.all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by period type
        period_type = self.request.query_params.get('period_type', None)
        if period_type:
            queryset = queryset.filter(period_type=period_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)
        
        # Filter active periods only
        active_only = self.request.query_params.get('active_only', None)
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(status='active')
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer) -> None:
        """
        Custom create logic if needed.
        """
        logger.info(f"Creating new payroll period: {serializer.validated_data}")
        serializer.save()
    
    def perform_update(self, serializer) -> None:
        """
        Custom update logic if needed.
        """
        logger.info(f"Updating payroll period {serializer.instance.id}")
        serializer.save()
    
    def perform_destroy(self, instance) -> None:
        """
        Custom delete logic - only allow deletion if period is not completed.
        """
        if instance.status == 'completed':
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                "Cannot delete a completed payroll period. "
                "Consider cancelling it instead."
            )
        
        logger.info(f"Deleting payroll period {instance.id}")
        instance.delete()
    
    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request: Request) -> HttpResponse:
        """
        Export payroll periods to CSV format.
        
        GET /payroll/periods/export-csv/
        
        Query parameters:
        - status: Filter by status
        - period_type: Filter by period type
        - start_date: Filter by start date (YYYY-MM-DD)
        - end_date: Filter by end date (YYYY-MM-DD)
        """
        try:
            # Get filtered queryset
            queryset = self.get_queryset()
            
            # Create CSV response
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="payroll_periods_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            writer = csv.writer(response)
            
            # Write header
            writer.writerow([
                'ID',
                'Start Date',
                'End Date',
                'Period Type',
                'Status',
                'Automation Enabled',
                'Automation Rule',
                'Description',
                'Created At',
                'Updated At',
                'Duration Days',
                'Is Active',
                'Is Current'
            ])
            
            # Write data rows
            for period in queryset:
                writer.writerow([
                    period.id,
                    period.start_date.strftime('%Y-%m-%d'),
                    period.end_date.strftime('%Y-%m-%d'),
                    period.get_period_type_display(),
                    period.get_status_display(),
                    'Yes' if period.automation_enabled else 'No',
                    str(period.automation_rule) if period.automation_rule else '',
                    period.description or '',
                    period.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    period.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                    period.duration_days,
                    'Yes' if period.is_active else 'No',
                    'Yes' if period.is_current else 'No',
                ])
            
            logger.info(f"Exported {queryset.count()} payroll periods to CSV")
            return response
            
        except Exception as e:
            logger.error(f"CSV export failed: {str(e)}")
            return Response(
                {'error': f'CSV export failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='import-csv', parser_classes=[MultiPartParser, FormParser])
    def import_csv(self, request: Request) -> Response:
        """
        Import payroll periods from CSV format.
        
        POST /payroll/periods/import-csv/
        
        Expected CSV format:
        - Start Date (YYYY-MM-DD)
        - End Date (YYYY-MM-DD)
        - Period Type (monthly/bi_weekly/weekly/custom)
        - Status (active/completed/cancelled)
        - Automation Enabled (Yes/No or True/False)
        - Description (optional)
        """
        try:
            csv_file = request.FILES.get('file')
            if not csv_file:
                return Response(
                    {'error': 'No CSV file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not csv_file.name.endswith('.csv'):
                return Response(
                    {'error': 'File must be a CSV format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Read and process CSV
            file_data = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(file_data))
            
            created_count = 0
            updated_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=1):
                try:
                    # Map CSV columns to model fields
                    period_data = {
                        'start_date': row.get('Start Date', '').strip(),
                        'end_date': row.get('End Date', '').strip(),
                        'period_type': self._map_period_type(row.get('Period Type', '').strip()),
                        'status': self._map_status(row.get('Status', '').strip()),
                        'automation_enabled': self._parse_boolean(row.get('Automation Enabled', '').strip()),
                        'description': row.get('Description', '').strip() or None,
                    }
                    
                    # Validate required fields
                    if not all([period_data['start_date'], period_data['end_date']]):
                        errors.append(f"Row {row_num}: Start Date and End Date are required")
                        continue
                    
                    # Check if period already exists (based on date range)
                    existing_period = PayrollPeriod.objects.filter(
                        start_date=period_data['start_date'],
                        end_date=period_data['end_date']
                    ).first()
                    
                    if existing_period:
                        # Update existing period
                        serializer = PayrollPeriodSerializer(existing_period, data=period_data, partial=True)
                        if serializer.is_valid():
                            serializer.save()
                            updated_count += 1
                        else:
                            errors.append(f"Row {row_num}: {serializer.errors}")
                    else:
                        # Create new period
                        serializer = PayrollPeriodSerializer(data=period_data)
                        if serializer.is_valid():
                            serializer.save()
                            created_count += 1
                        else:
                            errors.append(f"Row {row_num}: {serializer.errors}")
                            
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            result = {
                'message': f'Import completed. Created: {created_count}, Updated: {updated_count}',
                'created_count': created_count,
                'updated_count': updated_count,
                'error_count': len(errors),
                'errors': errors[:10] if errors else [],  # Limit errors shown
            }
            
            if errors and len(errors) > 10:
                result['errors'].append(f"... and {len(errors) - 10} more errors")
            
            logger.info(f"CSV import completed: {result['message']}")
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"CSV import failed: {str(e)}")
            return Response(
                {'error': f'CSV import failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _map_period_type(self, value: str) -> str:
        """Map CSV period type values to model choices."""
        mapping = {
            'monthly': 'monthly',
            'bi-weekly': 'bi_weekly',
            'bi_weekly': 'bi_weekly',
            'weekly': 'weekly',
            'custom': 'custom',
        }
        return mapping.get(value.lower(), 'monthly')
    
    def _map_status(self, value: str) -> str:
        """Map CSV status values to model choices."""
        mapping = {
            'active': 'active',
            'completed': 'completed',
            'cancelled': 'cancelled',
        }
        return mapping.get(value.lower(), 'active')
    
    def _parse_boolean(self, value: str) -> bool:
        """Parse CSV boolean values."""
        return value.lower() in ['yes', 'true', '1', 'on']


class SummaryAPIView(APIView):
    """
    API View for payroll period summary with aggregated totals.
    
    GET /payroll/periods/{id}/summary/
    
    Returns aggregated data for the specified payroll period including:
    - Basic period information
    - Total employees (placeholder - would be calculated from related models)
    - Total gross pay, deductions, net pay
    - Average pay amounts
    - Other relevant metrics
    
    Permissions: Finance, Admin, HR, or users with can_view_all_periods
    """
    
    permission_classes = [CanViewAllPeriods]
    
    def get(self, request: Request, period_id: int) -> Response:
        """
        Get summary data for a specific payroll period.
        """
        try:
            # Get the payroll period
            try:
                period = PayrollPeriod.objects.get(id=period_id)
            except PayrollPeriod.DoesNotExist:
                raise Http404("Payroll period not found")
            
            # In a real implementation, these aggregations would be based on
            # related models like PayrollPayment, Employee, etc.
            # For now, we'll use the summary serializer structure
            
            # Mock aggregated data - in production this would query related models
            aggregated_data = self._calculate_period_summary(period)
            
            # Attach aggregated data to the instance for serializer access
            period._aggregated_data = aggregated_data
            
            # Serialize the period with summary data
            serializer = PayrollPeriodSummarySerializer(period)
            
            logger.info(f"Retrieved summary for payroll period {period_id}")
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Http404:
            raise
        except Exception as e:
            logger.error(f"Failed to get summary for period {period_id}: {str(e)}")
            return Response(
                {'error': f'Failed to retrieve summary: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_period_summary(self, period: PayrollPeriod) -> Dict[str, Any]:
        """
        Calculate aggregated summary data for the payroll period.
        
        In a real implementation, this would query related models:
        - Employee records
        - PayrollPayment records
        - Deduction records
        - Tax records
        - etc.
        
        For now, returning mock data structure.
        """
        # This is where you would typically do something like:
        # payments = PayrollPayment.objects.filter(period=period)
        # totals = payments.aggregate(
        #     total_employees=Count('employee', distinct=True),
        #     total_gross_pay=Sum('gross_amount'),
        #     total_deductions=Sum('deductions_amount'),
        #     total_net_pay=Sum('net_amount'),
        #     average_gross_pay=Avg('gross_amount')
        # )
        
        # Mock data for demonstration
        mock_data = {
            'total_employees': 0,
            'total_gross_pay': '0.00',
            'total_deductions': '0.00',
            'total_net_pay': '0.00',
            'average_gross_pay': '0.00',
            # Additional summary fields
            'processed_at': None,
            'processing_status': 'pending',
            'payment_count': 0,
        }
        
        return mock_data


class PayrollRunAPIView(APIView):
    """
    API View for triggering payroll processing runs.
    
    POST /payroll/periods/{id}/run/
    
    Triggers the PayrollProcessor service to process payroll for the specified period.
    Accepts optional parameters to customize the payroll run.
    
    Permissions: Finance, Admin, or users with can_run_payroll permission
    """
    
    permission_classes = [CanRunPayroll]
    
    def post(self, request: Request, period_id: int) -> Response:
        """
        Trigger a payroll run for the specified period.
        """
        try:
            # Validate the period exists and is in a valid state
            try:
                period = PayrollPeriod.objects.get(id=period_id)
            except PayrollPeriod.DoesNotExist:
                raise Http404("Payroll period not found")
            
            # Prepare the payroll run data
            run_data = request.data.copy()
            run_data['period_id'] = period_id
            
            # Validate the run parameters
            serializer = PayrollRunSerializer(data=run_data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Invalid payroll run parameters', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            validated_data = serializer.validated_data
            
            # Initialize and run the payroll processor
            processor = PayrollProcessor()
            
            logger.info(f"Starting payroll run for period {period_id} with parameters: {validated_data}")
            
            # Execute the payroll run
            try:
                result = processor.run_payroll(period_id)
                
                # Enhanced result with run parameters
                enhanced_result = {
                    **result,
                    'run_parameters': {
                        'run_type': validated_data.get('run_type', 'full'),
                        'include_bonuses': validated_data.get('include_bonuses', True),
                        'include_overtime': validated_data.get('include_overtime', True),
                        'notification_emails': validated_data.get('notification_emails', []),
                        'notes': validated_data.get('notes', ''),
                    },
                    'period': {
                        'id': period.id,
                        'start_date': period.start_date.strftime('%Y-%m-%d'),
                        'end_date': period.end_date.strftime('%Y-%m-%d'),
                        'period_type': period.get_period_type_display(),
                    }
                }
                
                logger.info(f"Payroll run completed successfully for period {period_id}")
                return Response(enhanced_result, status=status.HTTP_200_OK)
                
            except PayrollProcessorError as e:
                logger.error(f"Payroll processing failed for period {period_id}: {str(e)}")
                return Response(
                    {
                        'error': 'Payroll processing failed',
                        'details': str(e),
                        'period_id': period_id
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
            
        except Http404:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during payroll run for period {period_id}: {str(e)}")
            return Response(
                {
                    'error': 'Unexpected error during payroll run',
                    'details': str(e),
                    'period_id': period_id
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
