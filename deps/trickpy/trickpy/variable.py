"""Data with associated units.

A `Variable` behaves just like a NumPy array, but in addition it has associated
units.  This is a fairly bare-bones feature, and its main purpose is to allow
the user to easily convert the data to a different set of units.  For a small
set of operations, the units will be preserved, but in general the units are
dropped.  For a more sophisticated treatment of quantities with units, check out
the AstroPy or Pint packages.

Examples
--------

>>> import trickpy.data_record as dr
>>> data = dr.load_run('RUN_example')
>>> alt = data['group']['altitude']

To get the units of a `Variable`:

>>> alt.units
'm'

To convert units:

>>> alt_ft = alt.to('ft')

To access additional information about a variable, if any:

>>> alt.info

"""

import numpy as np

from . import trick_units


class VariableInfo(object):
    """Information about a variable.

    Attributes
    ----------

    units : str
        Associated Trick units.

    """

    def __init__(self, units):
        self._units = units

    @property
    def units(self):
        return self._units

    def __eq__(self, other):
        if isinstance(other, VariableInfo):
            return self.units == other.units
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class Variable(np.ndarray):
    """Data with associated units.

    The associated units are denoted by a string using the Trick units
    conventions.

    Variables behave like NumPy arrays.  A limited number of methods
    have been implemented to preserve units.  In general, performing
    mathematical operations on Variables will simply drop the units
    and return NumPy arrays.

    Examples
    --------

    TrickPy often returns a read-only Variable for efficiency.  To get a
    writeable version:

    >>> var_writeable = var_readonly.copy()

    To convert units:

    >>> var_ft = var_m.to("ft")

    The Variable with the converted units owns its own data and is writeable.

    Attributes
    ----------

    units : str
        Associated Trick units.
    info :
        Information about the variable.

    """

    def __new__(cls, input_array, units, info=None, copy=True, readonly=False):
        """Create a new `Variable`.

        Parameters
        ----------

        input_array : array_like
            An array used to populate the `Variable`'s data.
        units : str
            Units of the data in *input_array*.
        info : `VariableInfo` or similar
            Associated information about the variable.
        copy : bool
            If ``True``, the new `Variable` will contain a copy of
            *input_array*.  Otherwise, it will contain a view.  Default is
            ``True``.
        readonly : bool
           If ``True``, the new `Variable` will be read-only.  Otherwise, it
           will be writeable.  Default is ``False``.

        """
        obj = np.asarray(input_array).view(cls)
        if copy:
            obj = obj.copy()
        obj._units = units
        obj._info = info
        if readonly:
            obj.flags['WRITEABLE'] = False
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self._units = getattr(obj, '_units', None)
        self._info = getattr(obj, '_info', None)

    def __array_wrap__(self, out_arr, context=None, return_scalar=False):
        # This method gets called after all ufuncs.  For certain ufuncs, we want
        # to return a Variable, and for others, we want to drop the units and
        # return a NumPy array.
        if context is not None:
            ufunc = context[0]
            if ufunc in (np.absolute, np.fabs):
                out = out_arr.view(Variable)
                out.__array_finalize__(self)
                return out
        return out_arr.view(np.ndarray)

    # See http://www.mail-archive.com/numpy-discussion@scipy.org/msg02446.html
    # I figured this out by looking at what astropy did for their Quantity object
    def __reduce__(self):
        object_state = list(np.ndarray.__reduce__(self))
        subclass_state = (self._units, self._info)
        object_state[2] = (object_state[2], subclass_state)
        return tuple(object_state)

    def __setstate__(self, state):
        nd_state, own_state = state
        np.ndarray.__setstate__(self, nd_state)
        self._units = own_state[0]
        self._info = own_state[1]

    def __getitem__(self, i):
        return Variable(self.view(np.ndarray).__getitem__(i),
                        self._units,
                        info=self._info,
                        copy=False)

    @property
    def units(self):
        return self._units

    @property
    def info(self):
        return self._info

    def to(self, units):
        """Return a new Variable with the data converted to *units*.

        The new Variable owns its data and is writeable.

        Parameters
        ----------

        units : str
            Trick units to convert the Variable to.

        Returns
        -------

        `Variable`

        """
        if self._units is None:
            raise Exception("variable has unknown units")
        data = trick_units.convert_units(self, self._units, units)
        return Variable(data, units, info=self._info, readonly=False)

    def copy(self, order="C"):
        """Return a new Variable with a copy of the data.

        The new Variable owns its data and is writeable.

        Parameters
        ----------

        order: {'C', 'F', 'A', 'K'}, optional
            Controls the memory layout of the copy. 'C' means C-order, 'F' means F-order, 'A' means
            'F' if a is Fortran contiguous, 'C' otherwise. 'K' means match the layout of a as
            closely as possible. (Note that this function and `numpy.copy` are very similar, but have
            different default values for their order= arguments.)

        Returns
        -------

        `Variable`

        """
        return np.ndarray.copy(self, order)

    def cumsum(self, axis=None, dtype=None, out=None):
        """Return the cumulative sum of the elements along the given axis.

        Refer to *numpy.cumsum* for full documentation.

        """
        return Variable(self.view(np.ndarray).cumsum(axis=axis,
                                                     dtype=dtype,
                                                     out=out),
                        self._units,
                        info=self._info,
                        readonly=False)

    def max(self, axis=None, out=None):
        """Return the maximum along a given axis.

        Refer to *numpy.amax* for full documentation.

        """
        return Variable(self.view(np.ndarray).max(axis=axis,
                                                  out=out),
                        self._units,
                        info=self._info,
                        readonly=False)

    def min(self, axis=None, out=None):
        """Return the minimum along a given axis.

        Refer to *numpy.amin* for full documentation.

        """
        return Variable(self.view(np.ndarray).min(axis=axis,
                                                  out=out),
                        self._units,
                        info=self._info,
                        readonly=False)

    def mean(self, axis=None, dtype=None, out=None):
        """Returns the average of the array elements along given axis.

        Refer to *numpy.mean* for full documentation.

        """
        return Variable(self.view(np.ndarray).mean(axis=axis,
                                                   dtype=dtype,
                                                   out=out),
                        self._units,
                        info=self._info,
                        readonly=False)

    def round(self, decimals=0, out=None):
        """Return a new Variable with each element rounded to the given number of decimals.

        Refer to *numpy.around* for full documentation.

        """
        return Variable(self.view(np.ndarray).round(decimals=decimals,
                                                    out=out),
                        self._units,
                        info=self._info,
                        readonly=False)

    def std(self, axis=None, dtype=None, out=None, ddof=0):
        """Returns the standard deviation of the array elements along given axis.

        Refer to *numpy.std* for full documentation.

        """
        return Variable(self.view(np.ndarray).std(axis=axis,
                                                  dtype=dtype,
                                                  out=out,
                                                  ddof=ddof),
                        self._units,
                        info=self._info,
                        readonly=False)

    def sum(self, axis=None, dtype=None, out=None):
        """Return the sum of the array elements over the given axis.

        Refer to *numpy.sum* for full documentation.

        """
        return Variable(self.view(np.ndarray).sum(axis=axis,
                                                  dtype=dtype,
                                                  out=out),
                        self._units,
                        info=self._info,
                        readonly=False)

    def trace(self, offset=0, axis1=0, axis2=1, dtype=None, out=None):
        """Return the sum along diagonals of the Variable array.

        Refer to *numpy.trace* for full documentation.

        """
        return Variable(self.view(np.ndarray).trace(offset=offset,
                                                    axis1=axis1,
                                                    axis2=axis2,
                                                    dtype=dtype,
                                                    out=out),
                        self._units,
                        info=self._info,
                        readonly=False)

    def __str__(self):
        array_str = np.array2string(self.view(np.ndarray), separator=", ")
        if self.units is None:
            return array_str
        else:
            return "{} {}".format(array_str, self.units)

    def __repr__(self):
        array_str = np.array2string(self.view(np.ndarray), prefix="Variable(", separator=", ")
        if self.units is None:
            return "Variable({})".format(array_str)
        else:
            return "Variable({}, '{}')".format(array_str, self.units)
