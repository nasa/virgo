"""Load FAST and ANTARES data collect files.

Examples
--------

The examples in this module assume `trickpy.data_collect` has been imported as:

  >>> import trickpy.data_collect as dc

To load a data collect file, do:

  >>> data = dc.load_file("/path/to/data_collect_file.h5")

To get the values for a condition and variable pair, do:

  >>> values = data.values(condition="condition name", variable="variable name")

And to get the times for a condition and variable pair, do:

  >>> times = data.times(condition="condition name", variable="variable name")

To load all of the data collect files in a RUN directory, do:

  >>> data = dc.load_run("/path/to/RUN_directory")

To load all of the data collect files at the top level of a MONTE directory, do:

  >>> data = dc.load_monte("/path/to/MONTE_directory")

And to load all of the data collect files from the RUN directories of a MONTE
directory, do:

  >>> data = dc.load_monte_runs("/path/to/MONTE_directory")

Notes
-----

If the h5py module is installed, TrickPy can load FAST data collect files and
multiGROUP data collect files.  If the scipy module is installed, TrickPy can
load multiMONTE data collect files.

A data collect group corresponds to a file.  There are several different file
name conventions in use.  To map a file name to a group name, the extension and
prefix are removed.  For example, if the file name were
``data_collect_orion.h5``, the group name would be "orion".

"""

import os
import numpy as np
import warnings
import re

from .variable import Variable
from .views import ListView, StringListView, StringPairListView, KeysView, ValuesView, ItemsView
from . import loaders
from .summaries import print_files_summary, print_runs_summary
from . import collections
from . import paths

try:
    import h5py
except ImportError:
    h5py = None

try:
    import scipy.io
except ImportError:
    scipy = None


_dc_file_re = re.compile(r"^(MONTE_)?data_collect(ion)?_(?P<group_name>.+)\.(h5|mat|MAT)$")


def _is_data_collect_file(path):
    """Return ``True`` if *path* is some kind of data collect file."""
    m = _dc_file_re.match(path.name)
    if m:
        if path.is_file():
            return True
    return False


def _parse_group_name(path):
    """Parse the group name from a data collect file *path*."""
    m = _dc_file_re.match(path.name)
    if m:
        return m.group("group_name")
    raise Exception("unable to parse group name")


def _is_fast_dense_file(f):
    """Return ``True`` if the data collect file is in the FAST dense format."""
    return "conditions" in f


def _is_antares_dense_file(f):
    """Return ``True`` if the data collect file is in the ANTARES dense format."""
    return "condition_name" in f and "index_CONDVAR" not in f


def _is_multi_group_file(f):
    """Return ``True`` if the data collect file is in the multiGROUP format."""
    return "index_CONDVAR" in f


class _ShouldLoadPair(object):

    def __init__(self, requested_conditions, requested_variables, requested_pairs):
        self.predicates = []

        if requested_conditions is not None:
            self.requested_conditions = set(requested_conditions)
            self.predicates.append(self.by_requested_conditions)

        if requested_variables is not None:
            self.requested_variables = set(requested_variables)
            self.predicates.append(self.by_requested_variables)

        if requested_pairs is not None:
            self.requested_pairs = set(requested_pairs)
            self.predicates.append(self.by_requested_pairs)

    def by_requested_conditions(self, condition, variable):
        return condition in self.requested_conditions

    def by_requested_variables(self, condition, variable):
        return variable in self.requested_variables

    def by_requested_pairs(self, condition, variable):
        return (condition, variable) in self.requested_pairs

    def __call__(self, condition, variable):
        """Return `True` if the *condition*, *variable* pair should be loaded."""
        for p in self.predicates:
            if p(condition, variable):
                return True
        return False


def _pair_indices_to_load(conditions, variables, condition_indices, variable_indices, requested_conditions, requested_variables, requested_pairs):
    """Return a 1-D NumPy array of pair indices to load."""
    conditions = np.asarray(conditions).reshape((-1,))
    variables = np.asarray(variables).reshape((-1,))
    condition_indices = np.asarray(condition_indices).reshape((-1,))
    variable_indices = np.asarray(variable_indices).reshape((-1,))

    should_load = np.zeros_like(condition_indices, dtype=bool)

    if requested_conditions is not None:
        requested_condition_indices = np.nonzero(np.isin(conditions, requested_conditions))[0]
        should_load = np.logical_or(should_load,
                                    np.isin(condition_indices, requested_condition_indices))

    if requested_variables is not None:
        requested_variable_indices = np.nonzero(np.isin(variables, requested_variables))[0]
        should_load = np.logical_or(should_load,
                                    np.isin(variable_indices, requested_variable_indices))

    if requested_pairs is not None:
        requested_pair_indices = [(ic, iv)
                                  for (ic, c) in enumerate(conditions)
                                  for (iv, v) in enumerate(variables)
                                  if (c, v) in requested_pairs]
        should_load = np.logical_or(should_load,
                                    [(ic, iv) in requested_pair_indices
                                     for (ic, iv) in zip(condition_indices, variable_indices)])

    return np.nonzero(should_load)[0]


class GroupInfo(object):
    """Information about a generic data collect group.

    Examples
    --------

    >>> info = dc.load_file_info('MONTE_RUN_example/data_collect_example.h5')

    To get a view of the conditions in the group:

    >>> info.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])

    To get a view of the variables in the group:

    >>> info.variables()
    StringListView(['altitude', 'altitude_rate'])

    The view objects are like read-only lists.  They also support searching by
    regular expression.

    >>> 'drogue_deploy' in info.conditions()
    True
    >>> len(info.conditions())
    3
    >>> info.conditions().search(r'deploy')
    ['drogue_deploy', 'main_deploy']

    To create a new mutable list from the view:

    >>> list(conditions)
    ['drogue_deploy', 'main_deploy', 'touchdown']

    """

    def __init__(self, path, conditions, variables, units):
        """Initialize a new `GroupInfo` object.

        Parameters
        ----------

        path : path-like
        conditions : numpy.ndarray of str
        variables : numpy.ndarray of str
        units : numpy.ndarray of str

        """
        self._path = path
        self._conditions = conditions
        self._variables = variables
        self._units = units

    def _condition_index(self, condition):
        """Return the index of *condition*."""
        try:
            return np.where(self._conditions.flat == condition)[0][0]
        except IndexError:
            raise ValueError("file does not contain condition: {}".format(condition))

    def _variable_index(self, variable):
        """Return the index of *variable*."""
        try:
            return np.where(self._variables.flat == variable)[0][0]
        except IndexError:
            raise ValueError("file does not contain variable: {}".format(variable))

    def conditions(self):
        """Return a new view of the condition names.

        Returns
        -------

        `~trickpy.views.StringListView`

        """
        return StringListView(self._conditions.flat)

    def variables(self):
        """Return a new view of the variable names.

        Returns
        -------

        `~trickpy.views.StringListView`

        """
        return StringListView(self._variables.flat)

    def __bool__(self):
        """Return ``True`` if there is at least one condition and at least one
        variable.

        """
        return self._conditions.size > 0 and self._variables.size > 0

    __nonzero__ = __bool__


