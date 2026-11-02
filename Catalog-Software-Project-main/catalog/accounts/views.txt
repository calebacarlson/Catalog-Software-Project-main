from django.shortcuts import render, get_object_or_404, resolve_url
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.conf import settings as s
from .models import University
from django.http import HttpResponseForbidden
from .decorators import permission_required
import logging

logger = logging.getLogger(__name__)

class CustomLoginView(LoginView):
    template_name = 'login.html'
    
    def get_success_url(self):
        """
        Route authenticated users to their appropriate landing page.
        
        Priority order:
        1. Superuser → platform admin panel
        2. Campus admin (is_staff + role + university) → their campus admin
        3. Regular user with university → their catalog
        4. Orphaned/misconfigured user → login with error
        """
        user = self.request.user

        # Platform superuser → super admin panel
        if user.is_superuser:
            return resolve_url(s.SUPER_ADMIN_URL)

        # Campus admin → their specific campus admin panel
        # Requires: is_staff flag, assigned role, AND university
        # (Step 1's clean() validation enforces this combo, but defend anyway)
        if user.is_staff and user.role and user.university:
            return resolve_url(s.SUPER_ADMIN_URL)

        # Regular user with university → their catalog
        if user.university:
            return f'/{user.university.slug}/catalog/'

        # Orphaned user: authenticated but no university assigned
        # Shouldn't happen after Step 1's validation, but handle gracefully
        logger.warning(
            "User %s logged in with no university assigned; redirecting to login",
            user.email,
        )
        return resolve_url(s.LOGIN_URL) + '?error=no_university'

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

# Catalog management view
@login_required
@permission_required('catalog.edit')
def admin_catalog_view(request):
    return render(request, 'admin_catalog.html', {
        'university': request.user.university,
    })