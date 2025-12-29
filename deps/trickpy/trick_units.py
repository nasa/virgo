import ctypes
import os
import subprocess
import numpy as np

try:
    _module_path = os.path.abspath(os.path.dirname(__file__))
    _libtrickunits_path = os.path.join(_module_path, "trick_units", "libtrickunits.so")

    if not os.path.exists(_libtrickunits_path):
        p = subprocess.Popen(["make", "-C", os.path.join(_module_path, "trick_units")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()
        if p.returncode != 0:
            raise Exception("failed to build libtrickunits.so")

    _libtrickunits = ctypes.cdll.LoadLibrary(_libtrickunits_path)

    _libtrickunits.initialize.argtypes = []
    _libtrickunits.initialize.restype = ctypes.c_int

    _status = _libtrickunits.initialize()
    if _status != 0:
        raise Exception("failed to initialize units conversion system")

    _libtrickunits.convert_doubles.argtypes = [ctypes.POINTER(ctypes.c_double),
                                               ctypes.c_size_t,
                                               ctypes.c_char_p,
                                               ctypes.c_char_p,
                                               ctypes.POINTER(ctypes.c_double)]
    _libtrickunits.convert_doubles.restype = ctypes.c_int

    def convert_units(value, from_units, to_units):
        value = np.require(value,
                           dtype=np.float64,
                           requirements="C")
        result = np.empty_like(value)
        status = _libtrickunits.convert_doubles(value.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                                                ctypes.c_size_t(value.size),
                                                ctypes.c_char_p(from_units.encode("ascii")),
                                                ctypes.c_char_p(to_units.encode("ascii")),
                                                result.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
        if status != 0:
            raise Exception("failed to convert from '{}' to '{}'".format(from_units, to_units))
        return result

except:
    def convert_units(value, from_units, to_units):
        raise Exception("unable to convert units, library was not built properly")
