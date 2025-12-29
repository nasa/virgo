from __future__ import print_function

import sys


def _print_summary(message, paths):
    if paths:
        print(message, file=sys.stderr)
        for p in paths:
            print("  {}".format(p), file=sys.stderr)


def print_files_summary(files):
    _print_summary("Failed to load the following files:", files)


def print_runs_summary(runs):
    _print_summary("Failed to load at least one file in the following RUNs:", runs)
