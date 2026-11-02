# Permission System Implementation Plan

## Overview

This document outlines the implementation of a hierarchical permission system for the multi-tenant catalog application. The architecture follows:

- **Flat storage** with hierarchy metadata for validation
- **Explicit permissions** assigned to roles via checkboxes
- **Subset enforcement** preventing privilege escalation
- **Defense in depth** across middleware, decorators, and admin hooks

### Hierarchy Levels

| Level | Role Type | Authority |
|-------|-----------|-----------|
| 1 | Platform Superuser | Unrestricted (implicit) |
| 2 | Campus Admin (University Admin) | Full university control |
| 3 | School Admin | School-scoped management |
| 4 | Campus Viewer | Read-only access |

---

## Change 1: Permission Vocabulary & Role Model Updates

**File:** `accounts/models.py`  
**Area:** Top of file (constants) and `Role` class

**Instructions:** Define `PERMISSION_CHOICES`, `DEFAULT_ROLE_PERMISSIONS`, update `RoleType` choices to include `SCHOOL_ADMIN`, add `level` hierarchy field, and add validation in `Role.clean()`.

```python
<<<< SEARCH
class Role(models.Model):
    """
    Custom role model replacing Django's SQL-based Group model.
    Stores customizable permissions as a list of strings in JSONField.
    """
    class RoleType(models.TextChoices):
        UNIVERSITY_ADMIN = 'university_admin', 'University Admin'
        DEPARTMENT_ADMIN = 'department_admin', 'Department Admin'
        CAMPUS_VIEWER = 'campus_viewer', 'Campus Viewer'

    name = models.CharField(max_length=100)
    role_type = models.CharField(
        max_length=30,
        choices=RoleType.choices,
        default=RoleType.CAMPUS_VIEWER
    )
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='roles',
        null=True,
        blank=True,
        help_text='Null for global default roles, or bound to a specific university'
    )
    # Permissions stored as list of strings, e.g. ["catalog.view", "catalog.add", "catalog.change"]
    permissions = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        db_table = 'roles'

    def __str__(self):
        if self.university:
            return f"{self.name} ({self.university.slug})"
        return self.name

    def has_permission(self, perm):
        return perm in self.permissions
>>>> REPLACE
PERMISSION_CHOICES = [
    # Catalog
    ('catalog.view', 'Catalog - View'),
    ('catalog.add', 'Catalog - Add'),
    ('catalog.edit', 'Catalog - Edit'),
    ('catalog.delete', 'Catalog - Delete'),
    # Users
    ('users.view', 'Users - View'),
    ('users.add', 'Users - Add'),
    ('users.edit', 'Users - Edit'),
    ('users.delete', 'Users - Delete'),
    ('users.assign_role', 'Users - Assign Role'),
    # Roles
    ('roles.view', 'Roles - View'),
    ('roles.add', 'Roles - Add'),
    ('roles.edit', 'Roles - Edit'),
    ('roles.delete', 'Roles - Delete'),
    # Schools
    ('schools.view', 'Schools - View'),
    ('schools.add', 'Schools - Add'),
    ('schools.edit', 'Schools - Edit'),
    ('schools.delete', 'Schools - Delete'),
]

ALL_PERMISSIONS = [code for code, _ in PERMISSION_CHOICES]

DEFAULT_ROLE_PERMISSIONS = {
    'university_admin': ALL_PERMISSIONS,
    'school_admin': [
        'catalog.view', 'catalog.add', 'catalog.edit',
        'users.view', 'schools.view'
    ],
    'campus_viewer': [
        'catalog.view', 'users.view', 'schools.view'
    ],
}


class Role(models.Model):
    """
    Custom role model replacing Django's SQL-based Group model.
    Stores customizable permissions as a list of strings in JSONField.
    Hierarchy level increases as authority decreases:
    Level 1: Platform Superuser (implicit)
    Level 2: Campus Admin (University Admin)
    Level 3: School Admin (Department/School Chair)
    Level 4: Campus Viewer / Read-only
    """
    class RoleType(models.TextChoices):
        UNIVERSITY_ADMIN = 'university_admin', 'University Admin'
        SCHOOL_ADMIN = 'school_admin', 'School Admin'
        CAMPUS_VIEWER = 'campus_viewer', 'Campus Viewer'

    name = models.CharField(max_length=100)
    role_type = models.CharField(
        max_length=30,
        choices=RoleType.choices,
        default=RoleType.CAMPUS_VIEWER
    )
    level = models.PositiveSmallIntegerField(
        default=4,
        help_text='Hierarchy level (2=Campus Admin, 3=School Admin, 4=Viewer). Higher number = less power.'
    )
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='roles',
        null=True,
        blank=True,
        help_text='Null for global default roles, or bound to a specific university'
    )
    permissions = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        db_table = 'roles'

    def __str__(self):
        if self.university:
            return f"{self.name} ({self.university.slug})"
        return self.name

    def clean(self):
        super().clean()
        # Validate that all assigned permissions exist in the platform vocabulary
        invalid_perms = [p for p in self.permissions if p not in ALL_PERMISSIONS]
        if invalid_perms:
            raise ValidationError({
                'permissions': f"Invalid permissions specified: {', '.join(invalid_perms)}"
            })

    def has_permission(self, perm):
        return perm in self.permissions
>>>>
```

