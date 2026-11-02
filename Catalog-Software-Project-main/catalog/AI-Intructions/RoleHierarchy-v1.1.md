# Role Hierarchy Implementation Plan

## Overview

This document outlines the implementation of:
- Removal of `role_type` field (rely on `level` + `permissions`)
- Auto-incrementing role levels based on creator's level
- School assignment requirement for School Admin roles (level 3)
- School-scoped querysets for School Admins

---

## Change #1

- **File:** `accounts/models.py`
- **Function/Scope:** Constants and `Role` class definition
- **Instruction:** Remove `RoleType` enum, remove `role_type` field from `Role`, keep `DEFAULT_ROLE_PERMISSIONS` for UX, update model docstrings.

```text
<<<<<<< SEARCH
DEFAULT_ROLE_PERMISSIONS = {
    'university_admin': ALL_PERMISSIONS,
    'school_admin': [
        'catalog.view', 'catalog.add', 'catalog.edit',
        'users.view', 'schools.view',
    ],
    'campus_viewer': [
        'catalog.view', 'users.view', 'schools.view',
    ],
}


class University(models.Model):
    """
    Tenant model - each university operates in isolation.
    All non-superuser accounts must belong to exactly one university.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)  # URL-safe identifier, e.g., "stanford"
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'University'
        verbose_name_plural = 'universities'
        db_table = 'universities'

    def __str__(self):
        return self.name


class Role(models.Model):
    """
    Custom role model replacing Django's SQL-based Group model.
    Stores customizable permissions as a list of strings in JSONField.
    Hierarchy level increases as authority decreases, from campus admin (2)
    through school admin (3) to campus viewer (4).
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
=======
DEFAULT_ROLE_PERMISSIONS = {
    'university_admin': ALL_PERMISSIONS,
    'school_admin': [
        'catalog.view', 'catalog.add', 'catalog.edit',
        'users.view', 'schools.view',
    ],
    'campus_viewer': [
        'catalog.view', 'users.view', 'schools.view',
    ],
}


class University(models.Model):
    """
    Tenant model - each university operates in isolation.
    All non-superuser accounts must belong to exactly one university.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)  # URL-safe identifier, e.g., "stanford"
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'University'
        verbose_name_plural = 'universities'
        db_table = 'universities'

    def __str__(self):
        return self.name


class Role(models.Model):
    """
    Custom role model replacing Django's SQL-based Group model.
    Stores customizable permissions as a list of strings in JSONField.
    Hierarchy level increases as authority decreases (2=Campus Admin, 3=School Admin, 4+=Subordinate roles).
    """
    name = models.CharField(max_length=100)
    level = models.PositiveSmallIntegerField(
        default=4,
        help_text='Hierarchy level (2=Campus Admin, 3=School Admin, 4+=Subordinate). Higher number = less power.'
    )
>>>>>>> REPLACE
```

---

## Change #2

- **File:** `accounts/models.py`
- **Function/Scope:** `User` model helper properties
- **Instruction:** Update `is_campus_admin` and `is_campus_viewer` properties to check `role.level` instead of `role.role_type`.

```text
<<<<<<< SEARCH
    # Property helpers matching previous middleware & view expectations
    @property
    def is_campus_admin(self):
        if not self.role:
            return False
        return self.role.role_type in [Role.RoleType.UNIVERSITY_ADMIN]

    @property
    def is_campus_viewer(self):
        if not self.role:
            return False
        return self.role.role_type == Role.RoleType.CAMPUS_VIEWER
=======
    # Property helpers matching previous middleware & view expectations
    @property
    def is_campus_admin(self):
        if not self.role:
            return False
        return self.role.level == 2

    @property
    def is_campus_viewer(self):
        if not self.role:
            return False
        return self.role.level >= 4
>>>>>>> REPLACE
```

---

## Change #3

- **File:** `accounts/admin.py`
- **Function/Scope:** `RoleAdminForm`
- **Instruction:** Remove `role_type` and `level` from form fields, filter permission choices to only those the creator possesses, validate subset delegation.

