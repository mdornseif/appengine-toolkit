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

Example::

    init_sequence('test', start=1000, end=1003)
    init_sequence('other', start=1005, end=1010)
    init_sequence('test', start=10100, end=10250)
    get_numbers('test', 5)
    [1000, 1001, 1002, 10100, 10101]

"""

# Performance could be achieved by a smart sharing setup. Rather than allocating
# from a single Sequence at a time, there could be several shards which have
# pre-allocated some amount of the Sequence (e.g. 100 of the sequence), and these
# could be allocated from on an e.g. random basis, performing a sort of load
# balancing of the transactions. This wouldn't necessarily guarantee a lack of
# gaps, but as long as enough small queries are received (e.g. for 1 numbers)
# over time the gaps will be filled.
# 
# To ensure correct allocation from one sequence to the next, sequences must be
# in the same entity group. Practically, this means all sequences need to have
# "parent" set. init_sequence() ensures this.
#
# See http://stackoverflow.com/questions/3985812 for a general discussion of the
# problem space.
# 
# Created 2010-11 by Sam Jansen for HUDORA

# pylint: disable-msg=E1103


from google.appengine.ext import db


class gaetkSequence(db.Model):
    """Sequence of numbers, as contained in the spec."""
    type = db.StringProperty()      # to differentiate betwwen dirrerent types (invoices, consignments, ...)
    start = db.IntegerProperty()    # fist number to be allocated
    end = db.IntegerProperty()      # first number to be ot allocated -> [start ; end [
    current = db.IntegerProperty()  # this is currentliy selected for allocation
    active = db.BooleanProperty(default=False)  # this can be selected for allocation
    created_at = db.DateTimeProperty(auto_now_add=True)

    def __repr__(self):
        return ('<gaetkSequence: type=%s, start=%d, end=%d, current=%s, active=%s, '
            'created_at=%s>') % (self.type, self.start, self.end, self.current,
                    self.active, self.created_at)


def _init_sequence_helper(typ, start, end, root):
    # ensure there are no overlapping ranges
    query1 = gaetkSequence.all().ancestor(root).filter('type = ', typ).filter(
                'start >= ', start).filter('start <', end).fetch(1)
    query2 = gaetkSequence.all().ancestor(root).filter('type = ', typ).filter(
                'end >= ', start).filter('end <', end).fetch(1)
    if query1 or query2:
        raise ValueError('%d:%d overlaps with %s/%s' % (start, end, query1, query2))
    seq = gaetkSequence(type=typ, parent=root, start=start, end=end, active=True)
    seq.put()
    return seq


def init_sequence(typ, start, end):
    assert start < end
    root = gaetkSequence.get_by_key_name('_%s_root' % typ)
    if not root:
        root = gaetkSequence.get_or_insert('_%s_root' % typ, type='_root', start=0, end=1, active=False)
    return db.run_in_transaction(_init_sequence_helper, typ, start, end, root.key())


def _get_numbers_helper(keys, needed):
    """Transaction to allocate numbers from a sequence."""
    results = []
    
    for key in keys:
        seq = db.get(key)
        start = seq.current or seq.start
        end = seq.end
        avail = end - start
        consumed = needed

        if avail <= needed:
            seq.active = False
            consumed = avail
        seq.current = start + consumed
        seq.put()

        results += range(start, start + consumed)
        needed -= consumed

        if needed == 0:
            return results

    raise RuntimeError('Not enough sequence space to allocate %d numbers.' % needed)


def get_numbers(typ, needed):
    """Returns a list of sequential numbers from the database."""

    query = gaetkSequence.all(keys_only=True).filter('type = ', typ).filter('active = ', True).order('start')
    rows = query.fetch(5)
    if rows:
        return db.run_in_transaction(_get_numbers_helper, rows, needed)
    else:
        raise Exception('No active sequences in database.')
