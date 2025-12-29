import os, sys, shutil, inspect
import unittest
import io
from unittest.mock import patch
from numpy.testing import assert_allclose
import pdb

# Add path to virgo module
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
virgo_dir=os.path.abspath(os.path.join(thisFileDir, '../'))
sys.path.append(virgo_dir)
from Virgo import *
meshes_dir=os.path.join(virgo_dir, 'meshes')
tests_dir=os.path.join(virgo_dir, 'tests')
from VisualizableTestCase import VisualizableTestCase

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoControlCenterInitTestCase))
    return (suites)


class VirgoControlCenterInitTestCase(unittest.TestCase):
    def setUp(self):
        self.renderers = VirgoScene.setup_renderers(bg_color=[0,0,0])
        self.render_window = vtkRenderWindow()
        self.interactor = vtkRenderWindowInteractor()
        self.scene = {}
        self.scene['actors']  = {}
        self.scene['actors']['test_actor'] = {'mesh': 'VIRGO_PREFAB:cube'}
        self.scene['data_source']  = {}
        self.scene['data_source']['trickpy']  = {}
        self.scene['data_source']['trickpy']['time']  = {}
        self.scene['data_source']['trickpy']['pos']  = {}
        self.scene['data_source']['trickpy']['time']['group']  = "one_body_static"
        self.scene['data_source']['trickpy']['pos']['group']  = "one_body_static"
        self.scene['data_source']['trickpy']['time']['var']  = "sys.exec.out.time"
        self.scene['data_source']['trickpy']['pos']['var']  = "position[0-2]"

    def tearDown(self):
        pass

    def post_init_nominal_assertions(self, inst: VirgoControlCenter):
        self.assertIs(inst.verbosity, 1)

    def test_init_nominal(self):

        self.instance = VirgoControlCenter(renderers=self.renderers,
                                           render_window=self.render_window,
                                           interactor=self.interactor,
                                           scene=self.scene)

        self.post_init_nominal_assertions(self.instance)

        # A controller needs more setup before initialize() can be called,
        # see the bottom of VirgoScene.initialize_nodes() where many things
        # are passed through into the controller
        #self.instance.initialize()
        #self.assertNotEqual(self.instance.nodes, {})