class DenseGroupInfo(GroupInfo):
    """Information about a dense data collect group.

    Examples
    --------

    >>> info = dc.load_file_info('MONTE_RUN_example/data_collect_example.h5')

    Inherits from `GroupInfo`:

    >>> info.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> info.variables()
    StringListView(['altitude', 'altitude_rate'])

    To get a view of the condition/variable pairs in the group:

    >>> info.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('drogue_deploy', 'altitude_rate'), ('main_deploy', 'altitude'), ('main_deploy', 'altitude_rate'), ('touchdown', 'altitude'), ('touchdown', 'altitude_rate')])

    To check if a particular condition/variable pair is in the group:

    >>> info.has_pair('drogue_deploy', 'altitude')
    True

    """

    def pairs(self):
        """Return a new view of the condition/variable pairs.

        Returns
        -------

        `~trickpy.views.StringPairListView`

        """
        return StringPairListView([(c, v) for c in self._conditions.flat for v in self._variables.flat])

    def has_pair(self, condition, variable):
        """Return True if the data collect group contains the pair of *condition* and
        *variable*.

        Returns
        -------

        bool

        """
        return condition in self._conditions and variable in self._variables


class SparseGroupInfo(GroupInfo):
    """Information about a sparse data collect group.

    Examples
    --------

    >>> info = dc.load_file_info('MONTE_RUN_example/data_collect_example.h5')

    Inherits from `GroupInfo`:

    >>> info.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> info.variables()
    StringListView(['altitude', 'altitude_rate'])

    To get a view of the condition/variable pairs in the group:

    >>> info.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('main_deploy', 'altitude'), ('touchdown', 'altitude_rate')])

    To check if a particular condition/variable pair is in the group:

    >>> info.has_pair('drogue_deploy', 'altitude')
    True

    """

    def __init__(self, path, conditions, variables, units, index_condvar):
        """Initialize a new `SparseGroupInfo` object.

        Parameters
        ----------

        path : path-like
        conditions : numpy.ndarray of str
        variables : numpy.ndarray of str
        units : numpy.ndarray of str
        index_condvar : np.ndarray
            A 2D array of 0-based indices.  The first row is the condition
            index, and the second is the variable index.  The column index
            corresponds to the pair.

        """
        GroupInfo.__init__(self, path, conditions, variables, units)
        self._index_condvar = index_condvar
        self._pairs = None

    def pairs(self):
        """Return a new view of the condition/variable pairs.

        Returns
        -------

        `~trickpy.views.StringPairListView`

        """
        return StringPairListView([(self._conditions.flat[ic], self._variables.flat[iv]) for ic, iv in zip(self._index_condvar[0, :], self._index_condvar[1, :])])

    def _pair_index(self, condition_index, variable_index):
        """Return the index corresponding to the pair with indices *condition_index* and
        *variable_index*.

        """
        try:
            return np.where(np.logical_and(self._index_condvar[0, :] == condition_index,
                                           self._index_condvar[1, :] == variable_index))[0][0]
        except IndexError:
            raise ValueError("condition/variable pair not in group")

    def has_pair(self, condition, variable):
        """Return True if the data collect group contains the pair of *condition* and
        *variable*.

        Returns
        -------

        bool

        """
        try:
            icon = self._condition_index(condition)
            ivar = self._variable_index(variable)
            ipair = self._pair_index(icon, ivar)
            return True
        except ValueError:
            return False

    def __bool__(self):
        """Return ``True`` if there is at least one condition/variable pair."""
        return bool(self._index_condvar.size > 0)

    __nonzero__ = __bool__


class DeprecatedGroupInterface(object):

    def get_values(self, condition, variable):
        warnings.warn("deprecated, use `values`", Warning, stacklevel=2)
        return self.values(condition, variable)

    def get_times(self, condition, variable):
        warnings.warn("deprecated, use `times`", Warning, stacklevel=2)
        return self.times(condition, variable)


class FASTDenseGroupInfo(DenseGroupInfo):
    """Information about a data collect group in the FAST dense format.

    Examples
    --------

    >>> info = dc.load_file_info('MONTE_RUN_example/data_collect_example.h5')

    Inherits from `DenseGroupInfo`:

    >>> info.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> info.variables()
    StringListView(['altitude', 'altitude_rate'])
    >>> info.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('drogue_deploy', 'altitude_rate'), ('main_deploy', 'altitude'), ('main_deploy', 'altitude_rate'), ('touchdown', 'altitude'), ('touchdown', 'altitude_rate')])
    >>> info.has_pair('drogue deploy', 'altitude')
    True

    To get a view of the list of run numbers:

    >>> info.runs()
    ListView([0, 1, 2])

    """

    def __init__(self, path, conditions, variables, units, runs):
        """Initialize a new `FASTDenseGroupInfo` object.

        Parameters
        ----------

        path : path-like
        conditions : numpy.ndarray of str
        variables : numpy.ndarray of str
        units : numpy.ndarray of str
        runs : numpy.ndarray of int

        """
        DenseGroupInfo.__init__(self, path, conditions, variables, units)
        self._runs = runs

    def runs(self):
        """Return a new view of the Monte Carlo run numbers.

        Returns
        -------

        `~trickpy.views.ListView`

        """
        runs = getattr(self, '_runs', None)
        if runs is None:
            raise Exception("group does not contain runs information")
        return ListView(runs)


