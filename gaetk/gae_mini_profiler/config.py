from google.appengine.api import users

# Set to `False` if you don't use Django templates
enable_django_templatetags = False


# Customize should_profile to return true whenever a request should be profiled.
# This function will be run once per request, so make sure its contents are fast.
def should_profile(environ):
    # Never profile calls to the profiler itself to avoid endless recursion.
    if environ["PATH_INFO"].startswith("/gae_mini_profiler/"):
        return False
    if users.is_current_user_admin():
        return True
    if environ["HTTP_HOST"].split(':')[0] in ["127.0.0.1", "localhost"]:
        return True
    return False
