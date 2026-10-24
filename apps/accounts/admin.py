"""
Admin configuration for accounts app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Address


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin."""
    
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'avatar', 'address', 'city', 'postal_code')}),
        ('Role & Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'is_verified')}),
        ('Groups', {'fields': ('groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'phone', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Address admin."""
    
    list_display = ['full_name', 'user', 'address_type', 'city', 'district', 'is_default', 'is_inside_dhaka']
    list_filter = ['address_type', 'is_default', 'is_inside_dhaka', 'city', 'district']
    search_fields = ['full_name', 'phone', 'address_line1', 'city']
    raw_id_fields = ['user']