---

## Change 2: School Model & User Updates

**File:** `accounts/models.py`  
**Area:** New `School` model and `User` model updates

**Instructions:** Add the `School` model scoped to University. Update `User` with single `school` FK. Enhance `has_perm()` and `has_module_perms()`.

```python
<<<< SEARCH
class User(AbstractBaseUser):
    """
    Custom user model using AbstractBaseUser.
    Avoids Django's default groups and permissions M2M tables.
    """
    email = models.EmailField(unique=True, blank=False, null=False)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    # Multi-tenant scoping
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
        help_text='Required for non-superuser accounts'
    )
    
    # Custom Role link
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    objects = CustomUserManager()

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'users'
        indexes = [
            models.Index(fields=['university', 'role']),
        ]

    def __str__(self):
        if self.university:
            return f'{self.email} ({self.university.slug})'
        return f'{self.email} (platform)'

    # Django-compatible permission methods
    def has_perm(self, perm, obj=None):
        if self.is_superuser:
            return True
        if self.role:
            return self.role.has_permission(perm)
        return False

    def has_module_perms(self, app_label):
        if self.is_superuser:
            return True
        if self.role:
            return any(p.startswith(f'{app_label}.') for p in self.role.permissions)
        return False
>>>> REPLACE
class School(models.Model):
    """
    Organizational unit within a university (e.g., School of Business, School of Engineering).
    Users belong to at most one school.
    """
    name = models.CharField(max_length=255)
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='schools'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'School'
        verbose_name_plural = 'Schools'
        db_table = 'schools'
        unique_together = ('name', 'university')

    def __str__(self):
        return f"{self.name} - {self.university.name}"


class User(AbstractBaseUser):
    """
    Custom user model for MongoDB using AbstractBaseUser.
    Avoids Django's default SQL-backed groups and permissions M2M tables.
    """
    email = models.EmailField(unique=True, blank=False, null=False)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    # Multi-tenant scoping
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
        help_text='Required for non-superuser accounts'
    )

    # Single school affiliation (Q8)
    school = models.ForeignKey(
        School,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text='Single school affiliation within their university'
    )
    
    # Custom Role link
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    objects = CustomUserManager()

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'users'
        indexes = [
            models.Index(fields=['university', 'role']),
            models.Index(fields=['university', 'school']),
        ]

    def __str__(self):
        if self.university:
            return f'{self.email} ({self.university.slug})'
        return f'{self.email} (platform)'

    # Django-compatible permission methods backed by Role
    def has_perm(self, perm, obj=None):
        if self.is_superuser:
            return True
        if self.role:
            return self.role.has_permission(perm)
        return False

    def has_module_perms(self, app_label):
        if self.is_superuser:
            return True
        if self.role:
            return any(
                p.startswith(f'{app_label}.') or p.split('.')[0] in ['catalog', 'users', 'roles', 'schools']
                for p in self.role.permissions
            )
        return False
>>>>
```

---

## Change 3: User School Validation

**File:** `accounts/models.py`  
**Area:** `User.clean()` method

**Instructions:** Validate that `user.school` belongs to the same university as `user.university`.

```python
<<<< SEARCH
        if self.is_staff and not self.is_superuser and not self.university:
            raise ValidationError({
                'university': 'Non-superuser staff must belong to a university.'
            })
>>>> REPLACE
        if self.is_staff and not self.is_superuser and not self.university:
            raise ValidationError({
                'university': 'Non-superuser staff must belong to a university.'
            })

        if self.school and self.university and self.school.university_id != self.university_id:
            raise ValidationError({
                'school': 'The assigned school must belong to the user's university.'
            })
>>>>
```

---

## Change 4: Permission Decorators (New File)

**File:** `accounts/decorators.py` (CREATE NEW FILE)  
**Area:** Custom view decorators for fine-grained permission enforcement

**Instructions:** Create `@permission_required` and `@role_level_required` decorators.

