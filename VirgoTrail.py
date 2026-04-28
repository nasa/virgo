from vtkmodules.vtkRenderingCore import (
  vtkActor,
  vtkPolyDataMapper,
)
from vtkmodules.vtkCommonCore import (
  vtkPoints,
)
from vtkmodules.vtkCommonDataModel import (
  vtkCellArray,
  vtkPolyData,
  vtkPolyLine,
)
import numpy as np
import math
from VirgoRendering import VirgoRendering

class VirgoTrailSegment:
    """
    A segment is a part of a trail
    """
    def __init__(self, node, color=[1.0, 1.0, 1.0],
                 thickness=2, opacity=1.0, max_length=1e3):
        self.node = node
        self.color = color
        self.thickness = thickness
        self.opacity = opacity
        self.full = False
        self.layer = VirgoRendering.user_facing_layers[-1] # front-most layer
        self.points = list([]) # List of all points this segment traversed
        self.max_length = max_length
        self._trail_points = vtkPoints()
        self._trail_lines = vtkCellArray()
        self._trail_polydata = vtkPolyData()
        self._trail_polydata.SetPoints(self._trail_points)
        self._trail_polydata.SetLines(self._trail_lines)

        self._trail_mapper = vtkPolyDataMapper()
        self._trail_mapper.SetInputData(self._trail_polydata)

        self._trail_actor = vtkActor()
        self._trail_actor.SetMapper(self._trail_mapper)
        self.set_color(color)
        self._trail_actor.GetProperty().SetLineWidth(thickness)
        self._trail_actor.GetProperty().SetOpacity(opacity)
        self._trail_actor.PickableOff()

        # Maintain a polyline of visited positions
        self._trail_polyline = vtkPolyLine()
        self._trail_polyline.GetPointIds().SetNumberOfIds(0)  # start empty
        # Bounding box variables
        self.bb = [0]*6 # This trail segment's bounding box
        self.bb_center = np.array([0]*3)
        self.bb_x_length = None
        self.bb_y_length = None
        self.bb_z_length = None
        self.bb_longest_length = None
        self.bb_shortest_length = None
        self.longest_length = 0.0
        self.update_bounding_box()

    def set_max_length(self, length):
        self.max_length = length

    def set_color(self, color):
        self._trail_actor.GetProperty().SetColor(color[0], color[1], color[2])

    def reduce_opacity(self, factor=0.5):
        self.opacity * factor
        self._trail_actor.GetProperty().SetOpacity(self.opacity*factor)

    def thicken(self, factor=2):
        self.thickness * factor
        self._trail_actor.GetProperty().SetLineWidth(int(self.thickness))
    
    def get_last_position(self):
        return(self.points[-1])

    def is_full(self):
        return(self.full)

    def set_layer(self, layer):
        self.layer = layer

    def update(self, world_position=None, fullcheck=True):
        """
        Add a point at world_position and connecting line (as long
        as there's another point to connect from) to the trail segment 

        Returns 0 if a normal update occurred
        Returns 1 if fullcheck=True and this segment is full and needs
           points moved
        """
        #print(f" DEBUG: TOP OF TRAIL SEGMENT UPDATE with world pos {world_position}")
        if not self._trail_points or self.full:
            return

        pos = world_position
        self.points.append(np.array(pos))
        num_points = len(self.points)

        pid = self._trail_points.InsertNextPoint(pos[0], pos[1], pos[2])
        self._trail_polyline.GetPointIds().InsertNextId(pid)

        # Update line structure
        self._trail_lines.Reset()
        self._trail_lines.InsertNextCell(self._trail_polyline)

        self._trail_points.Modified()
        self._trail_lines.Modified()
        self._trail_polydata.Modified()
        self.update_bounding_box()

        length = np.linalg.norm(self.points[0] - self.points[-1])
        if length > self.longest_length:
            self.longest_length = length
            #print(f"DEBUG: longest length set to {self.longest_length}")

        if (fullcheck and num_points > 1 and 
            self.get_distance_from_node() > self.max_length):
            self.full = True
            #print(f"DEBUG: this segment is full because more than 1 point and dist from "
            #      f"node {self.get_distance_from_node()} > {self.max_length}")
            return 1

        return 0


    def add_points(self, points, where='after'):
        """
        Add points to this segment and call self.update to draw
        the lines for those points
        
        :param self: Description
        :param points: points to add
        :param where: Order the points should be added, before or after
                      existing points
        """
        new_points = list([])
        if where == 'after':
            new_points = self.points + points
        elif where == 'before':
            new_points = points + self.points
        # Update/loop over all added points
        for point in points[:-1]:
            self.update(world_position=point, fullcheck=False)
        # Check for fullness only on the last point added
        self.update(world_position=new_points[-1], fullcheck=True)

    def update_bounding_box(self):
        # Update the size of this trail segment's bounding box
        self.bb = list(self._trail_actor.GetBounds())
        self.bb_center = np.array(self._trail_actor.GetCenter())
        self.bb_x_length = abs(self.bb[0] - self.bb[1])
        self.bb_y_length = abs(self.bb[2] - self.bb[3])
        self.bb_z_length = abs(self.bb[4] - self.bb[5])
        self.bb_longest_length = max(self.bb_x_length,
                                     self.bb_y_length,
                                     self.bb_z_length)
        self.bb_shortest_length = min(self.bb_x_length,
                                      self.bb_y_length,
                                      self.bb_z_length)

    def get_distance_from_node(self):
        """
        Get the distance this trail's (estimated) far side is from it's node.
        This is used to determine when points from a trail segment need to move
        so that the clipping ranges to not get too large
        """
        world_pos = np.array(self.node.get_world_position())
        distance = np.linalg.norm(world_pos - self.bb_center)
        distance = distance + (self.longest_length/2.0)
        # Never allow a negative distance by limiting to zero
        if distance < 0:
            distance = 0
        #print(f"      distance from node {distance/1000} km")
        return (distance)

    def get_distance_from_camera(self, camera_pos):
        """
        Get the distance from the camera to the far side of this segment.  An
        encompassing sphere computed from the max length of the segment is used
        to estimate the distance to the back face of the segment
        """
        distance = np.linalg.norm(camera_pos - self.bb_center)
        #print(f"  distance {distance/1000} km")
        #print(f"  longest_length {self.longest_length/1000} km")
        distance = distance + (self.longest_length/2.0)
        # Never allow a negative distance by limiting to zero
        if distance < 0:
            distance = 0
        #print(f"  Distance from camera {distance/1000} km")
        return (distance)

    def has_points(self):
        if len(self.points) > 0:
            return True
        return False

    def get_actor(self):
        return (self._trail_actor)

    def get_layer(self):
        """
        Get the layer this trail should be drawn in.
        """
        return self.layer

    def is_visible(self):
        return self._trail_actor.GetVisibility()

    def hide(self):
        return self._trail_actor.SetVisibility(0)

    def show(self):
        return self._trail_actor.SetVisibility(1)

    def reset_trail(self):
        """
        Remove all lines/points from this trail
        """
        if not self._trail_points:
            return
        self._trail_polyline.GetPointIds().Reset()
        self._trail_points.Reset()
        self._trail_lines.Reset()
        self._trail_points.Modified()
        self._trail_lines.Modified()
        self._trail_polydata.Modified()
        self.points = []
        self.full = False


