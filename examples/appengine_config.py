"""Configuration for each AppEngine Instance"""

import config
config.imported = True

import gaetk.gae_mini_profiler.middleware
from gaetk.gaesessions import SessionMiddleware
COOKIE_KEY = '%%PUT_RANDOM_VALUE_HERE%%'


def webapp_add_wsgi_middleware(app):
    """Called with each WSGI handler initialisation """
    app = SessionMiddleware(app, cookie_key=COOKIE_KEY)
    # for https://github.com/kamens/gae_mini_profiler
    app = gaetk.gae_mini_profiler.middleware.ProfilerWSGIMiddleware(app)
    return app

