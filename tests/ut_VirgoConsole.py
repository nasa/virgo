import os, sys, inspect
import unittest
import numpy as np

# Add path to virgo module
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
virgo_dir=os.path.abspath(os.path.join(thisFileDir, '../'))
sys.path.append(virgo_dir)
from VirgoConsole import VirgoConsole
meshes_dir=os.path.join(virgo_dir, 'meshes')
tests_dir=os.path.join(virgo_dir, 'tests')
from VisualizableTestCase import VisualizableTestCase

# --- Modular VTK Imports (Replaces 'import vtk') ---
from vtkmodules.vtkRenderingCore import (
  vtkRenderer,
  vtkRenderWindowInteractor,
)
def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoConsoleTestCase))
    return (suites)

# I'm not quite sure if VisualizableTestCase is a good idea for the testing of
# VirgoConsole because right now self.renderer and self.interactor in VisualizableTestCase
# aren't instantiated until vis() is called. That's why I'm using a different approach
# here. -Jordan
class VirgoConsoleTestCase(unittest.TestCase):

    def setUp(self):
        self.renderer = vtkRenderer()
        self.interactor = vtkRenderWindowInteractor()

        self.console = VirgoConsole(renderer=self.renderer, interactor=self.renderer, vcc=None)

    def tearDown(self):
      pass

    def test_construction(self):
        """
        Simple construction assertions
        """
        self.assertEqual(self.console.font_size, 16)
        self.assertIn('stop', self.console.hidden_functions)
