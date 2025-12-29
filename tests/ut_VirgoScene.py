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
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoSceneInitTestCase))
    return (suites)


class VirgoSceneInitTestCase(unittest.TestCase):
    def setUp(self):
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

    def post_init_nominal_assertions(self, inst: VirgoScene):
        self.assertIs(inst.controller_class, VirgoControlCenter)
        self.assertIs(inst.interactor_class, VirgoInteractorStyle)
        self.assertNotEqual(inst.scene, {})
        self.assertIs(inst.verbosity, 1)
        self.assertIs(inst.splash, True)
        self.assertIs(inst.headless, True)
        self.assertIsNone(inst.stop_time)
        self.assertEqual(inst.images_dir, "/tmp/")
        self.assertEqual(inst.video_filename, "/tmp/virgo.mp4")
        self.assertEqual(inst.fs, 14)
        assert_allclose(inst.max_sim_time, 0.0)
        self.assertIsNone(inst.vdl)
        self.assertEqual(inst.nodes, {})
        assert_allclose(inst.background_color, [0, 0, 0.05])
        assert_allclose(inst.highlight_color, [1, 1, 0])
        self.assertEqual(inst.description, "Untitled VIRGO Window")
        self.assertEqual(inst.name, "Untitled VIRGO Scene")
        self.assertEqual(inst.window_height, 600)
        self.assertEqual(inst.window_width, 800)
        self.assertIsNotNone(inst.render_window)
        self.assertNotEqual(inst.renderers, {})
        self.assertIsInstance(inst.interactor_style, inst.interactor_class)
        self.assertIsInstance(inst.controller, inst.controller_class)

    def test_init_nominal(self):

        self.instance = VirgoScene(scene=self.scene, headless=True)

        self.post_init_nominal_assertions(self.instance)

        self.instance.initialize()
        self.assertNotEqual(self.instance.nodes, {})
        win_size = self.instance.render_window.GetSize()
        assert_allclose(win_size, [self.instance.window_width, self.instance.window_height])
        self.assertTrue(self.instance.controller.is_initialized())
        self.assertTrue(self.instance.initialized)



