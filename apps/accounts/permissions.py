"""
Custom permissions for accounts app.
"""
from rest_framework import permissions


class IsSuperAdmin(permissions.BasePermission):
    """Permission check for super admin users."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'super_admin'


class IsStaffUser(permissions.BasePermission):
    """Permission check for staff users (seller, accountant, super_admin)."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['seller', 'accountant', 'super_admin']


class IsSeller(permissions.BasePermission):
    """Permission check for seller users."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['seller', 'super_admin']


class IsAccountant(permissions.BasePermission):
    """Permission check for accountant users."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['accountant', 'super_admin']


class IsSellerOrAccountant(permissions.BasePermission):
    """Permission check for seller or accountant users."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['seller', 'accountant', 'super_admin']
