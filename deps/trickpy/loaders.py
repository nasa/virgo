import os
import re
import multiprocessing
import warnings

from . import progress
from . import collections


class _TryWorker(object):

    def __init__(self, f):
        self.f = f

    def __call__(self, path):
        try:
            return self.f(path)
        except:
            return None


def _load_generic(paths, worker, description, show_progress, parallel, skip_errors):
    """Call *worker* for each element of *paths*."""

    if skip_errors:
        worker = _TryWorker(worker)

    number_paths = len(paths)

    if show_progress:
        prog = progress.ProgressBar(description, final_count=number_paths)

    if parallel:
        pool = multiprocessing.Pool()
        if show_progress:
            results = []
            for i, result in enumerate(pool.imap(worker, paths)):
                results.append(result)
                prog.show(i + 1)
        else:
            results = pool.map(worker, paths)
        pool.close()
    else:
        if show_progress:
            results = []
            for i, path in enumerate(paths):
                results.append(worker(path))
                prog.show(i + 1)
        else:
            results = map(worker, paths)

    if show_progress:
        prog.clear()

    return results


def load_groups(path, should_load, parse_group_name, groups, worker, show_progress, parallel, skip_errors):
    """Load the groups from a directory."""

    file_paths = []
    file_names = []
    group_names = []
    skipped_file_paths = []
    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if should_load(file_path):
            try:
                group_name = parse_group_name(file_name)
                if groups is None or group_name in groups:
                    file_paths.append(file_path)
                    file_names.append(file_name)
                    group_names.append(group_name)
            except:
                skipped_file_paths.append(file_path)

    results = _load_generic(file_paths, worker, "files", show_progress, parallel, skip_errors)

    data = {}
    for r, g, p in zip(results, group_names, file_paths):
        if r is None:
            skipped_file_paths.append(p)
        else:
            data[g] = r

    return collections.Groups(data), skipped_file_paths


_run_number_re = re.compile(r"RUN_(\d+)$")


def _is_run_dir(path):
    """Return ``True`` if *path* is a RUN directory."""
    file_name = os.path.basename(path)
    m = _run_number_re.match(file_name)
    if m:
        if os.path.isdir(path):
            return True
    return False


def _parse_run_number(path):
    """Parse the run number from the Monte Carlo RUN directory *path*."""
    file_name = os.path.basename(path)
    m = _run_number_re.match(file_name)
    if m:
        return int(m.group(1))
    raise Exception("unable to parse run number")


def load_monte_runs(path, runs, worker, show_progress, parallel, skip_errors, return_type=collections.Runs):
    """Load the RUN directories in a MONTE directory."""

    run_numbers = []
    run_paths = []
    run_paths_with_problems = []
    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if _is_run_dir(file_path):
            try:
                run_number = _parse_run_number(file_name)
                if runs is None or run_number in runs:
                    run_numbers.append(run_number)
                    run_paths.append(file_path)
            except:
                run_paths_with_problems.append(file_path)

    results = _load_generic(run_paths, worker, "RUN directories", show_progress, parallel, skip_errors)

    data = {}
    for r, n, p in zip(results, run_numbers, run_paths):
        if r is None:
            run_paths_with_problems.append(p)
        else:
            r, s = r
            data[n] = r
            if s:
                run_paths_with_problems.append(p)

    return return_type(data), run_paths_with_problems
