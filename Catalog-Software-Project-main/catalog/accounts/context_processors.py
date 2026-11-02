"""
Template context processors for the accounts app.

Context processors inject variables into every template's context,
avoiding the need for each view to pass common data explicitly.
"""


def scoped_university(request):
    """
    Expose the current request's scoped university to all templates.
    
    Set by AdminAccessMiddleware when the request path matches 
    /campus-admin/<slug>/. None for superuser admin and non-admin pages.
    
    Used by admin/base_site.html to display tenant-aware branding.
    """
    return {
        'scoped_university': getattr(request, 'scoped_university', None),
    }