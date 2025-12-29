"""Load Trick Monte Carlo dispersions.

Examples
--------

The examples in this module assume that `trickpy.dispersions` has been imported
as:

  >>> import trickpy.dispersions as dispersions

To load the dispersions from a MONTE directory, do:

  >>> disp = dispersions.load_monte("/path/to/MONTE_directory")

This function returns a Python dictionary, where the keys are the names of the
dispersed variables, and the values are NumPy arrays of the dispersed values
with indices that match the array of run numbers accessed by:

  >>> disp.runs()

Notes
-----

The dispersions from a Monte Carlo are written to the ``monte_runs`` file in the
MONTE directory.

"""

from __future__ import absolute_import

import os
import numpy as np
import re
try:
    import collections.abc as collections_abc
except ImportError:
    import collections as collections_abc
from collections import OrderedDict

from .variable import VariableInfo, Variable
from .views import ListView, KeysView, ValuesView, ItemsView


class FileVariableInfo(VariableInfo):
    """Information about a variable dispersed from a file.

    Attributes
    ----------

    file : str
        The file from which the dispersions are taken.
    column : int
        The column in the file from which the dispersions are taken.

    """

    def __init__(self, units, file, column):
        super(FileVariableInfo, self).__init__(units)
        self._file = file
        self._column = column

    @property
    def file(self):
        return self._file

    @property
    def column(self):
        return self._column


class RandomVariableInfo(VariableInfo):
    """Information about a randomly dispersed variable.

    Attributes
    ----------

    distribution : str
    seed : int
    sigma : float
    mu : float
    min : float
    max : float
    rel_min : float
    rel_max : float

    """

    def __init__(self, units, distribution, seed, sigma, mu, min, max, rel_min,
                 rel_max):
        super(RandomVariableInfo, self).__init__(units)
        self._distribution = distribution
        self._seed = seed
        self._sigma = sigma
        self._mu = mu
        self._min = min
        self._max = max
        self._rel_min = rel_min
        self._rel_max = rel_max

    @property
    def distribution(self):
        return self._distribution

    @property
    def seed(self):
        return self._seed

    @property
    def sigma(self):
        return self._sigma

    @property
    def mu(self):
        return self._mu

    @property
    def min(self):
        return self._min

    @property
    def max(self):
        return self._max

    @property
    def rel_min(self):
        return self._rel_min

    @property
    def rel_max(self):
        return self._rel_max


class DispersionsInfo(collections_abc.Mapping):
    """Information about Trick Monte Carlo dispersions.

    Maps variable names to information about that variable and its dispersion.
    Behaves like a read-only Python dictionary.

    Examples
    --------

    >>> info = dispersions.load_monte_info('MONTE_RUN_example')

    To check whether a variable is in the dispersions:

    >>> 'variable1' in info
    True

    Iterating over the dispersions iterates over the variables:

    >>> [v for v in info]
    ['variable1', 'variable2']
    >>> list(info)
    ['variable1', 'variable2']

    The length of the dispersions is the number of variables:

    >>> len(info)
    2

    To search for variable names that match a regular expression, do:

    >>> info.search(r'var')
    ['variable1', 'variable2']

    """

    def __init__(self, info):
        """Initialize a new `DispersionsInfo` object.

        Parameters
        ----------

        info : dict
            A dictionary mapping variable names to information about the
            variables.

        """
        self._info = info

    def __iter__(self):
        """Return a new iterator over the variables."""
        return iter(self._info)

    def __len__(self):
        """Return the number of variables."""
        return len(self._info)

    def __getitem__(self, variable):
        """Return a new object with information about *variable*."""
        return self._info[variable]

    def search(self, regex):
        """Return a list of variables that match *regex*.  If no variables match, return
        an empty list.

        """
        prog = re.compile(regex)
        return [v for v in self._info if prog.search(v) is not None]