class FASTDenseGroup(FASTDenseGroupInfo, DeprecatedGroupInterface):
    """A data collect group in the FAST dense format.

    Examples
    --------

    >>> data = dc.load_file('MONTE_RUN_example/data_collect_example.h5')

    Inherits from `FASTDenseGroupInfo`:

    >>> data.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> data.variables()
    StringListView(['altitude', 'altitude_rate'])
    >>> data.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('drogue_deploy', 'altitude_rate'), ('main_deploy', 'altitude'), ('main_deploy', 'altitude_rate'), ('touchdown', 'altitude'), ('touchdown', 'altitude_rate')])
    >>> data.has_pair('drogue deploy', 'altitude')
    True
    >>> data.runs()
    ListView([0, 1, 2])

    To get the values and times from a condition/variable pair:

    >>> data.values('drogue_deploy', 'altitude')
    Variable([12013.0, 12007.0, 12021.0], 'ft')
    >>> data.times('drogue_deploy', 'altitude')
    Variable([121.0, 123.0, 119.0], 's')

    """

    def __init__(self, path, conditions, variables, units, runs, times, values):
        """Initialize a new `FASTDenseGroup` object.

        Parameters
        ----------

        path : path-like
        conditions : numpy.ndarray of str
        variables : numpy.ndarray of str
        units : numpy.ndarray of str
        runs : numpy.ndarray of int
        times : numpy.ndarray
        values : numpy.ndarray

        """
        FASTDenseGroupInfo.__init__(self, path, conditions, variables, units, runs)
        self._times = times
        self._values = values

    def values(self, condition, variable):
        """Return a new read-only view of the values corresponding to the *condition*
        and *variable*.

        If the data is from a Monte Carlo, then the output is an array of the
        values for each run.  If the data is from a single run, then the output
        is the scalar value for that run.

        Returns
        -------

        `~trickpy.variable.Variable`

        """

        # FAST stores the data in (condition, variable) format for single runs
        # and (condition, variable, run) format for Monte Carlos

        icon = self._condition_index(condition)
        ivar = self._variable_index(variable)

        return Variable(self._values[icon, ivar, ...], self._units[ivar], copy=False, readonly=True)

    def times(self, condition, variable):
        """Return a new read-only view of the times corresponding to the *condition* and
        *variable*.

        If the data is from a Monte Carlo, then the output is an array of the
        times for each run.  If the data is from a single run, then the output
        is the scalar time for that run.

        Returns
        -------

        `~trickpy.variable.Variable`

        """

        # FAST stores the data in (condition, variable) format for single runs
        # and (condition, variable, run) format for Monte Carlos

        icon = self._condition_index(condition)
        ivar = self._variable_index(variable)

        return Variable(self._times[icon, ivar, ...], "s", copy=False, readonly=True)

    def _combine(self, groups, runs):
        monte_directory = os.path.dirname(os.path.dirname(self._path.path))
        file_name = self._path.name
        path = os.path.join(monte_directory, file_name)

        conditions = self._conditions
        variables = self._variables
        units = self._units

        values = np.stack([g._values for g in groups], axis=-1)
        times = np.stack([g._times for g in groups], axis=-1)

        return FASTDenseGroup(path, conditions, variables, units, runs, times, values)

    def save(self, directory=None):
        """Save the group to a file.

        Parameters
        ----------

        directory : str, optional
            The directory in which to save the data.  The full path is created
            by combining the provided directory with the base name of the path
            provided at construction.  If ``None``, use the path provided at
            construction without overriding the directory.  Default is ``None``.

        """
        if directory is None and isinstance(self._path, paths.TarFilePath):
            raise Exception("can't save to a tar file, you must specify the directory argument")
        if directory is None:
            path = str(self._path)
        else:
            path = os.path.join(directory, self._path.name)
        with h5py.File(path, "w") as f:
            vlen_bytes_dtype = h5py.special_dtype(vlen=bytes)
            f.create_dataset("conditions", data=np.char.encode(self._conditions), dtype=vlen_bytes_dtype)
            f.create_dataset("variables", data=np.char.encode(self._variables), dtype=vlen_bytes_dtype)
            f.create_dataset("units", data=np.char.encode(self._units), dtype=vlen_bytes_dtype)

            if self._runs is not None:
                f.create_dataset("runs", data=self._runs)

            if self._times.ndim == 3:
                f.create_dataset("times", data=self._times, chunks=(1, 1, self._times.shape[2]), compression="gzip")
            elif self._times.ndim == 2:
                f.create_dataset("times", data=self._times, chunks=(1, self._times.shape[1]), compression="gzip")
            else:
                raise Exception("bad times shape")

            if self._values.ndim == 3:
                f.create_dataset("values", data=self._values, chunks=(1, 1, self._values.shape[2]), compression="gzip")
            elif self._values.ndim == 2:
                f.create_dataset("values", data=self._values, chunks=(1, self._times.shape[1]), compression="gzip")
            else:
                raise Exception("bad values shape")


def _read_fast_dense_meta(f):
    """Read the metadata from a data collect file in the FAST dense format."""

    conditions = np.char.decode(f["conditions"][...].astype(bytes))
    variables = np.char.decode(f["variables"][...].astype(bytes))
    units = np.char.decode(f["units"][...].astype(bytes))
    if "runs" in f:
        runs = f["runs"][...]
    else:
        runs = None
    return conditions, variables, units, runs


def _read_fast_dense_info(f, path):
    """Load information about a data collect file in the FAST dense format."""
    conditions, variables, units, runs = _read_fast_dense_meta(f)
    return FASTDenseGroupInfo(path, conditions, variables, units, runs)


def _read_fast_dense(f, path, conditions, variables, pairs):
    """Load a data collect file in the FAST dense format."""
    all_conditions, all_variables, all_units, runs = _read_fast_dense_meta(f)

    if conditions is None and variables is None and pairs is None:
        times = f["times"][...]
        values = f["values"][...]
        return FASTDenseGroup(path,
                              all_conditions,
                              all_variables,
                              all_units,
                              runs,
                              times,
                              values)
    else:
        loaded_conditions = []
        loaded_variables = []
        loaded_units = []
        times = []
        values = []
        index_condvar = []
        times_dset = f["times"]
        values_dset = f["values"]
        should_load_pair = _ShouldLoadPair(conditions, variables, pairs)
        for ic, c in enumerate(all_conditions.flat):
            for iv, (v, u) in enumerate(zip(all_variables.flat, all_units.flat)):
                if should_load_pair(c, v):
                    if c not in loaded_conditions:
                        loaded_conditions.append(c)
                    if v not in loaded_variables:
                        loaded_variables.append(v)
                        loaded_units.append(u)
                    jc = loaded_conditions.index(c)
                    jv = loaded_variables.index(v)
                    index_condvar.append((jc, jv))
                    times.append(times_dset[ic, iv, ...])
                    values.append(values_dset[ic, iv, ...])
        loaded_conditions = np.array(loaded_conditions)
        loaded_variables = np.array(loaded_variables)
        loaded_units = np.array(loaded_units)
        index_condvar = np.array(index_condvar).T
        times = np.array(times).T
        values = np.array(values).T
        if runs is None:
            runs = np.array([], dtype=int)
        return MultiGroupGroup(path,
                               loaded_conditions,
                               loaded_variables,
                               loaded_units,
                               index_condvar,
                               runs,
                               times,
                               values)


class ANTARESDenseGroupInfo(DenseGroupInfo):
    """Information about a data collect group in the ANTARES dense format.

    Examples
    --------

    >>> info = dc.load_file_info('MONTE_RUN_example/data_collect_example.h5')

    Inherits from `DenseGroupInfo`:

    >>> info.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> info.variables()
    StringListView(['altitude', 'altitude_rate'])
    >>> info.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('drogue_deploy', 'altitude_rate'), ('main_deploy', 'altitude'), ('main_deploy', 'altitude_rate'), ('touchdown', 'altitude'), ('touchdown', 'altitude_rate')])
    >>> info.has_pair('drogue_deploy', 'altitude')
    True

    """
    pass


