import os, sys, shutil, inspect
import unittest
import pdb
from numpy.testing import assert_allclose

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
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoActorStaticFunctionsTestCase))
    return (suites)

class VirgoActorStaticFunctionsTestCase(unittest.TestCase):
    """
    Test the expand_env_vars function
    """
    def test_expand_env_vars(self):
        os.environ['MYVAR1'] = '/home/billy'
        os.environ['APP'] = 'myapp'
        
        output = VirgoActor.expand_env_vars("Hello $MYVAR1")
        self.assertEqual(output, 'Hello /home/billy')

        output = VirgoActor.expand_env_vars("Path: ${MYVAR1}/projects")
        self.assertEqual(output, 'Path: /home/billy/projects')

        output = VirgoActor.expand_env_vars("%APP% lives in ${MYVAR1}/%APP%")
        self.assertEqual(output, 'myapp lives in /home/billy/myapp')
        
        output = VirgoActor.expand_env_vars("No var here")
        self.assertEqual(output, 'No var here')

        with self.assertRaises(RuntimeError):
            output = VirgoActor.expand_env_vars("$UNDEFINED_VAR stays")

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
        # Note that GetOrientation returns X,Y,Z but offset_ypr is Z,Y,X
        for i, (a, b) in enumerate(zip(self.instance.GetOrientation(), [0.0, 0.0, 45.0])):
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
        self.assertEqual(self.instance.name, 'No Name')
        self.assertEqual(self.instance.offset_pos, [0, 1, 0])
        for i, (a, b) in enumerate(zip(self.instance.GetPosition(), [0.0, 1.0, 0.0])):
            self.assertAlmostEqual(a, b)
        # Note that GetOrientation returns X,Y,Z but offset_ypr is Z,Y,X
        for i, (a, b) in enumerate(zip(self.instance.GetOrientation(), [0.0, 0.0, -45.0])):
            self.assertAlmostEqual(a, b)
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)
    
    # VIRGO_PREFAB_cube tests, dimensions and scale
    def test_init_with_dimensions_cube(self):
        """
        Test the VIRGO_PREFAB:cube option with custom dimensions - regular case
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:cube", dimensions=[3.0, 4.0, 5.0])
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        self.instance.initialize()
        self.assertEqual(self.instance.dimensions, [3.0, 4.0, 5.0])
        self.assertEqual(self.instance.source.GetXLength(), 3.0)
        self.assertEqual(self.instance.source.GetYLength(), 4.0)
        self.assertEqual(self.instance.source.GetZLength(), 5.0)
    
    def test_init_with_zero_dimensions_cube(self):
        """
        Test the VIRGO_PREFAB:cube option with custom dimensions - error case
        """
        with self.assertRaises(ValueError) as error_info:
            self.instance = VirgoActor(mesh="VIRGO_PREFAB:cube", dimensions=[0,0,0])
            #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        self.assertIn("dimensions must be greater than 0.0, got", str(error_info.exception))

    def test_init_less_dimensions_cube(self):
        """
        Test the VIRGO_PREFAB:cube option with less than required dimensions - error case
        """
        with self.assertRaises(ValueError) as error_info:
            self.instance = VirgoActor(mesh="VIRGO_PREFAB:cube", dimensions=[4.0])
            #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        self.assertIn("must contain either 2 or 3 values, got 1 values", str(error_info.exception))

    def test_init_more_dimensions_cube(self):
        """
        Test the VIRGO_PREFAB:cube option with more than required dimensions - error case
        """
        with self.assertRaises(ValueError) as error_info:
            self.instance = VirgoActor(mesh="VIRGO_PREFAB:cube", dimensions=[3.1, 4.1, 5.9, 2.6])
            #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        self.assertIn("must contain either 2 or 3 values, got 4 values", str(error_info.exception))

    def test_init_default_dimensions_cube(self):
        """
        Test the VIRGO_PREFAB:cube option with no dimensions, fallback to default
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:cube")
        self.instance.initialize()

        self.assertEqual(self.instance.source.GetXLength(), 1.0)
        self.assertEqual(self.instance.source.GetYLength(), 1.0)
        self.assertEqual(self.instance.source.GetZLength(), 1.0)
        
    def test_init_with_neg_dimensions_cube(self):
        """
        Test the VIRGO_PREFAB:cube option with a negative dimension - expecting an error
        """
        with self.assertRaises(ValueError) as error_info:
            self.instance = VirgoActor(mesh="VIRGO_PREFAB:cube", dimensions=[-3, 3, 3])
            self.vis(actors=self.instance, show_origin=1, show_grid=1)
        self.assertIn("dimensions must be greater than 0.0,", str(error_info.exception))

    def test_init_with_dimensions_cylinder(self):
        """
        Test the VIRGO_PREFAB:cylinder option with custom dimensions - regular case
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:cylinder", dimensions=[5, 1])
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        self.instance.initialize()
        self.assertEqual(self.instance.GetScale(), (1.0, 1.0, 1.0))
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        bb = self.instance.GetBounds()
        # Z radius is at midpoint of line between vertices
        assert_allclose(bb, [-1.0, 1.0, -2.5, 2.5, -0.9980267286300659, 0.9980267286300659])

    def test_init_with_dimensions_and_scale_cylinder(self):
        """
        Test the VIRGO_PREFAB:cylinder option with custom dimensions - regular case
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:cylinder", dimensions=[5.0, 1.0], scale=2.0)
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        self.instance.initialize()
        self.assertEqual(self.instance.GetScale(), (2.0, 2.0, 2.0))
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        bb = self.instance.GetBounds()
        # Z radius is at midpoint of line between vertices
        assert_allclose(bb, [-2.0, 2.0, -5.0, 5.0, -1.99605345726, 1.99605345726])

    def test_init_with_zero_dimensions_cylinder(self):
        """
        Test the VIRGO_PREFAB:cylinder option with custom dimensions - zero error case
        """
        with self.assertRaises(ValueError):
            self.instance = VirgoActor(mesh="VIRGO_PREFAB:cylinder", dimensions=[0,0])
            #self.vis(actors=self.instance, show_origin=1, show_grid=1)

    # Holding off on testing to finalize location for error checking, whether within VirgoActor.py or just higher up.
    # TODO negative dimension cube -> raise value error

    def test_init_with_scale_cube(self):
        """
        Test the VIRGO_PREFAB:cube option with custom scaling
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:cylinder", dimensions=[5, 1], scale=0.5)
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        self.instance.initialize()
        self.assertEqual(self.instance._user_scale, 0.5)
        self.assertEqual(self.instance.GetScale(), (0.5, 0.5, 0.5))

    def test_init_zero_scale_cube(self):
        """
        Test the VIRGO_PREFAB:cube option with zero scale - expecting an error
        """
        with self.assertRaises(RuntimeError) as error_info:
            self.instance = VirgoActor(mesh="VIRGO_PREFAB:cube", scale=0.0)
            #self.vis(actors=self.instance, show_origin=1, show_grid=1)
        self.assertIn("scale must be a positive real number", str(error_info.exception))
        
    def test_init_negative_scale_cube(self):
        """
        Test the VIRGO_PREFAB:cube option with negative scaling - expecting error
        """
        with self.assertRaises(RuntimeError) as error_info:
            self.instance = VirgoActor(mesh="VIRGO_PREFAB:cube", scale=-5.0)
        self.assertIn("scale must be a positive real number", str(error_info.exception))
   
    def test_init_prefab_moon(self):
        """
        Test the VIRGO_PREFAB:moon option
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:moon")
        #self.vis(actors=self.instance, show_origin=1, oal=[3e6, 3e6, 3e6])
        self.assertEqual(self.instance.scale, (1.0, 1.0, 0.9987917841320982))
        # TODO assertions go here!

    def test_init_prefab_earth(self):
        """
        Test the VIRGO_PREFAB:earth option
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:earth")
        # TODO assertions go here!
        #self.vis(actors=self.instance, show_origin=1, oal=[1e7, 1e7, 1e7])

    def test_init_prefab_wgs84_earth(self):
        """
        Test the VIRGO_PREFAB:wgs84-earth option

        TODO: there is something weird with visualizing this test. The earth is showing
        up black even though it works in examples/launch/ and I swear I saw it work
        partially in this test one time but never again -Jordan 2025
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:wgs84-earth")
        # TODO assertions go here!
        #self.vis(actors=self.instance, show_origin=1, show_grid=0, oal=[1e7, 1e7, 1e7])

    def test_init_prefab_arrow(self):
        """
        Test the VIRGO_PREFAB:earth option
        """
        self.instance = VirgoActor(mesh="VIRGO_PREFAB:arrow")
        # TODO assertions go here!
        #self.vis(actors=self.instance, show_origin=1, show_grid=1)