class Dispersions(DispersionsInfo):
    """Trick Monte Carlo dispersions.

    Maps variable names to NumPy arrays of the dispersed values, which are
    indexed by the run number.  Behaves like a read-only Python dictionary.

    Examples
    --------

    >>> disp = dispersions.load_monte('MONTE_RUN_example')

    `Dispersions` inherits from `DispersionsInfo`, so it has the same behaviors:

    >>> 'variable1' in disp
    True
    >>> [v for v in disp]
    ['variable1', 'variable2']
    >>> list(disp)
    ['variable1', 'variable2']
    >>> len(disp)
    2
    >>> disp.search(r'var')
    ['variable1', 'variable2']

    The dispersed values can be accessed by indexing the dispersion file object
    with the variable name:

    >>> disp['variable1']
    Variable([3.1, 2.9, 2.6, 3.5], 'm')

    To get a new read-only view of the run numbers:

    >>> disp.runs()
    ListView([0, 1, 2, 3])

    New read-only views of the dispersed values are returned for every call:

    >>> v1 = disp['variable1']
    >>> v2 = disp['variable2']
    >>> v1 is v2
    False

    """

    def __init__(self, info, runs, data):
        """Initialize a new `Dispersions` object.

        Parameters
        ----------

        info : dict
            A dictionary mapping variable names to information about the
            variables.
        runs : list of int
        data : dict
            A dictionary mapping variable names to NumPy arrays of the dispersed
            values, indexed by the run number.

        """
        super(Dispersions, self).__init__(info)
        self._runs = runs
        self._data = data

    def __getitem__(self, variable):
        """Return a new read-only view of the dispersed values for *variable*.

        Returns
        -------

        `~trickpy.variable.Variable` or numpy.ndarray

        """
        data = self._data[variable]
        info = self._info.get(variable, None)
        if info is None:
            data = data.view()
            data.flags["WRITEABLE"] = False
            return data
        else:
            return Variable(data,
                            info.units,
                            info=info,
                            copy=False,
                            readonly=True)

    def keys(self):
        """Return a new view of the keys, which are the variables."""
        return KeysView(self)

    def values(self):
        """Return a new view of the values, which are the dispersed values."""
        return ValuesView(self)

    def items(self):
        """Return a new view of the items, which are ``(key, value)`` pairs."""
        return ItemsView(self)

    def runs(self):
        """Return a new view of the runs."""
        return ListView(self._runs)


def _read_monte_runs_meta_old_format(f):
    """Read the metadata from a monte_runs file in the old format."""

    # The first line is a space delimited list of the variable names.
    header = f.readline()
    header = header.lstrip('#').strip()
    variables = header.split()
    return variables[1:]        # remove the run_num variable


class InvalidMetadata(Exception):
    pass


def _read_meta_entry(f, key):
    """Read the next line from f, expecting an entry with *key*, and return its
    value.

    """
    line = f.readline()
    if not line.startswith("#{}:".format(key)):
        raise InvalidMetadata("unexpected line: {}".format(line))
    parts = line.split()
    if len(parts) == 1:
        return None
    elif len(parts) == 2:
        return parts[1]
    else:
        raise InvalidMetadata("unexpected line: {}".format(line))


def _read_meta_empty_line(f):
    """Read the next line from f, and enforce that it is empty."""
    line = f.readline()
    if line.strip() != "":
        raise InvalidMetadata("unexpected line: {}".format(line))


def _read_file_variable_meta(f):
    """Read the metadata for a MonteVarFile entry."""
    units = _read_meta_entry(f, "UNIT")
    file = _read_meta_entry(f, "FILE")
    column = int(_read_meta_entry(f, "COLUMN"))
    _read_meta_empty_line(f)
    return FileVariableInfo(units, file, column)


def _read_random_variable_meta(f):
    """Read the metadata for a MonteVarRandom entry."""
    units = _read_meta_entry(f, "UNIT")
    distribution = _read_meta_entry(f, "DISTRIBUTION")
    seed = int(_read_meta_entry(f, "SEED"))
    sigma = float(_read_meta_entry(f, "SIGMA"))
    mu = float(_read_meta_entry(f, "MU"))
    min = float(_read_meta_entry(f, "MIN"))
    max = float(_read_meta_entry(f, "MAX"))
    rel_min = float(_read_meta_entry(f, "REL_MIN"))
    rel_max = float(_read_meta_entry(f, "REL_MAX"))
    _read_meta_empty_line(f)
    return RandomVariableInfo(units,
                              distribution,
                              seed,
                              sigma,
                              mu,
                              min,
                              max,
                              rel_min,
                              rel_max)


def _read_variable_meta(f):
    """Read the metadata for a variable entry."""
    var_type = _read_meta_entry(f, "TYPE")
    if var_type == "FILE":
        return _read_file_variable_meta(f)
    elif var_type == "RANDOM":
        return _read_random_variable_meta(f)
    else:
        raise InvalidMetadata("unsupported type: {}".format(var_type))


def _read_monte_runs_meta_new_format(f):
    """Read the metadata from a monte_runs file in the new format."""

    # First, we read the metadata specifying the dispersions.
    info = {}
    while True:
        line = f.readline()

        if line.startswith("#NAME"):
            variable = line.split()[1]
            try:
                meta = _read_variable_meta(f)
            except InvalidMetadata:
                meta = None
            info[variable] = meta

        if line.startswith("# RUN"):
            break

    variables = line.split()[2:] # remove "#" and "RUN"

    return variables, info


_monte_header_re = re.compile(r"var\d+ = trick\.MonteVarFile\(\"(?P<variable>.+?)\", \".+?\", \d+(, \"(?P<units>.*?)\")?\)")
def _load_monte_header(path, variables):
    """Load the units from a monte_header file."""
    with open(path, "r") as f:
        out = dict()
        for line in f:
            m = _monte_header_re.match(line)
            if m is not None:
                groups = m.groupdict()
                v = groups["variable"]
                if v not in variables:
                    raise InvalidMetadata("unexpected variable: {}".format(v))
                u = groups["units"]
                out[v] = u

    for v in variables:
        if v not in out:
            raise InvalidMetadata("no units found for variable: {}".format(v))
    return out


