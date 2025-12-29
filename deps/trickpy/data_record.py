"""Load Trick data record files.

Examples
--------

The examples in this module assume that `trickpy.data_record` has been imported
as:

  >>> import trickpy.data_record as dr

To load a single data record file, do:

  >>> data = dr.load_file('/path/to/log_file.trk')

This method returns an object that behaves like a Python dictionary, where the
keys are variable names and the values are `~trickpy.variable.Variable` objects.

To load all of the data record groups in a RUN directory, do:

  >>> data = dr.load_run('/path/to/RUN_directory')

This method returns an object that behaves like a Python dictionary, where the
keys are log group names and the values are the same objects as returned by
`~trickpy.load_file` above.

To load all of the data record groups in all of the runs of a MONTE directory,
do:

  >>> data = dr.load_monte('/path/to/MONTE_directory')

This method returns an object that behaves like a Python ordered dictionary,
where the keys are the run numbers and the values are the same objects as
returned by `~trickpy.load_run` above.

Notes
-----

At a minimum, TrickPy is able to load ``.trk`` and ``.csv`` data record files.
If the h5py module is installed, TrickPy is also able to load ``.h5`` data
record files.

TrickPy supports data record formats from Trick 7, 10, and 13.

Trick allows for the creation of multiple data record groups.  Each group is
saved to a separate file, where the file name has the format ``log_<group
name>.<extension>``.  This is the group name used throughout TrickPy's data
record utilities.

"""

from __future__ import absolute_import, division

import sys
import os
import io
import numpy as np
import struct
import re
try:
    import collections.abc as collections_abc
except ImportError:
    import collections as collections_abc
from collections import OrderedDict

from .variable import VariableInfo, Variable
from .views import ListView, KeysView, ValuesView, ItemsView
from . import loaders
from .summaries import print_files_summary, print_runs_summary

try:
    import h5py
except ImportError:
    h5py = None

try:
    import pandas
except ImportError:
    pandas = None


class Group(collections_abc.Mapping):
    """A mapping from variable names to some associated data.

    Behaves like a read-only Python dictionary.

    Subtypes must provide a `__getitem__` method.

    Examples
    --------

    To check whether a variable is in the group:

    >>> 'sys.exec.out.time' in group
    True

    Iterating over the group iterates over the variable names:

    >>> [v for v in group]
    ['sys.exec.out.time', 'altitude', 'mass']

    The length of the group is the number of variables:

    >>> len(group)
    3

    >>> data = group["sys.exec.out.time"]

    To search for variable names that match a regular expression:

    >>> info.search(r'ti')
    ['sys.exec.out.time', 'altitude']

    """

    def __init__(self, variables):
        """Initialize a new `Group` object.

        Parameters
        ----------

        variables : iterable
            Some object which yields the variables when iterated.

        """
        self._variables = variables

    def __iter__(self):
        """Return a new iterator over the variables."""
        return iter(self._variables)

    def __len__(self):
        """Return the number of variables."""
        return len(self._variables)

    def keys(self):
        """Return a new view of the keys, which are the variable names."""
        return KeysView(self)

    def values(self):
        """Return a new view of the values, which are the data associated with the variables."""
        return ValuesView(self)

    def items(self):
        """Return a new view of the items, which are ``(key, value)`` pairs."""
        return ItemsView(self)

    def search(self, regex):
        """Return a list of variables that match *regex*.  If no variables match, return
        an empty list.

        """
        prog = re.compile(regex)
        return [v for v in self if prog.search(v) is not None]


class GroupInfo(Group):
    """Information about a data record group.

    Maps variables names to `~trickpy.variable.VariableInfo` objects.  Behaves like a read-only
    Python dictionary.

    Examples
    --------

    See `Group` for inherited behaviors.

    Indexing the group with a variable name returns a `~trickpy.variable.VariableInfo` object.

    >>> varinfo = group["altitude]
    >>> varinfo.units
    "ft"

    """

    def __init__(self, info):
        """Initialize a new `GroupInfo` object.

        Parameters
        ----------

        info : dict
            A dictionary mapping variable names to `~trickpy.variable.VariableInfo` objects.

        """
        super(GroupInfo, self).__init__(info)
        self._info = info

    def __getitem__(self, variable):
        """Return information about *variable*.

        Returns
        -------

        `~trickpy.variable.VariableInfo`

        """
        return self._info[variable]