```python
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.conf import settings as s


def permission_required(perm):
    """
    Decorator for views that checks whether the user has a specific permission string.
    Works with custom Role.permissions JSONField.
    Superusers bypass all checks.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f"{s.LOGIN_URL}?next={request.path}")
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if request.user.role and request.user.role.has_permission(perm):
                return view_func(request, *args, **kwargs)

            raise PermissionDenied(f"You lack the required permission: {perm}")
        return _wrapped_view
    return decorator


def role_level_required(max_allowed_level):
    """
    Decorator checking if a user's role level is sufficient (numeric level <= max_allowed_level).
    Level 1: Superuser, Level 2: Campus Admin, Level 3: School Admin, Level 4: Viewer.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f"{s.LOGIN_URL}?next={request.path}")

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if request.user.role and request.user.role.level <= max_allowed_level:
                return view_func(request, *args, **kwargs)

            raise PermissionDenied("Your role level is insufficient for this action.")
        return _wrapped_view
    return decorator
```

---

## Change 5: Middleware Permission Gate

**File:** `accounts/middleware.py`  
**Area:** `AdminAccessMiddleware._enforce_admin_access`

**Instructions:** Add broad permission gate requiring at least one valid permission.

```python
<<<< SEARCH
        # Campus admin: scoped to their own university
        if request.user.is_staff and request.user.role and request.user.university:
            request.scoped_university = request.user.university
            return self.get_response(request)
>>>> REPLACE
        # Campus / School admin: scoped to their university and must hold active permissions
        if request.user.is_staff and request.user.role and request.user.university:
            # Broad permission gate: Role must contain at least one valid permission
            if not request.user.role.permissions:
                logger.warning(
                    "User %s denied admin access: assigned role '%s' has empty permissions",
                    request.user.email,
                    request.user.role.name,
                )
                return HttpResponseForbidden("Access denied. Your role has no active permissions.")

            request.scoped_university = request.user.university
            return self.get_response(request)
>>>>
```

---

## Change 6: RoleAdminForm with Checkbox Widget

**File:** `accounts/admin.py`  
**Area:** Top of file imports and new `RoleAdminForm` class

**Instructions:** Import constants, create form with `CheckboxSelectMultiple` widget, implement subset and hierarchy validation.

```python
<<<< SEARCH
from .models import University, Role
from django.db import models
from django import forms
>>>> REPLACE
from .models import University, Role, School, PERMISSION_CHOICES, DEFAULT_ROLE_PERMISSIONS
from django.db import models
from django import forms
from django.forms.widgets import CheckboxSelectMultiple


class RoleAdminForm(forms.ModelForm):
    """
    Form for Role creation/editing in Admin.
    Presents permissions as checkboxes and validates delegation constraints.
    """
    permissions = forms.MultipleChoiceField(
        choices=PERMISSION_CHOICES,
        widget=CheckboxSelectMultiple,
        required=False,
        help_text="Select permissions granted to this role."
    )

    class Meta:
        model = Role
        fields = ('name', 'role_type', 'level', 'university', 'permissions')

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)

        # Set default pre-checked permissions on creation if role_type is selected
        if not self.is_bound and not self.instance.pk:
            initial_role_type = self.initial.get('role_type', Role.RoleType.CAMPUS_VIEWER)
            self.initial['permissions'] = DEFAULT_ROLE_PERMISSIONS.get(initial_role_type, [])

    def clean(self):
        cleaned_data = super().clean()
        perms = cleaned_data.get('permissions', [])
        level = cleaned_data.get('level')

        # Superusers bypass subset / level restrictions
        if not self.request_user or self.request_user.is_superuser:
            return cleaned_data

        creator_role = self.request_user.role
        if not creator_role:
            raise forms.ValidationError("You do not have a role configured to delegate permissions.")

        # Hierarchy validation: Created role must have level > creator level (lower authority)
        if level is not None and level <= creator_role.level:
            raise forms.ValidationError(
                f"Hierarchy error: You cannot create or edit a role with level {level}. "
                f"It must be strictly lower authority (greater than level {creator_role.level})."
            )

        # Subset enforcement: new permissions ⊆ creator permissions
        creator_perms = set(creator_role.permissions)
        target_perms = set(perms)
        unauthorized_perms = target_perms - creator_perms

        if unauthorized_perms:
            raise forms.ValidationError(
                f"Privilege escalation error: You cannot grant permissions you do not possess: "
                f"{', '.join(unauthorized_perms)}"
            )

        return cleaned_data
>>>>
```

---

## Change 7: RoleAdmin with Fine-Grained Hooks

**File:** `accounts/admin.py`  
**Area:** `RoleAdmin` class

