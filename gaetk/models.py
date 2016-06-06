#!/usr/bin/env python
# encoding: utf-8
"""
models.py

LoggedModel is a base class for models with automatic logging.
An AuditLog instance is created for each create, update and delete action.
The AuditLog contains the user, ip address and timestamp.
Furthermore, the property changes are logged as a changelist.

There is no support for logging of read actions yet.


Created by Christian Klein on 2011-01-22.
Copyright (c) 2011 HUDORA. All rights reserved.
"""
import decimal
import os

from gaetk.lib._gaesessions import get_current_session
from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext import db


def get_current_user():
    """Helper function to return a valid User instance.

    For users logged in via OpenID, the result is equivalent to users.get_current_user.
    If the user logged in via Basic Auth, the user id is taken from the related Credential object.
    """
    user = users.get_current_user()
    if user is not None:
        return user
    else:
        session = get_current_session()
        if session and 'uid' in session:
            return users.User(_user_id=session['uid'], email=session.get('email', ''), _strict_mode=False)


class AuditLog(db.Model):
    """Log for a model instance"""

    object = db.ReferenceProperty(required=True)
    event = db.StringProperty(required=True, choices=set(['CREATE', 'UPDATE', 'DELETE']))
    initiator = db.UserProperty()
    ip_address = db.StringProperty()
    changelist = db.StringListProperty()
    created_at = db.DateTimeProperty(auto_now_add=True)

    @classmethod
    def create(cls, obj, event, changelist):
        """Create an AuditLog Entry."""

        instance = cls(parent=obj, object=obj, event=event, changelist=changelist)
        instance.initiator = get_current_user()
        instance.ip_address = os.getenv('REMOTE_ADDR')
        instance.put()
        return instance

    def delete(self, **kwargs):
        """AuditLogs are not supposed to be deleted

        This only prevents accidentally deletions.
        """
        raise NotImplementedError

    @classmethod
    def kind(cls):
        """Returns entity kind."""
        return "_gaetk_AuditLog"


class LoggedModel(db.Model):
    """Subclass of db.Model that logs all changes.
       Does not work, if you use db.put(instance)."""

    def put(self, **kwargs):
        """Writes the model instance to the datastore and creates an AuditLog entry"""

        # If the instance has not been saved yet, the related entity does not exist
        entity = self._entity
        if entity is None:
            event = 'CREATE'
            entity = {}
        else:
            event = 'UPDATE'

        # Compare the property values with the entity values and build a changelist
        changelist = []
        for prop in self.properties().values():
            # see http://code.google.com/intl/de-DE/appengine/docs/python/datastore/propertyclass.html for
            # documentation of get_value_for_datastore() and make_value_from_datastore()
            tmp = entity.get(prop.name)
            current_value = prop.make_value_from_datastore(tmp)
            tmp = prop.get_value_for_datastore(self)
            new_value = prop.make_value_from_datastore(tmp)

            # Empty lists are stored as None
            if isinstance(prop, (db.ListProperty, db.StringListProperty)):
                if current_value is None:
                    current_value = new_value
            elif isinstance(prop, blobstore.BlobReferenceProperty):
                # Nice to have, but missing: Compare BlobInfo
                current_value = new_value

            if current_value != new_value:
                if isinstance(prop, db.UnindexedProperty):
                    # Reduce logging output to 500 chars (max length for StringProperty)
                    if current_value and len(current_value) > 245:
                        current_value = "%s ..." % current_value[:244]
                    if len(new_value) > 245:
                        new_value = "%s ..." % new_value[:244]
                change = u'%s: %s \u21d2 %s' % (prop.name, current_value, new_value)
                changelist.append(change[:500])

        key = super(LoggedModel, self).put(**kwargs)
        if changelist:
            AuditLog.create(self, event, changelist)
        return key

    def delete(self, **kwargs):
        """Deletes this entity from the datastore and creates an AuditLog entry"""
        entity = self._entity
        if entity is None:
            entity = {}
        changelist = []
        for prop in self.properties().values():
            changelist.append(u'%s: %r' % (prop.name, entity.get(prop.name)))
        AuditLog.create(self, 'DELETE', changelist)
        super(LoggedModel, self).delete(**kwargs)

    @property
    def logentries(self, event=None):
        """Retrieve all logentries for the current object"""

        if not self.is_saved:
            return []

        queryset = AuditLog.all().filter('object =', self)
        if event is not None:
            queryset.filter('event =', event)
        return queryset


class DecimalProperty(db.Property):
    """A decimal property"""

    data_type = decimal.Decimal

    def validate(self, value):
        """Validate decimal property.

        Returns:
        A valid value.

        Raises:
        BadValueError if value is not an integer or long instance.
        """

        value = super(DecimalProperty, self).validate(value)

        # If value is the empty string, it's being converted to None
        if value == u'':
            value = None

        if value is None or isinstance(value, self.data_type):
            return value
        elif isinstance(value, (basestring, int, long)):
            return self.data_type(value)
        raise db.BadValueError("Property %s must be a Decimal or string." % self.name)

    def empty(self, value):
        """Is decimal property empty.

        0 is not an empty value.

        Returns:
          True if value is None, else False.
        """
        return value is None

    def get_value_for_datastore(self, model_instance):
        """Get value from property to send to datastore.

        Returns:
            Value of string representtion of decimal value
        """
        tmp = super(DecimalProperty, self).get_value_for_datastore(model_instance)
        if tmp is None:
            return None
        return str(tmp)

    def make_value_from_datastore(self, value):
        """Native representation of this property.

        We receive a string representation retrieved from the entity and return
        a decimal.Decimal instance.
        """
        if value is None:
            return value
        return self.data_type(value)
