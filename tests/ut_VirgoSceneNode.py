import os, sys, inspect
import unittest
import numpy as np
import math
from numpy.testing import assert_allclose

import virgo
from virgo.VirgoActor import VirgoActor
from virgo.VirgoNode import VirgoSceneNode, VirgoSceneNodeVector
meshes_dir=os.path.join(os.path.dirname(virgo.__file__), 'meshes')
tests_dir=os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
from VisualizableTestCase import VisualizableTestCase

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoSceneNodeTestCase))
    return (suites)

class VirgoSceneNodeTestCase(VisualizableTestCase):

    def setUp(self):
        # Actors to be used in node construction
        self.teapot1 = VirgoActor(name='teapot1', mesh=os.path.join(meshes_dir, 'teapot.obj'))
        self.teapot1.initialize()
        self.teapot2 = VirgoActor(name='teapot2', mesh=os.path.join(meshes_dir, 'teapot.obj'))
        self.teapot2.initialize()
        self.teapot3 = VirgoActor(name='teapot3', mesh=os.path.join(meshes_dir, 'teapot.obj'))
        self.teapot3.initialize()
        self.teapot4 = VirgoActor(name='teapot4', mesh=os.path.join(meshes_dir, 'teapot.obj'),
             offset_pos=(0.0, 0.0, 0.0), offset_ypr=(0.0, 0.0, 90.0))
        self.teapot4.initialize()
        # Nodes to test with
        self.node0 = VirgoSceneNode(name='no_actor')
        self.node1 = VirgoSceneNode(name='parent_teapot', actor=self.teapot1)
        self.node2 = VirgoSceneNode(name='child_teapot', actor=self.teapot2)
        self.node3 = VirgoSceneNode(name='grandchild_teapot', actor=self.teapot3)
        self.node4 = VirgoSceneNode(name='actor_offset_teapot', actor=self.teapot4)

    def tearDown(self):
      pass

    def test_construction(self):
        """
        Simple construction assertions
        """
        # Two nodes not at all linked together
        nodes = [self.node0, self.node1, self.node2, self.node3]
        # The matrix we expect inside local_transform after construction
        default_matrix = np.array([
          [1.0, 0.0, 0.0,  0.0],
          [0.0, 1.0, 0.0,  0.0],
          [0.0, 0.0, 1.0,  0.0],
          [0.0, 0.0, 0.0,  1.0],
        ])
        for node in nodes:
            if node.name != 'no_actor':
                self.assertIn('teapot', node.name)
                self.assertIsNot(node.actor, None)
            self.assertEqual(node.children, [])
            self.assertIsNone(node.parent)
            for i in range(4):
              for j in range(4):
                self.assertEqual(default_matrix[i, j], node.local_transform.GetMatrix().GetElement(i, j))

    def test_add_child_ERROR(self):
        """
        Attempt to add a node to itself as a child, which isn't supported
        """
        with self.assertRaises(RuntimeError):
            # Make node2 a child of node1
            self.node1.add_child(self.node1)

    def test_add_child(self):
        """
        Add a child teapot to the parent, handle to tip, then rotate the entire
        assembly by 45 degrees in Y
        """
        # Make node2 a child of node1
        self.node1.add_child(self.node2)
        self.node2.set_pose(pos=(6.0, 1.7, 0.0)) # Positioned handle-to-tip

        node2_local_pos_before = self.node2.local_transform.GetPosition()
        node2_world_pos_before = self.node2.get_world_position()

        # Apply a rotation about y in parent node1
        self.node1.set_pose(ypr=(0.0, 45.0, 0.0))

        node2_local_pos_after = self.node2.local_transform.GetPosition()
        node2_world_pos_after = self.node2.get_world_position()

        # Visually confirmed success criteria using self.show_grid = True
        node2_world_pos_after_expected = (4.242640687119285, 1.7, -4.242640687119286)
        # Observe the child node2 moves along with parent node1 rotation
        np.testing.assert_array_almost_equal(node2_world_pos_after, node2_world_pos_after_expected, decimal=10)
        np.testing.assert_array_equal(node2_local_pos_before, node2_local_pos_after)

        #print(f"{node2_world_pos_after}")
        #self.vis(actors=self.node1.assembly, show_origin=1, show_grid=1)


    def test_add_grandchild(self):
        """
        Add a child teapot to the parent, handle to tip, and another
        grandchild teapot to the child, then rotate the entire
        assembly by 45 degrees in Y
        """
        # Make node2 a child of node1
        self.node1.add_child(self.node2)
        self.node2.set_pose(pos=(6.0, 1.7, 0.0)) # Positioned handle-to-tip
        # Make node3 a child of node2
        self.node2.add_child(self.node3)
        self.node3.set_pose(pos=(6.0, 1.7, 0.0)) # Positioned handle-to-tip

        node3_local_pos_before = self.node2.local_transform.GetPosition()
        node3_world_pos_before = self.node2.get_world_position()

        # Apply a rotation about y in parent node1
        self.node1.set_pose(ypr=(0.0, 45.0, 0.0))

        node3_local_pos_after = self.node3.local_transform.GetPosition()
        node3_world_pos_after = self.node3.get_world_position()

        # Visually confirmed success criteria using self.show_grid = True
        node3_world_pos_after_expected = (8.48528137423857, 3.4, -8.485281374238571)
        # Observe the child node2 moves along with parent node1 rotation
        np.testing.assert_array_almost_equal(node3_world_pos_after, node3_world_pos_after_expected, decimal=10)
        np.testing.assert_array_equal(node3_local_pos_before, node3_local_pos_after)

        #self.vis(actors=self.node1.assembly, show_origin=1, show_grid=1)

    def test_add_child_with_empty_offset(self):
        """
        Make an empty offset node and parent a teapot to it
        """
        self.node0.set_pose(pos=[1.0, 0.0, 0.0])  # Empty node, offset 1.0 in x-dir
        self.node0.add_child(self.node1)
        self.node1.set_pose(pos=(1.0, 0.0, 0.0))  # Child node, another 1.0 in x-dir

        self.node0.show_axes()
        self.node1.show_axes()
        #self.vis(actors=self.node0.assembly, show_origin=1, show_grid=1)

    def test_set_pose_ypr_90_90_90(self):
        """
        Do a more complicated yaw-pitch-roll maneuver Rotate a teapot (90,-90,0)
        in yaw-pitch-roll which is an Z-Y-X Tait Bryan Euler rotation. The
        teapot should end up with it's base at the world origin with base facing
        (in world coordinate space) negative Y, handle facing positive Z, spout
        facing negative Z and X completing the right-handed set
        """
        self.node1.set_pose(ypr=(90.0, 90.0, 90.0))

        # The matrix we expect inside local_transform after this ypr rotation
        expected_matrix = np.array([
          [0.0,  0.0, 1.0,  0.0],
          [0.0,  1.0, 0.0,  0.0],
          [-1.0, 0.0, 0.0,  0.0],
          [0.0,  0.0, 0.0,  1.0],
        ])
        self.node1.show_axes()
        #self.vis(actors=self.node1.assembly, show_origin=1, show_grid=1)
        for i in range(4):
          for j in range(4):
            self.assertAlmostEqual(expected_matrix[i, j], self.node1.local_transform.GetMatrix().GetElement(i, j))


    def test_set_pose_ypr_90_neg90_0(self):
        """
        Do a more complicated yaw-pitch-roll maneuver Rotate a teapot (90,-90,0)
        in yaw-pitch-roll which is an Z-Y-X Tait Bryan Euler rotation. The
        teapot should end up with it's base at the world origin with base facing
        (in world coordinate space) positive X, handle facing negative Z, spout
        facing positive Z and X completing the right-handed set
        """
        # Make node2 a child of node1
        self.node1.set_pose(ypr=(90.0, -90.0, 0.0))
        self.node1.show_axes()

        # The matrix we expect inside local_transform after this ypr rotation
        expected_matrix = np.array([
          [0.0, -1.0,  0.0, 0.0],
          [0.0,  0.0, -1.0,  0.0],
          [1.0,  0.0,  0.0, 0.0],
          [0.0,  0.0,  0.0,  1.0],
        ])
        for i in range(4):
          for j in range(4):
            self.assertAlmostEqual(expected_matrix[i, j], self.node1.local_transform.GetMatrix().GetElement(i, j))
        #self.vis(actors=self.node1.assembly, show_origin=1, show_grid=1)


    def test_set_pose_ypr_neg90_neg180_neg90(self):
        """
        Do a more complicated yaw-pitch-roll maneuver Rotate a teapot
        (-90,-180,-90) in yaw-pitch-roll which is an Z-Y-X Tait Bryan Euler
        rotation. The teapot should end up with it's base at the world origin
        with base facing (in world coordinate space) negative Z, handle facing
        negative Y, spout facing positive Y and X completing the right-handed
        set
        """
        # Make node2 a child of node1
        self.node1.set_pose(ypr=(-90.0, -180.0, -90.0))
        self.node1.show_axes()

        # The matrix we expect inside local_transform after this ypr rotation
        expected_matrix = np.array([
          [0.0, 0.0, 1.0, 0.0],
          [1.0, 0.0, 0.0, 0.0],
          [0.0, 1.0, 0.0,  0.0],
          [0.0, 0.0, 0.0,  1.0],
        ])
        self.node1.show_axes()
        #self.vis(actors=self.node1.assembly, show_origin=1, show_grid=1)
        for i in range(4):
          for j in range(4):
            self.assertAlmostEqual(expected_matrix[i, j], self.node1.local_transform.GetMatrix().GetElement(i, j))


    def test_set_pose_ypr_180_90_90(self):
        """
        Do a more complicated yaw-pitch-roll maneuver Rotate a teapot
        (180,90,90) in yaw-pitch-roll which is an Z-Y-X Tait Bryan Euler
        rotation. The teapot should end up with it's base at the world origin
        with base facing (in world coordinate space) positive X, handle facing
        positive Z, spout facing negative Z and X completing the right-handed
        set
        """
        self.node1.set_pose(ypr=(180.0, 90.0, 90.0))
        self.node1.show_axes()
        mat = self.node1.local_transform.GetMatrix()

        # The matrix we expect inside local_transform after this ypr rotation
        expected_matrix = np.array([
          [0.0, -1.0, 0.0, 0.0],
          [0.0,  0.0, 1.0, 0.0],
          [-1.0, 0.0, 0.0, 0.0],
          [0.0,  0.0, 0.0, 1.0],
        ])
        #self.vis(actors=self.node1.assembly, show_origin=1, show_grid=1)
        for i in range(4):
          for j in range(4):
            self.assertAlmostEqual(expected_matrix[i, j], self.node1.local_transform.GetMatrix().GetElement(i, j))

    def test_set_pose_pos_and_ypr(self):
        """
        Call set_pose() with both pos and ypr defined

        The teapot should end up with it's base at (1, 0, 0) in world coords
        with base facing (in world coordinate space) negative Y, handle facing
        positive Z, spout facing negative Z and X completing the right-handed
        """
        # Make node2 a child of node1
        self.node1.set_pose(pos=(1.0, 0.0, 0.0), ypr=(0.0, 90.0, 0.0))
        self.node1.show_axes()

        # The matrix we expect inside local_transform after this ypr rotation
        expected_matrix = np.array([
          [0.0,  0.0, 1.0, 1.0],
          [0.0,  1.0, 0.0, 0.0],
          [-1.0, 0.0, 0.0, 0.0],
          [0.0,  0.0, 0.0, 1.0],
        ])
        #self.vis(actors=self.node1.assembly, show_origin=1, show_grid=1)
        for i in range(4):
          for j in range(4):
            self.assertAlmostEqual(expected_matrix[i, j], self.node1.local_transform.GetMatrix().GetElement(i, j))


    def test_set_pose_dcm_identity(self):
        """
        Perform an identity dcm rotation on a node with set_pose() and ensure
        it has no rotation
        """
        dcm = np.array([
           [1.0, 0.0, 0.0],
           [0.0, 1.0, 0.0],
           [0.0, 0.0, 1.0]
        ])
        self.node1.set_pose(dcm=dcm)
        self.node1.show_axes()
        #self.vis(actors=self.node1.assembly, show_origin=1, show_grid=1)
        mat = self.node1.local_transform.GetMatrix()

        # The matrix we expect inside local_transform after this ypr rotation
        expected_matrix = np.array([
          [1.0, 0.0, 0.0, 0.0],
          [0.0, 1.0, 0.0, 0.0],
          [0.0, 0.0, 1.0, 0.0],
          [0.0, 0.0, 0.0, 1.0],
        ])
        for i in range(4):
          for j in range(4):
            self.assertAlmostEqual(expected_matrix[i, j], mat.GetElement(i, j))

    def test_set_pose_dcm_45_z(self):
        """
        Perform a 45 degree z rotation via passive dcm on a node with
        set_pose() and ensure it has expected orientation. Passive transformations
        are typical in aerospace and robotics but VTK expects active
        transformations. This test ensures a passive dcm enters set_pose()
        which is transposed internally and we can get the active version
        of that dcm via GetMatrix
        """
        import math
        cos45 = math.cos(math.radians(45))
        sin45 = math.sin(math.radians(45))
        dcm = np.array([
           [cos45,  sin45, 0.0],
           [-sin45, cos45, 0.0],
           [0.0,      0.0, 1.0]
        ])
        self.node1.set_pose(dcm=dcm, transpose_dcm=True)
        self.node1.show_axes()
        #self.vis(actors=self.node1.assembly, show_origin=1, show_grid=1)
        mat = self.node1.local_transform.GetMatrix()

        # The matrix we expect inside local_transform after this dcm rotation
        # Note the transpose since transpose_dcm=True above
        expected_matrix = np.array([
          [cos45, -sin45, 0.0, 0.0],
          [sin45, cos45, 0.0, 0.0],
          [0.0, 0.0, 1.0, 0.0],
          [0.0, 0.0, 0.0, 1.0],
        ])
        for i in range(4):
          for j in range(4):
            self.assertAlmostEqual(expected_matrix[i, j], mat.GetElement(i, j))


    def test_offset_ypr_90_0_0(self):
        self.teapot1 = VirgoActor(name='teapot1', mesh=os.path.join(meshes_dir, 'teapot.obj'),
                                  offset_ypr=[90, 0, 0] 
                                  )
        self.teapot1.initialize()
        # Visually confirmed here, TODO: need test criteria
        #self.vis(actors=self.teapot1, show_origin=1, show_grid=1)