**Instructions:** Wire `RoleAdminForm`, implement permission hooks (`roles.view`, `roles.add`, `roles.edit`, `roles.delete`), pass `request_user` to form.

```python
<<<< SEARCH
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'role_type', 'university')
    list_filter = ('role_type', 'university')
    search_fields = ('name',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request, 'scoped_university'):
            return qs.filter(
                models.Q(university=request.scoped_university) | 
                models.Q(university__isnull=True)
            )
        return qs
    def get_fieldsets(self, request, obj=None):
        """Hide permissions field from campus admins — only superuser edits perms."""
        if request.user.is_superuser:
            return (
                (None, {'fields': ('name', 'role_type', 'university', 'permissions')}),
            )
        return (
            (None, {'fields': ('name', 'role_type')}),  # No perms, no university
        )

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if request.user.is_superuser:
            return True
        if obj is None:
            return True  # Changelist access — queryset handles filtering
        # Campus admin: only roles belonging to their university
        scoped_uni = getattr(request, 'scoped_university', None)
        return obj.university_id == getattr(scoped_uni, 'id', None)

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        scoped_uni = getattr(request, 'scoped_university', None)
        # Block deletion of global roles (university=None) by campus admins
        return obj.university_id == getattr(scoped_uni, 'id', None)

    def has_module_permission(self, request):
        """Controls whether 'Roles' appears in the admin sidebar/index."""
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return (
            request.user.is_staff
            and request.user.role
            and request.user.university
        )

    def has_view_permission(self, request, obj=None):
        """Allows viewing roles scoped by get_queryset."""
        if request.user.is_superuser:
            return True
        if not self.has_module_permission(request):
            return False
        if obj is None:
            return True
        scoped_uni = getattr(request, 'scoped_university', None)
        # Allow viewing own-tenant and global roles
        return obj.university_id is None or obj.university_id == getattr(scoped_uni, 'id', None)

    def save_model(self, request, obj, form, change):
        """Auto-assign university for campus-admin-created roles."""
        if not change and not request.user.is_superuser:
            scoped_uni = getattr(request, 'scoped_university', None)
            if scoped_uni:
                obj.university = scoped_uni
        super().save_model(request, obj, form, change)
>>>> REPLACE
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    form = RoleAdminForm
    list_display = ('name', 'role_type', 'level', 'university')
    list_filter = ('role_type', 'level', 'university')
    search_fields = ('name',)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form_class = super().get_form(request, obj, change=change, **kwargs)
        class FormWithUser(form_class):
            def __new__(cls, *args, **fkwargs):
                fkwargs['request_user'] = request.user
                return form_class(*args, **fkwargs)
        return FormWithUser

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        scoped_uni = getattr(request, 'scoped_university', None)
        if scoped_uni:
            # Admins only see roles at their level or deeper
            user_level = request.user.role.level if request.user.role else 4
            return qs.filter(
                models.Q(university=scoped_uni) | models.Q(university__isnull=True),
                level__gte=user_level
            )
        return qs.none()

    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return (
                (None, {'fields': ('name', 'role_type', 'level', 'university', 'permissions')}),
            )
        # Campus admins can configure permissions and levels within their bounds
        return (
            (None, {'fields': ('name', 'role_type', 'level', 'permissions')}),
        )

    def has_module_permission(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return (
            request.user.is_staff
            and request.user.role
            and request.user.university
            and request.user.role.has_permission('roles.view')
        )

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not self.has_module_permission(request):
            return False
        if obj is None:
            return True
        scoped_uni = getattr(request, 'scoped_university', None)
        return obj.university_id is None or obj.university_id == getattr(scoped_uni, 'id', None)

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return bool(
            request.user.is_staff
            and request.user.role
            and request.user.role.has_permission('roles.add')
        )

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not (request.user.is_staff and request.user.role and request.user.role.has_permission('roles.edit')):
            return False
        if obj is None:
            return True
        scoped_uni = getattr(request, 'scoped_university', None)
        # Cannot edit global roles or roles above their level
        is_own_uni = obj.university_id == getattr(scoped_uni, 'id', None)
        is_subordinate = obj.level > request.user.role.level
        return is_own_uni and is_subordinate

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not (request.user.is_staff and request.user.role and request.user.role.has_permission('roles.delete')):
            return False
        if obj is None:
            return True
        scoped_uni = getattr(request, 'scoped_university', None)
        is_own_uni = obj.university_id == getattr(scoped_uni, 'id', None)
        is_subordinate = obj.level > request.user.role.level
        return is_own_uni and is_subordinate

    def save_model(self, request, obj, form, change):
        if not change and not request.user.is_superuser:
            scoped_uni = getattr(request, 'scoped_university', None)
            if scoped_uni:
                obj.university = scoped_uni
        super().save_model(request, obj, form, change)
>>>>
```