class ParsedGroup(Group):
    """Parsed data record group.

    Maps variable names to `~trickpy.variable.Variable` objects.  Behaves like a
    read-only Python dictionary.

    Examples
    --------

    See `Group` for inherited behaviors.

    Indexing the group with a variable name returns a read-only view of that
    variable's time history data:

    >>> group['altitude']
    Variable([10.0, 5.0, 0.0], 'm')

    A new read-only view is returned each time a variable is accessed:

    >>> v1 = group['altitude']
    >>> v2 = group['altitude']
    >>> v1 is v2
    False

    """

    def __init__(self, data):
        """Initialize a new `ParsedGroup` object.

        Parameters
        ----------

        data : dict
            A dictionary mapping variable names to `~trickpy.variable.Variable`
            objects.

        """
        super(ParsedGroup, self).__init__(data)
        self._data = data

    def __getitem__(self, variable):
        """Return a new read-only view of the data for *variable*.

        Returns
        -------

        `~trickpy.variable.Variable`

        """
        return self._data[variable].view()


class UnparsedGroup(Group):
    """Unparsed data record group.

    Maps variable names to `~trickpy.variable.Variable` objects.  Behaves like a
    read-only Python dictionary.

    Examples
    --------

    See `Group` for inherited behaviors.

    Indexing the group with a variable name returns a read-only view of that
    variable's time history data:

    >>> data['altitude']
    Variable([10.0, 5.0, 0.0], 'm')

    A new read-only view is returned each time a variable is accessed:

    >>> v1 = data['altitude']
    >>> v2 = data['altitude']
    >>> v1 is v2
    False

    """

    def __init__(self, data, info, indices):
        """Initialize a new `UnparsedGroup` object.

        Parameters
        ----------

        data : indexable
            An object that can be indexed by the values of *indices*.
        info : `Group` or subtype
        indices : dict
            A dictionary mapping variable names to the index or key that, when
            applied to *data*, retrieves the time history data for that
            variable.

        """
        super(UnparsedGroup, self).__init__(info)
        self._data = data
        self._info = info
        self._indices = indices

    def __getitem__(self, variable):
        """Return a new read-only view of the data for *variable*.

        Returns
        -------

        `~trickpy.variable.Variable`

        Raises
        ------

        ValueError

        """
        i = self._indices[variable]
        data = self._data[i]
        units = self._info[variable].units
        return Variable(data,
                        units,
                        info=self._info.get(variable),
                        copy=False,
                        readonly=True)


_dr_file_re = re.compile(r"log_(?P<group_name>.+)\.(trk|csv|h5)")


def _is_data_record_file(path):
    """Return ``True`` if *path* is a data record file."""
    file_name = os.path.basename(path)
    m = _dr_file_re.match(file_name)
    if m:
        if os.path.isfile(path):
            return True
    return False


def _parse_group_name(path):
    """Parse the group name from the data record file *path*."""
    file_name = os.path.basename(path)
    m = _dr_file_re.match(file_name)
    if m:
        return m.group("group_name")
    raise Exception("unable to parse group")


def _read_hdf5_info(f):
    """Read the header information of a data record file in the HDF5 format."""
    header = f['header']
    variables = [x.decode() for x in header['param_names'][...]]
    units = [x.decode() for x in header['param_units'][...]]
    data = OrderedDict((v, VariableInfo(u))
                       for v, u in zip(variables, units))
    return GroupInfo(data)


def _load_hdf5_info(path):
    """Load information about a data record file in the HDF5 format."""
    if h5py is None:
        raise IOError("loading .h5 files requires h5py")
    with h5py.File(path, 'r') as f:
        return _read_hdf5_info(f)


def _load_hdf5(path, variables):
    """Load a data record file in the HDF5 format."""

    if h5py is None:
        raise IOError("loading .h5 files requires h5py")

    with h5py.File(path, 'r') as f:

        info = _read_hdf5_info(f)

        if variables is None:
            data = OrderedDict((v, Variable(f[v][...],
                                            info[v].units,
                                            info=info.get(v),
                                            copy=False,
                                            readonly=True))
                               for v in info)
        else:
            data = OrderedDict((v, Variable(f[v][...],
                                            info[v].units,
                                            info=info.get(v),
                                            copy=False,
                                            readonly=True))
                               for v in info if v in variables)

        out = ParsedGroup(data)

    return out


