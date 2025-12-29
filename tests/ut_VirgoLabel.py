import os, sys, inspect
import unittest
import numpy as np

# Add path to virgo module
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
virgo_dir=os.path.abspath(os.path.join(thisFileDir, '../'))
sys.path.append(virgo_dir)
from VirgoLabel import VirgoLabel
meshes_dir=os.path.join(virgo_dir, 'meshes')
tests_dir=os.path.join(virgo_dir, 'tests')
from VisualizableTestCase import VisualizableTestCase

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoLabelTestCase))
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

    def test_find_clauses(self):
        """
        Test the find_clauses static method
        """
        # No special curly brace {} clauses
        text = "hello"
        clauses = VirgoLabel.find_clauses(text)
        self.assertEqual(clauses, []) # Returns empty string

        # One special curly brace {} clause with no formatting
        text = "hello {myvar[0]}"
        clauses = VirgoLabel.find_clauses(text)
        # Returns a list of one tuple with empty string as 2nd value
        self.assertEqual(clauses[0].var, 'myvar[0]')
        self.assertEqual(clauses[0].fmt, '')

        # One special curly brace {} clause with formatting
        text = "hello {myvar[0]:.2f}"
        clauses = VirgoLabel.find_clauses(text)
        # Returns a list of one tuple
        self.assertEqual(clauses[0].var, 'myvar[0]')
        self.assertEqual(clauses[0].fmt, '.2f')

        # Two special curly brace {} clauses both with formatting
        text = "hello {myvar[0]:.2f} {myvar[1]:04x}"
        clauses = VirgoLabel.find_clauses(text)
        # Returns a list of two tuples
        self.assertEqual(clauses[0].var, 'myvar[0]')
        self.assertEqual(clauses[0].fmt, '.2f')
        self.assertEqual(clauses[1].var, 'myvar[1]')
        self.assertEqual(clauses[1].fmt, '04x')