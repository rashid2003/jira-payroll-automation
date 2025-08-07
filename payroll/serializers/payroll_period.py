from rest_framework import serializers
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from ..models import PayrollPeriod


class PayrollPeriodSerializer(serializers.ModelSerializer):
    """
    Full CRUD serializer for PayrollPeriod model.
    Handles all fields with proper validation.
    """
    
    # Read-only computed fields
    is_active = serializers.ReadOnlyField()
    is_current = serializers.ReadOnlyField()
    duration_days = serializers.ReadOnlyField()
    
    class Meta:
        model = PayrollPeriod
        fields = [
            'id',
            'start_date',
            'end_date',
            'period_type',
            'automation_enabled',
            'automation_rule',
            'status',
            'description',
            'meta',
            'created_at',
            'updated_at',
            # Computed fields
            'is_active',
            'is_current',
            'duration_days',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """
        Custom validation for the payroll period including overlap and uniqueness checks
        """
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        period_type = data.get('period_type', 'monthly')  # Default from model
        
        # Validate date range
        if start_date and end_date:
            if end_date < start_date:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date.'
                })
            
            # Check for date overlaps with existing periods
            from django.db.models import Q
            overlapping_periods = PayrollPeriod.objects.filter(
                Q(start_date__lte=end_date) &
                Q(end_date__gte=start_date) &
                Q(period_type=period_type)
            )
            
            # Exclude current instance if updating
            if self.instance:
                overlapping_periods = overlapping_periods.exclude(pk=self.instance.pk)
            
            if overlapping_periods.exists():
                overlapping_period = overlapping_periods.first()
                raise serializers.ValidationError({
                    'start_date': f'This period overlaps with existing {PayrollPeriod.PERIOD_TYPE_CHOICES[next(i for i, x in enumerate(PayrollPeriod.PERIOD_TYPE_CHOICES) if x[0] == period_type)][1]} period '
                                f'({overlapping_period.start_date} to {overlapping_period.end_date}).'
                })
            
            # Check for exact duplicate periods (same dates and type)
            duplicate_periods = PayrollPeriod.objects.filter(
                start_date=start_date,
                end_date=end_date,
                period_type=period_type
            )
            
            # Exclude current instance if updating
            if self.instance:
                duplicate_periods = duplicate_periods.exclude(pk=self.instance.pk)
            
            if duplicate_periods.exists():
                raise serializers.ValidationError({
                    'start_date': f'A {PayrollPeriod.PERIOD_TYPE_CHOICES[next(i for i, x in enumerate(PayrollPeriod.PERIOD_TYPE_CHOICES) if x[0] == period_type)][1]} period with these exact dates already exists.'
                })
        
        # Validate automation rule if provided
        automation_rule = data.get('automation_rule')
        if automation_rule:
            if not isinstance(automation_rule, dict):
                raise serializers.ValidationError({
                    'automation_rule': 'Automation rule must be a valid JSON object.'
                })
            
            # Check for valid automation rule keys
            valid_keys = {'cron', 'days_before_end', 'run_on_date'}
            if not any(key in automation_rule for key in valid_keys):
                raise serializers.ValidationError({
                    'automation_rule': f'Automation rule must contain at least one of: {", ".join(valid_keys)}'
                })
            
            # Validate specific automation rule formats
            if 'run_on_date' in automation_rule:
                from datetime import datetime
                try:
                    datetime.strptime(automation_rule['run_on_date'], '%Y-%m-%d')
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        'automation_rule': 'run_on_date must be in YYYY-MM-DD format'
                    })
            
            if 'days_before_end' in automation_rule:
                try:
                    days = int(automation_rule['days_before_end'])
                    if days < 0:
                        raise ValueError
                except (ValueError, TypeError):
                    raise serializers.ValidationError({
                        'automation_rule': 'days_before_end must be a non-negative integer'
                    })
        
        return data
    
    def validate_start_date(self, value):
        """
        Validate start date is not in the past for new periods
        """
        if not self.instance and value < timezone.now().date():
            raise serializers.ValidationError(
                "Start date cannot be in the past for new payroll periods."
            )
        return value


class PayrollPeriodSummarySerializer(serializers.ModelSerializer):
    """
    Read-only serializer for aggregated payroll period summaries.
    Provides essential information with computed totals.
    """
    
    # Computed read-only fields
    is_active = serializers.ReadOnlyField()
    is_current = serializers.ReadOnlyField()
    duration_days = serializers.ReadOnlyField()
    
    # Aggregated fields (these would be populated by the view)
    total_employees = serializers.IntegerField(read_only=True)
    total_gross_pay = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    total_deductions = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    total_net_pay = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    average_gross_pay = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    
    class Meta:
        model = PayrollPeriod
        fields = [
            'id',
            'start_date',
            'end_date',
            'period_type',
            'status',
            'description',
            'created_at',
            'updated_at',
            # Computed fields
            'is_active',
            'is_current',
            'duration_days',
            # Aggregated fields
            'total_employees',
            'total_gross_pay',
            'total_deductions',
            'total_net_pay',
            'average_gross_pay',
        ]
        read_only_fields = '__all__'  # All fields are read-only
    
    def to_representation(self, instance):
        """
        Add computed aggregated data to the representation
        """
        data = super().to_representation(instance)
        
        # In a real implementation, these would be computed from related models
        # For now, providing structure with default values
        if not hasattr(instance, '_aggregated_data'):
            data.update({
                'total_employees': 0,
                'total_gross_pay': '0.00',
                'total_deductions': '0.00',
                'total_net_pay': '0.00',
                'average_gross_pay': '0.00',
            })
        
        return data


class PayrollRunSerializer(serializers.Serializer):
    """
    Input serializer for triggering payroll runs.
    Takes a period_id and optional parameters to initiate payroll processing.
    """
    
    period_id = serializers.IntegerField(
        help_text="ID of the payroll period to run payroll for"
    )
    
    # Optional parameters for the payroll run
    run_type = serializers.ChoiceField(
        choices=[
            ('full', 'Full Run'),
            ('preview', 'Preview Only'),
            ('test', 'Test Run'),
        ],
        default='full',
        help_text="Type of payroll run to execute"
    )
    
    include_bonuses = serializers.BooleanField(
        default=True,
        help_text="Whether to include bonuses in the payroll run"
    )
    
    include_overtime = serializers.BooleanField(
        default=True,
        help_text="Whether to include overtime calculations"
    )
    
    notification_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True,
        help_text="List of email addresses to notify when run completes"
    )
    
    notes = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Optional notes for this payroll run"
    )
    
    def validate_period_id(self, value):
        """
        Validate that the period exists and is in a valid state for running payroll
        """
        try:
            period = PayrollPeriod.objects.get(id=value)
        except PayrollPeriod.DoesNotExist:
            raise serializers.ValidationError(
                f"Payroll period with ID {value} does not exist."
            )
        
        if period.status != 'active':
            raise serializers.ValidationError(
                f"Cannot run payroll for period with status '{period.status}'. "
                "Period must be active."
            )
        
        # Check if period dates are valid
        current_date = timezone.now().date()
        if period.end_date < current_date:
            raise serializers.ValidationError(
                "Cannot run payroll for a period that has already ended."
            )
        
        return value
    
    def validate(self, data):
        """
        Cross-field validation
        """
        # Additional validation can be added here
        # For example, checking if a payroll run is already in progress
        
        return data
    
    def create(self, validated_data):
        """
        This serializer is for input only and doesn't create model instances.
        The actual payroll run would be handled by the view/service layer.
        """
        return validated_data
