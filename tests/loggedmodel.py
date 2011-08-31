#!/usr/bin/env python
# encoding: utf-8
"""
loggedmodell.py

Tests for gaetk.models.LoggedModel

Created by Chrstoph Borgolte on 2011-09-01.
Copyright (c) 2011 HUDORA GmbH. All rights reserved.
"""


from google.appengine.ext import db
import datetime
import decimal
import gaetk.models
import unittest
import logging
import pprint


class MyLoggedModel(gaetk.models.LoggedModel):
    """A simple LoggedModell containing some Properties."""

    dateprop = db.DateProperty()
    datetimeprop = db.DateTimeProperty()
    intprop = db.IntegerProperty()
    stringprop = db.StringProperty()
    stringlistprop = db.StringListProperty()
    textprop = db.TextProperty()



class LoggedModelTestCase(unittest.TestCase):
    """Testcase for LoggedModel"""

    def setUp(self):
        db.delete(gaetk.models.AuditLog.all(keys_only=True))
        db.delete(MyLoggedModel.all(keys_only=True))

    def test_changes(self):
        """Test Auditlog creation for changes of LoggedModel instances."""

        # create an instance
        instance = MyLoggedModel(
            dateprop = datetime.date(2011, 9, 1),
            datetimeprop = datetime.datetime(2011, 9, 1, 17, 01),
            intprop = 100,
            stringprop = u"üö@ß®†Ω«",
            stringlistprop = [u'abcdßü', u'®†∂©', u'12323'],
            textprop = u'this is a textproperty €®©üäö')
        instance.put()

        # one AuditLog instance should be created now.
        self.assertEqual(gaetk.models.AuditLog.all().count(), 1)
        al = gaetk.models.AuditLog.all().get()
        self.assertEqual(al.event, 'CREATE')

        # Check 'no changes'
        instance = MyLoggedModel.all().get()
        instance.put()
        # No additional AuditLogs should be created by this put()
        self.assertEqual(gaetk.models.AuditLog.all().count(), 1)

        # Check 'DateProperty'
        instance = MyLoggedModel.all().get()
        instance.dateprop = datetime.date(2010, 8, 26)
        instance.put()
        al = gaetk.models.AuditLog.all().filter('object =', instance).order('-created_at').get()
        self.assertEqual(al.changelist, [u'dateprop: 2011-09-01 \u21d2 2010-08-26'])
        self.assertEqual(al.event, 'UPDATE')

        # Check 'DateTimeProperty'
        instance = MyLoggedModel.all().get()
        instance.datetimeprop = datetime.datetime(2010, 8, 26, 2, 15)
        instance.put()
        al = gaetk.models.AuditLog.all().filter('object =', instance).order('-created_at').get()
        self.assertEqual(al.changelist, [u'datetimeprop: 2011-09-01 17:01:00 \u21d2 2010-08-26 02:15:00'])
        self.assertEqual(al.event, 'UPDATE')

        # Check 'StringListProperty'
        instance = MyLoggedModel.all().get()
        instance.stringlistprop = ['abcd', 'hkij']
        instance.put()
        al = gaetk.models.AuditLog.all().filter('object =', instance).order('-created_at').get()
        change = (u"stringlistprop: [u'abcd\\xdf\\xfc', u'\\xae\\u2020\\u2202\\xa9', u'12323'] "
                  u"\u21d2 ['abcd', 'hkij']")
        self.assertEqual(al.changelist,[change])
        self.assertEqual(al.event, 'UPDATE')

        # Check 'StringProperty'
        instance = MyLoggedModel.all().get()
        instance.stringprop += u'+='
        instance.put()
        al = gaetk.models.AuditLog.all().filter('object =', instance).order('-created_at').get()
        change = u'stringprop: \xfc\xf6@\xdf\xae\u2020\u03a9\xab \u21d2 \xfc\xf6@\xdf\xae\u2020\u03a9\xab+='
        self.assertEqual(al.changelist,[change])
        self.assertEqual(al.event, 'UPDATE')

        # Check 'TextProperty'
        instance = MyLoggedModel.all().get()
        instance.textprop += u'+='
        instance.put()
        al = gaetk.models.AuditLog.all().filter('object =', instance).order('-created_at').get()
        change = (u'textprop: this is a textproperty \u20ac\xae\xa9\xfc\xe4\xf6 '
                  u'\u21d2 this is a textproperty \u20ac\xae\xa9\xfc\xe4\xf6+=')
        self.assertEqual(al.changelist,[change])
        self.assertEqual(al.event, 'UPDATE')

    def test_changes_fail(self):
        """Documentation of misbehaviour for the LoggedModell.

        The following changes to an instance of LoggedModel do not create AuditLog entries, which is not the
        expected behaviour.
        """

        # create an instance
        instance = MyLoggedModel(
            dateprop = datetime.date(2011, 9, 1),
            datetimeprop = datetime.datetime(2011, 9, 1, 17, 01),
            intprop = 100,
            stringprop = u"üö@ß®†Ω«",
            stringlistprop = [u'abcdßü', u'®†∂©', u'12323'],
            textprop = u'this is a textproperty €®©üäö')
        instance.put()
        self.assertEqual(gaetk.models.AuditLog.all().count(), 1)

        # Check 'StringListProperty'
        instance = MyLoggedModel.all().get()
        instance.stringlistprop.append('this doesnt create an AuditLog entry')
        instance.put()
        self.assertEqual(gaetk.models.AuditLog.all().count(), 1)  # wrong: count() should result in 2