---

## Change 8: SchoolAdmin Registration

**File:** `accounts/admin.py`  
**Area:** New `SchoolAdmin` class (add after `RoleAdmin`)

**Instructions:** Register `School` model with fine-grained permission hooks and tenant scoping.

```python
@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'university', 'created_at')
    search_fields = ('name',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        scoped_uni = getattr(request, 'scoped_university', None)
        if scoped_uni:
            return qs.filter(university=scoped_uni)
        return qs.none()

    def has_module_permission(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return bool(
            request.user.is_staff
            and request.user.role
            and request.user.university
            and request.user.role.has_permission('schools.view')
        )

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not self.has_module_permission(request):
            return False
        if obj is None:
            return True
        scoped_uni = getattr(request, 'scoped_university', None)
        return obj.university_id == getattr(scoped_uni, 'id', None)

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return bool(
            request.user.is_staff
            and request.user.role
            and request.user.role.has_permission('schools.add')
        )

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not (request.user.is_staff and request.user.role and request.user.role.has_permission('schools.edit')):
            return False
        if obj is None:
            return True
        scoped_uni = getattr(request, 'scoped_university', None)
        return obj.university_id == getattr(scoped_uni, 'id', None)

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not (request.user.is_staff and request.user.role and request.user.role.has_permission('schools.delete')):
            return False
        if obj is None:
            return True
        scoped_uni = getattr(request, 'scoped_university', None)
        return obj.university_id == getattr(scoped_uni, 'id', None)

    def save_model(self, request, obj, form, change):
        if not change and not request.user.is_superuser:
            scoped_uni = getattr(request, 'scoped_university', None)
            if scoped_uni:
                obj.university = scoped_uni
        super().save_model(request, obj, form, change)
```

---

## Change 9: User Forms with School Field

**File:** `accounts/admin.py`  
**Area:** `CustomUserCreationForm` and `CustomUserChangeForm`

**Instructions:** Add `school` field to both form Meta classes.

### CustomUserCreationForm

```python
<<<< SEARCH
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'university', 'role',
                  'is_active', 'is_staff', 'is_superuser')
>>>> REPLACE
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'university', 'school', 'role',
                  'is_active', 'is_staff', 'is_superuser')
>>>>
```

### CustomUserChangeForm

```python
<<<< SEARCH
    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'university',
                  'role', 'is_active', 'is_staff', 'is_superuser')
>>>> REPLACE
    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'university',
                  'school', 'role', 'is_active', 'is_staff', 'is_superuser')
>>>>
```

---

## Change 10: CustomUserAdmin Permission Hooks & FK Scoping

**File:** `accounts/admin.py`  
**Area:** `CustomUserAdmin` class

**Instructions:** Wire fine-grained user permissions, include `school` in fieldsets, filter `school` FK dropdown to scoped university.

### Part A: get_fieldsets

