import os, sys, shutil, inspect
import unittest
import pdb
from numpy.testing import assert_allclose

import virgo
from virgo.VirgoAxes import *
meshes_dir=os.path.join(os.path.dirname(virgo.__file__), 'meshes')
tests_dir=os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
from VisualizableTestCase import VisualizableTestCase

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoAxesTestCase))
    return (suites)

class VirgoAxesTestCase(VisualizableTestCase):

    def setUp(self):
        pass

    def tearDown(self):
        self.instance = None
        del self.instance

    def get_axes_lengths_from_bb(self):
        bb = self.instance.axes_assembly.GetBounds()
        xlen = bb[1]
        ylen = bb[3]
        zlen = bb[5]
        return(xlen, ylen, zlen)

    def test_nominal_init(self):
        """
        This test checks when VirgoAxes is called, it will default to a scale of 1.
        The scale is an argument of VirgoAxes that normally equals 1 unless told otherwise.
        """
        self.instance = VirgoAxes()
        # Uncomment to see the VirgoAxes in this unit test!
        # self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=0)

        (xlen, ylen, zlen) =  self.get_axes_lengths_from_bb()
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=1)
        self.assertAlmostEqual(xlen, 1.0)
        self.assertAlmostEqual(ylen, 1.0)
        self.assertAlmostEqual(zlen, 1.0)

    def test_init_with_sized_axes(self):
        """
        This test checks that when VirgoAxes has a scale number passed as an argument,
        and that axes will size appropriately.
        """
        self.instance = VirgoAxes(xlen=2.0, ylen=2.0, zlen=2.0)
        (xlen, ylen, zlen) =  self.get_axes_lengths_from_bb()
        self.assertAlmostEqual(xlen, 2.0)
        self.assertAlmostEqual(ylen, 2.0)
        self.assertAlmostEqual(zlen, 2.0)
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=1)

    def test_set_axes_length(self):
        """
        Set the VirgoAxes and test that they result in changes to the associated
        axes
        """
        self.instance = VirgoAxes() # Default length is (1,1,1)
        # Set length of X-axis to 2.0
        self.instance.set_length(xlen=2.0)
        self.assertEqual(self.instance.axes_data.xlen, 2.0)

        (xlen, ylen, zlen) =  self.get_axes_lengths_from_bb()
        self.assertAlmostEqual(xlen, 2.0)
        self.assertAlmostEqual(ylen, 1.0)
        self.assertAlmostEqual(zlen, 1.0)
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=1)
        # Set length of Y-axis to 2.0
        self.instance.set_length(ylen=3.0)
        (xlen, ylen, zlen) =  self.get_axes_lengths_from_bb()
        self.assertAlmostEqual(xlen, 2.0)
        self.assertAlmostEqual(ylen, 3.0)
        self.assertAlmostEqual(zlen, 1.0)
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=1)
        # Set length of Z-axis to 4.0
        self.instance.set_length(zlen=4.0)
        (xlen, ylen, zlen) =  self.get_axes_lengths_from_bb()
        self.assertAlmostEqual(xlen, 2.0)
        self.assertAlmostEqual(ylen, 3.0)
        self.assertAlmostEqual(zlen, 4.0)
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=1)

    def test_set_axes_length_huge(self):
        """
        Set axes length to very large value
        Used for debugging while designing VirgoAxes shaft/tip/radius
        """
        self.instance = VirgoAxes() # Default length is (1,1,1)
        huge = 1e6
        self.instance.set_length(xlen=huge, ylen=huge, zlen=huge)
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=0, oal=[huge*2, huge*2, huge*2])

    def test_set_negative_length_axes(self):
        """
        This test checks if the value of any arrow in an axes is negative. If
        the arrow has a negative value, a ValueError will be raised.
        """
        self.instance = VirgoAxes()
        with self.assertRaises(ValueError):
            self.instance.set_length(xlen=-1.0, ylen=-2.0, zlen=-3.0)

    def test_set_none_length_axes(self):
        """
        Test that when all values given to set_length() are none it raises
        """
        self.instance = VirgoAxes()
        with self.assertRaises(ValueError):
            self.instance.set_length()

    def test_set_negative_length_axes(self):
        """
        Test that when negative value given to set_length() are none it raises
        """
        self.instance = VirgoAxes()
        with self.assertRaises(ValueError):
            self.instance.set_length(xlen=-1.0)

    def test_set_zero_length_axes(self):
        """
        Test that when a zero length axis is set, it falls back to the
        self.minimum_arrow_length value
        """
        self.instance = VirgoAxes()
        #with self.assertRaises(ValueError):
        self.instance.set_length(ylen=0.0)
        (xlen, ylen, zlen) =  self.get_axes_lengths_from_bb()
        # Since ylen comes from the bounding box we can't compare against
        # self.minimum_arrow_length directly as X/Z arrow heads are still in the
        # bounding box. A less than original value check is used instead
        self.assertLess(ylen, 1.0)
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=0)

    def test_show_axes(self):
        """
        This test checks that the visibility is set to True.
        """
        self.instance = VirgoAxes()
        self.instance.show()
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=0)
        self.assertTrue(self.instance.axes_assembly.GetVisibility())
        self.assertTrue(self.instance.visible)

    def test_hide_axes(self):
        """
        This test checks that the visibility is set to False.
        """
        self.instance = VirgoAxes()
        self.instance.hide()
        self.assertFalse(self.instance.x_arrow.GetVisibility())
        self.assertFalse(self.instance.y_arrow.GetVisibility())
        self.assertFalse(self.instance.z_arrow.GetVisibility())
        self.assertFalse(self.instance.visible)
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=0)

    def test_line_style(self):
        """
        Change axes style to "line"
        """
        self.instance = VirgoAxes(xlen=0.5, ylen=2.5, zlen=3.5)
        self.instance.set_style('line')
        # Size of arrows should be unaffected
        (xlen, ylen, zlen) =  self.get_axes_lengths_from_bb()
        self.assertAlmostEqual(xlen, 0.5)
        self.assertAlmostEqual(ylen, 2.5)
        self.assertAlmostEqual(zlen, 3.5)
        #self.vis(actors=self.instance.get_assembly(), show_origin=1, show_grid=0)