class ANTARESDenseGroup(ANTARESDenseGroupInfo, DeprecatedGroupInterface):
    """A data collect group in the ANTARES dense format.

    Examples
    --------

    >>> data = dc.load_file('MONTE_RUN_example/data_collect_example.h5')

    Inherits from `ANTARESDenseGroupInfo`:

    >>> data.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> data.variables()
    StringListView(['altitude', 'altitude_rate'])
    >>> data.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('drogue_deploy', 'altitude_rate'), ('main_deploy', 'altitude'), ('main_deploy', 'altitude_rate'), ('touchdown', 'altitude'), ('touchdown', 'altitude_rate')])
    >>> data.has_pair('drogue_deploy', 'altitude')
    True

    To get the values and times from a condition/variable pair:

    >>> data.values('drogue_deploy', 'altitude')
    Variable(12013.0, 'ft')
    >>> data.times('drogue_deploy', 'altitude')
    Variable(121.0, 's')

    """

    def __init__(self, path, conditions, variables, units, times, values):
        """Initialize a new `ANTARESDenseGroup` object.

        Parameters
        ----------

        path : path-like
        conditions : numpy.ndarray of str
        variables : numpy.ndarray of str
        units : numpy.ndarray of str
        times : numpy.ndarray
        values : numpy.ndarray

        """
        ANTARESDenseGroupInfo.__init__(self, path, conditions, variables, units)
        self._times = times
        self._values = values

    def values(self, condition, variable):
        """Return a new read-only view of the value corresponding to the *condition* and
        *variable*.

        Returns
        -------

        `~trickpy.variable.Variable`

        """

        # This version of data collect stores data in (1, variable, condition)
        # format.

        icon = self._condition_index(condition)
        ivar = self._variable_index(variable)

        return Variable(self._values[..., ivar, icon].squeeze(), self._units[ivar], copy=False, readonly=True)

    def times(self, condition, variable):
        """Return a new read-only view of the time corresponding to *condition* and
        *variable*.

        Returns
        -------

        `~trickpy.variable.Variable`

        """

        # This version of data collect stores data in (1, variable, condition)
        # format.

        icon = self._condition_index(condition)
        ivar = self._variable_index(variable)

        return Variable(self._times[..., ivar, icon].squeeze(), "s", copy=False, readonly=True)


def _read_antares_dense_meta(f):
    """Read the metadata from a dense ANTARES data collect file."""
    conditions = np.char.decode(f["condition_name"][...].astype(bytes))
    variables = np.char.decode(f["variable_name"][...].astype(bytes))
    units = np.char.decode(f["variable_units"][...].astype(bytes))
    return conditions, variables, units


def _read_antares_dense_info(f, path):
    """Load information about a dense ANTARES data collect file."""
    conditions, variables, units = _read_antares_dense_meta(f)
    return ANTARESDenseGroupInfo(path, conditions, variables, units)


def _read_antares_dense(f, path, conditions, variables, pairs):
    """Load a dense ANTARES data collect file."""
    all_conditions, all_variables, all_units = _read_antares_dense_meta(f)

    if conditions is None and variables is None and pairs is None:
        times = f["condition_time"][...]
        values = f["condition_value"][...]
        return ANTARESDenseGroup(path,
                                 all_conditions,
                                 all_variables,
                                 all_units,
                                 times,
                                 values)
    else:
        loaded_conditions = []
        loaded_variables = []
        loaded_units = []
        times = []
        values = []
        index_condvar = []
        times_dset = f["condition_time"]
        values_dset = f["condition_value"]
        should_load_pair = _ShouldLoadPair(conditions, variables, pairs)
        for ic, c in enumerate(all_conditions.flat):
            for iv, (v, u) in enumerate(zip(all_variables.flat, all_units.flat)):
                if should_load_pair(c, v):
                    if c not in loaded_conditions:
                        loaded_conditions.append(c)
                    if v not in loaded_variables:
                        loaded_variables.append(v)
                        loaded_units.append(u)
                    jc = loaded_conditions.index(c)
                    jv = loaded_variables.index(v)
                    index_condvar.append((jc, jv))
                    times.append(times_dset[..., iv, ic])
                    values.append(values_dset[..., iv, ic])
        loaded_conditions = np.array(loaded_conditions)
        loaded_variables = np.array(loaded_variables)
        loaded_units = np.array(loaded_units)
        index_condvar = np.array(index_condvar).T
        times = np.array(times).T
        values = np.array(values).T
        return MultiGroupGroup(path,
                               loaded_conditions,
                               loaded_variables,
                               loaded_units,
                               index_condvar,
                               np.array([], dtype=int),
                               times,
                               values)


class MultiGroupGroupInfo(SparseGroupInfo):
    """Information about a data collect group in the multiGROUP format.

    This format stores a sparse set of the condition/variable pairs.  This can
    either be from a single run or a Monte Carlo.

    Examples
    --------

    >>> info = dc.load_file_info('RUN_example/data_collect_example.h5')

    Inherits from `SparseGroupInfo`:

    >>> info.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> info.variables()
    StringListView(['altitude', 'altitude_rate'])
    >>> info.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('main_deploy', 'altitude'), ('touchdown', 'altitude_rate')])
    >>> info.has_pair('drogue_deploy', 'altitude')
    True

    To get the Monte Carlo run number corresponding to this file:

    >>> info.runs()
    ListView([-1])

    """

    def __init__(self, path, conditions, variables, units, index_condvar, runs):
        """Initialize a new `MultiGroupGroupInfo` object."""
        SparseGroupInfo.__init__(self, path, conditions, variables, units, index_condvar)
        self._runs = runs

    def runs(self):
        """Return a new view of the run numbers.

        If the file is from a single run, the run number will be ``-1``.

        Returns
        -------

        ListView

        """
        return ListView(self._runs)


