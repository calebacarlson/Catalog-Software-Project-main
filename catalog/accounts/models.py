from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models


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

    def clean(self):
        super().clean()
        if not self.is_superuser and not self.university:
            raise ValidationError('Non-superuser accounts must belong to a university.')

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

    # Property helpers matching previous middleware & view expectations
    @property
    def is_campus_admin(self):
        if not self.role:
            return False
        return self.role.role_type in [Role.RoleType.UNIVERSITY_ADMIN, Role.RoleType.DEPARTMENT_ADMIN]

    @property
    def is_campus_viewer(self):
        if not self.role:
            return False
        return self.role.role_type == Role.RoleType.CAMPUS_VIEWER