```text
<<<<<<< SEARCH
class RoleAdminForm(forms.ModelForm):
    """Role editor with checkbox permissions and delegation validation."""
    permissions = forms.MultipleChoiceField(
        choices=PERMISSION_CHOICES,
        widget=CheckboxSelectMultiple,
        required=False,
        help_text='Select permissions granted to this role.',
    )

    class Meta:
        model = Role
        fields = ('name', 'role_type', 'level', 'university', 'permissions')

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)

        if not self.is_bound and not self.instance.pk:
            role_type = self.initial.get('role_type', Role.RoleType.CAMPUS_VIEWER)
            self.initial['permissions'] = DEFAULT_ROLE_PERMISSIONS.get(role_type, [])

    def clean(self):
        cleaned_data = super().clean()
        permissions = cleaned_data.get('permissions', [])
        level = cleaned_data.get('level')

        if not self.request_user or self.request_user.is_superuser:
            return cleaned_data

        creator_role = self.request_user.role
        if not creator_role:
            raise forms.ValidationError(
                'You do not have a role configured to delegate permissions.'
            )

        if level is not None and level <= creator_role.level:
            raise forms.ValidationError(
                f'Hierarchy error: the new role level must be greater than '
                f'your level ({creator_role.level}).'
            )

        unauthorized_permissions = set(permissions) - set(creator_role.permissions)
        if unauthorized_permissions:
            raise forms.ValidationError(
                'You cannot grant permissions you do not possess: '
                f"{', '.join(sorted(unauthorized_permissions))}"
            )

        return cleaned_data
=======
class RoleAdminForm(forms.ModelForm):
    """Role editor with checkbox permissions and delegation validation."""
    permissions = forms.MultipleChoiceField(
        choices=PERMISSION_CHOICES,
        widget=CheckboxSelectMultiple,
        required=False,
        help_text='Select permissions granted to this role.',
    )

    class Meta:
        model = Role
        fields = ('name', 'permissions')

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)

        if self.request_user and not self.request_user.is_superuser and self.request_user.role:
            # Non-superusers can only assign permissions they already have
            allowed_permissions = set(self.request_user.role.permissions)
            self.fields['permissions'].choices = [
                (code, label) for code, label in PERMISSION_CHOICES if code in allowed_permissions
            ]

    def clean(self):
        cleaned_data = super().clean()
        permissions = cleaned_data.get('permissions', [])

        if not self.request_user or self.request_user.is_superuser:
            return cleaned_data

        creator_role = self.request_user.role
        if not creator_role:
            raise forms.ValidationError(
                'You do not have a role configured to delegate permissions.'
            )

        unauthorized_permissions = set(permissions) - set(creator_role.permissions)
        if unauthorized_permissions:
            raise forms.ValidationError(
                'You cannot grant permissions you do not possess: '
                f"{', '.join(sorted(unauthorized_permissions))}"
            )

        return cleaned_data
>>>>>>> REPLACE
```

---

## Change #4

- **File:** `accounts/admin.py`
- **Function/Scope:** `RoleAdmin` class
- **Instruction:** Remove `role_type` from `list_display`, `list_filter`, and `get_fieldsets`. Auto-set `level` and `university` in `save_model`.

