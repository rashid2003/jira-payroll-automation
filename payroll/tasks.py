"""
Celery tasks for payroll automation.
"""

import logging
from typing import Dict, List
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from .models import PayrollPeriod
from .services.payroll_processor import PayrollProcessor, PayrollProcessorError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def auto_run_payroll():
    """
    Automated payroll processing task.
    
    This task:
    1. Queries PayrollPeriod objects with automation_enabled=True
    2. Checks if they are due for processing based on automation rules
    3. Calls PayrollProcessor.run_payroll() for eligible periods
    4. Ensures idempotency by checking status before processing
    
    Returns:
        Dict with summary of processed periods
    """
    logger.info("Starting automated payroll processing")
    
    processed_periods = []
    skipped_periods = []
    failed_periods = []
    
    try:
        # Query periods with automation enabled
        eligible_periods = PayrollPeriod.objects.filter(
            automation_enabled=True,
            status='active'  # Only process active periods
        ).select_related()
        
        logger.info(f"Found {eligible_periods.count()} periods with automation enabled")
        
        for period in eligible_periods:
            try:
                # Check if this period is due for processing
                if not period.is_due_for_automation():
                    logger.debug(f"Period {period.id} is not due for automation yet")
                    continue
                
                # Ensure idempotency - check if already being processed
                cache_key = f"payroll_processing_{period.id}"
                if cache.get(cache_key):
                    logger.warning(f"Period {period.id} is already being processed, skipping")
                    skipped_periods.append({
                        'period_id': period.id,
                        'reason': 'Already processing'
                    })
                    continue
                
                # Set processing lock with 1 hour expiration
                cache.set(cache_key, True, timeout=3600)
                
                try:
                    # Process the payroll
                    result = process_payroll_period(period.id)
                    processed_periods.append({
                        'period_id': period.id,
                        'result': result
                    })
                    logger.info(f"Successfully processed period {period.id}")
                    
                except Exception as e:
                    logger.error(f"Failed to process period {period.id}: {str(e)}")
                    failed_periods.append({
                        'period_id': period.id,
                        'error': str(e)
                    })
                    
                finally:
                    # Always release the processing lock
                    cache.delete(cache_key)
                    
            except Exception as e:
                logger.error(f"Error evaluating period {period.id}: {str(e)}")
                failed_periods.append({
                    'period_id': period.id,
                    'error': f"Evaluation error: {str(e)}"
                })
        
        summary = {
            'timestamp': timezone.now().isoformat(),
            'processed_count': len(processed_periods),
            'skipped_count': len(skipped_periods),
            'failed_count': len(failed_periods),
            'processed_periods': processed_periods,
            'skipped_periods': skipped_periods,
            'failed_periods': failed_periods
        }
        
        logger.info(f"Automated payroll processing completed. Summary: {summary}")
        return summary
        
    except Exception as e:
        logger.error(f"Critical error in automated payroll processing: {str(e)}")
        raise


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def process_payroll_period(period_id: int) -> Dict:
    """
    Process payroll for a specific period.
    
    This is a separate task to allow for individual retry logic
    and better error handling for each period.
    
    Args:
        period_id: ID of the PayrollPeriod to process
        
    Returns:
        Dict containing processing results
        
    Raises:
        PayrollProcessorError: If processing fails
    """
    logger.info(f"Processing payroll for period {period_id}")
    
    try:
        # Double-check the period status for idempotency
        try:
            period = PayrollPeriod.objects.get(id=period_id)
        except PayrollPeriod.DoesNotExist:
            raise PayrollProcessorError(f"PayrollPeriod {period_id} not found")
        
        # Ensure idempotency - check if already completed
        if period.status == 'completed':
            logger.warning(f"Period {period_id} is already completed, skipping")
            return {
                'period_id': period_id,
                'status': 'already_completed',
                'message': 'Period was already processed'
            }
        
        if period.status != 'active':
            raise PayrollProcessorError(
                f"Period {period_id} has status '{period.status}', cannot process"
            )
        
        # Create processor instance and run payroll
        processor = PayrollProcessor()
        result = processor.run_payroll(period_id)
        
        logger.info(f"Successfully completed payroll processing for period {period_id}")
        return {
            'period_id': period_id,
            'status': 'completed',
            'result': result
        }
        
    except PayrollProcessorError as e:
        logger.error(f"Payroll processing error for period {period_id}: {str(e)}")
        # Don't retry on PayrollProcessorError as these are usually business logic issues
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error processing period {period_id}: {str(e)}")
        # Retry on unexpected errors
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying payroll processing for period {period_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=e, countdown=self.default_retry_delay)
        else:
            logger.error(f"Max retries exceeded for period {period_id}")
            raise


@shared_task
def cleanup_old_payroll_locks():
    """
    Cleanup task to remove stale processing locks.
    
    This task should run periodically to clean up any locks that
    weren't properly released due to worker crashes or other issues.
    """
    logger.info("Cleaning up old payroll processing locks")
    
    # Note: This is a simple implementation. In production, you might want
    # to use Redis-specific commands to find and delete keys by pattern
    # For now, we rely on the cache timeout to handle cleanup
    
    return {"status": "completed", "message": "Cleanup relies on cache timeout"}


# Additional utility tasks for manual operations

@shared_task
def run_payroll_for_period(period_id: int, force: bool = False) -> Dict:
    """
    Manual task to run payroll for a specific period.
    
    Args:
        period_id: ID of the PayrollPeriod to process
        force: If True, bypass automation rules and status checks
        
    Returns:
        Dict containing processing results
    """
    logger.info(f"Manual payroll processing requested for period {period_id}, force={force}")
    
    if force:
        # Force processing regardless of automation rules
        return process_payroll_period(period_id)
    else:
        # Check automation rules like the automated task does
        try:
            period = PayrollPeriod.objects.get(id=period_id)
            if period.is_due_for_automation() or period.automation_enabled:
                return process_payroll_period(period_id)
            else:
                return {
                    'period_id': period_id,
                    'status': 'skipped',
                    'message': 'Period is not due for automation'
                }
        except PayrollPeriod.DoesNotExist:
            return {
                'period_id': period_id,
                'status': 'error',
                'message': 'Period not found'
            }
