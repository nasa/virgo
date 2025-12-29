import os, sys, shutil, inspect
import unittest
import io
from unittest.mock import patch
import pdb

# Add path to virgo module
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
virgo_dir=os.path.abspath(os.path.join(thisFileDir, '../'))
sys.path.append(virgo_dir)
from VirgoDataPlayback import *
meshes_dir=os.path.join(virgo_dir, 'meshes')
tests_dir=os.path.join(virgo_dir, 'tests')
from VisualizableTestCase import VisualizableTestCase

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoDataPlaybackInitTestCase))
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoDataPlaybackFunctionsTestCase))
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoDataPlaybackHeadlessTestCase))
    return (suites)

    import time

class VirgoDataPlaybackInitTestCase(unittest.TestCase):
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

    def test_init_RUN_0(self):
        self.instance = VirgoDataPlayback(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_0'),
            scene=self.scene, headless=True)

        # NOTE: if headless=False passed into self.instance, this initialize()
        # method somehow will affect later suite tests. I noticed the
        # self.instance.run() in a completely different suite would render an
        # image to a window even though that instance has headless=True. I never
        # understood this and moved forward with headless=True on all
        # self.instance constructors, as that's a better approach anyhow. Still
        # wish I knew how this could happen - Jordan 11/2025
        self.instance.initialize()
    
class VirgoDataPlaybackFunctionsTestCase(unittest.TestCase):
    def setUp(self):
        self.scene = {}
        self.scene['actors']  = {}
        self.scene['actors']['test_actor'] = {'mesh': 'VIRGO_PREFAB:cube'}
        self.scene['vectors']  = {}
        self.scene['vectors']['test_vector'] = {'parent': 'test_actor'}
        self.scene['data_source']  = {}
        self.scene['data_source']['trickpy']  = {}
        self.scene['data_source']['trickpy']  = {}
        self.scene['data_source']['trickpy']['time']  = {}
        self.scene['data_source']['trickpy']['pos']  = {}
        self.scene['data_source']['trickpy']['time']['group']  = "one_body_static"
        self.scene['data_source']['trickpy']['pos']['group']  = "one_body_static"
        self.scene['data_source']['trickpy']['time']['var']  = "sys.exec.out.time"
        self.scene['data_source']['trickpy']['pos']['var']  = "position[0-2]"

        self.instance = VirgoDataPlayback(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_0'),
            scene=self.scene)

    def tearDown(self):
        pass

    def test_create_actor(self):
        actor_dict = self.scene['actors']['test_actor']
        actor = self.instance.create_actor('test_actor', actor_dict)
        self.assertEqual(actor.name, 'test_actor')

    def test_create_vector(self):
        vector_dict = self.scene['vectors']['test_vector']
        vector = self.instance.create_vector('test_vector', vector_dict)
        self.assertEqual(vector.name, 'test_vector')
        self.assertEqual(vector.mesh, 'VIRGO_PREFAB:arrow')

    def test_create_custom_vector(self):
        """
        Test customization of a vector by changing it's configurable parameters
        """
        self.scene['vectors']['test_vector']['scale'] = 10.0
        self.scene['vectors']['test_vector']['tip_length'] = 0.7
        self.scene['vectors']['test_vector']['tip_radius'] = 0.1
        self.scene['vectors']['test_vector']['tip_resolution'] = 5
        self.scene['vectors']['test_vector']['shaft_radius'] = 0.03
        self.scene['vectors']['test_vector']['shaft_resolution'] = 5
        vector_dict = self.scene['vectors']['test_vector']
        custom_vector = self.instance.create_vector('test_vector', vector_dict)
        self.assertEqual(custom_vector.name, 'test_vector')
        self.assertEqual(custom_vector.mesh, 'VIRGO_PREFAB:arrow')


class VirgoDataPlaybackHeadlessTestCase(unittest.TestCase):
    def setUp(self):
        self.test_name =f"{self.__class__.__name__}_{self._testMethodName}"
        self.test_video = os.path.join(thisFileDir, '.'+self.test_name+'.mp4')
        self.scene = {}
        self.scene['resolution']  = "640x320"
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

    def test_headless_RUN_0_no_driven_by(self):
        """
        This test case runs headless mode on RUN_0 which has no driven nodes, so
        nothing should be rendered
        """
        self.instance = VirgoDataPlayback(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_0'),
            scene=self.scene, headless=True, video_filename=self.test_video)

        self.instance.initialize()
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            self.instance.run()
            printed_output = mock_stdout.getvalue().strip()
            self.assertIn("Nothing to render", printed_output)


    def test_headless_RUN_0_driven_by(self):
        """
        This test case runs headless mode on RUN_0 which has a driven_by
        section so a video is rendered even though there's no motion in
        the data file
        """
        self.scene['actors']['test_actor']['driven_by'] = {}
        self.scene['actors']['test_actor']['driven_by']['time'] = 'time'
        self.scene['actors']['test_actor']['driven_by']['pos'] =  'pos'

        self.instance = VirgoDataPlayback(
            run_dir=os.path.join(tests_dir, 'trickpy_data_source/RUN_0'),
            scene=self.scene, headless=True, video_filename=self.test_video)

        self.instance.initialize()
        self.instance.run()