_trick10_format_dict = {
    (1, 1): "b",
    (2, 1): "B",
    (4, 2): "i2",
    (5, 2): "u2",
    (6, 4): "i4",
    (7, 4): "u4",
    (8, 8): "i8",
    (9, 8): "u8",
    (10, 4): "f4",
    (11, 8): "f8",
    (12, 4): "i4",
    (12, 8): "i8",
    (13, 4): "u4",
    (13, 8): "u8",
    (14, 8): "i8",
    (15, 8): "u8",
    (17, 1): "?",
    (21, 4): "i4",
}

def _trick10_format(t, s):
    """Convert a Trick 10 type code and size to a format string."""
    if t == 3:
        return "S" + str(s)
    else:
        dtype = _trick10_format_dict.get((t, s))
        if dtype is not None:
            return dtype
        else:
            return "V" + str(s)


_trick7_format_dict = {
    (0, 1): "b",
    (1, 1): "B",
    (3, 2): "i2",
    (4, 2): "u2",
    (5, 4): "i4",
    (6, 4): "u4",
    (7, 8): "i8",
    (8, 8): "u8",
    (9, 4): "f4",
    (10, 8): "f8",
    (13, 8): "i8",
    (14, 8): "u8",
    (17, 1): "?",
    (102, 4): "i4",
}

def _trick7_format(t, s):
    """Convert a Trick 7 type code and size to a format string."""
    if t == 2:
        return "S" + str(s)
    else:
        dtype = _trick7_format_dict.get((t, s))
        if dtype is not None:
            return dtype
        else:
            return "V" + str(s)


class TrkVariableInfo(VariableInfo):
    """Information about a variable in a data record file in the Trick binary format.

    Attributes
    ----------

    units : str
    code : int
        Trick type code for the variable.
    size : int
        Size of the variable in bytes.
    typestr : str
        Type string used for constructing a NumPy `dtype`.

    """

    def __init__(self, units, code, size, version, endianness):
        super(TrkVariableInfo, self).__init__(units)
        self._code = code
        self._size = size
        self._endianness = endianness
        if version == 10:
            self._format = _trick10_format
        elif version == 7:
            self._format = _trick7_format
        else:
            raise IOError("unsupported Trick version")

    @property
    def code(self):
        return self._code

    @property
    def size(self):
        return self._size

    @property
    def typestr(self):
        return self._endianness + self._format(self._code, self._size)


class TrkGroupInfo(GroupInfo):
    """Information about a data record group in the Trick binary format.

    Maps variable names to `TrkVariableInfo` objects.  Behaves like a read-only Python dictionary.

    Attributes
    ----------

    version : int
        Major version of Trick that created the group.
    endianness : str
        Endianness of the data.  Either "<" or ">", following the conventions of the struct module.

    Examples
    --------

    See `GroupInfo` for inherited behaviors.

    """

    def __init__(self, variables, info, version, endianness):
        """Initialize a new `TrkGroupInfo` object.

        Parameters
        ----------

        variables : list
            A list of all variables in the file, in order, including duplicates.
        info : dict
            A dictionary mapping variable names to `TrkVariableInfo` objects.
        version : int
        endianness : str

        """
        super(TrkGroupInfo, self).__init__(info)
        self._raw_variables = variables
        self._version = version
        self._endianness = endianness

    @property
    def version(self):
        return self._version

    @property
    def endianness(self):
        return self._endianness

    def raw_variables(self):
        """Return a read-only view of the ordered list of all variables in the file, including duplicates.

        """
        return ListView(self._raw_variables)

    def __getitem__(self, variable):
        """Return information about *variable*.

        Returns
        -------

        `TrkVariableInfo`

        """
        return super(TrkGroupInfo, self).__getitem__(variable)