```python
<<<< SEARCH
    def get_fieldsets(self, request, obj=None):
        """
        Return fieldsets based on user role and form type (add vs change).
        
        - Superuser add: full add form with all fields including is_superuser
        - Superuser change: full change form with Permissions section
        - Campus admin add: no is_staff/is_superuser toggles
        - Campus admin change: no Permissions section
        """
        # Superuser branches — full access
        if request.user.is_superuser:
            if obj is None:
                # Add form for superuser
                return (
                    (None, {
                        'classes': ('wide',),
                        'fields': (
                            'email',
                            'password1',
                            'password2',
                            'first_name',
                            'last_name',
                            'university',
                            'role',
                            'is_active',
                            'is_staff',
                            'is_superuser',
                        ),
                    }),
                )
            # Change form for superuser
            return (
                (None, {'fields': ('email', 'password')}),
                ('Personal info', {'fields': ('first_name', 'last_name')}),
                ('Tenant & Role', {'fields': ('university', 'role')}),
                ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
                ('Important dates', {'fields': ('last_login', 'date_joined')}),
            )

        # Campus admin branches — restricted
        if obj is None:
            # Add form for campus admin
            return (
                (None, {
                    'classes': ('wide',),
                    'fields': (
                        'email',
                        'password1',
                        'password2',
                        'first_name',
                        'last_name',
                        'university',
                        'role',
                        'is_active',
                    ),
                }),
            )
        # Change form for campus admin
        return (
            (None, {'fields': ('email', 'password')}),
            ('Personal info', {'fields': ('first_name', 'last_name')}),
            ('Tenant & Role', {'fields': ('university', 'role')}),
            ('Status', {'fields': ('is_active',)}),
            ('Important dates', {'fields': ('last_login', 'date_joined')}),
        )
>>>> REPLACE
    def get_fieldsets(self, request, obj=None):
        """
        Return fieldsets based on user role and form type (add vs change).
        Hides role assignment if user lacks 'users.assign_role'.
        """
        can_assign_role = request.user.is_superuser or (
            request.user.role and request.user.role.has_permission('users.assign_role')
        )
        tenant_fields = ['university', 'school']
        if can_assign_role:
            tenant_fields.append('role')

        if request.user.is_superuser:
            if obj is None:
                return (
                    (None, {
                        'classes': ('wide',),
                        'fields': (
                            'email', 'password1', 'password2',
                            'first_name', 'last_name',
                            'university', 'school', 'role',
                            'is_active', 'is_staff', 'is_superuser',
                        ),
                    }),
                )
            return (
                (None, {'fields': ('email', 'password')}),
                ('Personal info', {'fields': ('first_name', 'last_name')}),
                ('Tenant & Affiliation', {'fields': ('university', 'school', 'role')}),
                ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
                ('Important dates', {'fields': ('last_login', 'date_joined')}),
            )

        # Campus admin branches
        if obj is None:
            add_fields = ['email', 'password1', 'password2', 'first_name', 'last_name', 'university', 'school']
            if can_assign_role:
                add_fields.append('role')
            add_fields.append('is_active')
            return (
                (None, {'classes': ('wide',), 'fields': tuple(add_fields)}),
            )

        return (
            (None, {'fields': ('email', 'password')}),
            ('Personal info', {'fields': ('first_name', 'last_name')}),
            ('Tenant & Affiliation', {'fields': tuple(tenant_fields)}),
            ('Status', {'fields': ('is_active',)}),
            ('Important dates', {'fields': ('last_login', 'date_joined')}),
        )
>>>>
```

### Part B: Permission Hooks

```python
<<<< SEARCH
    def has_change_permission(self, request, obj=None):
        ...existing code...

    def has_delete_permission(self, request, obj=None):
        ...existing code...

    def has_module_permission(self, request):
        ...existing code...

    def has_view_permission(self, request, obj=None):
        ...existing code...
>>>> REPLACE
    def has_module_permission(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return bool(
            request.user.is_staff
            and request.user.role
            and request.user.university
            and request.user.role.has_permission('users.view')
        )

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not self.has_module_permission(request):
            return False
        if obj is None:
            return True
        scoped_uni = getattr(request, 'scoped_university', None)
        if obj.is_superuser:
            return False
        return obj.university_id == getattr(scoped_uni, 'id', None)

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return bool(
            request.user.is_staff
            and request.user.role
            and request.user.role.has_permission('users.add')
        )

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not (request.user.is_staff and request.user.role and request.user.role.has_permission('users.edit')):
            return False
        if obj is None:
            return True
        if obj.is_superuser:
            return False
        scoped_uni = getattr(request, 'scoped_university', None)
        return obj.university_id == getattr(scoped_uni, 'id', None)

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not (request.user.is_staff and request.user.role and request.user.role.has_permission('users.delete')):
            return False
        if obj is None:
            return True
        if obj.is_superuser:
            return False
        scoped_uni = getattr(request, 'scoped_university', None)
        return obj.university_id == getattr(scoped_uni, 'id', None)
>>>>
```

### Part C: formfield_for_foreignkey

```python
<<<< SEARCH
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Scope foreign key dropdowns for campus admins:
        - role: only roles belonging to their university OR global (university=None)
        - university: locked to their own university (can't reassign users cross-tenant)
        
        Superusers see all options unfiltered.
        """
        scoped_uni = getattr(request, 'scoped_university', None)

        if scoped_uni and not request.user.is_superuser:
            if db_field.name == 'role':
                kwargs['queryset'] = Role.objects.filter(
                    models.Q(university=scoped_uni) | models.Q(university__isnull=True)
                )

            if db_field.name == 'university':
                kwargs['queryset'] = University.objects.filter(id=scoped_uni.id)
                kwargs['initial'] = scoped_uni.id

        return super().formfield_for_foreignkey(db_field, request, **kwargs)
>>>> REPLACE
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Scope foreign key dropdowns for campus admins:
        - role: only roles belonging to their university OR global, and level >= current user's level
        - school: only schools belonging to their university
        - university: locked to their own university
        """
        scoped_uni = getattr(request, 'scoped_university', None)

        if scoped_uni and not request.user.is_superuser:
            if db_field.name == 'role':
                user_level = request.user.role.level if request.user.role else 4
                kwargs['queryset'] = Role.objects.filter(
                    (models.Q(university=scoped_uni) | models.Q(university__isnull=True)),
                    level__gte=user_level
                )

            if db_field.name == 'school':
                kwargs['queryset'] = School.objects.filter(university=scoped_uni)

            if db_field.name == 'university':
                kwargs['queryset'] = University.objects.filter(id=scoped_uni.id)
                kwargs['initial'] = scoped_uni.id

        return super().formfield_for_foreignkey(db_field, request, **kwargs)
>>>>
```

