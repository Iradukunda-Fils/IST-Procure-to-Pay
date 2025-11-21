from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin interface for the custom User model.
    """
    
    # Fields to display in the user list
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    
    # Add role field to the user form
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role Information', {
            'fields': ('role',),
            'description': 'User role determines access permissions in the procurement system.'
        }),
    )
    
    # Add role field to the add user form
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role Information', {
            'fields': ('role',),
        }),
    )