def _read_trk_info(f):
    """Read the header information of a data record file in the Trick binary
    format.

    """

    # The first 10 characters are Trick-vv-e, where vv is the Trick
    # major version which created the file, and e is the endianness.

    title = struct.unpack('10s', f.read(10))[0].decode()
    title, version, endianness = title.split('-')
    if endianness == 'L':
        endianness = '<'
    else:
        endianness = '>'
    version = int(version)

    # The next value is the number of parameters.

    number_parameters = struct.unpack(endianness + 'i', f.read(4))[0]

    # The rest of the header describes the variables recorded.  Each
    # entry contains: the size of the name string, the name string, the
    # size of the units string, the units string, the type, and the
    # size.

    variables = []
    units = []
    codes = []
    sizes = []
    int_struct = struct.Struct(endianness + "i")
    for index in range(number_parameters):
        b = f.read(4)
        variable_length = int_struct.unpack(b)[0]

        b = f.read(variable_length)
        variables.append(struct.unpack(endianness + str(variable_length) + 's', b)[0].decode())

        b = f.read(4)
        units_length = int_struct.unpack(b)[0]

        b = f.read(units_length)
        units.append(struct.unpack(endianness + str(units_length) + 's', b)[0].decode())

        b = f.read(4)
        codes.append(int_struct.unpack(b)[0])

        b = f.read(4)
        sizes.append(int_struct.unpack(b)[0])

    data = OrderedDict((v, TrkVariableInfo(u, c, s, version, endianness))
                       for v, u, c, s in zip(variables, units, codes, sizes))
    return TrkGroupInfo(variables, data, version, endianness)


def _load_trk_info(path):
    """Load information about a data record file in the Trick binary format."""
    with open(path, 'rb') as f:
        return _read_trk_info(f)


def _load_trk(path, variables):
    """Load a data record file in the Trick binary format."""

    with open(path,'rb') as f:

        info = _read_trk_info(f)

        dtype = []
        fields = {}
        for i, v in enumerate(info.raw_variables()):
            field = 'f{}'.format(i)
            varinfo = info[v]
            dtype.append((field, varinfo.typestr))
            fields[v] = field

        if variables is None:
            data = np.fromfile(f, dtype=dtype)
            out = UnparsedGroup(data, info, fields)
        else:
            total_size = sum(info[v].size for v in info.raw_variables())
            chunk_size = 100 * 1024 * 1024 # 100 MB
            lines_per_chunk = chunk_size // total_size

            variables_to_load = [v for v in info if v in variables]

            loaded_raw_data = {}
            while True:
                data = np.fromfile(f, dtype=dtype, count=lines_per_chunk)
                if data.size == 0:
                    break
                for v in variables_to_load:
                    array = loaded_raw_data.get(v)
                    field = fields[v]
                    if array is None:
                        loaded_raw_data[v] = data[field]
                    else:
                        loaded_raw_data[v] = np.append(array, data[field])

            loaded_data = OrderedDict((v, Variable(loaded_raw_data.get(v, []),
                                                   info[v].units,
                                                   info=info.get(v),
                                                   copy=False,
                                                   readonly=True))
                                      for v in variables_to_load)

            out = ParsedGroup(loaded_data)

    return out


class CsvVariableInfo(VariableInfo):
    """Information about a variable in a data record file in CSV/ASCII format.

    Attributes
    ----------

    units : str
    column_index : int
        The column in the CSV file from which the data is taken.

    """

    def __init__(self, units, column_index):
        super(CsvVariableInfo, self).__init__(units)
        self._column_index = column_index

    @property
    def column_index(self):
        return self._column_index


def _read_csv_info(f):
    """Read the header information of a data record file in the Trick ASCII format."""

    # The first line contains a comma separated list of variable {unit}
    # entries.

    header = f.readline()
    columns = [c.strip() for c in header.split(',')]
    variables = []
    units = []
    for c in columns:
        v, u = c.split()
        u = u.strip('{}')
        variables.append(v)
        units.append(u)
    data = OrderedDict((v, CsvVariableInfo(u, i))
                       for i, (v, u) in enumerate(zip(variables, units)))
    return GroupInfo(data)


def _load_csv_info(path):
    """Load information about a data record file in the Trick ASCII format."""
    with open(path, 'r') as f:
        return _read_csv_info(f)