---

## Change 11: View Decorators

**File:** `accounts/views.py`  
**Area:** Non-admin catalog views

**Instructions:** Apply `@permission_required` decorator to catalog views.

```python
<<<< SEARCH
# Any authenticated user
@login_required
def catalog_view(request, university_slug):
    university = get_object_or_404(University, slug=university_slug, is_active=True)

    # Verify user belongs to this university (unless superuser)
    if not request.user.is_superuser and request.user.university != university:
        if request.user.university == None:
            return HttpResponseForbidden("No University Assigned")
        
        return HttpResponseForbidden("You do not have access to this catalog.")
    
    return render(request, 'catalog.html', {'university': university})

# Admin only
@login_required
@user_passes_test(lambda u: u.is_staff and u.role and u.university)
def admin_catalog_view(request):
    return render(request, 'admin_catalog.html', {
        'university': request.user.university,
    })
>>>> REPLACE
from .decorators import permission_required

# Any authenticated user with catalog.view permission
@login_required
@permission_required('catalog.view')
def catalog_view(request, university_slug):
    university = get_object_or_404(University, slug=university_slug, is_active=True)

    # Verify user belongs to this university (unless superuser)
    if not request.user.is_superuser and request.user.university != university:
        if request.user.university is None:
            return HttpResponseForbidden("No University Assigned")
        
        return HttpResponseForbidden("You do not have access to this catalog.")
    
    return render(request, 'catalog.html', {'university': university})

# Admin catalog management view
@login_required
@permission_required('catalog.edit')
def admin_catalog_view(request):
    return render(request, 'admin_catalog.html', {
        'university': request.user.university,
    })
>>>>
```

---

# Implementation Order

## Phase 1: Models & Vocabulary

| Step | Change | Description |
|------|--------|-------------|
| 1.1 | Change 1 | Define `PERMISSION_CHOICES`, `DEFAULT_ROLE_PERMISSIONS`, update `Role` model |
| 1.2 | Change 2 | Add `School` model, update `User` with `school` FK |
| 1.3 | Change 3 | Add school-university validation in `User.clean()` |
| 1.4 | — | Run `python manage.py makemigrations` and `python manage.py migrate` |

**→ Proceed to Checkpoint 1**

---

## Phase 2: Decorators & Middleware

| Step | Change | Description |
|------|--------|-------------|
| 2.1 | Change 4 | Create `accounts/decorators.py` with permission decorators |
| 2.2 | Change 5 | Update middleware with broad permission gate |

**→ Proceed to Checkpoint 2**

---

## Phase 3: Admin Layer & Forms

| Step | Change | Description |
|------|--------|-------------|
| 3.1 | Change 6 | Add `RoleAdminForm` with checkbox widget and validation |
| 3.2 | Change 7 | Update `RoleAdmin` with form and permission hooks |
| 3.3 | Change 8 | Add `SchoolAdmin` registration |
| 3.4 | Change 9 | Update user forms with `school` field |
| 3.5 | Change 10 | Update `CustomUserAdmin` with permission hooks and FK scoping |

**→ Proceed to Checkpoint 3**

---

## Phase 4: Views & Integration

| Step | Change | Description |
|------|--------|-------------|
| 4.1 | Change 11 | Apply decorators to catalog views |

**→ Proceed to Final Checkpoint**

---

# Testing Checkpoints

## Checkpoint 1: Model & Schema Verification

**Pause after:** Phase 1 complete (Changes 1-3 + migrations)

| Test | Description | Expected Result |
|------|-------------|-----------------|
| 1.1 | Create School under University A, assign to User in University B, call `user.full_clean()` | `ValidationError` on `school` field |
| 1.2 | Create Role with `permissions=["invalid.perm"]`, call `role.full_clean()` | `ValidationError` on `permissions` field |
| 1.3 | Create Role with `permissions=["catalog.view"]`, assign to User, call `user.has_perm('catalog.view')` | Returns `True` |
| 1.4 | Same user, call `user.has_perm('catalog.delete')` | Returns `False` |

