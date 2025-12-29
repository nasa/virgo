import os, sys, shutil, inspect
import unittest
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
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoActorTestCase))
    return (suites)

class VirgoActorTestCase(VisualizableTestCase):

    def setUp(self):
        pass

    def tearDown(self):
        self.instance = None
        del self.instance

    def test_incomplete_init(self):
        """
        Test a incomplete construction with optional args left out
        """
        self.instance = VirgoActor(mesh=os.path.join(meshes_dir, 'teapot.obj'))
        self.assertEqual(self.instance.name, 'No Name')
        self.assertEqual(self.instance.offset_ypr, None)

        #self.assertEqual(self.instance.are_axes_visible(), False)

    def test_init_with_ypr_offset(self):
        """
        Test a incomplete construction with a 45-degree pitch offset given
        """
        self.instance = VirgoActor(mesh=os.path.join(meshes_dir, 'teapot.obj'),
                                               offset_ypr=[45, 0, 0])
        self.instance.initialize()
        self.assertEqual(self.instance.name, 'No Name')
        self.assertEqual(self.instance.offset_ypr, [45, 0, 0])
        for i, (a, b) in enumerate(zip(self.instance.GetOrientation(), [45.0, 0.0, 0.0])):
            self.assertAlmostEqual(a, b)

    def test_init_with_pos_offset(self):
        """
        Test a incomplete construction with a [1, 0, 0] unit position offset given
        """
        self.instance = VirgoActor(mesh=os.path.join(meshes_dir, 'teapot.obj'),
                                               offset_pos=[1, 0, 0])
        self.instance.initialize()
        #import pdb; pdb.set_trace()
        self.assertEqual(self.instance.name, 'No Name')
        #self.assertAlmostEqual(self.instance.GetPosition()[0], 1.0)
        self.assertEqual(self.instance.offset_pos, [1, 0, 0])
        for i, (a, b) in enumerate(zip(self.instance.GetPosition(), [1.0, 0.0, 0.0])):
            self.assertAlmostEqual(a, b)
        #self.vis(actors=self.instance, show_origin=1, show_grid=0)

    def test_init_with_pos_and_ypr_offset(self):
        """
        Test a incomplete construction with a [0, 1, 0] unit position offset
        and [-45, 0, 0] yaw-pitch-roll offset given
        """
        self.instance = VirgoActor(mesh=os.path.join(meshes_dir, 'teapot.obj'),
                                               offset_pos=[0, 1, 0],
                                               offset_ypr=[-45, 0, 0])
        self.instance.initialize()
        #import pdb; pdb.set_trace()
        self.assertEqual(self.instance.name, 'No Name')
        #self.assertAlmostEqual(self.instance.GetPosition()[0], 1.0)
        self.assertEqual(self.instance.offset_pos, [0, 1, 0])
        for i, (a, b) in enumerate(zip(self.instance.GetPosition(), [0.0, 1.0, 0.0])):
            self.assertAlmostEqual(a, b)
        for i, (a, b) in enumerate(zip(self.instance.GetOrientation(), [-45.0, 0.0, 0.0])):
            self.assertAlmostEqual(a, b)
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)

    def test_init_prefab_moon(self):
        """
        Test the VIRGO_PREFAB:moon option
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:moon8k")
        #self.vis(actors=self.instance, show_origin=1, show_grid=1, oal=[3e6, 3e6, 3e6])
        # TODO assertions go here!

    def test_init_prefab_earth(self):
        """
        Test the VIRGO_PREFAB:earth option
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:earth")
        # TODO assertions go here!
        #self.vis(actors=self.instance, show_origin=1, show_grid=1, oal=[1e7, 1e7, 1e7])

    def test_init_prefab_arrow(self):
        """
        Test the VIRGO_PREFAB:earth option
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:arrow")
        # TODO assertions go here!
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)