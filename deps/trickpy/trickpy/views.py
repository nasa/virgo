from __future__ import absolute_import

import re
try:
    import collections.abc as collections_abc
except ImportError:
    import collections as collections_abc


class ListView(collections_abc.Sequence):
    """A view of a list-like object.

    Behaves like a read-only list.  It is a dynamic view of the original list
    object, in that if the original list changes, the view reflects the changes.

    Using a ListView avoids creating unnecessary copies of lists.  If you need
    an actual list, pass the view to the ``list`` builtin.

    Examples
    --------

    To create a view:

    >>> numbers = [0, 1, 2, 3, 4]
    >>> view = ListView(numbers)

    A view behaves like a read-only list:

    >>> len(view)
    5
    >>> 2 in view
    True
    >>> view[:2]
    [0, 1]
    >>> [x + 1 for x in view]
    [1, 2, 3, 4, 5]
    >>> view[3] = 10
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    AttributeError: 'ListView' object does not support item assignment
    >>> view.append(10)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    AttributeError: 'ListView' object has no attribute 'append'

    To create a list from a view:

    >>> list(view)
    [0, 1, 2, 3, 4]

    """

    def __init__(self, obj):
        """Initialize a new `ListView` object as a view of *obj*."""
        self._obj = obj

    def __len__(self):
        """Return the length of the viewed list."""
        return len(self._obj)

    def __getitem__(self, i):
        """Return the element of the viewed list at index *i*."""
        return self._obj[i]

    def __repr__(self):
        return "ListView({})".format(list(self))


class StringListView(ListView):
    """A view of a list-like object whose elements are strings.

    Examples
    --------

    >>> beatles = ['paul', 'ringo', 'john', 'george']
    >>> view = StringListView(beatles)

    To find the strings in the list that match a regular expression:

    >>> view.search(r'g.?o')
    ['ringo', 'george']

    """

    def search(self, regex):
        """Return a list of items that match *regex*.  If no items match, return an
        empty list.

        """
        prog = re.compile(regex)
        return [x for x in self if prog.search(x) is not None]

    def __repr__(self):
        return "StringListView({})".format(list(self))


class StringPairListView(ListView):
    """A view of a list-like object of pairs (2-tuples) of strings.

    Examples
    --------

    >>> pairs = [('paul', 'mccartney'), ('ringo', 'starr'), ('george', 'harrison'), ('john', 'lennon')]
    >>> view = StringPairListView(pairs)

    To find the pairs whose first or second string match a regular expression:

    >>> view.search(r'ar[rt]')
    [('paul', 'mccartney'), ('ringo', 'starr'), ('george', 'harrison')]

    """

    def search(self, regex):
        """Return a list of pairs (2-tuples) whose first or second string match *regex*.
        If no pairs match, return an empty list.

        """
        prog = re.compile(regex)
        return [x for x in self if prog.search(x[0]) is not None or prog.search(x[1]) is not None]

    def __repr__(self):
        return "StringPairListView({})".format(list(self))


class KeysView(collections_abc.KeysView, collections_abc.Hashable):

    __hash__ = collections_abc.Set._hash

    def __repr__(self):
        return "KeysView({})".format(list(self))


class ValuesView(collections_abc.ValuesView):

    def __repr__(self):
        return "ValuesView({})".format(list(self))


class ItemsView(collections_abc.ItemsView):

    def __repr__(self):
        return "ItemsView({})".format(list(self))
