#!/usr/bin/env python3

"""
Unit test script to test VIRGO module

If you are trying to run a single test, suggest using something like:
  python -m unittest ut_VirgoScene.py 
"""

# An attempt to workaround unsafe garbage collection interacting with python VTK
# See the following link for details on why we do this
# https://discourse.vtk.org/t/looking-for-guidance-on-writing-python-unit-tests-using-python-vtk/16148/6
import gc; gc.disable()

import os, sys, pdb
import unittest, argparse

import ut_VirgoTrickpyFileLoader
import ut_VirgoDataFileSource
import ut_VirgoActor
import ut_VirgoDataPlayback
import ut_VirgoScene
import ut_VirgoControlCenter
import ut_VirgoSceneNode
import ut_VirgoLabel
import ut_VirgoConsole

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
      description='Run all VIRGO unit tests.'
    )
    parser.add_argument('--headless', action="store_true",
      help='Forcibly suppress all rendered windows by setting'
      ' VIRGO_BATCH_TESTS_OVERRIDE=1 before execution.'
    )
    parser.add_argument('-t', '--times-to-repeat', default=1, type=int,
      help='Re-run all unit tests this number of times. This is helpful in'
      'testing determinism but be careful because it uses a lot of memory'
    )
    args = parser.parse_args()

    if args.headless: # Never bring up a rendering window
      os.environ["VIRGO_BATCH_TESTS_OVERRIDE"] = "1"

    for i in range(args.times_to_repeat):
        print(f"\n--- Suite execution {i+1}/{args.times_to_repeat}---")
        # Create the suite
        suites = unittest.TestSuite()

        suites.addTests(ut_VirgoTrickpyFileLoader.suite())
        suites.addTests(ut_VirgoDataFileSource.suite())
        suites.addTests(ut_VirgoActor.suite())
        suites.addTests(ut_VirgoSceneNode.suite())
        suites.addTests(ut_VirgoLabel.suite())
        suites.addTests(ut_VirgoDataPlayback.suite())
        suites.addTests(ut_VirgoScene.suite())
        suites.addTests(ut_VirgoControlCenter.suite())
        suites.addTests(ut_VirgoConsole.suite())

        # Execute all tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suites)
        if not result.wasSuccessful():
            print(f"Failed on execution number {i+1}")
            sys.exit(1)
    else:
        print(f"Executed all tests {args.times_to_repeat} times with success!")
        sys.exit(0)
