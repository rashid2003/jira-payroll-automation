"""
Custom permission classes for the payroll system.

These permissions enforce role-based access control ensuring only users
with appropriate roles can create/run payroll periods and access sensitive operations.
"""

from rest_framework.permissions import BasePermission
from .models import UserProfile


class IsFinanceOrAdmin(BasePermission):
    """
    Permission class that only allows access to users with Finance or Admin roles.
    """
    message = "Only Finance or Admin users can perform this action."
    
    def has_permission(self, request, view):
        """
        Check if the user has finance or admin role.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.userprofile
            return profile.is_finance_or_admin
        except UserProfile.DoesNotExist:
            # Create profile if it doesn't exist (should not happen due to signals)
            UserProfile.objects.create(user=request.user)
            return False


class CanCreatePayrollPeriods(BasePermission):
    """
    Permission class for creating payroll periods.
    Allows Finance, Admin, or users with explicit can_create_periods permission.
    """
    message = "You don't have permission to create payroll periods. Only Finance/Admin roles or users with explicit permissions can create periods."
    
    def has_permission(self, request, view):
        """
        Check if the user can create payroll periods.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.userprofile
            return profile.is_finance_or_admin or profile.can_create_periods
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=request.user)
            return False


class CanRunPayroll(BasePermission):
    """
    Permission class for running payroll operations.
    Allows Finance, Admin, or users with explicit can_run_payroll permission.
    """
    message = "You don't have permission to run payroll. Only Finance/Admin roles or users with explicit permissions can run payroll."
    
    def has_permission(self, request, view):
        """
        Check if the user can run payroll operations.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.userprofile
            return profile.is_finance_or_admin or profile.can_run_payroll
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=request.user)
            return False


class CanViewAllPeriods(BasePermission):
    """
    Permission class for viewing all payroll periods.
    Allows Finance, Admin, HR, or users with explicit can_view_all_periods permission.
    """
    message = "You don't have permission to view all payroll periods."
    
    def has_permission(self, request, view):
        """
        Check if the user can view all payroll periods.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.userprofile
            return (profile.is_finance_or_admin or 
                   profile.role == 'hr' or 
                   profile.can_view_all_periods)
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=request.user)
            return False


class PayrollPeriodPermissions(BasePermission):
    """
    Custom permission class for PayrollPeriod operations.
    Implements different permission levels based on the HTTP method.
    """
    
    def has_permission(self, request, view):
        """
        Check permissions based on the action being performed.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=request.user)
            return False
        
        # GET requests (list, retrieve) - allow if user can view all periods
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return (profile.is_finance_or_admin or 
                   profile.role == 'hr' or 
                   profile.can_view_all_periods)
        
        # POST requests (create) - only finance/admin or explicit permission
        elif request.method == 'POST':
            return profile.is_finance_or_admin or profile.can_create_periods
        
        # PUT, PATCH, DELETE requests (update, destroy) - only finance/admin
        elif request.method in ['PUT', 'PATCH', 'DELETE']:
            return profile.is_finance_or_admin
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Check object-level permissions for specific payroll periods.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            return False
        
        # Finance and Admin can access any object
        if profile.is_finance_or_admin:
            return True
        
        # For GET requests, check if user can view all periods
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return profile.role == 'hr' or profile.can_view_all_periods
        
        # For modifications, only finance/admin allowed
        return False


class IsOwnerOrFinanceOrAdmin(BasePermission):
    """
    Permission class that allows access to owners of an object, or Finance/Admin users.
    Useful for user profile management.
    """
    message = "You can only access your own profile unless you have Finance or Admin role."
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user is the owner of the object or has finance/admin role.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user owns the object (assuming obj has a user field)
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        
        # Check if user has finance or admin role
        try:
            profile = request.user.userprofile
            return profile.is_finance_or_admin
        except UserProfile.DoesNotExist:
            return False


# Permission combination classes for common use cases
class FinanceAdminOrReadOnly(BasePermission):
    """
    Permission class that allows read-only access to authenticated users,
    but write access only to Finance or Admin users.
    """
    
    def has_permission(self, request, view):
        """
        Allow read permissions to authenticated users,
        write permissions to Finance/Admin only.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Read permissions for authenticated users
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # Write permissions only for Finance/Admin
        try:
            profile = request.user.userprofile
            return profile.is_finance_or_admin
        except UserProfile.DoesNotExist:
            return False
