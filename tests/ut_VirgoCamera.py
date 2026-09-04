import os, sys, inspect
import unittest
import copy
import numpy as np
from numpy.testing import assert_allclose

import virgo
from virgo.VirgoCamera import VirgoCamera
from virgo.VirgoActor import VirgoActor
from virgo.VirgoNode import VirgoSceneNode
from unittest.mock import Mock
meshes_dir=os.path.join(os.path.dirname(virgo.__file__), 'meshes')
tests_dir=os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
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
        self.assertIsNotNone(self.camera1.frustum)
        self.assertIsNotNone(self.camera1.frustum_assembly)
        self.assertEqual(self.camera1.frustum.polydata.GetNumberOfPoints(), 5)
        self.assertEqual(self.camera1.frustum.polydata.GetNumberOfLines(), 8)

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

    # Frustum Tests

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
        self.camera2 = VirgoCamera(
            name='camera1', 
            view_up=[0,1,0], 
            mode='FP', 
            static=True, 
            frustum_far_plane=4,
            frustum_color=[1.0, 0.0, 0.0]
            )
        self.camera2.orient(self.node1)
        self.camera2.update_frustum(window_height=1.0, window_width=2.0)
        #self.vis(actors=[self.node1.assembly, self.camera2.frustum_assembly], show_origin=1, show_grid=1)
        # 5 points: apex (camera position) + 4 far-face corners.
        # far_center magnitude scales linearly with frustum_far_plane, so
        #   x: 2.1435935497283936
        #   y: 4.0
        #   z: 1.0717967748641968
        expected_frustum_points = [
            (0.0, 0.0, 0.0),                                       # 0: apex
            (-2.1435935497283936, 4.0, 1.0717967748641968),        # 1: (-x, +z)
            (2.1435935497283936, 4.0, 1.0717967748641968),         # 2: (+x, +z)
            (2.1435935497283936, 4.0, -1.0717967748641968),        # 3: (+x, -z)
            (-2.1435935497283936, 4.0, -1.0717967748641968),       # 4: (-x, -z)
        ]
        pts = self.camera2.frustum.polydata.GetPoints()
        cam_pos = self.camera2.get_position()
        for i in range(pts.GetNumberOfPoints()):
            world_pt = np.array(pts.GetPoint(i)) + np.array(cam_pos)
            assert_allclose(expected_frustum_points[i], world_pt)


    # Frustum Geometry Correctness
    
    def test_apex_at_camera_position_for_multiple_poses(self):
        """
        Apex should always be the camera's own local origin (0,0,0),
        regardless of camera orientation/pose - it's not derived from
        direction/right/up at all.
        """
        test_yprs = [
            [0.0, 0.0, 0.0],
            [45.0, 0.0, 0.0],
            [90.0, 30.0, 0.0],
            [-60.0, 0.0, 15.0],
        ]
        for ypr in test_yprs:
            with self.subTest(ypr=ypr):
                self.node1.set_pose(ypr=ypr)
                cam = VirgoCamera(name='apex_test_cam', view_up=[0, 1, 0],
                                   mode='FP', static=True)
                cam.orient(self.node1)
                cam.update_frustum(window_height=1.0, window_width=2.0)
                pts = cam.frustum.polydata.GetPoints()
                apex_local = np.array(pts.GetPoint(0))
                assert_allclose(apex_local, [0.0, 0.0, 0.0], atol=1e-6)

    def test_far_plane_scaling_is_linear(self):
        """
        far_height/far_width/far_center should all scale linearly with
        frustum_far_plane. Compare two values and check the ratio.
        """
        self.node1.set_pose(ypr=[90.0, 0.0, 0.0])

        cam_a = VirgoCamera(name='scale_a', view_up=[0, 1, 0], mode='FP',
                             static=True, frustum_far_plane=1.0)
        cam_a.orient(self.node1)
        cam_a.update_frustum(window_height=1.0, window_width=2.0)
        pts_a = cam_a.frustum.polydata.GetPoints()

        cam_b = VirgoCamera(name='scale_b', view_up=[0, 1, 0], mode='FP',
                             static=True, frustum_far_plane=4.0)
        cam_b.orient(self.node1)
        cam_b.update_frustum(window_height=1.0, window_width=2.0)
        pts_b = cam_b.frustum.polydata.GetPoints()

        # Every far corner (indices 1-4) should scale by exactly 4x
        for i in range(1, 5):
            a = np.array(pts_a.GetPoint(i))
            b = np.array(pts_b.GetPoint(i))
            assert_allclose(b, a * 4.0, atol=1e-6)

    def test_aspect_ratio_changes_width_not_height(self):
        """
        Changing window_width (holding window_height fixed) should scale
        the far face's width but not its height.
        """
        self.node1.set_pose(ypr=[90.0, 0.0, 0.0])
        cam = VirgoCamera(name='aspect_cam', view_up=[0, 1, 0], mode='FP',
                           static=True, frustum_far_plane=1.0)
        cam.orient(self.node1)

        cam.update_frustum(window_height=1.0, window_width=2.0)  # aspect 2.0
        pts_wide = [np.array(cam.frustum.polydata.GetPoints().GetPoint(i))
                    for i in range(5)]

        cam.update_frustum(window_height=1.0, window_width=1.0)  # aspect 1.0
        pts_square = [np.array(cam.frustum.polydata.GetPoints().GetPoint(i))
                      for i in range(5)]

        width_ratio = pts_square[2][0] / pts_wide[2][0]
        height_ratio = pts_square[2][2] / pts_wide[2][2]
        assert_allclose(width_ratio, 0.5, atol=1e-6)
        assert_allclose(height_ratio, 1.0, atol=1e-6)

    
    # Frustum edges and faces

    def test_wireframe_has_correct_point_and_line_count(self):
        """
        5 points (apex + 4 far corners), 8 edges (4 apex-to-corner +
        4 base edges) per the pyramid shape.
        """
        self.node1.set_pose(ypr=[0.0, 0.0, 0.0])
        cam = VirgoCamera(name='wire_cam', view_up=[0, 1, 0], mode='FP',
                        static=True)
        cam.orient(self.node1)
        cam.update_frustum(window_height=1.0, window_width=2.0)

        pd = cam.frustum.polydata
        self.assertEqual(pd.GetNumberOfPoints(), 5)
        self.assertEqual(pd.GetLines().GetNumberOfCells(), 8)

    def test_wireframe_edges_connect_expected_indices(self):
        """
        Confirm the actual edge list matches (0,1),(0,2),(0,3),(0,4),
        (1,2),(2,3),(3,4),(4,1) - apex spokes + base ring.
        """
        self.node1.set_pose(ypr=[0.0, 0.0, 0.0])
        cam = VirgoCamera(name='edge_cam', view_up=[0, 1, 0], mode='FP',
                        static=True)
        cam.orient(self.node1)
        cam.update_frustum(window_height=1.0, window_width=2.0)

        lines = cam.frustum.polydata.GetLines()
        lines.InitTraversal()
        from vtkmodules.vtkCommonCore import vtkIdList 
        id_list = vtkIdList()  
        actual_edges = set()
        while lines.GetNextCell(id_list):
            a, b = id_list.GetId(0), id_list.GetId(1)
            actual_edges.add(tuple(sorted((a, b))))

        expected_edges = {
            (0, 1), (0, 2), (0, 3), (0, 4),
            (1, 2), (2, 3), (3, 4), (1, 4),
        }
        self.assertEqual(actual_edges, expected_edges)

    def test_face_polydata_point_and_cell_count(self):
        """
        Face polydata: 5 points, 4 side triangles + base (1 quad cell,
        or 2 triangles - adjust expected_cells to match whichever fix
        was used for the seam-blending issue).
        """
        self.node1.set_pose(ypr=[0.0, 0.0, 0.0])
        cam = VirgoCamera(name='face_cam', view_up=[0, 1, 0], mode='FP',
                        static=True)
        cam.orient(self.node1)
        cam.update_frustum(window_height=1.0, window_width=2.0)

        face_pd = cam.frustum.face_polydata
        self.assertEqual(face_pd.GetNumberOfPoints(), 5)
        # 4 side tris + 1 base quad cell == 5 total polys
        self.assertEqual(face_pd.GetPolys().GetNumberOfCells(), 5)

    def test_wireframe_and_face_share_same_points(self):
        """
        Regression guard: if someone edits update_frustum() to change
        one point set but not the other, this catches the divergence.
        """
        self.node1.set_pose(ypr=[30.0, 10.0, 0.0])
        cam = VirgoCamera(name='shared_pts_cam', view_up=[0, 1, 0],
                        mode='FP', static=True)
        cam.orient(self.node1)
        cam.update_frustum(window_height=1.0, window_width=2.0)

        wire_pts = cam.frustum.polydata.GetPoints()
        face_pts = cam.frustum.face_polydata.GetPoints()
        self.assertEqual(wire_pts.GetNumberOfPoints(),
                        face_pts.GetNumberOfPoints())
        for i in range(wire_pts.GetNumberOfPoints()):
            assert_allclose(wire_pts.GetPoint(i), face_pts.GetPoint(i),
                            atol=1e-9)

    # Frustum wiring (toggle) / opacity / line thickness

    def test_frustum_color_applies_to_both_actors(self):
        color = [0.2, 0.4, 0.9]
        cam = VirgoCamera(name='color_cam', frustum_when='always',
                           frustum_color=color)
        self.assertIsNotNone(cam.frustum)
        assert_allclose(cam.frustum.actor.GetProperty().GetColor(), color,
                         atol=1e-6)
        assert_allclose(cam.frustum.face_actor.GetProperty().GetColor(),
                         color, atol=1e-6)

    def test_set_frustum_face_opacity_updates_face_actor_only(self):
        cam = VirgoCamera(name='opacity_cam', frustum_when='always', frustum_face_opacity=0.5)
        wire_opacity_before = cam.frustum.actor.GetProperty().GetOpacity()

        self.assertAlmostEqual(
            cam.frustum.face_actor.GetProperty().GetOpacity(), 0.5)
        # Wireframe opacity should be untouched by this call
        self.assertAlmostEqual(
            cam.frustum.actor.GetProperty().GetOpacity(),
            wire_opacity_before)

    def test_frustum_face_opacity_constructor_default(self):
        cam = VirgoCamera(name='opacity_default_cam', frustum_when='always',
                           frustum_face_opacity=0.33)
        self.assertAlmostEqual(
            cam.frustum.face_actor.GetProperty().GetOpacity(), 0.33)


    def test_frustum_line_width_applies(self):
        cam = VirgoCamera(name='linewidth_cam', frustum_when='always',
                           frustum_line_width=5.0)
        self.assertAlmostEqual(
            cam.frustum.actor.GetProperty().GetLineWidth(), 5.0)
        
    # Frustum-when / construction gating
    def test_frustum_when_never_skips_construction(self):
        cam = VirgoCamera(name='never_cam', frustum_when='never')
        self.assertIsNone(cam.frustum)
        self.assertIsNone(cam.frustum_assembly)
        self.assertFalse(cam.has_frustum())

    def test_frustum_when_always_constructs_frustum(self):
        cam = VirgoCamera(name='always_cam', frustum_when='always')
        self.assertIsNotNone(cam.frustum)
        self.assertTrue(cam.has_frustum())

    def test_frustum_when_toggled_constructs_frustum(self):
        cam = VirgoCamera(name='toggled_cam', frustum_when='toggled')
        self.assertIsNotNone(cam.frustum)
        self.assertTrue(cam.has_frustum())

    def test_default_named_camera_never_gets_frustum(self):
        """
        Even with frustum_when explicitly set to 'always', a camera
        named 'default' should never construct a frustum.
        """
        cam = VirgoCamera(name='default', frustum_when='always')
        self.assertIsNone(cam.frustum)
        self.assertFalse(cam.has_frustum())

    def test_disable_frustum_clears_references(self):
        cam = VirgoCamera(name='disable_cam', frustum_when='always')
        self.assertTrue(cam.has_frustum())
        cam.disable_frustum()
        self.assertIsNone(cam.frustum)
        self.assertIsNone(cam.frustum_assembly)
        self.assertFalse(cam.has_frustum())

    # Camera switching

    def test_frustum_size_independent_across_cameras(self):
        """
        Regression test for the original bug: each camera's frustum
        far-face size should depend only on its own frustum_far_plane,
        never on another camera's state (e.g. from a shared/stale
        clipping-range read).
        """
        self.node1.set_pose(ypr=[0.0, 0.0, 0.0])

        cam_small = VirgoCamera(name='switch_small', view_up=[0, 1, 0],
                                    mode='FP', static=True,
                                    frustum_far_plane=1.0)
        cam_small.orient(self.node1)

        cam_large = VirgoCamera(name='switch_large', view_up=[0, 1, 0],
                                    mode='FP', static=True,
                                    frustum_far_plane=50.0)
        cam_large.orient(self.node1)

        # Update both, in both orders, and confirm neither leaks state
        # into the other.
        cam_small.update_frustum(window_height=1.0, window_width=2.0)
        cam_large.update_frustum(window_height=1.0, window_width=2.0)

        far_pt_small = np.array(cam_small.frustum.polydata.GetPoints().GetPoint(2))
        far_pt_large = np.array(cam_large.frustum.polydata.GetPoints().GetPoint(2))

        expected_ratio = 50.0
        actual_ratio = (np.linalg.norm(far_pt_large) /
                            np.linalg.norm(far_pt_small))
        assert_allclose(actual_ratio, expected_ratio, rtol=1e-6)

        # Re-update small camera again after large was updated - its
        # size should be unchanged (no bleed-over from cam_large).
        cam_small.update_frustum(window_height=1.0, window_width=2.0)
        far_pt_small_again = np.array(
            cam_small.frustum.polydata.GetPoints().GetPoint(2))
        assert_allclose(far_pt_small_again, far_pt_small, atol=1e-9)

    # Edge case

    def test_degenerate_view_up_produces_finite_geometry(self):
        """
        view_up parallel (or near-parallel) to view direction should
        fall back to a safe value (per the existing warning path) and
        still produce finite, non-NaN frustum geometry rather than
        raising or producing garbage.
        """
        cam = VirgoCamera(name='degenerate_cam', mode='FP', static=True,
                           position=[0, 0, 0], focal_point=[0, 0, -1],
                           view_up=[0, 0, 1])  # parallel to focal direction
        cam.update_frustum(window_height=1.0, window_width=2.0)
        pts = cam.frustum.polydata.GetPoints()
        for i in range(pts.GetNumberOfPoints()):
            p = pts.GetPoint(i)
            self.assertTrue(np.all(np.isfinite(p)),
                             f"Non-finite point at index {i}: {p}")

    # NOTE: only include if set_frustum_far_plane actually validates
    # its input - remove or invert the assertion if it doesn't.
    def test_zero_or_negative_far_plane_is_rejected_or_handled(self):
        cam = VirgoCamera(name='invalid_far_cam')
        with self.assertRaises((ValueError, RuntimeError)):
            cam.set_frustum_far_plane(0.0)
        with self.assertRaises((ValueError, RuntimeError)):
            cam.set_frustum_far_plane(-5.0)