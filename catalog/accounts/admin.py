from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import University, Role

User = get_user_model()


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'role_type', 'university')
    list_filter = ('role_type', 'university')
    search_fields = ('name',)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    # Disable SQL-based M2M widgets that trigger unhashable errors in Mongo
    filter_horizontal = ()
    filter_vertical = ()

    list_display = ('email', 'university', 'role', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'university', 'role')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    # Form layout when editing an existing user
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Tenant & Role', {'fields': ('university', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    # Form layout when creating a new user in admin
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'password1',
                'password2',
                'university',
                'role',
                'is_staff',
                'is_superuser',
                'is_active',
            ),
        }),
    )