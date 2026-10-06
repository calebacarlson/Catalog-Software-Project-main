from django.contrib.auth import get_user_model

class MongoPermissionBackend:
    """
    Custom authentication and permission backend that operates 
    cleanly with MongoDB and our custom Role schema.
    """
    def authenticate(self, request, email=None, password=None, **kwargs):
        User = get_user_model()
        
        # Django's LoginView sends 'username', not 'email'
        if email is None:
            email = kwargs.get('username')
        
        if not email or not password:
            return None
        
        try:
            user = User.objects.get(email=email)
            if user.check_password(password) and user.is_active:
                return user
        except User.DoesNotExist:
            return None
        return None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def has_perm(self, user_obj, perm, obj=None):
        if not user_obj or not user_obj.is_active:
            return False
        return user_obj.has_perm(perm, obj)