class VirgoSceneNodeVectorTestCase(VisualizableTestCase):

    def setUp(self):
        # Actors to be used in node construction
        self.arrow0 = VirgoActor(name='arrow0', mesh='VIRGO_PREFAB:arrow')
        self.arrow0.initialize()
        # Nodes to test with
        self.node0 = VirgoSceneNodeVector(name='myvec0', actor=self.arrow0)

    def tearDown(self):
      pass

    def test_construction(self):
        """
        Simple construction assertions
        """
        # The matrix we expect inside local_transform after construction
        default_matrix = np.array([
          [1.0, 0.0, 0.0,  0.0],
          [0.0, 1.0, 0.0,  0.0],
          [0.0, 0.0, 1.0,  0.0],
          [0.0, 0.0, 0.0,  1.0],
        ])
        for i in range(4):
          for j in range(4):
            self.assertEqual(default_matrix[i, j], self.node0.local_transform.GetMatrix().GetElement(i, j))

        # TBD more assertions go here
        #self.vis(actors=self.node0.assembly, show_origin=1, show_grid=1)
    
    def test_set_vector_pose_x_only(self):
        """
        Test a set_vector_pose() call that points the vector along X
        which is no transformation
        """
        self.node0.set_vector_pose(vec=[1.0, 0.0, 0.0])
        # vect points in X dir but is still located at 0,0,0
        expected_position = np.array([0.0, 0.0, 0.0])
        actual_position = self.node0.get_world_position()
        assert_allclose(expected_position, actual_position, atol=1e-15)
        expected_matrix = np.array([
          [1.0, 0.0, 0.0,  0.0],
          [0.0, 1.0, 0.0,  0.0],
          [0.0, 0.0, 1.0,  0.0],
          [0.0, 0.0, 0.0,  1.0],
        ])
        #self.vis(actors=self.node0.assembly, show_origin=1, show_grid=1)
        actual_matrix = self.vtk_matrix_to_numpy_array(self.node0.local_transform.GetMatrix())
        assert_allclose(expected_matrix, actual_matrix, atol=1e-15)

    def test_set_vector_pose_xyz(self):
        """
        Test a set_vector_pose() call that moves the vector to point to
        [1,1,1]
        """
        self.node0.set_vector_pose(vec=[1.0, 1.0, 1.0])
        expected_position = np.array([0.0, 0.0, 0.0])
        actual_position = self.node0.get_world_position()
        assert_allclose(expected_position, actual_position, atol=1e-15)

        # Manually verified, rotating an X-pointing vector to [1,1,1]
        expected_matrix = np.array([
           [ 0.57735 , -0.57735 , -0.57735 ,  0.0  ],
          [  0.57735 ,  0.788675, -0.211325,  0.0  ],
          [  0.57735 , -0.211325,  0.788675,  0.0  ],
          [  0.0     ,  0.0     ,  0.0     ,  1.0  ]])
        actual_matrix = self.vtk_matrix_to_numpy_array(self.node0.local_transform.GetMatrix())
        #self.vis(actors=self.node0.assembly, show_origin=1, show_grid=1)
        assert_allclose(actual_matrix, expected_matrix, rtol=1e-5)

    def test_set_vector_pose_unit_mode(self):
        """
        Test a set_pose() call on given a scale of 2.0 in unit mode
        """
        self.node0.set_mode('unit')
        self.node0.set_user_scale(2.0)
        self.node0.set_vector_pose(vec=[1.0, 0.0, 0.0])
        # The matrix we expect inside local_transform after construction
        expected_matrix = np.array([
          [2.0, 0.0, 0.0,  0.0],
          [0.0, 2.0, 0.0,  0.0],
          [0.0, 0.0, 2.0,  0.0],
          [0.0, 0.0, 0.0,  1.0],
        ])
        #self.vis(actors=self.node0.assembly, show_origin=1, show_grid=1)
        actual_matrix = self.vtk_matrix_to_numpy_array(self.node0.local_transform.GetMatrix())
        assert_allclose(expected_matrix, actual_matrix, atol=1e-15)

    def test_set_vector_pose_absolute_mode(self):
        """
        Test a set_pose() call on given a scale of 1.0 in absolute mode
        """
        self.node0.set_mode('absolute')
        self.node0.set_user_scale(1.0)
        self.node0.set_vector_pose(vec=[2.0, 0.0, 0.0])
        # The matrix we expect inside local_transform after construction
        expected_matrix = np.array([
          [2.0, 0.0, 0.0,  0.0],
          [0.0, 2.0, 0.0,  0.0],
          [0.0, 0.0, 2.0,  0.0],
          [0.0, 0.0, 0.0,  1.0],
        ])
        #self.vis(actors=self.node0.assembly, show_origin=1, show_grid=1)
        actual_matrix = self.vtk_matrix_to_numpy_array(self.node0.local_transform.GetMatrix())
        assert_allclose(expected_matrix, actual_matrix, atol=1e-15)

    def test_set_vector_pose_opacity(self):
        """
        Test a set_vector_pose() call with a 0.5 opacity
        """
        self.node0.set_vector_pose(vec=[1.0,0.0,0.0], opacity=0.5)
        actual_opacity = self.node0.actor.GetProperty().GetOpacity()

        self.assertAlmostEqual(0.5, actual_opacity)
        #self.vis(actors=self.node0.assembly, show_origin=1, show_grid=1)