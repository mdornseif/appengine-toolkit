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

from google.appengine.ext import db
from google.appengine.api import users

import decimal
import os


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
        instance.initiator = users.get_current_user()
        instance.ip_address = os.getenv('REMOTE_ADDR')
        instance.put()
        return instance

    def delete(self, **kwargs):
        """AuditLogs are not supposed to be deleted

        This only prevents accidentally deletions.
        """
        raise NotImplementedError


class LoggedModel(db.Model):
    """Subclass of db.Model that logs all changes"""

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
            current_value = entity.get(prop.name)
            new_value = getattr(self, prop.name, None)
            if current_value != new_value:
                if isinstance(prop, db.UnindexedProperty):
                    change = u'changed'
                else:
                    change = u'%r > %r' % (current_value, new_value)
                changelist.append(u'%s: %s' % (prop.name, change))

        super(LoggedModel, self).put(**kwargs)
        AuditLog.create(self, event, changelist)

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
        if not event is None:
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
