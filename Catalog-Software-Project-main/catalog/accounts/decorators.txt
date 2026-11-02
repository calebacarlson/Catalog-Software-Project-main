from functools import wraps

from django.conf import settings as s
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def permission_required(perm):
    """Require an authenticated user to hold a specific role permission."""
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
    """Require an authenticated user's role level to be at or above the limit."""
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