class MultiGroupGroup(MultiGroupGroupInfo, DeprecatedGroupInterface):
    """A data collect group in the multiGROUP format.

    This format stores a sparse set of the condition/variable pairs.  This can
    either be from a single run or a Monte Carlo.

    Examples
    --------

    >>> data = dc.load_file('RUN_example/data_collect_example.h5')

    Inherits from `MultiGroupGroupInfo`:

    >>> data.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> data.variables()
    StringListView(['altitude', 'altitude_rate'])
    >>> data.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('main_deploy', 'altitude'), ('touchdown', 'altitude_rate')])
    >>> data.has_pair('drogue_deploy', 'altitude')
    True
    >>> data.runs()
    ListView([-1])

    To get the values and times from a condition/variable pair:

    >>> data.values('drogue_deploy', 'altitude')
    Variable(12013.0, 'ft')
    >>> data.times('drogue_deploy', 'altitude')
    Variable(121.0, 's')

    """

    def __init__(self, path, conditions, variables, units, index_condvar, runs, times, values):
        """Initialize a new `MultiGroupGroup` object."""
        MultiGroupGroupInfo.__init__(self, path, conditions, variables, units, index_condvar, runs)
        self._times = times
        self._values = values

    def values(self, condition, variable):
        """Return a new read-only view of the values corresponding to the *condition*
        and *variable*.

        If the data is from a Monte Carlo, then the output is an array of the
        values for each run.  If the data is from a single run, then the output
        is the scalar value for that run.

        Returns
        -------

        `~trickpy.variable.Variable`

        """

        # This version of data collect stores the data in a sparse format as
        # (run, pair).

        icon = self._condition_index(condition)
        ivar = self._variable_index(variable)
        ipair = self._pair_index(icon, ivar)

        return Variable(self._values[..., ipair], self._units.flat[ivar], copy=False, readonly=True)

    def times(self, condition, variable):
        """Return a new read-only view of the times corresponding to *condition* and
        *variable*.

        If the data is from a Monte Carlo, then the output is an array of the
        times for each run.  If the data is from a single run, then the output
        is the scalar time for that run.

        Returns
        -------

        `~trickpy.variable.Variable`

        """

        # This version of data collect stores the data in a sparse format as
        # (run, pair).

        icon = self._condition_index(condition)
        ivar = self._variable_index(variable)
        ipair = self._pair_index(icon, ivar)

        return Variable(self._times[..., ipair], "s", copy=False, readonly=True)

    def _combine(self, groups, runs):
        monte_directory = os.path.dirname(os.path.dirname(self._path.path))
        file_name = self._path.name
        path = os.path.join(monte_directory, "MONTE_" + file_name)

        conditions = self._conditions
        variables = self._variables
        units = self._units

        index_condvar = self._index_condvar

        values = np.stack([g._values for g in groups], axis=0)
        times = np.stack([g._times for g in groups], axis=0)

        return MultiGroupGroup(path,
                               conditions,
                               variables,
                               units,
                               index_condvar,
                               runs,
                               times,
                               values)

    def save(self, directory=None):
        """Save the group to a file.

        Parameters
        ----------

        directory : str, optional
            The directory in which to save the data.  The full path is created
            by combining the provided directory with the base name of the path
            provided at construction.  If ``None``, use the path provided at
            construction without overriding the directory.  Default is ``None``.

        """
        if directory is None and isinstance(self._path, paths.TarFilePath):
            raise Exception("can't save to a tar file, you must specify the directory argument")
        if directory is None:
            path = str(self._path)
        else:
            file_name = self._path.name
            path = os.path.join(directory, file_name)
        with h5py.File(path, "w") as f:
            vlen_bytes_dtype = h5py.special_dtype(vlen=bytes)
            f.create_dataset("info.RUN_number", data=self._runs)
            f.create_dataset("condition_name", data=np.char.encode(self._conditions), dtype=vlen_bytes_dtype)
            f.create_dataset("variable_name", data=np.char.encode(self._variables), dtype=vlen_bytes_dtype)
            f.create_dataset("variable_units", data=np.char.encode(self._units), dtype=vlen_bytes_dtype)
            f.create_dataset("index_CONDVAR", data=self._index_condvar + 1) # use 1-based indices in the file for consistency with other tools

            if self._times.ndim == 2:
                f.create_dataset("condition_time", data=self._times, chunks=(self._times.shape[0], 1), compression="gzip")
            elif self._times.ndim == 1:
                f.create_dataset("condition_time", data=self._times)
            else:
                raise Exception("bad times shape")

            if self._values.ndim == 2:
                f.create_dataset("condition_value", data=self._values, chunks=(self._values.shape[0], 1), compression="gzip")
            elif self._values.ndim == 1:
                f.create_dataset("condition_value", data=self._values)
            else:
                raise Exception("bad values shape")


def _read_multi_group_meta(f):
    """Read the metadata from a data collect file in the multiGROUP format."""
    conditions = np.char.decode(f["condition_name"][...].astype(bytes))
    variables = np.char.decode(f["variable_name"][...].astype(bytes))
    units = np.char.decode(f["variable_units"][...].astype(bytes))
    index_condvar = f["index_CONDVAR"][...].astype(int) - 1 # the file stores 1-based indices
    runs = f["info.RUN_number"][...].astype(int)
    return conditions, variables, units, index_condvar, runs


def _read_multi_group_info(f, path):
    """Load information about a data collect file in the multiGROUP format."""
    conditions, variables, units, index_condvar, runs = _read_multi_group_meta(f)
    return MultiGroupGroupInfo(path, conditions, variables, units, index_condvar, runs)


def _read_multi_group(f, path, conditions, variables, pairs):
    """Load a data collect file in the multiGROUP format."""
    all_conditions, all_variables, all_units, all_index_condvar, runs = _read_multi_group_meta(f)

    if conditions is None and variables is None and pairs is None:
        loaded_conditions = all_conditions
        loaded_variables = all_variables
        loaded_units = all_units
        loaded_index_condvar = all_index_condvar
        times = f["condition_time"][...]
        values = f["condition_value"][...]
    else:
        loaded_conditions = []
        loaded_variables = []
        loaded_units = []
        loaded_index_condvar = []
        times = []
        values = []
        times_dset = f["condition_time"]
        values_dset = f["condition_value"]

        all_condition_indices = all_index_condvar[0, :]
        all_variable_indices = all_index_condvar[1, :]

        pair_indices_to_load = _pair_indices_to_load(all_conditions,
                                                     all_variables,
                                                     all_condition_indices,
                                                     all_variable_indices,
                                                     conditions,
                                                     variables,
                                                     pairs)

        for ip in pair_indices_to_load:
            ic = all_condition_indices.flat[ip]
            iv = all_variable_indices.flat[ip]
            c = all_conditions.flat[ic]
            v = all_variables.flat[iv]
            if c not in loaded_conditions:
                loaded_conditions.append(c)
            if v not in loaded_variables:
                loaded_variables.append(v)
                u = all_units.flat[iv]
                loaded_units.append(u)
            jc = loaded_conditions.index(c)
            jv = loaded_variables.index(v)
            loaded_index_condvar.append((jc, jv))
            times.append(times_dset[..., ip])
            values.append(values_dset[..., ip])
        loaded_conditions = np.array(loaded_conditions)
        loaded_variables = np.array(loaded_variables)
        loaded_units = np.array(loaded_units)
        loaded_index_condvar = np.array(loaded_index_condvar).T
        times = np.array(times).T
        values = np.array(values).T

    return MultiGroupGroup(path,
                           loaded_conditions,
                           loaded_variables,
                           loaded_units,
                           loaded_index_condvar,
                           runs,
                           times,
                           values)


class MultiMonteGroupInfo(SparseGroupInfo):
    """Information about a data collect group in the multiMONTE format.

    Examples
    --------

    >>> info = dc.load_file_info('MONTE_RUN_example/data_collect_example.mat')

    Inherits from `SparseGroupInfo`:

    >>> info.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> info.variables()
    StringListView(['altitude', 'altitude_rate'])
    >>> info.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('main_deploy', 'altitude'), ('touchdown', 'altitude_rate')])
    >>> info.has_pair('drogue_deploy', 'altitude')
    True

    """
    pass