class VirgoTrail:
    """
    Management class for VIRGO trails. Trails are lines drawn where an
    actor has previously been. Trails are comprised of VirgoTrailSegments.
    """
    def __init__(self, node, color=[1.0, 1.0, 1.0], thickness=2, opacity=1.0,
                 fg_far_bound=1e5, mg_far_bound=1e8):
        """
        color: User defined color of the trail
        thickness: User defined thickness of the trail
        opacity: User defined opacity of the trail
        fg_far_bound: distance away a foreground trail segment can be 
           before it's moved into the midground
        mg_far_bound: distance away a miground trail segment can be 
           before it's moved into the background
        """
        # split factor represents segments per midground/background distance space
        # and this magic number 3.0 seems to work well. We may need to adjust this
        # over time - Jordan Feb 2026
        self.split_factor = 3.0
        self.node = node    # The node associated with this trail
        self.color = color  # User defined color of the trail
        self.thickness = thickness  # User defined thickness of the trail
        self.opacity = opacity      # User defined opacity of the trail
        # Distances associated with rendering layer boundaries, used to
        # move trails between layers automatically
        self.foreground_far_boundary = fg_far_bound
        self.midground_far_boundary = mg_far_bound
        # The latest segment is the one getting points and lines
        # added when actors move in the scene
        self.latest_segment = VirgoTrailSegment(
                self.node, color=color,
                thickness=thickness, opacity=opacity,
                max_length=self.foreground_far_boundary/self.split_factor)
        # The segments list holds history of trails, containing points
        # and lines added from self.latest_segment, up to the
        # self.max_segments limit
        self.segments = []
        self.segment_idx = 0  # Current idx of self.segments
        # Maximum number of segments to store in memory
        self.max_segments = 10
        for s in range(self.max_segments):
            seg = VirgoTrailSegment( self.node, color=color,
                thickness=thickness, opacity=opacity,
                max_length=self.midground_far_boundary/self.split_factor) 
            self.segments.append( seg)
        # Debug visual help on seeing each segment
        self.segment_debug_colors = False # Turn on to change all segments to unique colors

    def color_the_segments(self):
        """Make each segment a unique color. This is for debugging"""
        colors = [
            [1.0,  0.0,  0.0 ],  # Red
            [0.0,  1.0,  0.0 ],  # Lime Green
            [0.0,  0.5,  1.0 ],  # Azure Blue
            [1.0,  1.0,  0.0 ],  # Yellow
            [1.0,  0.0,  1.0 ],  # Magenta
            [0.0,  1.0,  1.0 ],  # Cyan
            [1.0,  0.5,  0.0 ],  # Orange
            [0.5,  0.0,  1.0 ],  # Violet
            [0.0,  1.0,  0.5 ],  # Spring Green
            [1.0,  0.75, 0.8 ],  # Pink
            [1.0,  1.0,  1.0 ],  # White
        ]
        self.latest_segment.set_color(colors[0])
        for idx, segment in enumerate(self.segments):
            segment.set_color(colors[idx+1])
        self.segment_debug_colors = True

    def uncolor_the_segments(self):
        """Enforce the user color on all segments"""
        self.latest_segment.set_color(self.color)
        for idx, segment in enumerate(self.segments):
            segment.set_color(self.color)
        self.segment_debug_colors = False

    def set_far_boundary(self, layer, distance):
        """
        Set the far boundary of trail's in their rendering layer(s)
        and set the max_length for each associated segment which
        is also based on this distance
        """
        if layer == 'foreground':
            self.foreground_far_boundary = distance
            self.latest_segment.set_max_length(
                self.foreground_far_boundary/self.split_factor)
        elif layer == 'midground':
            self.midground_far_boundary = distance
            for seg in self.segments:
                seg.set_max_length(
                    self.midground_far_boundary/self.split_factor)

    def update(self, world_position):
        """
        Draw the line to the next world_position. Move points to a segment
        in self.segments if appropriate.
        """
        #print(f"------- DEBUG: TOP OF TRAIL UPDATE with world pos {world_position} ---------")
        full = self.latest_segment.update(world_position)
        # If the active segment is now full, move points self.segments
        if full:
            self.segment_idx = self.get_segment_idx()
            self.move_points()
        #print(f"------- DEBUG: END OF TRAIL UPDATE with world pos {world_position} ---------")

    def get_segment_idx(self):
        """
        Prepare self.segments and return the segment buffer idx that should be used given the
        state of self.segments element fullness. If all segments are full, clear
        and roll over self.segments[0]
        """
        current_segment = self.segments[self.segment_idx]
        # There's room in the current segment buffer
        if not current_segment.is_full():
            #print(f"  DEBUG: in get_segment_idx returning {self.segment_idx}")
            return self.segment_idx
        # There's no room in this self.segment_idx but there's more segments in the buffer
        elif (self.segment_idx + 1) < self.max_segments:
            self.segments[(self.segment_idx + 1)].reset_trail()
            #print(f"  DEBUG: in get_segment_idx returning {self.segment_idx+1}")
            return (self.segment_idx + 1)
        # Buffer full, rollover back to 0
        else:
            self.segments[0].reset_trail()
            #print(f"  DEBUG: in get_segment_idx rollover returning 0")
            return (0)

    def move_points(self):
        """
        Move points from latest segment to the appropriate self.segments
        instance

        TODO: Right now the entire segment's points get moved, and as a result
        we see midground clipping issues with other large objects in the scene.
        It might be better to move the last fraction of points instead of all of
        them (perhaps use self.split_factor) but the logic would have to change
        from calling self.latest_segment.reset_trail() to removal of only those
        points. Bigger fish to fry right now -Jordan Feb 2026
        """
        #print(f"   DEBUG: Moving points to {self.segment_idx}")
        last_point = self.latest_segment.points[-1]

        add_these = self.latest_segment.points
        if len(add_these) == 0:
            # No points to move
            return
        to_segment = self.segments[self.segment_idx]

        to_segment.add_points(points=add_these)
        # Clear the trail of the latest segment so it's ready for more points
        self.latest_segment.reset_trail()
        # prime the latest segment with the last point so no gap in trail
        # will appear
        self.latest_segment.update(last_point)
        #print(f"   DEBUG: {len(add_these)} points moved from latest to {self.segment_idx}")

    def configure_layers(self, camera_pos):
        """
        Set the layer for each trail segment based on how far it is from the camera
        """
        all_segments = self.segments + [self.latest_segment]
        camera_pos = np.array(camera_pos)
        for segment in all_segments:
          if not segment.has_points():
            continue
          current_layer = segment.get_layer()
          dist_from_camera = segment.get_distance_from_camera(camera_pos)
          #print(f"{self.node.name} curr layer: {current_layer} cam dist: {dist_from_camera}, ffb: {self.foreground_far_boundary}")
          if dist_from_camera > self.midground_far_boundary:
            layer = 'background'
          elif dist_from_camera > self.foreground_far_boundary:
            layer = 'midground'
          else:
            layer = 'foreground'
          if current_layer != layer:
            #print(f"{self.node.name} trail layer changed to {layer}, cam dist {dist_from_camera}")
            segment.set_layer(layer)

    def get_trail_actors_and_their_layers(self):
        """
        Return a list of tuples of (Trail Actor, rendering layer)
        to add to rendering layers
        """
        aatl = [ (self.latest_segment.get_actor(), self.latest_segment.get_layer()) ] 
        for segment in self.segments:
            if segment.has_points():
                aatl.append( (segment.get_actor(), segment.get_layer()))
        return aatl

    def is_visible(self):
        visabilities = [self.latest_segment.is_visible()]
        for segment in self.segments:
            visabilities.append( segment.is_visible())
        return any(visabilities)

    def hide(self):
        self.latest_segment.hide()
        for segment in self.segments:
            segment.hide()

    def show(self):
        self.latest_segment.show()
        for segment in self.segments:
            segment.show()

    def reset_trail(self):
        """
        Remove all lines/points from this trail
        """
        self.latest_segment.reset_trail()
        for segment in self.segments:
            segment.reset_trail()
