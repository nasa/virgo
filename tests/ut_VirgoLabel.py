import os, sys, inspect
import unittest
import numpy as np

import virgo
from virgo.VirgoLabel import VirgoLabel
meshes_dir=os.path.join(os.path.dirname(virgo.__file__), 'meshes')
tests_dir=os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
from VisualizableTestCase import VisualizableTestCase

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoLabelTestCase))
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoLabelStaticFunctionsTestCase))
    return (suites)

class VirgoLabelTestCase(VisualizableTestCase):

    def setUp(self):
        # Actors to be used in node construction
        self.label1 = VirgoLabel(name='myname', text='simple text')
        self.label2 = VirgoLabel(name='velocity', text='vel: {vel[0]}')
        self.label3 = VirgoLabel(name='velocity', text='vel: {vel[0]:.2f}')

    def tearDown(self):
        self.instance = None
        self.label1 = None
        self.label2 = None
        self.label3 = None

    def test_construction(self):
        """
        Simple construction assertions
        """

        # TODO more assertions go here
        self.assertEqual(self.label1.name, 'myname')
        self.assertEqual(self.label1.data_source, None)
        self.assertEqual(self.label1.scale, 0.3)

        self.assertEqual(self.label2.name, 'velocity')
        self.assertEqual(self.label3.name, 'velocity')


    def test_labels_enabled(self):
        """
        Enable the labels to show they are visible
        """

        self.label1.enable()
        self.label2.set_position([0, 0, 1])
        self.label2.enable()
        self.label3.set_position([0, 0, 2])
        self.label3.enable()

        # Visualize
        actors = [self.label1.get_follower(), self.label2.get_follower(),
                  self.label3.get_follower()]
        #self.vis(actors=actors, show_origin=1, show_grid=0)


class VirgoLabelStaticFunctionsTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_find_clauses(self):
        """
        Test the find_clauses static method
        """
        # No special curly brace {} clauses
        text = "hello"
        clauses = VirgoLabel.find_clauses(text)
        self.assertEqual(clauses, []) # Returns empty string

        # One special curly brace {} clause with no formatting
        # and missing the time part of the clause
        text = "hello {myvar[0]}"
        clauses = VirgoLabel.find_clauses(text)
        # Returns a list of one tuple with empty string as 2nd value
        self.assertEqual(clauses[0].var, 'myvar[0]')
        self.assertEqual(clauses[0].time, '')
        self.assertEqual(clauses[0].fmt, '')

        # One special curly brace {} clause with formatting
        # and the time part of the clause
        text = "hello {myvar[0]@mytime:.2f}"
        clauses = VirgoLabel.find_clauses(text)
        # Returns a list of one tuple
        self.assertEqual(clauses[0].var, 'myvar[0]')
        self.assertEqual(clauses[0].time, 'mytime')
        self.assertEqual(clauses[0].fmt, '.2f')

        # Two special curly brace {} clauses both with formatting
        text = "hello {myvar[0]@mytime1:.2f} {myvar[1]@mytime2:04x}"
        clauses = VirgoLabel.find_clauses(text)
        # Returns a list of two tuples
        self.assertEqual(clauses[0].var, 'myvar[0]')
        self.assertEqual(clauses[0].time, 'mytime1')
        self.assertEqual(clauses[0].fmt, '.2f')
        self.assertEqual(clauses[1].var, 'myvar[1]')
        self.assertEqual(clauses[1].time, 'mytime2')
        self.assertEqual(clauses[1].fmt, '04x')