import os, sys, inspect
import unittest
import numpy as np
from numpy.testing import assert_allclose

import virgo
from virgo.VirgoTrail import VirgoTrail, VirgoTrailSegment
from unittest.mock import Mock
meshes_dir=os.path.join(os.path.dirname(virgo.__file__), 'meshes')
tests_dir=os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
from VisualizableTestCase import VisualizableTestCase

def suite():
    """Create test suite from test cases here and return"""
    suites = []
    suites.append(unittest.TestLoader().loadTestsFromTestCase(VirgoTrailTestCase))
    return (suites)

class VirgoTrailTestCase(VisualizableTestCase):

    def vis(self, trail):
        """Visualize the trail in an interactive window"""
        actors = [actor for actor, _ in trail.get_trail_actors_and_their_layers()]
        self.trail1.latest_segment._trail_actor.GetProperty().SetColor([1,0,0]) # Red
        self.trail1.segments[0]._trail_actor.GetProperty().SetColor([0,1,0]) # Green
        self.trail1.segments[1]._trail_actor.GetProperty().SetColor([0,0,1]) # Blue

        super().vis(actors=actors, show_origin=1, show_grid=1)

    def setUp(self):
        # Actors to be used in node construction
        self.instance = None
        # Mock the VirgoSceneNode interface
        self.node1 = Mock()
        self.node1.get_world_position.return_value = [0.0, 0.0, 0.0]
        self.trail1 = VirgoTrail(node=self.node1, thickness=3)
        import random
        for segment in self.trail1.segments:
            color = [random.random(), random.random(), random.random()]
            segment.set_color(color)

    def tearDown(self):
        self.instance = None
        self.trail1 = None

    def test_construction(self):
        """
        Simple construction assertions
        """
        # TODO more assertions go here
        self.assertEqual(self.trail1.color, [1,1,1])
        self.assertIsInstance(self.trail1.latest_segment, VirgoTrailSegment)
        self.assertIsInstance(self.trail1.segments, list)
        for i in range(self.trail1.max_segments):
            self.assertIsInstance(self.trail1.segments[i], VirgoTrailSegment)
        for segment in self.trail1.segments:
            self.assertEqual(segment.get_layer(), 'foreground')


    def test_latest_segment_only(self):
        points = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0],
                  [2.0, 2.0, 2.0], [3.0, 3.0, 3.0],
                  [4.0, 4.0, 4.0], [5.0, 5.0, 5.0],
                  ]
        for p in points:
            self.trail1.update(world_position=p)
        assert_allclose(self.trail1.latest_segment.points, points)
        self.assertEqual(len(self.trail1.segments[0].points), 0 )
        #self.vis(trail=self.trail1)

    def test_move_points(self):
        """
        Move points from the foreground to the midground segment
        """
        points = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0],
                  [2.0, 2.0, 2.0], [3.0, 3.0, 3.0],
                  [4.0, 4.0, 4.0], [5.0, 5.0, 5.0],
                  ]
        for p in points:
            self.trail1.update(world_position=p)

        #self.vis(trail=self.trail1) # Before the move
        self.trail1.move_points()
        assert_allclose(self.trail1.segments[0].points, points)
        # The last point should be preserved after the move
        self.assertEqual(len(self.trail1.latest_segment.points), 1 )

        last_point = points[-1]
        more_points = [[6.0, 6.0, 6.0], [7.0, 7.0, 7.0]]
        for p in more_points:
            self.trail1.update(world_position=p)

        #self.vis(trail=self.trail1) 
        # When more points are added, they should appear after the earlier
        # added points. Note that last_point is the duplicate point that
        # shows up when the move is done, which allows for no gap in the
        # trail
        self.trail1.move_points()
        assert_allclose(self.trail1.segments[0].points, points + [last_point] + more_points)

    def test_update_until_move(self):
        """
        Test the update() function until points are moved. Max length is
        shortened for the test such that all self.segment buffers are filled
        and it rolls back to the first instance. Visualizing this should
        show segments getting populated until they are all filled, then
        the oldest segments drop off.
        """
        # Normally these values are much larger, but force the limits to
        # smaller so that we can test the update point moving logic
        self.trail1.latest_segment.set_max_length(2.0)
        for segment in self.trail1.segments:
            segment.set_max_length(4.0)
        points = [[i] * 3 for i in range(35)]
        for p in points:
            # Fake update the node position
            self.node1.get_world_position.return_value = p
            self.trail1.update(world_position=p)
            # Turn this vis call on to see each iteration
            #self.vis(trail=self.trail1) 
        #import pdb; pdb.set_trace()
        #self.vis(trail=self.trail1) 

    def test_get_segment_idx(self):
        """
        Test the get_segment_idx function which determines which
        instance of self.segments should be used based on which ones
        are full
        """
        idx = self.trail1.get_segment_idx()
        self.assertEqual(idx, 0)
        # Fake out fullness of 0
        self.trail1.segments[0].full = True
        idx = self.trail1.get_segment_idx()
        self.assertEqual(idx, 1)

        # Fake out fullness of 0-max to test rollover back to 0
        for i in range(0, self.trail1.max_segments):
            self.trail1.segments[i].full = True
        self.trail1.segment_idx = self.trail1.max_segments - 1
        # Now we should get zero again
        idx = self.trail1.get_segment_idx()
        self.assertEqual(idx, 0)
        # And points should be empty
        self.assertEqual(len(self.trail1.segments[idx].points), 0)

    def test_configure_layers(self):
        """
        TBD
        """
        camera_pos = [0.0, 0.0, 0.0]
        points = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0],
                  [2.0, 2.0, 2.0], [3.0, 3.0, 3.0],
                  [4.0, 4.0, 4.0], [5.0, 5.0, 5.0],
                  ]
        for p in points:
            self.trail1.update(world_position=p)
        # Test 1, no change in layer
        self.trail1.configure_layers(camera_pos=camera_pos)
        # Expect no change from the default 'foreground'
        self.assertEqual(self.trail1.latest_segment.get_layer(), 'foreground')

        # Test 2 put the camera further away than the foreground far boundary 
        # so that the trail wants to be in the midground
        camera_pos = [20.0, 0.0, 0.0]
        self.trail1.foreground_far_boundary = 10
        self.trail1.configure_layers(camera_pos=camera_pos)
        self.assertEqual(self.trail1.latest_segment.get_layer(), 'midground')

        # Test 3 put the camera further away than the midground far boundary 
        # so that the trail wants to be in the background
        camera_pos = [50.0, 0.0, 0.0]
        self.trail1.midground_far_boundary = 20
        self.trail1.configure_layers(camera_pos=camera_pos)
        self.assertEqual(self.trail1.latest_segment.get_layer(), 'background')