```text
<<<<<<< SEARCH
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    form = RoleAdminForm
    list_display = ('name', 'role_type', 'level', 'university')
    list_filter = ('role_type', 'level', 'university')
    search_fields = ('name',)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form_class = super().get_form(request, obj, change=change, **kwargs)

        class FormWithUser(form_class):
            def __init__(self, *args, **form_kwargs):
                form_kwargs['request_user'] = request.user
                super().__init__(*args, **form_kwargs)

        return FormWithUser

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset

        scoped_university = getattr(request, 'scoped_university', None)
        creator_role = request.user.role
        if not scoped_university or not creator_role:
            return queryset.none()

        return queryset.filter(
            models.Q(university=scoped_university) | models.Q(university__isnull=True),
            level__gte=creator_role.level,
        )

    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return (
                (None, {'fields': ('name', 'role_type', 'level', 'university', 'permissions')}),
            )
        return (
            (None, {'fields': ('name', 'role_type', 'level', 'permissions')}),
        )

    def has_module_permission(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return bool(
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
        scoped_university = getattr(request, 'scoped_university', None)
        creator_role = request.user.role
        is_visible_university = (
            obj.university_id is None
            or obj.university_id == getattr(scoped_university, 'id', None)
        )
        return is_visible_university and obj.level >= creator_role.level

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
        if not (
            request.user.is_staff
            and request.user.role
            and request.user.role.has_permission('roles.edit')
        ):
            return False
        if obj is None:
            return True
        scoped_university = getattr(request, 'scoped_university', None)
        return (
            obj.university_id == getattr(scoped_university, 'id', None)
            and obj.level > request.user.role.level
        )

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not (
            request.user.is_staff
            and request.user.role
            and request.user.role.has_permission('roles.delete')
        ):
            return False
        if obj is None:
            return True
        scoped_university = getattr(request, 'scoped_university', None)
        return (
            obj.university_id == getattr(scoped_university, 'id', None)
            and obj.level > request.user.role.level
        )

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            scoped_university = getattr(request, 'scoped_university', None)
            if scoped_university:
                obj.university = scoped_university
        super().save_model(request, obj, form, change)
=======
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    form = RoleAdminForm
    list_display = ('name', 'level', 'university')
    list_filter = ('level', 'university')
    search_fields = ('name',)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form_class = super().get_form(request, obj, change=change, **kwargs)

        class FormWithUser(form_class):
            def __init__(self, *args, **form_kwargs):
                form_kwargs['request_user'] = request.user
                super().__init__(*args, **form_kwargs)

        return FormWithUser

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset

        scoped_university = getattr(request, 'scoped_university', None)
        creator_role = request.user.role
        if not scoped_university or not creator_role:
            return queryset.none()

        return queryset.filter(
            models.Q(university=scoped_university) | models.Q(university__isnull=True),
            level__gte=creator_role.level,
        )

    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return (
                (None, {'fields': ('name', 'university', 'permissions')}),
            )
        return (
            (None, {'fields': ('name', 'permissions')}),
        )

    def has_module_permission(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return bool(
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
        scoped_university = getattr(request, 'scoped_university', None)
        creator_role = request.user.role
        is_visible_university = (
            obj.university_id is None
            or obj.university_id == getattr(scoped_university, 'id', None)
        )
        return is_visible_university and obj.level >= creator_role.level

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
        if not (
            request.user.is_staff
            and request.user.role
            and request.user.role.has_permission('roles.edit')
        ):
            return False
        if obj is None:
            return True
        scoped_university = getattr(request, 'scoped_university', None)
        return (
            obj.university_id == getattr(scoped_university, 'id', None)
            and obj.level > request.user.role.level
        )

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not (
            request.user.is_staff
            and request.user.role
            and request.user.role.has_permission('roles.delete')
        ):
            return False
        if obj is None:
            return True
        scoped_university = getattr(request, 'scoped_university', None)
        return (
            obj.university_id == getattr(scoped_university, 'id', None)
            and obj.level > request.user.role.level
        )

    def save_model(self, request, obj, form, change):
        if not change:
            if request.user.is_superuser:
                obj.level = 2
            elif request.user.role:
                obj.level = request.user.role.level + 1

        if not request.user.is_superuser:
            scoped_university = getattr(request, 'scoped_university', None)
            if scoped_university:
                obj.university = scoped_university
        super().save_model(request, obj, form, change)
>>>>>>> REPLACE
```

---

## Change #5

- **File:** `accounts/admin.py`
- **Function/Scope:** `CustomUserCreationForm` and `CustomUserChangeForm`
- **Instruction:** Add `clean()` validation requiring `school` field when assigned role has `level == 3`.