class MultiMonteGroup(MultiMonteGroupInfo, DeprecatedGroupInterface):
    """A data collect group in the multiMONTE format.

    Examples
    --------

    >>> data = dc.load_file('MONTE_RUN_example/data_collect_example.h5')

    Inherits from `MultiMonteGroupInfo`:

    >>> data.conditions()
    StringListView(['drogue_deploy', 'main_deploy', 'touchdown'])
    >>> data.variables()
    StringListView(['altitude', 'altitude_rate'])
    >>> data.pairs()
    StringPairListView([('drogue_deploy', 'altitude'), ('main_deploy', 'altitude'), ('touchdown', 'altitude_rate')])
    >>> data.has_pair('drogue_deploy', 'altitude')
    True

    To get the values and times from a condition/variable pair:

    >>> data.values('drogue_deploy', 'altitude')
    Variable([12013.0, 12007.0, 12021.0], 'ft')
    >>> data.times('drogue_deploy', 'altitude')
    Variable([121.0, 123.0, 119.0], 's')

    """

    def __init__(self, path, conditions, variables, units, index_condvar, times, values):
        """Initialize a new `MultiMonteGroup` object."""
        MultiMonteGroupInfo.__init__(self, path, conditions, variables, units, index_condvar)
        self._times = times
        self._values = values

    def values(self, condition, variable):
        """Return a new read-only view of the values corresponding to the *condition*
        and *variable*.

        Returns
        -------

        `~trickpy.variable.Variable`

        """

        # This version of data collect stores the data in a sparse format as
        # (pair, run).

        icon = self._condition_index(condition)
        ivar = self._variable_index(variable)
        ipair = self._pair_index(icon, ivar)

        return Variable(self._values[ipair, ...], self._units[ivar], copy=False, readonly=True)

    def times(self, condition, variable):
        """Return a new read-only view of the time corresponding to the *condition* and
        *variable*.

        Returns
        -------

        `~trickpy.variable.Variable`

        """

        # This version of data collect stores the data in a sparse format as
        # (pair, run).

        icon = self._condition_index(condition)
        ivar = self._variable_index(variable)
        ipair = self._pair_index(icon, ivar)

        return Variable(self._times[ipair, ...], "s", copy=False, readonly=True)


def _read_multi_monte_meta(f):
    """Read the metadata from a data collect file in the multiMONTE format."""
    conditions = f["condition_name"].item()
    variables = f["variable_name"].item()
    units = f["variable_units"].item()
    index_condvar = f["index_CONDVAR"].item().T - 1 # the file stores 1-based indices
    return conditions, variables, units, index_condvar


def _read_multi_monte_info(f, path):
    """Load information about a data collect file in the multiMONTE format."""
    conditions, variables, units, index_condvar = _read_multi_monte_meta(f)
    return MultiMonteGroupInfo(path, conditions, variables, units, index_condvar)


def _read_multi_monte(f, path, conditions, variables, pairs):
    all_conditions, all_variables, all_units, all_index_condvar = _read_multi_monte_meta(f)

    times = f["condition_time"].item()
    values = f["condition_value"].item()

    if conditions is None and variables is None and pairs is None:
        loaded_conditions = all_conditions
        loaded_variables = all_variables
        loaded_units = all_units
        loaded_index_condvar = all_index_condvar
        loaded_times = times
        loaded_values = values
    else:
        loaded_conditions = []
        loaded_variables = []
        loaded_units = []
        loaded_index_condvar = []
        loaded_times = []
        loaded_values = []

        all_condition_indices = all_index_condvar[0, :]
        all_variable_indices = all_index_condvar[1, :]

        pair_indices_to_load = _pair_indices_to_load(all_conditions,
                                                     all_variables,
                                                     all_condition_indices,
                                                     all_variable_indices,
                                                     conditions,
                                                     variables,
                                                     pairs)

        for ip in pair_indices_to_load:
            ic = all_condition_indices.flat[ip]
            iv = all_variable_indices.flat[ip]
            c = all_conditions.flat[ic]
            v = all_variables.flat[iv]
            if c not in loaded_conditions:
                loaded_conditions.append(c)
            if v not in loaded_variables:
                loaded_variables.append(v)
                u = all_units.flat[iv]
                loaded_units.append(u)
            jc = loaded_conditions.index(c)
            jv = loaded_variables.index(v)
            loaded_index_condvar.append((jc, jv))
            loaded_times.append(times[ip, ...])
            loaded_values.append(values[ip, ...])
        loaded_conditions = np.array(loaded_conditions)
        loaded_variables = np.array(loaded_variables)
        loaded_units = np.array(loaded_units)
        loaded_index_condvar = np.array(loaded_index_condvar).T
        loaded_times = np.array(loaded_times)
        loaded_values = np.array(loaded_values)

    return MultiMonteGroup(path,
                           loaded_conditions,
                           loaded_variables,
                           loaded_units,
                           loaded_index_condvar,
                           loaded_times,
                           loaded_values)


def _load_h5_file_info(path):
    """Load information about a data collect .h5 file."""
    if h5py is None:
        raise IOError("loading .h5 files requires the h5py module")
    with path.open("rb") as ff:
        with h5py.File(ff, "r") as f:
            if _is_fast_dense_file(f):
                return _read_fast_dense_info(f, path)
            elif _is_multi_group_file(f):
                return _read_multi_group_info(f, path)
            elif _is_antares_dense_file(f):
                return _read_antares_dense_info(f, path)
            else:
                raise Exception("unknown data collect format")


def _load_mat_file_info(path):
    """Load information about a data collect .mat file."""
    if scipy is None:
        raise IOError("loading .mat files requires the scipy module")
    with path.open("rb") as f:
        data = scipy.io.loadmat(f, squeeze_me=True)["data"]
        return _read_multi_monte_info(data, path)


def _load_file_info(path):
    """Load information about a data collect file."""
    root, ext = os.path.splitext(path.name)
    if ext == ".h5":
        return _load_h5_file_info(path)
    elif ext in (".mat", ".MAT"):
        return _load_mat_file_info(path)
    else:
        raise IOError("unsupported file extension")


def _load_h5_file(path, conditions, variables, pairs):
    """Load data from a data collect .h5 file."""
    if h5py is None:
        raise IOError("loading .h5 files requires the h5py module")
    with path.open("rb") as ff:
        with h5py.File(ff, "r") as f:
            if _is_fast_dense_file(f):
                return _read_fast_dense(f, path, conditions, variables, pairs)
            elif _is_multi_group_file(f):
                return _read_multi_group(f, path, conditions, variables, pairs)
            elif _is_antares_dense_file(f):
                return _read_antares_dense(f, path, conditions, variables, pairs)
            else:
                raise Exception("unknown data collect format")


def _load_mat_file(path, conditions, variables, pairs):
    """Load data from a data collect .mat file."""
    if scipy is None:
        raise IOError("loading .mat files requires the scipy module")
    with path.open("rb") as f:
        data = scipy.io.loadmat(f, squeeze_me=True)["data"]
        return _read_multi_monte(data, path, conditions, variables, pairs)


def _load_file(path, conditions, variables, pairs):
    """Load a data collect file."""
    root, ext = os.path.splitext(path.name)
    if ext == ".h5":
        return _load_h5_file(path, conditions, variables, pairs)
    elif ext in (".mat", ".MAT"):
        return _load_mat_file(path, conditions, variables, pairs)
    else:
        raise IOError("unsupported file extension")