**Shell commands:**
```python
from accounts.models import University, School, Role, User

# Test 1.1
uni_a = University.objects.create(name="Stanford", slug="stanford")
uni_b = University.objects.create(name="MIT", slug="mit")
school = School.objects.create(name="Business", university=uni_a)
user = User(email="test@mit.edu", university=uni_b, school=school)
user.full_clean()  # Should raise ValidationError

# Test 1.2
role = Role(name="Bad Role", permissions=["invalid.perm"])
role.full_clean()  # Should raise ValidationError

# Test 1.3 & 1.4
role = Role.objects.create(name="Viewer", permissions=["catalog.view"], university=uni_a)
user = User.objects.create_user(email="viewer@stanford.edu", university=uni_a, role=role)
print(user.has_perm('catalog.view'))   # True
print(user.has_perm('catalog.delete')) # False
```

---

## Checkpoint 2: Middleware & Decorator Enforcement

**Pause after:** Phase 2 complete (Changes 4-5)

| Test | Description | Expected Result |
|------|-------------|-----------------|
| 2.1 | Assign staff user a role with `permissions=[]`, navigate to `/app-admin/` | `403 Forbidden: Access denied. Your role has no active permissions.` |
| 2.2 | Create test view with `@permission_required('catalog.edit')`, call with user lacking permission | `PermissionDenied` raised |

**Manual test for 2.1:**
1. Create user with `is_staff=True`, role with empty permissions
2. Log in as that user
3. Navigate to admin URL
4. Verify 403 response

**Unit test for 2.2:**
```python
from django.test import TestCase, RequestFactory
from django.core.exceptions import PermissionDenied
from accounts.decorators import permission_required
from accounts.models import University, Role, User

class DecoratorTest(TestCase):
    def test_permission_denied_without_permission(self):
        uni = University.objects.create(name="Test", slug="test")
        role = Role.objects.create(name="No Edit", permissions=["catalog.view"], university=uni)
        user = User.objects.create_user(email="test@test.edu", university=uni, role=role, is_staff=True)
        
        @permission_required('catalog.edit')
        def mock_view(request):
            return "OK"
        
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = user
        
        with self.assertRaises(PermissionDenied):
            mock_view(request)
```

---

## Checkpoint 3: Admin UI & Privilege Escalation Defenses

**Pause after:** Phase 3 complete (Changes 6-10)

| Test | Description | Expected Result |
|------|-------------|-----------------|
| 3.1 | Log in as Superuser, open Role add form | Permissions appear as checkboxes |
| 3.2 | Log in as Campus Admin (Level 2), create role with `level=1` | Form validation error: hierarchy violation |
| 3.3 | Same admin, create role with permission they don't have | Form validation error: privilege escalation |
| 3.4 | Log in as School Admin (Level 3), verify cannot see Campus Admin roles | Changelist filtered to level >= 3 |
| 3.5 | Create schools under different universities, verify FK dropdown scoping | Only same-university schools appear |

**Manual verification steps:**

1. **Test 3.1:** Navigate to `/app-admin/accounts/role/add/` as superuser
2. **Test 3.2:** As Campus Admin, submit role form with `level=1`
3. **Test 3.3:** As Campus Admin without `users.delete`, try to create role with `users.delete`
4. **Test 3.4:** Create School Admin user, log in, check role list
5. **Test 3.5:** Create schools under Stanford and MIT, log in as Stanford admin, check user form school dropdown

---

## Final Checkpoint: End-to-End Tenant & Role Isolation

**Pause after:** Phase 4 complete (Change 11)

| Test | Description | Expected Result |
|------|-------------|-----------------|
| 4.1 | Log in as `campus_viewer` (only `catalog.view`), visit `/<slug>/catalog/` | Page renders successfully |
| 4.2 | Same user, visit `/admin_catalog/` | `403 Forbidden` (requires `catalog.edit`) |
| 4.3 | Same user, visit `/app-admin/` | `403 Forbidden` or limited sidebar |
| 4.4 | Add `catalog.edit` to viewer role, refresh without re-login | New permission takes effect immediately |

**Verification for 4.4 (Universal Role Test):**
1. Open two browser sessions with different viewer users
2. In admin, add `catalog.edit` to their shared role
3. Both users should gain access to `admin_catalog_view` without logging out

---

# Deferred Items (Next Iteration)

- [ ] Department/School-level scoping for School Admins (filter querysets by `user.school`)
- [ ] Custom/tenant-defined permissions (campus admins add their own)
- [ ] Permission inheritance (if needed)
- [ ] Audit logging of permission changes
- [ ] Individual user permission overrides (breaking out of universal role)
