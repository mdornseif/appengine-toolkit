"""Configuration for each AppEngine Instance"""

import config
config.imported = True

import os

import gae_mini_profiler.profiler
from gaetk.gaesessions import SessionMiddleware
COOKIE_KEY = '13f22fe71b26d13940626c0555787e4bf78f5fb26b8ffae123-5a17'


gaetk_replication_SQL_INSTANCE_NAME = 'huwawisql:qvexport-eu'
gaetk_replication_SQL_DATABASE_NAME = 'wwwhudorade2'
gaetk_replication_SQL_QUEUE_NAME = 'sqlq'

import cs.huwawi_local
cs.huwawi_local.activate_local()


def gae_mini_profiler_should_profile_production():
    """Force Profiling on certain Production Servers"""
    if os.environ.get('SERVER_NAME', '').startswith('dev'):
        from google.appengine.api import users
        return users.is_current_user_admin()
    return False


def webapp_add_wsgi_middleware(app):
    """Called with each WSGI handler initialisation """
    app = SessionMiddleware(app, cookie_key=COOKIE_KEY, ignore_paths='^/hua/.*')
    app = gae_mini_profiler.profiler.ProfilerWSGIMiddleware(app)
    return app
