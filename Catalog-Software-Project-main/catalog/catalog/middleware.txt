from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.conf import settings as s
from accounts.models import ALL_PERMISSIONS
import logging

logger = logging.getLogger(__name__)


class AdminAccessMiddleware:
    """
    Enforces admin panel access and sets tenant scope on the request.

    Single admin URL for everyone. Tenancy is derived from the user's
    assigned university, not from the URL. Cross-tenant protection
    lives in admin.py's get_queryset and has_*_permission hooks.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(s, 'SUPER_ADMIN_URL') and request.path.startswith(s.SUPER_ADMIN_URL):
            return self._enforce_admin_access(request)
        return self.get_response(request)

    def _enforce_admin_access(self, request):
        if not request.user.is_authenticated:
            return redirect(f"{s.LOGIN_URL}?next={request.path}")

        # Platform superuser: unrestricted
        if request.user.is_superuser:
            return self.get_response(request)

        # Campus / school admin: scoped to their university with active permissions
        if request.user.is_staff and request.user.role and request.user.university:
            permissions = request.user.role.permissions
            if not isinstance(permissions, list) or not any(
                permission in ALL_PERMISSIONS for permission in permissions
            ):
                logger.warning(
                    "User %s denied admin access: assigned role '%s' has no active permissions",
                    request.user.email,
                    request.user.role.name,
                )
                return HttpResponseForbidden(
                    "Access denied. Your role has no active permissions."
                )

            request.scoped_university = request.user.university
            return self.get_response(request)

        # Everyone else: blocked
        logger.warning(
            "User %s attempted admin access without proper role "
            "(IP: %s, UA: %s)",
            request.user.email,
            request.META.get('REMOTE_ADDR', 'unknown'),
            request.META.get('HTTP_USER_AGENT', 'unknown'),
        )
        return HttpResponseForbidden(
            "Access denied. Administrator privileges required."
        )
    
    def _get_client_ip(self, request):
        """Extract client IP for logging"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')