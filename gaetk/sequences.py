#!/usr/bin/env python

"""Google App Engine sequential number generator.

Generates sequences of numbers from a database of sequences, invaliding
sequences as they are allocated. The implementation guarantees there will be
no gap in the numbers returned if the requested amount of numbers fits into the
current sequence.

Integrity/consistency is carried out by a transaction. Due to App Engines
architecture, and the fact that only one sequence is allocated from at a time,
all allocations of numbers from the database will synchronise on the same
resource and the performance will be low - around 5-10 queries per second.

Performance could be achieved by a smart sharing setup. Rather than allocating
from a single Sequence at a time, there could be several shards which have
pre-allocated some amount of the Sequence (e.g. 100 of the sequence), and these
could be allocated from on an e.g. random basis, performing a sort of load
balancing of the transactions. This wouldn't necessarily guarantee a lack of
gaps, but as long as enough small queries are received (e.g. for 1 numbers)
over time the gaps will be filled.

To ensure correct allocation from one sequence to the next, sequences must be
in the same entity group. Practically, this means all sequences need to have
"parent" set: it's easiest to always set this to be the first sequence, though
it could be anything (e.g. a special SequenceRoot model could be created just
for this purpose to simplify the design perhaps).
"""

# Created 2010-01 by Sam Jansen for HUDORA

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext import db

class Sequence(db.Model):
    """Sequence of numbers, as contained in the spec."""
    start = db.IntegerProperty()
    end = db.IntegerProperty()
    current = db.IntegerProperty()
    active = db.BooleanProperty(default=False)
    deleted = db.BooleanProperty(default=False)
    created_at = db.DateTimeProperty(auto_now_add=True)

    def __str__(self):
        return ('Sequence: start=%d,end=%d,current=%s,active=%s,deleted=%s,'
            'created_at=%s') % (self.start, self.end, self.current,
                    self.active, self.deleted, self.created_at)


def get_numbers(count=1):
    """Returns a list of sequential numbers from the database."""

    def get_nums_from_db(keys, count):
        """Transaction to allocate numbers from a sequence."""
        results = []
        orig_count = count
        
        for key in keys:
            # pylint: disable-msg=E1103
            seq = db.get(key)

            if seq.current:
                start = seq.current
            else:
                start = seq.start

            end = seq.end
            avail = end - start
            consumed = count

            if avail <= count:
                seq.active = False
                consumed = avail

            seq.current = start + consumed
            seq.put()

            # pylint: enable-msg=E1103

            results += range(start, start + consumed)
            count -= consumed

            if count == 0:
                return results

        raise Exception('Not enough sequence space to allocate %d numbers.' %
                orig_count)

    query = db.GqlQuery(
            'SELECT * FROM Sequence '
            'WHERE active = TRUE '
            'ORDER BY start')
    rows = query.fetch(2)

    if rows:
        return db.run_in_transaction(get_nums_from_db,
                [r.key() for r in rows], count)
    else:
        raise Exception('No active sequences in database.')


class MainHandler(webapp.RequestHandler):
    """Handler for /, allocates numbers."""
    def get(self):
        """Allocates numbers and prints them in a plain textual form."""
        self.response.headers['Content-type'] = 'text/plain'

        # All a bit ugly, just a hack to make it easy to use
        try:
            num_required = int(self.request.get('num', default_value='1'))
        except ValueError:
            num_required = 1

        self.response.out.write('\n'.join([str(x) for x in
            get_numbers(num_required)]))


class StateHandler(webapp.RequestHandler):
    """Handler for /status, prints database status."""
    def get(self):
        """Prints the current database state in a human-readable form."""
        self.response.headers['Content-type'] = 'text/plain'

        query = db.GqlQuery(
            'SELECT * FROM Sequence '
            'ORDER BY start ')
        
        self.response.out.write('\n'.join([str(x) for x in query]))


def main():
    """Just creates a simple Google App Engine "wepapp" to show the use of the
    number allocation."""

    application = webapp.WSGIApplication(
            [('/', MainHandler),
             ('/status', StateHandler)],
            debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    # Some test code below to set up the database, uncomment for testing.
    #s = Sequence(start=0, end=100, active=True)
    #s.put()
    #Sequence(parent=s, start=1000, end=1010, active=True).put()
    #Sequence(parent=s, start=10100, end=10250, active=False).put()
    #Sequence(parent=s, start=10500, end=11000, active=True).put()
    #Sequence(parent=s, start=20000, end=100000, active=True).put()
    #Sequence(parent=s, start=30000, end=39999, active=False)
    #Sequence(parent=s, start=10000000, end=10049999, active=False)
    #Sequence(parent=s, start=10010000, end=10019999, active=False)
    main()

# vim: set sts=4 shiftwidth=4 :
