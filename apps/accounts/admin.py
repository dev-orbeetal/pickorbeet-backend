"""
Admin configuration for accounts app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import AuthSession, LoginEvent, SecurityCode, User, Address, BdDivision, BdDistrict, BdPostOffice


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
        ('Security', {'fields': ('two_factor_enabled', 'recovery_email', 'recovery_email_verified')}),
        ('Groups', {'fields': ('groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'phone', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(AuthSession)
class AuthSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_name', 'platform', 'ip_address', 'last_seen', 'revoked_at']
    list_filter = ['platform', 'revoked_at']
    search_fields = ['user__email', 'device_name', 'device_id', 'ip_address']
    raw_id_fields = ['user']


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ['email', 'method', 'success', 'device_name', 'ip_address', 'created_at']
    list_filter = ['method', 'success', 'platform']
    search_fields = ['email', 'device_name', 'ip_address']
    raw_id_fields = ['user']


@admin.register(SecurityCode)
class SecurityCodeAdmin(admin.ModelAdmin):
    list_display = ['user', 'purpose', 'created_at', 'expires_at', 'used_at', 'attempts']
    list_filter = ['purpose']
    search_fields = ['user__email', 'target_email']
    raw_id_fields = ['user']


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Address admin."""
    
    list_display = ['full_name', 'user', 'address_type', 'division', 'city', 'district', 'is_default', 'is_inside_dhaka']
    list_filter = ['address_type', 'is_default', 'is_inside_dhaka', 'division', 'district']
    search_fields = ['full_name', 'phone', 'address_line1', 'city', 'division', 'district']
    raw_id_fields = ['user']


@admin.register(BdDivision)
class BdDivisionAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'display_order']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(BdDistrict)
class BdDistrictAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'division']
    list_filter = ['division']
    search_fields = ['name', 'slug']
    raw_id_fields = ['division']


@admin.register(BdPostOffice)
class BdPostOfficeAdmin(admin.ModelAdmin):
    list_display = ['name', 'postal_code', 'district']
    list_filter = ['district__division']
    search_fields = ['name', 'postal_code', 'district__name']
    raw_id_fields = ['district']
