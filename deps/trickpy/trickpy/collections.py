from __future__ import absolute_import

import os
import sys
import re
try:
    import collections.abc as collections_abc
except ImportError:
    import collections as collections_abc

from .views import KeysView, ValuesView, ItemsView, ListView


class Groups(collections_abc.Mapping):
    """A collection of groups.

    Maps the names of either data record or data collect groups to their
    associated objects.  Behaves like a read-only Python dictionary.

    Examples
    --------

    >>> data = dr.load_run('RUN_example')

    To check whether a group is in the collection:

    >>> 'group1' in data
    True

    Iterating over the collection iterates over the group names:

    >>> [g for g in data]
    ['group1', 'group2']

    The length of the collection is the number of groups:

    >>> len(data)
    2

    To search for group names that match a regular expression:

    >>> data.search(r'group')
    ['group1', 'group2']

    The group objects are accessed by indexing the collection with the group
    name:

    >>> data['group1']

    """

    def __init__(self, data):
        """Initialize a new `Groups` object.

        Parameters
        ----------

        data : dict
            A dictionary mapping group names to group objects.

        """
        self._data = data

    def __getitem__(self, name):
        """Return the group with *name*."""
        return self._data[name]

    def __iter__(self):
        """Return a new iterator over the group names."""
        return iter(self._data)

    def __len__(self):
        """Return the number of groups."""
        return len(self._data)

    def keys(self):
        """Return a new view of the keys, which are the group names.

        Returns
        -------

        `~trickpy.views.KeysView`

        """
        return KeysView(self)

    def values(self):
        """Return a new view of the values, which are the group objects.

        Returns
        -------

        `~trickpy.views.ValuesView`

        """
        return ValuesView(self)

    def items(self):
        """Return a new view of the items, which are ``(key, value)`` pairs.

        Returns
        -------

        `~trickpy.views.ItemsView`

        """
        return ItemsView(self)

    def search(self, regex):
        """Return a list of group names that match *regex*.  If no group names match,
        return an empty list.

        Returns
        -------

        list of str

        """
        prog = re.compile(regex)
        return [g for g in self if prog.search(g) is not None]


class Runs(collections_abc.Mapping):
    """A collection of runs.

    Maps run numbers to `Groups` objects.  Behaves like a read-only Python
    dictionary.

    The keys (run numbers) are guaranteed to be sorted in increasing order.

    Examples
    --------

    >>> data = dr.load_monte('MONTE_RUN_example')
    >>> data.keys()
    KeysView([0, 1, 2, 3, 4])

    To check whether a run is in the collection:

    >>> 3 in data
    True

    Iterating over the collection iterates over the run numbers:

    >>> [n for n in data]
    [0, 1, 2, 3, 4]

    The length of the collection is the number of runs:

    >>> len(data)
    5

    The `Groups` objects are accessed by indexing with the run numbers:

    >>> data[3]

    """

    def __init__(self, data):
        """Initialize a new `Runs` object.

        Parameters
        ----------

        data : dict
            A dictionary mapping run numbers to `Groups` objects.

        """
        self._run_numbers = sorted(data)
        self._data = data

    def __getitem__(self, run_number):
        """Return the `Groups` object for *run_number*.

        Returns
        -------

        `Groups`

        """
        return self._data[run_number]

    def __iter__(self):
        """Return a new iterator over the run numbers."""
        return iter(self._run_numbers)

    def __len__(self):
        """Return the number of runs."""
        return len(self._run_numbers)

    def keys(self):
        """Return a new view of the keys, which are the run numbers.

        Returns
        -------

        `~trickpy.views.KeysView`

        """
        return KeysView(self)

    def values(self):
        """Return a new list of the values, which are `Groups` objects.

        Returns
        -------

        `~trickpy.views.ValuesView`

        """
        return ValuesView(self)

    def items(self):
        """Return a new view of the items, which are ``(key, value)`` pairs.

        Returns
        -------

        `~trickpy.views.ItemsView`

        """
        return ItemsView(self)
