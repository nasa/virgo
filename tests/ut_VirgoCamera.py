import os, sys, inspect
import unittest
import copy
from numpy.testing import assert_allclose

# Add path to virgo module
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
virgo_dir=os.path.abspath(os.path.join(thisFileDir, '../'))
sys.path.append(virgo_dir)
from VirgoCamera import VirgoCamera
from VirgoActor import VirgoActor
from VirgoNode import VirgoSceneNode
from unittest.mock import Mock
meshes_dir=os.path.join(virgo_dir, 'meshes')
tests_dir=os.path.join(virgo_dir, 'tests')
from VisualizableTestCase import VisualizableTestCase

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoCameraTestCase))
    return (suites)

class VirgoCameraTestCase(VisualizableTestCase):
    """
    Test cases for the VirgoCamera class. Note that the cameras defined
    in these tests are not actually used in the self.vis() functionality,
    the god's eye view provided by that function is intended to show
    the frustum of the camera from a 3rd person perspective.
    """

    def setUp(self):
        # Actors to be used in node construction
        self.instance = None
        self.teapot1 = VirgoActor(name='teapot1', mesh=os.path.join(meshes_dir, 'teapot.obj'))
        self.teapot1.initialize()
        self.node1 = VirgoSceneNode(name='teapot1', actor=self.teapot1)
        self.camera1 = VirgoCamera(name='camera1', view_up=[0,1,0])
        # Convienence copy for checking against a restore in tests


    def tearDown(self):
        self.instance = None
        self.trail1 = None

    def test_construction(self):
        """
        Simple construction assertions
        """
        self.assert_construction_members()
        self.assert_construction_camera_params()
        #self.vis(actors=[self.node1.actor, self.camera1.frustum_assembly], show_origin=1, show_grid=1)

    def assert_construction_members(self):
        # Internal member assertions
        self.assertEqual(self.camera1.name, 'camera1')
        self.assertEqual(self.camera1.interactor_mode, 'TB')
        assert_allclose(self.camera1.position, [0.0,0.0,0.0])
        assert_allclose(self.camera1.view_up, [0.0,1.0,0.0])
        self.assertEqual(self.camera1.static, False)
        self.assertEqual(self.camera1.frustum_when, 'toggled')

    def assert_construction_camera_params(self):
        # Make sure the params flowed down to the camera itself
        assert_allclose(self.camera1.camera.GetPosition(), (0.0,0.0,0.0))
        assert_allclose(self.camera1.camera.GetFocalPoint(), (1.0,0.0,0.0), atol=1e-12)
        assert_allclose(self.camera1.camera.GetViewUp(), (0.0,1.0,0.0))
        self.assertEqual(self.camera1.camera.GetViewAngle(), 30) # Default for all cams


    def test_set_interactor_mode(self):
        """
        Test the setting of interactor modes
        """
        # TODO more assertions go here
        self.camera1.set_interactor_mode('FP')
        self.assertEqual(self.camera1.get_interactor_mode(), 'FP')
        self.camera1.set_interactor_mode('TB')
        self.assertEqual(self.camera1.get_interactor_mode(), 'TB')
        with self.assertRaises(RuntimeError):
            self.camera1.set_interactor_mode('badmode')

    def test_set_frustum_mode(self):
        """
        Test the setting of frustum modes
        """
        # TODO more assertions go here
        self.camera1.set_frustum_mode('toggled')
        self.assertEqual(self.camera1.get_frustum_mode(), 'toggled')
        self.camera1.set_frustum_mode('always')
        self.assertEqual(self.camera1.get_frustum_mode(), 'always')
        self.camera1.set_frustum_mode('never')
        self.assertEqual(self.camera1.get_frustum_mode(), 'never')
        with self.assertRaises(RuntimeError):
            self.camera1.set_frustum_mode('badmode')

    def test_set_frustum_far_plane(self):
        """
        Test the setting of frustum far plane distance
        """
        # TODO more assertions go here
        self.camera1.set_frustum_far_plane(2.0)
        self.assertEqual(self.camera1.get_frustum_far_plane(), 2.0)
        with self.assertRaises(RuntimeError):
            self.camera1.set_frustum_far_plane(0.0)
        with self.assertRaises(RuntimeError):
            self.camera1.set_frustum_far_plane(-10.0)

    def camera_setters_look_at_lid(self):
        """
        Configure the camera to be at a position looking at the lid of the
        teapot, with +Z being the up direction and a view angle (zoom) of 20
        degrees values when the camera is created and then restored

        Return a tuple of what was set so the success criteria can be used
        by tests
        """
        cam_pos = (4.0,3.0,0)
        cam_focal_point = (0,3,0)
        cam_view_up = (0,0,1)
        cam_view_angle = 20  # degrees
        self.camera1.set_position(cam_pos[0], cam_pos[1], cam_pos[2])
        self.camera1.set_focal_point(cam_focal_point[0], cam_focal_point[1], cam_focal_point[2])
        self.camera1.set_view_up(cam_view_up[0], cam_view_up[1], cam_view_up[2])
        self.camera1.set_view_angle(cam_view_angle)
        self.camera1.update_frustum(window_height=1.0, window_width=2.0)

        return (cam_pos, cam_focal_point, cam_view_up, cam_view_angle)

    def test_camera_setters(self):
        """
        Test the camera setting functions
        """
        (cam_pos, cam_focal_point, cam_view_up, cam_view_angle) = self.camera_setters_look_at_lid()
        self.assertEqual(self.camera1.camera.GetPosition(), cam_pos)
        self.assertEqual(self.camera1.camera.GetFocalPoint(), cam_focal_point)
        self.assertEqual(self.camera1.camera.GetViewUp(), cam_view_up)
        self.assertEqual(self.camera1.camera.GetViewAngle(), cam_view_angle) # Default for all cams

    def test_camera_restore(self):
        """
        A test case where the camera parameters are changed from their
        values when the camera is created and then restored
        """
        # Change the camera parameters by moving it
        (cam_pos, cam_focal_point, cam_view_up, cam_view_angle) = self.camera_setters_look_at_lid()
        self.camera1.update_frustum(window_height=1.0, window_width=2.0)
        #self.vis(actors=[self.node1.actor, self.camera1.frustum_assembly], show_origin=1, show_grid=1)
        # Ensure values aren't the original construction values
        self.assertNotEqual(self.camera1.camera.GetPosition(), [0,0,0])

        # Restore the camera to its original parameters
        self.camera1.restore_original_camera_params()
        self.assert_construction_camera_params()
        self.camera1.update_frustum(window_height=1.0, window_width=2.0)
        #self.vis(actors=[self.node1.actor, self.camera1.frustum_assembly], show_origin=1, show_grid=1)

    def test_camera_looking_down_spout(self):
        """
        A test case where the camera is placed in the direction of the teapot
        spout and the camera's focal point is at the origin of the teapot which
        makes the frustum point down the spout.
        """
        cam_pos = [4.0,3.0,0]
        self.camera1.set_position(cam_pos[0], cam_pos[1], cam_pos[2])
        vtk_pos = self.camera1.camera.GetPosition()
        assert_allclose(vtk_pos, cam_pos)
        self.camera1.update_frustum(window_height=1.0, window_width=2.0)
        #self.vis(actors=[self.node1.actor, self.camera1.frustum_assembly], show_origin=1, show_grid=1)

    def test_camera_follow_single_node(self):
        """
        A test case where the camera is placed at [2, 0, 0] and the teapot
        node is placed at [1, 1, 1]. The camera is then told to follow the
        teapot node, placing it at the same position as the node.
        """
        self.node1.show_axes()
        self.node1.set_pose(pos=[1.0, 1.0, 1.0])
        self.camera2 = VirgoCamera(name='camera1', view_up=[0,1,0], mode='FP')
        # Start the camera at a location not where the node is
        cam_pos = [2.0,0.0,0]
        self.camera2.set_position(cam_pos[0], cam_pos[1], cam_pos[2])
        self.camera2.update_frustum(window_height=1.0, window_width=2.0)
        #self.vis(actors=[self.node1.assembly, self.camera2.frustum_assembly], show_origin=1, show_grid=1)
        # Have the camera follow the node
        self.camera2.follow(self.node1)
        self.camera2.update_frustum(window_height=1.0, window_width=2.0)
        # The camera should have moved to where the node is
        node_pos = self.node1.get_world_position()
        cam_pos = self.camera2.get_position()
        assert_allclose(node_pos, cam_pos)
        #self.vis(actors=[self.node1.assembly, self.camera2.frustum_assembly], show_origin=1, show_grid=1)

    def test_camera_view_up(self):
        """
        A test case where the camera is configured in a singularity, where the
        position and focal point make the view direction in +Z and the view_up
        is attempted to be set to +Z, making them parallel. This test ensures
        that state cannot be reached
        """
        pos = [0,0,2]
        fp = [0,0,1]
        vu = [0,0,1]
        self.camera1.set_position(*pos)
        self.camera1.set_focal_point(*fp)
        self.camera1.set_view_up(*vu)
        self.assertNotEqual(self.camera1.get_view_up(), vu)

    def test_camera_orient(self):
        """
        A test case where the teapot is rotated 90 about yaw so the spout faces +Y
        The camera is then told to orient itself with the frame of the teapot,
        resulting in the camera located at the base of the teapot with view facing
        +X in the teapot coord system (+Y in global coordinates) and with view_up
        direction being +Z in the teapot coord system (+Z in global coords)
        """
        self.node1.show_axes()
        self.node1.set_pose(ypr=[90.0, 0.0, 0.0])
        self.camera2 = VirgoCamera(name='camera1', view_up=[0,1,0], mode='FP', static=True)
        self.camera2.orient(self.node1)
        self.camera2.update_frustum(window_height=1.0, window_width=2.0)
        #self.vis(actors=[self.node1.assembly, self.camera2.frustum_assembly], show_origin=1, show_grid=1)
        # TODO: test disabled as the frustum approach doesn't work well
        # in scenes as large as ours. See comments in VirgoCamera.get_frustum_assembly()
        # Values taken from observation of the frustum and the print in the for
        # loop below
        #expected_frustum_points = [
        #    (-0.5358983874320984, 1.0, -0.2679491937160492),
        #    (0.5358983874320984, 1.0, -0.2679491937160492),
        #    (0.5358983874320984, 1.0, 0.2679491937160492),
        #    (-0.5358983874320984, 1.0, 0.2679491937160492),
        #    (-0.005358983762562275, 0.009999999776482582, -0.0026794918812811375),
        #    (0.005358983762562275, 0.009999999776482582, -0.0026794918812811375),
        #    (0.005358983762562275, 0.009999999776482582, 0.0026794918812811375),
        #    (-0.005358983762562275, 0.009999999776482582, 0.0026794918812811375),
        #    (0.0, 0.0, 0.0),
        #    (0.0, 0.0, 0.0),
        #    (0.0, 0.0, 0.0),
        #    (0.0, 0.0, 0.0),
        #    (0.0, 0.0, 0.0),
        #]
        ## Force the frustum source to update, without this, pts is None unless
        ## self.vis is called
        #self.camera2.frustum_source.Update()
        #pts = self.camera2.frustum_source.GetOutput().GetPoints()
        #for i in range(pts.GetNumberOfPoints()):
        #    #print(pts.GetPoint(i))
        #    assert_allclose(expected_frustum_points[i], pts.GetPoint(i))