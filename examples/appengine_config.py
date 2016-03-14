"""Configuration for each AppEngine Instance"""

import config

import logging
import os

# import cs.huwawi_local
import gae_mini_profiler.profiler

from gaetk import gaesessions
from google.appengine.ext import vendor

vendor.add('lib/site-packages')

config.imported = True
logging.captureWarnings(True)

# cs.huwawi_local.activate_local()

COOKIE_KEY = '%%PUT_RANDOM_VALUE_HERE%%'


# gaetk_replication_SQL_INSTANCE_NAME = 'huwawisql:qvexport-eu'
# gaetk_replication_SQL_DATABASE_NAME = 'wwwhudorade23'
# gaetk_replication_SQL_QUEUE_NAME = 'sqlq'

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