def _load_groups_info(path, skip_errors):
    """Load information about data collect groups in a directory."""
    return loaders.load_groups(path,
                               _is_data_collect_file,
                               _parse_group_name,
                               None,
                               _load_file_info,
                               show_progress=False,
                               parallel=False,
                               skip_errors=skip_errors)


class _FileWorker(object):
    """Callable for loading a file."""

    def __init__(self, conditions, variables, pairs):
        self.conditions = conditions
        self.variables = variables
        self.pairs = pairs

    def __call__(self, path):
        return _load_file(path, self.conditions, self.variables, self.pairs)


def _load_groups(path, groups, conditions, variables, pairs, show_progress, parallel, skip_errors):
    """Load data collect groups in a RUN directory."""
    worker = _FileWorker(conditions, variables, pairs)
    return loaders.load_groups(path,
                               _is_data_collect_file,
                               _parse_group_name,
                               groups,
                               worker,
                               show_progress,
                               parallel,
                               skip_errors)


class _RunWorker(object):
    """Callable for loading a RUN directory."""

    def __init__(self, groups, conditions, variables, pairs, skip_errors):
        self.groups = groups
        self.conditions = conditions
        self.variables = variables
        self.pairs = pairs
        self.skip_errors = skip_errors

    def __call__(self, path):
        return _load_groups(path,
                            self.groups,
                            self.conditions,
                            self.variables,
                            self.pairs,
                            False,
                            False,
                            self.skip_errors)


def _load_monte_runs(path, runs, groups, conditions, variables, pairs, show_progress, parallel, skip_errors):
    """Load data collect groups in a MONTE directory."""
    worker = _RunWorker(groups, conditions, variables, pairs, skip_errors)
    return loaders.load_monte_runs(path,
                                   runs,
                                   worker,
                                   show_progress,
                                   parallel,
                                   skip_errors,
                                   return_type=Runs)


def load_file_info(path):
    """Load information about a data collect file.

    Parameters
    ----------

    path : path-like
        File system path of the data collect file.

    Returns
    -------

    `~trickpy.data_collect.FASTDenseGroupInfo`, `~trickpy.data_collect.ANTARESDenseGroupInfo`, `~trickpy.data_collect.MultiGroupGroupInfo`, or `~trickpy.data_collect.MultiMonteGroupInfo`

    Examples
    --------

    >>> info = dc.load_file_info('MONTE_RUN_example/data_collect_group.h5')
    >>> info.has_pair(condition='condition1', variable='variable1')
    True

    """
    path = paths.infer(path)
    return _load_file_info(path)


class Runs(collections.Runs):
    """A collection of data collect groups from multiple runs.

    Examples
    --------

    This object is indexed by run number, such that you end up pulling out
    scalar values for each condition/variable pair.  Often it is more convenient
    to combine all of the scalar data, so that you get an array of values for
    each condition/variable pair.  You can do that with the `combine` method.

    >>> data = dr.load_monte_runs('MONTE_RUN_example')
    >>> data[0]['group1'].values(condition='condition1', variable='variable1')
    Variable(1.0, 'm')
    >>> combined = data.combine()
    >>> combined['group1'].values(condition='condition1', variable='variable1')
    Variable([1.0, 1.1, 0.9], 'm')
    >>> combined['group1'].runs()
    ListView([0, 1, 2])

    """

    def combine(self, groups=None):
        """Combine the data from each run.

        Parameters
        ----------

        groups : list of str, optional
            Names of groups to include in combined output.  All other groups
            will be skipped.  If ``None``, include all groups.  Default is
            ``None``.

        Returns
        -------

        `~trickpy.collections.Groups`

        """

        # If a group failed for some runs, it won't be in that run's dictionary.
        # So let's be paranoid and look at all runs to make sure we get all of
        # the groups.
        group_names = set()
        for run in self:
            group_names = group_names.union(self[run].keys())

        if groups is not None:
            group_names = group_names.intersection(groups)

        data = {}
        for group_name in group_names:
            runs = np.fromiter((r for r in self if group_name in self[r]), dtype=int)

            group = self[runs[0]][group_name]

            data[group_name] = group._combine([self[run][group_name] for run in runs], runs)

        return collections.Groups(data)


def load_file(path, conditions=None, variables=None, pairs=None):
    """Load a data collect file.

    Parameters
    ----------

    path : path-like
        File system path of the data collect file.
    conditions : list of str, optional
        The list of conditions to load.  If a pair's condition is in this list,
        it will be loaded, regardless of the variable.  If ``None``, don't
        filter by condition.  Default is ``None``.
    variables : list of str, optional
        The list of variables to load.  If a pair's variable is in this list, it
        will be loaded, regardless of the condition.  If ``None``, don't filter
        by variable.  Default is ``None``.
    pairs : list of 2-tuples of str, optional
        The list of condition/variable pairs to load.  If ``None``, don't filter
        by pairs.  Default is ``None``.

    Returns
    -------

    `~trickpy.data_collect.FASTDenseGroup`, `~trickpy.data_collect.ANTARESDenseGroup`, `~trickpy.data_collect.MultiGroupGroup`, or `~trickpy.data_collect.MultiMonteGroup`

    Examples
    --------

    >>> data = dc.load_file('MONTE_RUN_example/data_collect_group.h5')
    >>> data.values(condition='condition1', variable='variable1')
    Variable([1.0, 1.1, 0.9], 'm')

    """
    path = paths.infer(path)
    return _load_file(path, conditions, variables, pairs)


def load_run_info(path, show_warnings=True, skip_errors=False):
    """Load information about the data collect files in a RUN directory.

    Parameters
    ----------

    path : path-like
        File system path of the RUN directory.
    show_warnings : bool, optional
        If ``True``, show a warning if any of the data collect files could not
        be loaded.  If ``False``, do not show warnings.  Default is ``True``.
    skip_errors : bool, optional
        If ``True``, skip any files that fail to load without throwing an
        exception.  If ``False``, throw an exception if an error is encountered.
        Default is ``False``.

    Returns
    -------

    `~trickpy.collections.Groups`

    Examples
    --------

    >>> info = dc.load_run_info('RUN_example')
    >>> info.keys()
    KeysView(['group1', 'group2'])

    """
    path = paths.infer(path)

    info, skipped_files = _load_groups_info(path, skip_errors)

    if show_warnings:
        print_files_summary(skipped_files)

    return info


