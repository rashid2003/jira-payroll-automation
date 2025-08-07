"""
Django Admin configuration for payroll models.

Provides admin interfaces for managing PayrollPeriod and UserProfile models
with appropriate field configurations and filtering options.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import PayrollPeriod, UserProfile


class PayrollPeriodAdmin(admin.ModelAdmin):
    """
    Admin interface for PayrollPeriod model.
    """
    
    list_display = [
        'id', 
        'period_type', 
        'start_date', 
        'end_date', 
        'status', 
        'automation_enabled',
        'duration_days',
        'is_current',
        'created_at'
    ]
    
    list_filter = [
        'period_type',
        'status',
        'automation_enabled',
        'created_at',
    ]
    
    search_fields = [
        'description',
        'period_type',
        'status',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'is_active',
        'is_current',
        'duration_days',
    ]
    
    fieldsets = (
        ('Period Information', {
            'fields': (
                'id',
                'period_type',
                'start_date',
                'end_date',
                'status',
                'description',
            )
        }),
        ('Automation Settings', {
            'fields': (
                'automation_enabled',
                'automation_rule',
            ),
            'classes': ('collapse',),
        }),
        ('Computed Fields', {
            'fields': (
                'is_active',
                'is_current',
                'duration_days',
            ),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': (
                'meta',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    date_hierarchy = 'start_date'
    ordering = ['-start_date']
    
    def get_queryset(self, request):
        """
        Customize queryset based on user permissions.
        """
        qs = super().get_queryset(request)
        
        # If user is not finance or admin, they might have limited access
        if hasattr(request.user, 'userprofile'):
            profile = request.user.userprofile
            if not profile.is_finance_or_admin:
                # For non-finance/admin users, you might want to filter
                # or limit what they can see
                pass
        
        return qs


class UserProfileInline(admin.StackedInline):
    """
    Inline admin for UserProfile to be shown in User admin.
    """
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    
    fields = [
        'role',
        'department',
        'employee_id',
        'can_create_periods',
        'can_run_payroll',
        'can_view_all_periods',
    ]
    
    readonly_fields = []


class UserProfileAdmin(admin.ModelAdmin):
    """
    Standalone admin interface for UserProfile model.
    """
    
    list_display = [
        'user',
        'get_user_email',
        'role',
        'department',
        'employee_id',
        'can_create_periods',
        'can_run_payroll',
        'can_view_all_periods',
        'created_at',
    ]
    
    list_filter = [
        'role',
        'department',
        'can_create_periods',
        'can_run_payroll',
        'can_view_all_periods',
        'created_at',
    ]
    
    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email',
        'employee_id',
        'department',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': (
                'user',
                'employee_id',
                'department',
            )
        }),
        ('Role & Permissions', {
            'fields': (
                'role',
                'can_create_periods',
                'can_run_payroll',
                'can_view_all_periods',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def get_user_email(self, obj):
        """Get the email of the associated user."""
        return obj.user.email
    get_user_email.short_description = 'Email'
    get_user_email.admin_order_field = 'user__email'


class ExtendedUserAdmin(BaseUserAdmin):
    """
    Extended User admin that includes UserProfile inline.
    """
    inlines = (UserProfileInline,)
    
    def get_inline_instances(self, request, obj=None):
        """
        Only show the profile inline if the user object exists.
        """
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)


# Register the models
admin.site.register(PayrollPeriod, PayrollPeriodAdmin)
admin.site.register(UserProfile, UserProfileAdmin)

# Unregister the original User admin and register the extended one
admin.site.unregister(User)
admin.site.register(User, ExtendedUserAdmin)

# Customize admin site headers
admin.site.site_header = "Payroll System Administration"
admin.site.site_title = "Payroll Admin"
admin.site.index_title = "Welcome to Payroll System Admin"
