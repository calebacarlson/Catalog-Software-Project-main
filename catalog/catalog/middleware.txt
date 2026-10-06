from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.conf import settings as s
import logging

logger = logging.getLogger(__name__)


class AdminAccessMiddleware:
    """
    Enforces access control for admin panels:
    - /app-admin/: Platform superusers only
    - /campus-admin/: University admins (is_staff and has university admin role)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Platform admin - superusers only
        if hasattr(s, 'SUPER_ADMIN_URL') and path.startswith(s.SUPER_ADMIN_URL):
            return self._enforce_superuser_access(request)

        # Campus admin - university admins only
        if hasattr(s, 'CAMPUS_ADMIN_URL') and path.startswith(s.CAMPUS_ADMIN_URL):
            return self._enforce_campus_admin_access(request)

        return self.get_response(request)

    def _enforce_superuser_access(self, request):
        """Only is_superuser can access platform superadmin panel"""
        if not request.user.is_authenticated:
            return redirect(f"{s.LOGIN_URL}?next={request.path}")

        if not request.user.is_superuser:
            return HttpResponseForbidden(
                "Access denied. Platform administrator privileges required."
            )

        return self.get_response(request)

    def _enforce_campus_admin_access(self, request):
        """Verify user belongs to AND has admin rights for the specific university"""
        if not request.user.is_authenticated:
            return redirect(f"{s.LOGIN_URL}?next={request.path}")

        # Superusers can access any campus
        if request.user.is_superuser:
            return self.get_response(request)

        # Extract university slug from URL: /campus-admin/<slug>/...
        university_slug = self._extract_university_slug(request.path)

        if not university_slug:
            return HttpResponseForbidden("Invalid campus admin URL.")

        # Verify user belongs to THIS university
        if not self._user_belongs_to_university(request.user, university_slug):
            return HttpResponseForbidden(
                "Access denied. You do not belong to this university."
            )

        # Verify user has admin role at THIS university
        if not self._is_university_admin(request.user, university_slug):
            return HttpResponseForbidden(
                "Access denied. University administrator privileges required."
            )

        return self.get_response(request)

    def _extract_university_slug(self, path):
        """Helper to safely extract the university slug from path."""
        prefix = getattr(s, 'CAMPUS_ADMIN_URL', '/campus-admin/')
        stripped = path[len(prefix):].strip('/')
        parts = stripped.split('/')
        return parts[0] if parts and parts[0] else None

    def _user_belongs_to_university(self, user, university_slug):
        """Check if user is assigned to this specific university"""
        if not user.university:
            return False
        return user.university.slug == university_slug

    def _is_university_admin(self, user, university_slug):
        """
        Check if user has admin role at this specific university.
        Compatible with our MongoDB Role model.
        """
        if not user.university or user.university.slug != university_slug:
            return False
        
        # User must have an active admin-tier role
        return user.is_campus_admin

    def _get_client_ip(self, request):
        """Extract client IP for logging"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')