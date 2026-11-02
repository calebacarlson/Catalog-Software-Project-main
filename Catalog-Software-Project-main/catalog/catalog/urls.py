"""
URL configuration for catalog project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views
from accounts.views import CustomLoginView, catalog_view
from django.conf import settings as s


def url_pattern(setting_url):
    """Convert '/app-admin/' to 'app-admin/'"""
    return setting_url.strip('/') + '/'


urlpatterns = [
    path(url_pattern(s.LOGIN_URL), CustomLoginView.as_view(template_name='login.html'), name='login'),
    path(url_pattern(s.LOGOUT_URL), views.LogoutView.as_view(next_page='login'), name='logout'),

    # Catalog views
    path('<slug:university_slug>/catalog/', catalog_view, name='catalog'),
    
    # Admin panels - both route to Django's admin.site
    # Middleware (AdminAccessMiddleware) enforces role-based access.
    # The <slug:university_slug> is captured for middleware scoping,
    # but admin.site.urls itself ignores it.
    path(url_pattern(s.SUPER_ADMIN_URL), admin.site.urls),
]