def _load_csv(path, variables):
    """Load a data record file in the Trick ASCII format."""

    if pandas is None:
        raise IOError("loading .csv files requires pandas")

    with open(path, 'r') as f:

        info = _read_csv_info(f)

        data = pandas.read_csv(f,
                               engine="c",
                               skipinitialspace=True,
                               usecols=[i.column_index for i in info.values()],
                               header=None)

        if variables is None:
            loaded_data = OrderedDict((v, Variable(data[i.column_index].values,
                                                   i.units,
                                                   info=i,
                                                   copy=False,
                                                   readonly=True))
                                      for (v, i) in info.items())
        else:
            loaded_data = OrderedDict((v, Variable(data[i.column_index].values,
                                                   i.units,
                                                   info=i,
                                                   readonly=True)) # The underlying data is all in one np.array, so we need to copy
                                      for (v, i) in info.items() if v in variables)

        out = ParsedGroup(loaded_data)

    return out


def _load_file_info(path):
    """Load information about a data record file."""
    root, ext = os.path.splitext(os.path.basename(path))
    if ext == '.h5':
        return _load_hdf5_info(path)
    elif ext == '.trk':
        return _load_trk_info(path)
    elif ext == '.csv':
        return _load_csv_info(path)
    else:
        raise IOError("unsupported file extension")


def _load_file(path, variables):
    """Load a data record file."""
    root, ext = os.path.splitext(os.path.basename(path))
    if ext == '.h5':
        return _load_hdf5(path, variables)
    elif ext == '.trk':
        return _load_trk(path, variables)
    elif ext == '.csv':
        return _load_csv(path, variables)
    else:
        raise IOError("unsupported file extension")


def _load_run_info(path, skip_errors):
    """Load information about data record groups in a RUN directory."""
    return loaders.load_groups(path,
                               _is_data_record_file,
                               _parse_group_name,
                               None,
                               _load_file_info,
                               show_progress=False,
                               parallel=False,
                               skip_errors=skip_errors)


class _FileWorker(object):
    """Callable for loading a file."""

    def __init__(self, variables):
        self.variables = variables

    def __call__(self, path):
        return _load_file(path, self.variables)


def _load_run(path, groups, variables, show_progress, parallel, skip_errors):
    """Load data record groups in a RUN directory."""
    worker = _FileWorker(variables)
    return loaders.load_groups(path,
                               _is_data_record_file,
                               _parse_group_name,
                               groups,
                               worker,
                               show_progress,
                               parallel,
                               skip_errors)


class _RunWorker(object):
    """Callable for loading a RUN directory."""

    def __init__(self, groups, variables, skip_errors):
        self.groups = groups
        self.variables = variables
        self.skip_errors = skip_errors

    def __call__(self, path):
        return _load_run(path, self.groups, self.variables, False, False, self.skip_errors)


def _load_monte(path, runs, groups, variables, show_progress, parallel, skip_errors):
    """Load data record groups in a MONTE directory."""
    worker = _RunWorker(groups, variables, skip_errors)
    return loaders.load_monte_runs(path, runs, worker, show_progress, parallel, skip_errors)


def load_file_info(path):
    """Load information about a data record file.

    Parameters
    ----------

    path : str
        File system path of the data record file.

    Returns
    -------

    `~trickpy.data_record.Group`

    Examples
    --------

    >>> info = dr.load_file_info('RUN_example/log_group.trk')
    >>> 'altitude' in info
    True
    >>> len(info)
    3
    >>> list(info)
    ['sys.exec.out.time', 'altitude', 'mass']

    """
    return _load_file_info(path)


def load_file(path, variables=None):
    """Load a data record file.

    Parameters
    ----------

    path : str
        File system path of the data record file.
    variables : list of str, optional
        Names of the variables to load.  All other variables will be skipped.
        If ``None``, load all variables.  Default is ``None``.

    Returns
    -------

    `~trickpy.data_record.ParsedGroup` or
    `~trickpy.data_record.UnparsedGroup`

    Examples
    --------

    >>> data = dr.load_file('RUN_example/log_example.trk')
    >>> data['sys.exec.out.time']
    Variable([0.0, 0.1, 0.2], 's')

    """
    return _load_file(path, variables)