def load_run(path, groups=None, conditions=None, variables=None, pairs=None,
             show_progress=True, show_warnings=True, parallel=False,
             skip_errors=False):
    """Load data collect files in a RUN directory.

    Parameters
    ----------

    path : path-like
        File system path of the RUN directory.
    groups : list of str, optional
        Names of the groups to load.  All other groups will be skipped.  If
        ``None``, load all groups.  Default is ``None``.
    conditions : list of str, optional
        The list of conditions to load.  If a pair's condition is in this list,
        it will be loaded, regardless of the variable.  If ``None``, don't
        filter by condition.  Default is ``None``.
    variables : list of str, optional
        The list of variables to load.  If a pair's variable is in this list, it
        will be loaded, regardless of the condition.  If ``None``, don't filter
        by variable.  Default is ``None``.
    pairs : list of 2-tuples of str, optional
        The list of condition/variable pairs to load.  If ``None``, don't filter
        by pairs.  Default is ``None``.
    show_progress : bool, optional
        If ``True``, show a progress bar during loading.  If ``False``, do not
        show a progress bar.  Default is ``True``.
    show_warnings : bool, optional
        If ``True``, show a warning if any data collect files could not be
        loaded.  If ``False``, do not show warnings.  Default is ``True``.
    parallel : bool, optional
        If ``True``, load the data collect files in parallel.  If ``False``,
        load them serially.  Default is ``False``.
    skip_errors : bool, optional
        If ``True``, skip any files that fail to load without throwing an
        exception.  If ``False``, throw an exception if an error is encountered.
        Default is ``False``.

    Returns
    -------

    `~trickpy.collections.Groups`

    Examples
    --------

    >>> data = dc.load_run('RUN_example')
    >>> data.keys()
    KeysView(['group1', 'group2'])
    >>> data['group1'].values('drogue_deploy', 'altitude')
    Variable(12013.0, 'ft')

    """
    path = paths.infer(path)

    data, skipped_files = _load_groups(path, groups, conditions, variables,
                                       pairs, show_progress, parallel,
                                       skip_errors)

    if show_warnings:
        print_files_summary(skipped_files)

    return data


def load_monte_info(path, show_warnings=True, skip_errors=False):
    """Load information about the data collect files at the top level of a MONTE
    directory.

    This does *not* recursively load information about the files in each RUN
    directory in the MONTE directory.

    Parameters
    ----------

    path : path-like
        File system path of the MONTE directory.
    show_warnings : bool, optional
        If ``True``, show a warning if any of the data collect files could not
        be loaded.  If ``False``, do not show warnings.  Default is ``True``.
    skip_errors : bool, optional
        If ``True``, skip any files that fail to load without throwing an
        exception.  If ``False``, throw an exception if an error is encountered.
        Default is ``False``.

    Returns
    -------

    `~trickpy.collections.Groups`

    Examples
    --------

    >>> info = dc.load_monte_info('MONTE_RUN_example')
    >>> info.keys()
    KeysView(['group1', 'group2'])

    """
    path = paths.infer(path)

    info, skipped_files = _load_groups_info(path, skip_errors)

    if show_warnings:
        print_files_summary(skipped_files)

    return info


def load_monte(path, groups=None, conditions=None, variables=None, pairs=None,
               show_progress=True, show_warnings=True, parallel=False,
               skip_errors=False):
    """Load data collect files at the top level of a MONTE directory.

    This does *not* recursively load the files from each RUN directory in a
    MONTE directory.  To do that, see the `load_monte_runs` function.

    Parameters
    ----------

    path : path-like
        File system path of the MONTE directory.
    groups : list of str, optional
        Names of the groups to load.  All other groups will be skipped.  If
        ``None``, load all groups.  Default is ``None``.
    conditions : list of str, optional
        The list of conditions to load.  If a pair's condition is in this list,
        it will be loaded, regardless of the variable.  If ``None``, don't
        filter by condition.  Default is ``None``.
    variables : list of str, optional
        The list of variables to load.  If a pair's variable is in this list, it
        will be loaded, regardless of the condition.  If ``None``, don't filter
        by variable.  Default is ``None``.
    pairs : list of 2-tuples of str, optional
        The list of condition/variable pairs to load.  If ``None``, don't filter
        by pairs.  Default is ``None``.
    show_progress : bool, optional
        If ``True``, show a progress bar during loading.  If ``False``, do not
        show a progress bar.  Default is ``True``.
    show_warnings : bool, optional
        If ``True``, show a warning if any data collect files could not be
        loaded.  If ``False``, do not show warnings.  Default is ``True``.
    parallel : bool, optional
        If ``True``, load the data collect files in parallel.  If ``False``, load them
        serially.  Default is ``False``.
    skip_errors : bool, optional
        If ``True``, skip any files that fail to load without throwing an
        exception.  If ``False``, throw an exception if an error is encountered.
        Default is ``False``.

    Returns
    -------

    `~trickpy.collections.Groups`

    Examples
    --------

    >>> data = dc.load_monte('MONTE_RUN_example')
    >>> data.keys()
    KeysView(['group1', 'group2'])

    """
    path = paths.infer(path)

    data, skipped_files = _load_groups(path, groups, conditions, variables,
                                       pairs, show_progress, parallel,
                                       skip_errors)

    if show_warnings:
        print_files_summary(skipped_files)

    return data


def load_monte_runs(path, runs=None, groups=None, conditions=None,
                    variables=None, pairs=None, show_progress=True,
                    show_warnings=True, parallel=False, skip_errors=False):
    """Load data collect files in the RUN directories of a MONTE directory.

    Parameters
    ----------

    path : path-like
        Path of the MONTE directory.
    runs : list of int, optional
        Run numbers to load.  All other runs will be skipped.  If ``None``, load
        all runs.  Default is ``None``.
    groups : list of str, optional
        Names of the groups to load.  All other groups will be skipped.  If
        ``None``, load all groups.  Default is ``None``.
    conditions : list of str, optional
        The list of conditions to load.  If a pair's condition is in this list,
        it will be loaded, regardless of the variable.  If ``None``, don't
        filter by condition.  Default is ``None``.
    variables : list of str, optional
        The list of variables to load.  If a pair's variable is in this list, it
        will be loaded, regardless of the condition.  If ``None``, don't filter
        by variable.  Default is ``None``.
    pairs : list of 2-tuples of str, optional
        The list of condition/variable pairs to load.  If ``None``, don't filter
        by pairs.  Default is ``None``.
    show_progress : bool, optional
        If ``True``, show a progress bar during loading.  If ``False``, do not
        show a progress bar.  Default is ``True``.
    show_warnings : bool, optional
        If ``True``, show a warning if any runs had data collect files that
        could not be loaded.  If ``False``, do not show warnings.  Default is
        ``True``.
    parallel : bool, optional
        If ``True``, load the runs in parallel.  If ``False``, load them
        serially.  Default is ``False``.
    skip_errors : bool, optional
        If ``True``, skip any files that fail to load without throwing an
        exception.  If ``False``, throw an exception if an error is encountered.
        Default is ``False``.

    Returns
    -------

    `Runs`

    Examples
    --------

    >>> data = dc.load_monte_runs('MONTE_RUN_example')
    >>> data.keys()
    KeysView([0, 1, 2, 3, 4])
    >>> data[0].keys()
    KeysView(['group1', 'group2'])
    >>> data[0]['group1'].values('drogue_deploy', 'altitude')
    Variable(12013.0, 'ft')

    """
    path = paths.infer(path)

    data, problem_runs = _load_monte_runs(path, runs, groups, conditions,
                                          variables, pairs, show_progress,
                                          parallel, skip_errors)

    if show_warnings:
        print_runs_summary(problem_runs)

    return data
