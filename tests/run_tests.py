#!/usr/bin/env python3
import argparse
import doctest
import unittest, subprocess, collections
import os
import sys
import logging

from io import StringIO

import os, sys, pdb

import virgo
import virgo.Virgo
import virgo.VirgoActor
from virgo.Virgo import *

this_dir = os.path.abspath(os.path.dirname(__file__))
virgo_dir = os.path.dirname(virgo.__file__)

def run_subprocess(command, m_shell=False, m_cwd=None, m_stdout=subprocess.PIPE, m_stderr=subprocess.PIPE):
    """
    Utility method for running a subprocess and returning stdout, stderr, and return code

    >>> result = run_subprocess(command='echo hi', m_shell=subprocess.PIPE, m_stdout=subprocess.PIPE)
    >>> result.code
    0
    >>> result.stdout  #doctest: +ELLIPSIS
    'hi...

    Parameters
    ----------
    command : str
        command to be run in subprocess instance
    m_shell : bool
        passthrough to subprocess shell parameter
    m_cwd : bool
        passthrough to subprocess cwd parameter
    m_stdout : bool
        passthrough to subprocess stdout parameter
    m_stderr : bool
        passthrough to subprocess stderr parameter

    Returns
    -------
    namedtuple
        Collection of process's final exit code, stdout, and stderr
    """
    result = collections.namedtuple("Process", ["code", "stdout", "stderr"])
    p = subprocess.Popen(command, shell=m_shell, cwd=m_cwd, stdout=m_stdout, stderr=m_stderr)
    result.stdout, result.stderr = p.communicate()
    if (result.stdout != None):
        result.stdout = result.stdout.decode(errors='ignore')
    if (result.stderr != None):
        result.stderr = result.stderr.decode(errors='ignore')
    result.code = p.returncode
    return result

def run_tests(args):

    os.environ["VIRGO_BATCH_TESTS_OVERRIDE"] = "1"  # Force all visualization off
    loader = unittest.TestLoader()

    suites = loader.discover(start_dir=this_dir, pattern='test.py', top_level_dir=this_dir)
    overall_suite = unittest.TestSuite()
    for test_suite in suites:
        if test_suite._tests:
            overall_suite.addTests(test_suite)

    logger = logging.getLogger()
    logger.handlers = []
    logger.disabled = True

    # Run all unit tests
    print("Executing all python unit test suites...")
    runner = unittest.TextTestRunner(verbosity=args.verbosity, buffer=True)
    ut_results = runner.run(overall_suite)

    # Run all doc tests by eating our own dogfood. Doctests are run in-process
    # (rather than via `python -m doctest <file>`) because Virgo.py and
    # VirgoActor.py use package-relative imports, which only resolve when the
    # module is imported as part of the virgo package, not as a standalone script.
    doctest_modules = [virgo.Virgo, virgo.VirgoActor]
    doctest_results = []
    for module in doctest_modules:
        print(f"Running doctest on {module.__name__}...")
        stdout_capture = StringIO()
        previous_stdout = sys.stdout
        sys.stdout = stdout_capture
        try:
            result = doctest.testmod(module, verbose=True)
        finally:
            sys.stdout = previous_stdout
        code = 1 if result.failed > 0 else 0
        if code != 0:
            print(f"  FAILED")
        else:
            print(f"  OK")
        doctest_results.append(code)
        with open(f'{module.__name__}_doctest_stdout.txt', 'w') as f:
            f.write(stdout_capture.getvalue())

    print(f"doctest verbose output can be found in tests/<file>_doctest_*.txt")
    return (len(ut_results.failures) > 0  or len(ut_results.errors) > 0 or
            any(doctest_results))


# Main execution block
if __name__ == '__main__':
    # Create our Argument Parser
    parser = argparse.ArgumentParser(
        description="Execute all VIRGO python unit and doc tests. Must be run from this directory"
        " inside a python3 environment with the virgo package installed (pip install .).")
    parser.add_argument("-v", "--verbosity", type=int,
         help="Reporting level when running from the console.", choices=[1, 2, 3, 4, 5], default=1)

    # Parse the arguments
    args = parser.parse_args()

    # Execute our tests
    sys.exit(run_tests(args))
