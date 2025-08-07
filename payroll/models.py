from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class BaseModel(models.Model):
    """
    Base model with common fields for all models
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class PayrollPeriod(BaseModel):
    """
    Model representing a payroll period with automation capabilities
    """
    
    # Period type choices
    PERIOD_TYPE_CHOICES = [
        ('monthly', 'Monthly'),
        ('bi_weekly', 'Bi-weekly'),
        ('weekly', 'Weekly'),
        ('custom', 'Custom'),
    ]
    
    # Status choices
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Core date fields
    start_date = models.DateField(
        help_text="Start date of the payroll period"
    )
    end_date = models.DateField(
        help_text="End date of the payroll period"
    )
    
    # Period configuration
    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_TYPE_CHOICES,
        default='monthly',
        help_text="Type of payroll period"
    )
    
    # Automation settings
    automation_enabled = models.BooleanField(
        default=False,
        help_text="Whether automation is enabled for this period"
    )
    automation_rule = models.JSONField(
        blank=True,
        null=True,
        help_text="Automation rules in JSON format. Examples: {'cron': '0 0 25 * *'} for monthly on 25th, or {'days_before_end': 3} for 3 days before end"
    )
    
    # Status and metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Current status of the payroll period"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description or notes for this payroll period"
    )
    
    # Additional metadata
    meta = models.JSONField(
        blank=True,
        null=True,
        help_text="Additional metadata stored as JSON"
    )
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = "Payroll Period"
        verbose_name_plural = "Payroll Periods"
        
        # Ensure no overlapping periods for the same type
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='payroll_period_end_after_start'
            )
        ]
    
    def __str__(self):
        return f"{self.get_period_type_display()} - {self.start_date} to {self.end_date}"
    
    def clean(self):
        """
        Validate the model fields including date overlaps and period uniqueness
        """
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({
                    'end_date': 'End date must be after start date.'
                })
            
            # Check for date overlaps with existing periods
            overlapping_periods = PayrollPeriod.objects.filter(
                models.Q(start_date__lte=self.end_date) &
                models.Q(end_date__gte=self.start_date) &
                models.Q(period_type=self.period_type)
            )
            
            # Exclude current instance if updating
            if self.pk:
                overlapping_periods = overlapping_periods.exclude(pk=self.pk)
            
            if overlapping_periods.exists():
                overlapping_period = overlapping_periods.first()
                raise ValidationError({
                    'start_date': f'This period overlaps with existing {self.get_period_type_display()} period '
                                f'({overlapping_period.start_date} to {overlapping_period.end_date}).'
                })
            
            # Check for exact duplicate periods (same dates and type)
            duplicate_periods = PayrollPeriod.objects.filter(
                start_date=self.start_date,
                end_date=self.end_date,
                period_type=self.period_type
            )
            
            # Exclude current instance if updating
            if self.pk:
                duplicate_periods = duplicate_periods.exclude(pk=self.pk)
            
            if duplicate_periods.exists():
                raise ValidationError({
                    'start_date': f'A {self.get_period_type_display()} period with these exact dates already exists.'
                })
        
        # Validate automation rule format if provided
        if self.automation_rule:
            if not isinstance(self.automation_rule, dict):
                raise ValidationError({
                    'automation_rule': 'Automation rule must be a valid JSON object.'
                })
            
            # Check for valid automation rule keys
            valid_keys = {'cron', 'days_before_end', 'run_on_date'}
            if not any(key in self.automation_rule for key in valid_keys):
                raise ValidationError({
                    'automation_rule': f'Automation rule must contain at least one of: {", ".join(valid_keys)}'
                })
    
    def save(self, *args, **kwargs):
        """
        Override save to run clean validation
        """
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """
        Check if the payroll period is currently active
        """
        return self.status == 'active'
    
    @property
    def is_current(self):
        """
        Check if the current date falls within this payroll period
        """
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date
    
    @property
    def duration_days(self):
        """
        Calculate the duration of the payroll period in days
        """
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
    
    def is_due_for_automation(self):
        """
        Check if this payroll period is due for automated processing.
        
        Returns True if:
        1. Automation is enabled
        2. Status is active
        3. Current date matches automation rule criteria
        """
        if not self.automation_enabled or self.status != 'active':
            return False
            
        if not self.automation_rule:
            return False
            
        today = timezone.now().date()
        
        # Check for specific run date
        if 'run_on_date' in self.automation_rule:
            try:
                from datetime import datetime
                run_date = datetime.strptime(
                    self.automation_rule['run_on_date'], '%Y-%m-%d'
                ).date()
                return today == run_date
            except (ValueError, KeyError):
                pass
        
        # Check for days before end date
        if 'days_before_end' in self.automation_rule:
            try:
                days_before = int(self.automation_rule['days_before_end'])
                target_date = self.end_date - timezone.timedelta(days=days_before)
                return today == target_date
            except (ValueError, KeyError, TypeError):
                pass
        
        # For cron expressions, we'll rely on Celery Beat scheduling
        # The cron check is handled at the task scheduler level
        if 'cron' in self.automation_rule:
            # This method is called from the scheduled task,
            # so if we reach here with a cron rule, it means it's time to run
            return True
            
        return False


class UserProfile(BaseModel):
    """
    User profile model to extend the default Django User model with role-based permissions.
    """
    
    # Role choices for payroll system
    ROLE_CHOICES = [
        ('employee', 'Employee'),
        ('manager', 'Manager'),
        ('hr', 'HR'),
        ('finance', 'Finance'),
        ('admin', 'Admin'),
    ]
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        help_text="Associated Django user account"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='employee',
        help_text="User role in the payroll system"
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Department or team the user belongs to"
    )
    employee_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        help_text="Unique employee identifier"
    )
    
    # Permission-related fields
    can_create_periods = models.BooleanField(
        default=False,
        help_text="Whether user can create new payroll periods"
    )
    can_run_payroll = models.BooleanField(
        default=False,
        help_text="Whether user can trigger payroll runs"
    )
    can_view_all_periods = models.BooleanField(
        default=False,
        help_text="Whether user can view all payroll periods"
    )
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ['user__last_name', 'user__first_name']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()}"
    
    @property
    def is_finance_or_admin(self):
        """
        Check if user has finance or admin role
        """
        return self.role in ['finance', 'admin']
    
    @property
    def has_payroll_permissions(self):
        """
        Check if user has permissions to create periods or run payroll
        """
        return self.is_finance_or_admin or self.can_create_periods or self.can_run_payroll
    
    def save(self, *args, **kwargs):
        """
        Override save to automatically set permissions based on role
        """
        # Automatically grant permissions for finance and admin roles
        if self.role in ['finance', 'admin']:
            self.can_create_periods = True
            self.can_run_payroll = True
            self.can_view_all_periods = True
        elif self.role == 'hr':
            self.can_view_all_periods = True
        
        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Signal to automatically create or update UserProfile when User is created/updated
    """
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # Update existing profile if it exists
        try:
            profile = instance.userprofile
            profile.save()  # This will trigger the role-based permission updates
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=instance)
