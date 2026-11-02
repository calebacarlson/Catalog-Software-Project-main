from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models


PERMISSION_CHOICES = [
    ('catalog.view', 'Catalog - View'),
    ('catalog.add', 'Catalog - Add'),
    ('catalog.edit', 'Catalog - Edit'),
    ('catalog.delete', 'Catalog - Delete'),
    ('users.view', 'Users - View'),
    ('users.add', 'Users - Add'),
    ('users.edit', 'Users - Edit'),
    ('users.delete', 'Users - Delete'),
    ('users.assign_role', 'Users - Assign Role'),
    ('roles.view', 'Roles - View'),
    ('roles.add', 'Roles - Add'),
    ('roles.edit', 'Roles - Edit'),
    ('roles.delete', 'Roles - Delete'),
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
    Hierarchy level increases as authority decreases (2=Campus Admin,
    3=School Admin, 4+=Subordinate roles).
    """
    name = models.CharField(max_length=100)
    level = models.PositiveSmallIntegerField(
        default=4,
        help_text='Hierarchy level (2=Campus Admin, 3=School Admin, 4+=Subordinate). Higher number = less power.'
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
        if not isinstance(self.permissions, list):
            raise ValidationError({
                'permissions': 'Permissions must be a list of valid permission codes.'
            })
        invalid_perms = [permission for permission in self.permissions if permission not in ALL_PERMISSIONS]
        if invalid_perms:
            raise ValidationError({
                'permissions': f"Invalid permissions specified: {', '.join(invalid_perms)}"
            })

    def has_permission(self, perm):
        return perm in self.permissions


class CustomUserManager(BaseUserManager):
    """
    Custom manager for email-based authentication.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

    def for_university(self, university):
        """Filter users by university tenant."""
        return self.filter(university=university)


class School(models.Model):
    """Organizational unit within a university; users belong to at most one."""
    name = models.CharField(max_length=255)
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='schools',
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

    def clean(self):
        """
        Enforce that any user with admin access (is_staff=True) must have 
        a role assigned, unless they are a superuser.
        
        Superusers bypass the role requirement because is_superuser=True 
        grants all permissions via has_perm() short-circuit.
        """
        super().clean()
        
        if self.is_staff and not self.is_superuser and not self.role:
            raise ValidationError({
                'role': 'Staff users must have a role assigned. '
                        'Only superusers may have is_staff=True without a role.'
            })
        
        if self.is_staff and not self.is_superuser and not self.university:
            raise ValidationError({
                'university': 'Non-superuser staff must belong to a university.'
            })

        if self.school and self.university and self.school.university_id != self.university_id:
            raise ValidationError({
                'school': 'The assigned school must belong to the user\'s university.'
            })


    def save(self, *args, **kwargs):
        """
        Run full validation before saving. This ensures that users created 
        via shell, scripts, or migrations cannot bypass the role requirement 
        that the admin form would normally enforce.
        """
        self.full_clean()
        super().save(*args, **kwargs)

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