def load_run_info(path, show_warnings=True, skip_errors=False):
    """Load information about data record groups in a RUN directory.

    Parameters
    ----------

    path : str
        File system path of the data record file.
    show_warnings : bool, optional
        If ``True``, show a warning for data record files that could not be
        loaded.  If ``False``, do not show warnings.  Default is ``True``.
    skip_errors : bool, optional
        If ``True``, skip any files that fail to load without throwing an
        exception.  If ``False``, throw an exception if an error is encountered.
        Default is ``False``.

    Returns
    -------

    `~trickpy.collections.Groups`

    Examples
    --------

    >>> info = dr.load_run_info('RUN_example')
    >>> info.keys()
    KeysView(['group1', 'group2'])

    """
    info, skipped_files = _load_run_info(path, skip_errors)

    if show_warnings:
        print_files_summary(skipped_files)

    return info


def load_run(path, groups=None, variables=None, show_progress=True, show_warnings=True,
             parallel=False, skip_errors=False):
    """Load data record groups in a RUN directory.

    Parameters
    ----------

    path : str
        File system path of the RUN directory.
    groups : list of str, optional
        Names of the groups to load.  All other groups will be skipped.  If
        ``None``, load all groups.  Default is ``None``.
    variables : list of str, optional
        Names of the variables to load.  All other variables will be skipped.
        If ``None``, load all variables.  Default is ``None``.
    show_progress : bool, optional
        If ``True``, show a progress bar during loading.  If ``False``, do not
        show a progress bar.  Default is ``True``.
    show_warnings : bool, optional
        If ``True``, show a warning for data record files that could not be
        loaded.  If ``False``, do not show warnings.  Default is ``True``.
    parallel : bool, optional
        If ``True``, load the data record files in parallel.  If ``False``, load
        them serially.  Default is ``False``.
    skip_errors : bool, optional
        If ``True``, skip any files that fail to load without throwing an
        exception.  If ``False``, throw an exception if an error is encountered.
        Default is ``False``.

    Returns
    -------

    `~trickpy.collections.Groups`

    Examples
    --------

    >>> data = dr.load_run('RUN_example')
    >>> data.keys()
    KeysView(['group1', 'group2'])
    >>> data['group1']['sys.exec.out.time']
    Variable([0.0, 0.1, 0.2], 's')

    """
    data, skipped_files = _load_run(path, groups, variables, show_progress, parallel, skip_errors)

    if show_warnings:
        print_files_summary(skipped_files)

    return data


def load_monte(path, runs=None, groups=None, variables=None, show_progress=True, show_warnings=True,
               parallel=False, skip_errors=False):
    """Load data record groups in a MONTE directory.

    Parameters
    ----------

    path : str
        File system path of the MONTE directory.
    runs : list of int, optional
        Run numbers to load.  All other runs will be skipped.  If ``None``, load
        all runs.  Default is ``None``.
    groups : list of str, optional
        Names of the groups to load.  All other groups will be skipped.  If
        ``None``, load all groups.  Default is ``None``.
    variables : list of str, optional
       Names of the variables to load.  All other variables will be skipped.  If
       ``None``, load all variables.  Default is ``None``.
    show_progress : bool, optional
        If ``True``, show a progress bar during loading.  If ``False``, do not
        show a progress bar.  Default is ``True``.
    show_warnings : bool, optional
        If ``True``, show a warning if any runs had data record files that could
        not be loaded.  If ``False``, do not show warnings.  Default is
        ``True``.
    parallel : bool, optional
        If ``True``, load the runs in parallel.  If ``False``, load them
        serially.  Default is ``False``.

        .. note:: Default changed in TrickPy 2.1.

                  Loading ``.trk`` files is now so fast that it is often not
                  beneficial to use multiple processes.  You can try this option
                  to see if it helps for your particular data set.
    skip_errors : bool, optional
        If ``True``, skip any files that fail to load without throwing an
        exception.  If ``False``, throw an exception if an error is encountered.
        Default is ``False``.

    Returns
    -------

    `~trickpy.collections.Runs`

    Examples
    --------

    >>> data = dr.load_monte('MONTE_RUN_example')
    >>> data.keys()
    KeysView([0, 1, 2, 3, 4])
    >>> data[0].keys()
    KeysView(['group1', 'group2'])
    >>> data[0]['group1']['sys.exec.out.time']
    Variable([0.0, 0.1, 0.2], 's')

    """
    data, problem_runs = _load_monte(path, runs, groups, variables, show_progress, parallel, skip_errors)

    if show_warnings:
        print_runs_summary(problem_runs)

    return data
