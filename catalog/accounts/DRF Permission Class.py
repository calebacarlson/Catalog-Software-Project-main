# Your middleware handles route-level gatekeeping. 
# DRF permissions handle action-level authorization within your API views.

# Block all access to /app-admin/* for non-superusers --- Middleware (you have this)
# Allow campus viewers to GET catalog items but not POST/DELETE --- DRF Permission Class
# Ensure users only see data from their own university --- DRF Permission Class 

# TODO: Implement this later