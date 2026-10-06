from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.shortcuts import resolve_url
from django.conf import settings as s

# Any authenticated user
@login_required
def catalog_view(request):
    return render(request, 'catalog.html')

# Admin only
@user_passes_test(lambda u: u.is_staff)
def admin_catalog_view(request):
    return render(request, 'admin_catalog.html')

class CustomLoginView(LoginView):
    template_name = 'login.html'
    
    def get_success_url(self):
        user = self.request.user
        
        if user.is_superuser:
            return resolve_url(s.SUPER_ADMIN_URL)
        elif user.university and self._is_university_admin(user):
            # Redirect to THEIR university's campus admin
            return resolve_url(f'{s.CAMPUS_ADMIN_URL}{user.university.slug}/')
        else:
            return resolve_url(s.CATALOG_MAIN_URL)
    
    def _is_university_admin(self, user):
        return user.is_campus_admin

    # ALTERNATIVE: Role-Based
    # def get_success_url(self):
    # if self.request.user.is_superuser:
    #     return '/admin/'
    # elif self.request.user.is_staff:
    #     return '/staff-dashboard/'
    # else:
    #     return '/catalog/'

    # ALTERNATIVE: Permission-Based
    # def get_success_url(self):
    # user = self.request.user
    # if user.has_perm('catalog.manage_catalog'):
    #     return '/admin/'
    # else:
    #     return '/catalog/'