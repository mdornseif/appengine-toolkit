#!/usr/bin/env python
# encoding: utf-8
"""
helpers.py - smal view-helper-functions

Created by Maximillian Dornseif on 2016-12-15.
Copyright (c) 2016 Cyberlogi. All rights reserved.
"""

import gaetk.compat

from webob.exc import HTTPNotFound as HTTP404_NotFound

def get_object_or_404(model_class, key_id, message=None, **kwargs):
    """Get object by key name or raise HTTP404"""
    obj = gaetk.compat.get_by_id_or_name(model_class, key_id, **kwargs)
    if not obj:
        raise HTTP404_NotFound(message)
    return obj


def check404(obj, message='Objekt nicht gefunden.'):
    """Raises 404 if obj in None"""
    if not obj:
        raise HTTP404_NotFound(message)
    return obj