def _read_meta_old_format(f, monte_header_path):
    """Read dispersions metadata in the old format."""
    variables = _read_monte_runs_meta_old_format(f)
    if monte_header_path is not None:
        units = _load_monte_header(monte_header_path, variables)
        info = OrderedDict((v, VariableInfo(units[v]))
                           for v in variables)
    else:
        info = OrderedDict((v, None)
                           for v in variables)
    return (DispersionsInfo(info),
            {v: i + 1 for i, v in enumerate(variables)})


def _read_meta_new_format(f):
    """Read dispersions metadata in the new format."""
    variables, info = _read_monte_runs_meta_new_format(f)
    return (DispersionsInfo(OrderedDict((v, info.get(v, None))
                                       for v in variables)),
            {v: i + 1 for i, v in enumerate(variables)})


def _read_meta(f, monte_header_path):
    """Detect the file format and read dispersions metadata."""
    line = f.readline()
    f.seek(0)
    if line.startswith("#NAME") or line.startswith("# RUN"):
        return _read_meta_new_format(f)
    else:
        return _read_meta_old_format(f, monte_header_path)


def load_file_info(monte_runs_path, monte_header_path=None):
    """Load information about a dispersions file.

    Parameters
    ----------

    monte_runs_path : str
        File system path of the `monte_runs` file.
    monte_header_path : str, optional
        File system path of the `monte_header` file.  Defaults to ``None``.  If
        the `monte_runs` file is in the new format, this argument will be
        ignored.  If the `monte_runs` file is in the old format, then this
        argument is required for units information to be available.

    Returns
    -------

    `~trickpy.dispersions.DispersionsInfo`

    Examples
    --------

    >>> disp = dispersions.load_file_info('MONTE_RUN_example/monte_runs')
    >>> list(disp)
    ['variable1', 'variable2']
    >>> disp['variable1'].units
    'ft'
    >>> disp['variable1'].distribution
    'FLAT'

    """
    with open(monte_runs_path, "r") as f:
        info, _ = _read_meta(f, monte_header_path)
        return info


def load_file(monte_runs_path, monte_header_path=None):
    """Load a dispersions file.

    Parameters
    ----------

    monte_runs_path : str
        File system path of the `monte_runs` file.
    monte_header_path : str, optional
        File system path of the `monte_header` file.  Defaults to ``None``.  If
        the `monte_runs` file is in the new format, this argument will be
        ignored.  If the `monte_runs` file is in the old format, then this
        argument is required for units information to be available.

    Returns
    -------

    `~trickpy.dispersions.Dispersions`

    Examples
    --------

    >>> disp = dispersions.load_file('MONTE_RUN_example/monte_runs')
    >>> disp.keys()
    ['variable1', 'variable2']
    >>> disp['variable1']
    array([3.1, 2.9, 2.6, 3.5])

    >>> disp = dispersions.load_file('MONTE_RUN_example/monte_runs', 'MONTE_RUN_example/monte_header')
    >>> disp['variable1']
    Variable([3.1, 2.9, 2.6, 3.5], 'm')

    >>> disp['variable1'].info.distribution
    'FLAT'

    """
    with open(monte_runs_path, "r") as f:

        info, column_indices = _read_meta(f, monte_header_path)

        # The rest of the file is space delimited data.

        raw_data = [line.strip().split() for line in f]
        raw_data = list(zip(*raw_data))

    runs = [int(x) for x in raw_data[0]]
    data = OrderedDict((v, np.array(raw_data[column_indices[v]], dtype=float))
                       for v in info)

    return Dispersions(info,
                       runs,
                       data)


def load_monte_info(path):
    """Load information about the dispersions file in a MONTE directory.

    Parameters
    ----------

    path : str
        File system path of the MONTE directory.

    Returns
    -------

    `~trickpy.dispersions.DispersionsInfo`

    Examples
    --------

    >>> disp = dispersions.load_monte_info('MONTE_RUN_example')
    >>> list(disp)
    ['variable1', 'variable2']

    """
    monte_runs_path = os.path.join(path, 'monte_runs')
    monte_header_path = os.path.join(path, 'monte_header')
    if not os.path.exists(monte_header_path):
        monte_header_path = None
    return load_file_info(monte_runs_path, monte_header_path)


def load_monte(path):
    """Load the dispersions file in a MONTE directory.

    Parameters
    ----------

    path : str
        File system path of the MONTE directory.

    Returns
    -------

    `~trickpy.dispersions.Dispersions`

    Examples
    --------

    >>> disp = dispersions.load_monte('MONTE_RUN_example')
    >>> disp.keys()
    ['variable1', 'variable2']
    >>> disp['variable1']
    Variable([3.1, 2.9, 2.6, 3.5], 'm')

    """
    monte_runs_path = os.path.join(path, 'monte_runs')
    monte_header_path = os.path.join(path, 'monte_header')
    if not os.path.exists(monte_header_path):
        monte_header_path = None
    return load_file(monte_runs_path, monte_header_path)