```text
<<<<<<< SEARCH
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    """
    Form for editing existing users in admin.
    Displays password hash as readonly (never editable raw).
    """
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text=(
            "Raw passwords are not stored, so there is no way to see this "
            "user's password, but you can change it using "
            "<a href=\"../password/\">this form</a>."
        ),
    )

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'university',
                  'school', 'role', 'is_active', 'is_staff', 'is_superuser')

    def clean_password(self):
        # Field is readonly — return the initial hash regardless of input
        return self.initial.get('password')
=======
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        school = cleaned_data.get('school')

        if role and role.level == 3 and not school:
            self.add_error('school', 'School assignment is required for School Admin roles.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    """
    Form for editing existing users in admin.
    Displays password hash as readonly (never editable raw).
    """
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text=(
            "Raw passwords are not stored, so there is no way to see this "
            "user's password, but you can change it using "
            "<a href=\"../password/\">this form</a>."
        ),
    )

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'university',
                  'school', 'role', 'is_active', 'is_staff', 'is_superuser')

    def clean_password(self):
        # Field is readonly — return the initial hash regardless of input
        return self.initial.get('password')

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        school = cleaned_data.get('school')

        if role and role.level == 3 and not school:
            self.add_error('school', 'School assignment is required for School Admin roles.')

        return cleaned_data
>>>>>>> REPLACE
```

---

## Change #6

- **File:** `accounts/admin.py`
- **Function/Scope:** `CustomUserAdmin.get_queryset`
- **Instruction:** Scope user queryset so School Admins (level >= 3 with school) only see users in their school.

```text
<<<<<<< SEARCH
    def get_queryset(self, request):
        """
        Scope the user list by tenant.
        
        - Superusers: see all users across all universities.
        - Campus admins: see only users within their scoped university,
        and NEVER see superusers (prevents enumeration of platform admins).
        """
        qs = super().get_queryset(request)
      
        if request.user.is_superuser:
            return qs
        
        scoped_uni = getattr(request, 'scoped_university', None)
        if scoped_uni:
            return qs.filter(university=scoped_uni, is_superuser=False)
        
        # Fallback: authenticated staff hitting admin without scope → see nothing
        return qs.none()
=======
    def get_queryset(self, request):
        """
        Scope the user list by tenant and school.
        
        - Superusers: see all users across all universities.
        - Campus Admins (level <= 2): see all users within their scoped university (non-superusers).
        - School Admins (level >= 3 with school): see only users within their specific school.
        """
        qs = super().get_queryset(request)
      
        if request.user.is_superuser:
            return qs
        
        scoped_uni = getattr(request, 'scoped_university', None)
        if scoped_uni:
            user_qs = qs.filter(university=scoped_uni, is_superuser=False)
            if request.user.role and request.user.role.level >= 3 and request.user.school:
                return user_qs.filter(school=request.user.school)
            return user_qs
        
        # Fallback: authenticated staff hitting admin without scope → see nothing
        return qs.none()
>>>>>>> REPLACE
```

---

## Change #7

- **File:** `accounts/admin.py`
- **Function/Scope:** `CustomUserAdmin.formfield_for_foreignkey`
- **Instruction:** Restrict `school` dropdown to the acting user's school if they are a School Admin.

```text
<<<<<<< SEARCH
        scoped_uni = getattr(request, 'scoped_university', None)

        if scoped_uni and not request.user.is_superuser:
            if db_field.name == 'role':
                user_level = request.user.role.level if request.user.role else 4
                kwargs['queryset'] = Role.objects.filter(
                    models.Q(university=scoped_uni) | models.Q(university__isnull=True),
                    level__gte=user_level,
                )

            if db_field.name == 'school':
                kwargs['queryset'] = School.objects.filter(university=scoped_uni)

            if db_field.name == 'university':
                kwargs['queryset'] = University.objects.filter(id=scoped_uni.id)
                kwargs['initial'] = scoped_uni.id
=======
        scoped_uni = getattr(request, 'scoped_university', None)

        if scoped_uni and not request.user.is_superuser:
            if db_field.name == 'role':
                user_level = request.user.role.level if request.user.role else 4
                kwargs['queryset'] = Role.objects.filter(
                    models.Q(university=scoped_uni) | models.Q(university__isnull=True),
                    level__gte=user_level,
                )

            if db_field.name == 'school':
                if request.user.role and request.user.role.level >= 3 and request.user.school:
                    kwargs['queryset'] = School.objects.filter(id=request.user.school_id)
                    kwargs['initial'] = request.user.school_id
                else:
                    kwargs['queryset'] = School.objects.filter(university=scoped_uni)

            if db_field.name == 'university':
                kwargs['queryset'] = University.objects.filter(id=scoped_uni.id)
                kwargs['initial'] = scoped_uni.id
>>>>>>> REPLACE
```

