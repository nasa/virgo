"""This module provides a generic interface for interacting with different kinds of paths, including
normal paths on the file system and paths to files contained in a tar file.

When a TrickPy function accepts a path-like argument, that argument may be a string or one of the
path objects defined in this module.  If the argument is a string, TrickPy will automatically
determine what kind of path it is.  If the string is the path to a tar file followed by a colon and
an additional path (e.g., ``"some/file.tar:some/path"``), TrickPy will recognize that as a `TarFile`
or `TarFilePath`.  Otherwise, TrickPy assumes the string is a `FileSystemPath`.

The API is modeled after Python's `pathlib` module.

"""

from __future__ import absolute_import

import os
import re
import tarfile
from collections import OrderedDict


class FileSystemPath(object):
    """A path on the file system.

    Attributes
    ----------

    path : str
        The path to the file.
    name : str
        The final component of the path (i.e., the basename).

    """

    def __init__(self, path):
        """Create a new `FileSystemPath`.

        Parameters
        ----------

        path : str
            The file system path.

        """
        self._path = path

    def iterdir(self):
        for file_name in os.listdir(self._path):
            yield FileSystemPath(os.path.join(self._path, file_name))

    def __truediv__(self, path):
        return FileSystemPath(os.path.join(self._path, path))
    __div__ = __truediv__       # Python 2 compatibility

    def open(self, mode="r"):
        return open(self._path, mode)

    def is_dir(self):
        return os.path.isdir(self._path)

    def is_file(self):
        return os.path.isfile(self._path)

    @property
    def name(self):
        return os.path.basename(self._path)

    @property
    def path(self):
        return self._path

    def __str__(self):
        return self._path


# The file object returned by the Python 2 version of tarfile.TarFile.extractfile method doesn't
# work as a context manager!  So we extend it here to add that capability.
class _TarExtractedFile(tarfile.ExFileObject):

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, traceback):
        return


class _TarMember(object):

    def __init__(self, tar, info):
        self._tar = tar
        self._info = info

    def extractfile(self):
        return self._tar.extractfile(self._info)


class _TarFileNode(object):

    def __init__(self, member):
        self._member = member

    def is_dir(self):
        return False

    def is_file(self):
        return True

    def extractfile(self):
        return self._member.extractfile()


class _TarDirectoryNode(object):

    def __init__(self):
        self._contents = OrderedDict()

    def insert(self, path, member):
        parts = path.split("/", 1)
        if len(parts) == 1:
            self._contents[parts[0]] = _TarFileNode(member)
        else:
            node = self._contents.setdefault(parts[0], _TarDirectoryNode())
            node.insert(parts[1], member)

    def get(self, path):
        parts = path.split("/", 1)
        if len(parts) == 1:
            return self._contents[parts[0]]
        else:
            return self._contents[parts[0]].get(parts[1])

    def is_dir(self):
        return True

    def is_file(self):
        return False

    def items(self):
        return self._contents.items()


class TarFilePath(object):
    """A path to a member in a tar archive.

    Attributes
    ----------

    path : str
        The path to the file, using TrickPy's format for a member of a tar file, which is the path
        to the tar file followed by a colon and then the name of the member.
    name : str
        The final component of the path (i.e., the basename).

    """

    def __init__(self, tar, path, node):
        self._tar = tar
        self._path = path
        self._node = node

    def iterdir(self):
        if not self._node.is_dir():
            raise NotADirectoryError(self.path)
        for (path, node) in self._node.items():
            yield TarFilePath(self._tar,
                              os.path.join(self._path, path),
                              node)

    def __truediv__(self, path):
        return TarFilePath(self._tar,
                           os.path.join(self._path, path),
                           self._node.get(path))
    __div__ = __truediv__       # Python 2 compatibility

    def open(self, mode="r"):
        if self.is_dir():
            raise IsADirectoryError(self.path)
        return self._node.extractfile()

    def is_dir(self):
        return self._node.is_dir()

    def is_file(self):
        return self._node.is_file()

    @property
    def name(self):
        return os.path.basename(self._path)

    @property
    def path(self):
        return "{}:{}".format(self._tar.path, self._path)

    def __str__(self):
        return self.path


class TarFile(object):
    """A tar file.

    Attributes
    ----------

    path : str
        The path to the tar file.

    """

    def __init__(self, path):
        """Create a new `TarFile` object to interact with the tar file at *path*.

        Parameters
        ----------

        path : str
            Path to the tar file.

        """

        self._path = path
        self._open()

        # Iterating over a tarfile.TarFile is very slow.  So we need to do this once and cache the
        # results.  Furthermore, we want to reconstruct the directory tree structure.
        self._root = _TarDirectoryNode()
        for member in self._file:
            # We don't care about the directories, because we infer them from the member names.
            # There's no guarantee the directory is even listed as a member in the tar file.
            if member.isfile():
                self._root.insert(member.name, _TarMember(self, member))

    def _open(self):
        self._file = tarfile.open(self._path, "r")
        self._file.fileobject = _TarExtractedFile

    def __del__(self):
        self._file.close()

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["_file"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._open()

    def iterdir(self):
        return TarFilePath(self, "", self._root).iterdir()

    def __truediv__(self, path):
        return TarFilePath(self, path, self._root.get(path))
    __div__ = __truediv__       # Python 2 compatibility

    def extractfile(self, info):
        return self._file.extractfile(info)

    @property
    def path(self):
        return self._path

    def __str__(self):
        return "TarFile('{}')".format(self._path)


_tar_file_re = re.compile(r"(?P<path>.+\.(tar|tgz|tar\.gz|tbz|tar\.bz2))(:(?P<member>.*))?")


def infer(path):
    """Return a path object for *path*.

    If the type of *path* is one of the path objects, return *path* unchanged.  Otherwise, look at
    the value of *path* and convert it to an appropriate path object.

    """
    if isinstance(path, TarFilePath) or isinstance(path, TarFile):
        return path
    elif isinstance(path, FileSystemPath):
        return path
    else:
        m = _tar_file_re.match(path)
        if m:
            path = m.group("path")
            member = m.group("member")
            tar = TarFile(path)
            if member is None or member == "":
                return tar
            else:
                return tar / member
        else:
            return FileSystemPath(path)
