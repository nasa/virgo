import os, sys, shutil, inspect
import unittest
import io
from numpy.testing import assert_allclose
import pdb

import virgo
from virgo.Virgo import *
meshes_dir=os.path.join(os.path.dirname(virgo.__file__), 'meshes')
tests_dir=os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
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
        self.scene['actors']['cube_actor'] = {'mesh': 'VIRGO_PREFAB:cube'}
        self.scene['actors']['sphere_actor'] = {'mesh': 'VIRGO_PREFAB:sphere'}
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
        # Can't do this yet, see create_test_nodes docstring
        #self.instance.initialize()
        #self.assertNotEqual(self.instance.nodes, {})


    def create_test_nodes(self):
        """
        A controller needs more setup before initialize() can be called,
        see the bottom of VirgoScene.initialize_nodes() where many things
        are passed through into the controller. This function will populate
        self.nodes in a similar way to VirgoScene.initialize_nodes() without
        actually calling that function. 

        Returns: dictionary of nodes, similar to what VirgoScene.initialize()
        nodes produces.

        TODO: Figure out if we should be mocking VirgoScene content or
        calling it directly here. -Jordan July 2026
        """
        nodes = {}
        for name in ['cube_actor', 'sphere_actor']:
            nodes[name] = VirgoSceneNode(name=name)
            nodes[name].create_trail()
        return nodes

    def test_enable_trails(self):
        # 1. Setup
        self.instance = VirgoControlCenter(renderers=self.renderers,
                                           render_window=self.render_window,
                                           interactor=self.interactor,
                                           scene=self.scene)
        self.instance.nodes = self.create_test_nodes()
        self.instance.enable_trails()
        # Assert that all actor trails are on
        for n in self.instance.nodes:
            self.assertTrue(self.instance.nodes[n].is_trail_visible())
    

    def test_disable_trails(self):
        # 1. Setup
        self.instance = VirgoControlCenter(renderers=self.renderers, 
                                           render_window=self.render_window, 
                                           interactor=self.interactor, 
                                           scene=self.scene)
        self.instance.nodes = self.create_test_nodes()
        self.instance.disable_trails()
        # Assert that all actor trails are off
        for n in self.instance.nodes:
            self.assertFalse(self.instance.nodes[n].is_trail_visible())