---

## Change #8

- **File:** `accounts/admin.py`
- **Function/Scope:** `CustomUserAdmin.save_model`
- **Instruction:** Auto-assign the acting user's school if the creator is a School Admin.

```text
<<<<<<< SEARCH
    def save_model(self, request, obj, form, change):
        """Keep non-superuser user records within their assigned tenant."""
        scoped_uni = getattr(request, 'scoped_university', None)
        if scoped_uni and not request.user.is_superuser:
            obj.university = scoped_uni
        super().save_model(request, obj, form, change)
=======
    def save_model(self, request, obj, form, change):
        """Keep non-superuser user records within their assigned tenant and school."""
        scoped_uni = getattr(request, 'scoped_university', None)
        if scoped_uni and not request.user.is_superuser:
            obj.university = scoped_uni
            if request.user.role and request.user.role.level >= 3 and request.user.school:
                obj.school = request.user.school
        super().save_model(request, obj, form, change)
>>>>>>> REPLACE
```

---

## Logical Execution Order

### Step 1: Schema & Models
Apply **Change #1** and **Change #2** to `accounts/models.py`.

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

### Step 2: Role Administration & Level Hierarchy
Apply **Change #3** and **Change #4** to `accounts/admin.py`.

### Step 3: User Administration & School Scoping
Apply **Change #5**, **Change #6**, **Change #7**, and **Change #8** to `accounts/admin.py`.

---

## Testing Checkpoints

### Checkpoint 1: Model & Schema Verification

**Pause after:** Changes #1 and #2 + migrations

| Test | Command/Action | Expected Result |
|------|----------------|-----------------|
| 1.1 | `python manage.py shell -c "from accounts.models import Role; print([f.name for f in Role._meta.get_fields()])"` | `role_type` is NOT in the list; `level`, `name`, `university`, `permissions` are present |
| 1.2 | Create a user with a level-2 role, check `user.is_campus_admin` | Returns `True` |
| 1.3 | Create a user with a level-4 role, check `user.is_campus_viewer` | Returns `True` |

---

### Checkpoint 2: Role Creation & Auto-Level

**Pause after:** Changes #3 and #4

| Test | Action | Expected Result |
|------|--------|-----------------|
| 2.1 | Log in as Campus Admin (level=2), create role "Department Coordinator" | Role is created with `level=3` |
| 2.2 | Log in as level-3 user, create role "Assistant" | Role is created with `level=4` |
| 2.3 | Verify role form does NOT show `role_type` or `level` fields | Only `name` and `permissions` checkboxes visible |
| 2.4 | Attempt to grant a permission the creator doesn't have | Validation error raised |

**Shell verification:**
```bash
python manage.py shell -c "from accounts.models import Role; r = Role.objects.get(name='Department Coordinator'); print(f'Level: {r.level}, University: {r.university}')"
```

---

### Checkpoint 3: User Administration & School Scoping

**Pause after:** Changes #5 through #8

| Test | Action | Expected Result |
|------|--------|-----------------|
| 3.1 | As Campus Admin, create user with level-3 role WITHOUT selecting school | Validation error: "School assignment is required for School Admin roles." |
| 3.2 | As Campus Admin, create user with level-3 role WITH school selected | User created successfully |
| 3.3 | Log in as School Admin (level=3, School A), view User list | Only users from School A are visible |
| 3.4 | As School Admin, attempt to view/edit user from School B | User not visible in list |
| 3.5 | As School Admin, create new user | User auto-assigned to School A |
| 3.6 | As School Admin, check school dropdown when adding user | Only School A appears in dropdown |

---

## Summary

| Phase | Changes | Files Modified |
|-------|---------|----------------|
| 1 | #1, #2 | `accounts/models.py` |
| 2 | #3, #4 | `accounts/admin.py` |
| 3 | #5, #6, #7, #8 | `accounts/admin.py` |

**Total changes:** 8
**Files modified:** 2
