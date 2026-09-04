import numpy as np
import math
from typing import Self

from vtkmodules.vtkRenderingCore import (
  vtkActor,
  vtkCamera,
  vtkPolyDataMapper,
)
from vtkmodules.vtkCommonDataModel import (
  vtkPolyData,
  vtkCellArray,
)
from vtkmodules.vtkCommonCore import (
    vtkPoints,
)

from .VirgoNode import VirgoSceneNode

class VirgoCamera():
    """
    This class provides the management layer for cameras within the
    VIRGO scene.
    """
    # Frustum visibility modes
    frustum_when_modes = ['always', 'never', 'toggled']
    # Interactor modes: TB: trackball, FP: first-person
    interactor_modes = ['TB', 'FP']
    # Flag to track visibility of state of all 'toggled' frustums
    global_show_toggled_frustums = False

    def __init__(self, name, mode='TB',
                 position=[0.0, 0.0, 0.0],
                 focal_point=[1.0, 0.0, 0.0],
                 view_up=[0.0, 0.0, 1.0],
                 view_angle=30,
                 static=False,
                 frustum_when='toggled',
                 frustum_far_plane=1.0,
                 frustum_color=[1.0, 0.9, 0.1],
                 frustum_face_opacity=0.15,
                 frustum_line_width=2.0,
                 priority=1,
                 parent=None): 
        self.active = False
        self.name = name
        self.set_interactor_mode(mode)
        self.position = position
        self.focal_point = focal_point
        # Relative Tolerance used by np.allclose when evaluating
        # whether focal_point is too close to the position of the
        # camera. TODO: I think this number can go lower using
        # double precision but we really need to test it before
        # adjusting it too much - Jordan 4/2026
        self.pos_fp_tolerance = 1e-10
        # Same tolerance but for view_up parallel to view direction
        self.parallel_view_up_tolerance = 1e-6
        self.view_up = view_up
        self.view_angle = view_angle
        self.static = static
        self.set_frustum_mode(frustum_when)
        self.set_frustum_far_plane(frustum_far_plane)
        self.frustum_color = frustum_color
        self.frustum_face_opacity = frustum_face_opacity
        self.frustum_line_width = frustum_line_width
        self.priority = priority
        self.parent = parent
        self.verbosity=1  # TODO make adjustable
        self.camera = self.create_vtk_camera()

        # Frustum specific members. self.frustum_assembly always gets a real
        # default here (None) so it's never simply *missing* from the
        # instance - only ever None (frustum disabled/not yet updated) or a
        # real vtkAssembly. set_frustum_visible()/set_frustum_invisible()
        # rely on that.
        self.frustum = None
        self.frustum_assembly = None
        if self.frustum_when != 'never' and self.name != 'default':
            self.frustum = VirgoCameraFrustum(
                name=f"{self.name}-frustum", 
                color=self.frustum_color, 
                line_width=self.frustum_line_width, 
                face_opacity=self.frustum_face_opacity
            )
            self.frustum_assembly = self.frustum.assembly
            # Populate real geometry right away rather than waiting for the
            # first external update_frustum() call, same as the rest of
            # this class's construction-time initialization.
            self.update_frustum(1.0, 1.0)
        self.stored_clipping_range = self.store_clipping_range()

        # Parameters describing position relative to a parent, if self.parent != None
        self.relative_offset = list(self.position)
        # Camera GetViewUp() direction when self.relative_offset was stored
        self.relative_view_up = list(self.view_up)
        # Focal point relative to node position, used in first person mode
        self.relative_focal_point = [0,0,0]

        self.original_camera_params = self.store_camera_parameters()

    def has_frustum(self):
        return (self.frustum != None)

    def disable_frustum(self):
        self.frustum = None
        self.frustum_assembly = None

    def update(self, window_width, window_height):
        """
        The main update loop for a camera. Position the camera to follow
        its parent node (if it has one) and update its frustum
        visualization. Following the parent is NOT gated on whether the
        frustum is enabled - those are two independent concerns.
        """
        if self.parent:
            self.follow(node=self.parent)
        if self.frustum_when == 'never':
                    return
        self.update_frustum(window_width=window_width, window_height=window_height)
        # Hide the active camera's frustum so it does not block the view.
        # Inactive cameras with frustum_when always/toggled stay visible.
        if self.is_active():
            self.set_frustum_invisible()
        elif self.frustum_when in ('always'):
            self.set_frustum_visible()
        elif self.frustum_when in ('toggled'):
            if VirgoCamera.global_show_toggled_frustums:
                self.set_frustum_visible()
            else:
                self.set_frustum_invisible()

    def get_frustum(self):
        return self.frustum

    def get_frustum_assembly(self):
        return self.frustum_assembly

    def get_priority(self):
        return(self.priority)

    def set_priority(self, pr):
        self.priority = pr

    def store_camera_parameters(self):
        """
        Return the camera paramters from internal members in a dictionary
        format
        """
        stored_params = {}
        stored_params['position'] = self.position
        stored_params['focal_point'] = self.focal_point
        stored_params['view_up'] = self.view_up
        stored_params['view_angle'] = self.camera.GetViewAngle()
        stored_params['relative_offset'] = self.get_relative_offset()
        stored_params['relative_focal_point'] = self.get_relative_focal_point()
        return stored_params

    def set_camera_params(self, cam_params:dict):
        """
        Set camera parameters to the values in cam_params dict

        TODO: better error checking on cam_params should be done Also this
        doesn't respect the parent of the camera and perhaps it should
        """
        self.camera.SetPosition(cam_params['position'])
        self.camera.SetFocalPoint(cam_params['focal_point'])
        self.camera.SetViewUp(cam_params['view_up'])
        self.camera.SetViewAngle(cam_params['view_angle'])
        self.set_relative_offset(cam_params['relative_offset'])
        self.set_relative_focal_point(cam_params['relative_focal_point'])

    def restore_original_camera_params(self):
        """
        Set params in self.camera that were initially given when this
        class instance was created
        """
        self.set_camera_params(self.original_camera_params)

    def create_vtk_camera(self):
        """
        Create the vtkCamera instance with the current camera parameters
        and return it.
        """
        camera = vtkCamera()
        camera.SetPosition(self.position)
        camera.SetFocalPoint(self.focal_point)
        camera.SetViewUp(self.view_up)
        camera.SetViewAngle(self.view_angle)

        return camera

    def set_interactor_mode(self, new_mode):
        """
        Set the camera interactor mode
        """
        if new_mode.upper() in self.interactor_modes:
            self.interactor_mode = new_mode.upper()
        else:
          msg = (f"ERROR: Interactor mode {new_mode} not recognized by "
                 f"{self.__class__.__name__}. Valid options are {self.interactor_modes}")
          raise RuntimeError (msg)

    def get_interactor_mode(self):
        return self.interactor_mode

    def set_frustum_mode(self, new_mode):
        """
        Set the camera frustum mode
        """
        if new_mode.lower() in self.frustum_when_modes:
            self.frustum_when = new_mode.lower()
        else:
          msg = (f"ERROR: Frustum mode {new_mode} not recognized by "
                 f"{self.__class__.__name__}. Valid options are {self.frustum_when_modes}")
          raise RuntimeError (msg)

    def get_frustum_mode(self):
        return self.frustum_when

    def set_frustum_far_plane(self, distance):
        """
        Set the camera far plane distance
        """
        if distance > 0.0:
            self.frustum_far_plane = distance
        else:
          msg = (f"ERROR: Frustum far plane {distance} must be > 0.0 in "
                 f"{self.__class__.__name__}")
          raise RuntimeError (msg)

    def set_position(self, x, y, z, warn=True):
        """
        Move the internal vtkCamera a.k.a self.camera to the given world coord
        [x, y, z] world position. Check to make sure this won't put position
        at the same location as focal point, if so, adjust focal point to
        deconflict that case
        """
        current_fp = self.get_focal_point()
        if np.allclose(current_fp, [x, y, z], rtol=self.pos_fp_tolerance):
          if warn:
            print(f"WARNING: Attempt to set camera {self.name}'s position to "
                  f"[{x}, {y}, {z}] would move {self.name} too close to "
                  f"current focal point {current_fp}. Automatically adjusting "
                  f"focal_point to deconflict")
          # We want a small offset based on characteristic length
          cl = self.get_characteristic_length(vec=[x,y,z])
          self.set_focal_point(x=current_fp[0] + cl*0.001,
                               y=current_fp[1],
                               z=current_fp[2])
        self.camera.SetPosition(x, y, z)

    def set_focal_point(self, x, y, z, warn=True):
        """
        Set the internal vtkCamera a.k.a self.camera's focal point
        to the [x, y, z] world position. If this would put the focal point
        too close to the position of the camera, offset it by a characteristic
        length
        """
        current_pos = self.get_position()
        if np.allclose(current_pos, [x, y, z], rtol=self.pos_fp_tolerance):
          #import pdb; pdb.set_trace()
          cl = self.get_characteristic_length(vec=[x,y,z])
          # We want a small offset based on characteristic length
          offset = cl*0.001
          if warn:
            print(f"WARNING: Attempt to set focal point to [{x}, {y}, {z}] "
                  f"failed as this is too close to current position "
                  f"{current_pos}. Automatically adding {offset} offset "
                  f"in x direction")
          x = x+cl
          #import pdb; pdb.set_trace()
        self.camera.SetFocalPoint(x, y, z)

    def get_focal_point(self):
        """
        Get the internal vtkCamera a.k.a self.camera's focal point
        """
        return(self.camera.GetFocalPoint())


    def set_view_up(self, x, y, z, warn=True):
        """
        Set the internal vtkCamera a.k.a self.camera's view_up vector
        view_up = [x, y, z] world position

        Guard against the singularity where view-up is parallel to the
        view direction
        """
        pos = np.array(self.get_position())
        fp = np.array(self.get_focal_point())
        view_dir = fp - pos
        dist = np.linalg.norm(view_dir)
        view_dir_n = view_dir / dist
        up = [x, y, z]

        up_n = up / np.linalg.norm(up)
        parallelism = abs(np.dot(view_dir_n, up_n))
        if parallelism > 1 - self.parallel_view_up_tolerance:
            # Auto-pick a safe alternative view-up
            up = np.array([0, 0, 1]) if abs(view_dir_n[2]) < 0.9 else np.array([1, 0, 0])
            if warn:
              print(f"WARNING: Attempt to set view_up to [{x}, {y}, {z}] "
                    f"failed as this is too close to parallel with "
                    f"the view direction {view_dir_n}. Automatically using " 
                    f"safer value {up}.")

        self.camera.SetViewUp(*up)

    def get_view_up(self):
        """
        Get the internal vtkCamera a.k.a self.camera's view_up vector
        """
        return(self.camera.GetViewUp())

    def set_view_angle(self, view_angle: float):
        """
        Set the internal vtkCamera a.k.a self.camera's view_angle in
        degrees
        """
        self.camera.SetViewAngle(view_angle)

    def get_view_angle(self):
        """
        Get the internal vtkCamera a.k.a self.camera's view_angle in
        degrees
        """
        return(self.camera.GetViewAngle())

    def set_clipping_range(self, near, far):
        """
        Set the internal vtkCamera a.k.a self.camera's clipping range
        """
        self.camera.SetClippingRange(near, far)

    def get_clipping_range(self):
        """
        Return the internal vtkCamera a.k.a self.camera's clipping range
        """
        return (self.camera.GetClippingRange())

    def store_clipping_range(self):
        """
        Store the current clipping range in self.stored_clipping_range
        """
        self.stored_clipping_range = self.get_clipping_range()
        return(self.stored_clipping_range)

    def restore_clipping_range(self):
        """
        Make the internal vtkCamera's clipping range the values stored
        in self.stored_clipping_range
        """
        self.camera.SetClippingRange(self.stored_clipping_range)

    def get_world_position(self):
        """
        Return the internal vtkCamera a.k.a self.camera's position in world
        space
        """
        return (self.camera.GetPosition())

    def get_position(self):
        return(self.get_world_position())

    def zoom(self, factor):
        """
        Apply a zoom scale factor to the current zoom.
        """
        if factor > 0.0:
            self.camera.Zoom(factor)
        else:
          msg = (f"ERROR: Zoom factor {factor} must be > 0.0 in "
                 f"{self.__class__.__name__}.")
          raise RuntimeError (msg)

    def set_frustum_visible(self):
        if self.get_frustum_mode() != 'never' and self.frustum_assembly:
            self.frustum_assembly.SetVisibility(1)

    def set_frustum_invisible(self):
        """
        Not guarded behind frustum_mode as we need to be able to disable
        this for rendering clipping range reasons
        """
        if self.frustum_assembly:
            self.frustum_assembly.SetVisibility(0)


    def update_frustum(self, window_width, window_height):
        """
        Recompute the frustum visualization's geometry and keep it
        positioned at the camera. Only touches frustum-visualization state, 
        does not move the camera itself or follow a parent, see update().
        """
        if self.frustum is None:
            return
        self.frustum.update_frustum(
            camera=self, 
            window_width=window_width, 
            window_height=window_height)
        self.frustum_assembly = self.frustum.assembly

    def get_frustum_far_plane(self):
        return self.frustum_far_plane

    def get_vtk_camera(self):
        return (self.camera)

    def set_vtk_camera(self, cam:vtkCamera):
        if not isinstance(cam, vtkCamera):
          msg = (f"ERROR: Camera {cam} not an instance of vtkCamera in "
                 f"{self.__class__.__name__}.")
          raise RuntimeError (msg)
        self.camera = cam

    def sync_with(self, in_cam: Self):
        """
        Sync this camera wit the params of in_cam
        """
        pos = in_cam.get_position()
        self.set_position(pos[0], pos[1], pos[2])
        fp = in_cam.get_focal_point()
        self.set_focal_point(fp[0], fp[1], fp[2])
        va = in_cam.get_view_angle()
        self.set_view_angle(va)
        ro = in_cam.get_relative_offset()
        self.set_relative_offset(ro)
        # view up deliberately last as other params can affect it
        vu = in_cam.get_view_up()
        self.set_view_up(vu[0], vu[1], vu[2])
        #print(f"DEBUG: {self.name} sync_with {in_cam.name}, pos: {pos}")

    def sync_with_vtk_camera(self, in_cam: vtkCamera):
        """
        Sync this camera wit the params of in_cam
        """
        pos = in_cam.GetPosition()
        self.set_position(pos[0], pos[1], pos[2])
        fp = in_cam.GetFocalPoint()
        self.set_focal_point(fp[0], fp[1], fp[2])
        va = in_cam.GetViewAngle()
        self.set_view_angle(va)
        # view up deliberately last as other params can affect it
        vu = in_cam.GetViewUp()
        self.set_view_up(vu[0], vu[1], vu[2])
        #print(f"DEBUG: {self.name} sync_with {hex(id(in_cam))}, pos: {pos}, va: {va}")

    def report(self, indent=''):
        print(f"{indent}Name: {self.name}, "
              f"parent: {self.get_parent_name()}, "
              f"active: {self.is_active()}")
        #print(f"{indent*2}address: {hex(id(self.camera))}")
        print(f"{indent*2}position: {self.camera.GetPosition()}")
        print(f"{indent*2}focal point: {self.camera.GetFocalPoint()}")
        print(f"{indent*2}view up: {self.camera.GetViewUp()}")
        print(f"{indent*2}clipping range: {self.camera.GetClippingRange()}")
        print(f"{indent*2}relative offset: {self.get_relative_offset()}")
        print(f"{indent*2}relative focal point: {self.get_relative_focal_point()}")
    
    def has_parent(self):
        if self.parent:
            return True
        else:
            return False

    def get_parent(self):
        return self.parent

    def get_parent_name(self):
        if self.parent:
            return self.parent.name
        else:
            return None

    def set_parent(self, parent):
        if parent == None:
            self.parent = None
            return
        if (not isinstance(parent, VirgoSceneNode) and 
            not issubclass(parent, VirgoSceneNode)):
            msg = (f"ERROR: Cannot set parent to: {parent}. Must be of "
              f"type VirgoSceneNode but got {type(parent)} instead.")
            raise RuntimeError (msg)
        self.parent = parent

    def get_name(self):
        return self.name

    def is_active(self):
        return self.active

    def is_static(self):
        return self.static

    def activate(self):
        self.active = True
        self.set_frustum_visible()

    def deactivate(self):
        self.active = False
        self.set_frustum_invisible()
    
    def set_relative_offset(self, ro):
        self.relative_offset = ro

    def get_relative_offset(self):
        return(self.relative_offset)

    def set_relative_focal_point(self, rfp):
        self.relative_focal_point = rfp

    def get_relative_focal_point(self):
        return(self.relative_focal_point)

    def clear_relative_focal_point(self):
        self.relative_focal_point = [0,0,0]

    def clear_relative_camera_info(self):
        """
        Clear relative camera info
        """
        self.relative_offset = None
        self.view_up = None

    def set_free(self):
        """
        Remove parent relationship by setting self.parent to None
        """
        self.parent = None

    def follow(self, node: VirgoSceneNode, initial_offset=None):
        """
        Positions the camera such that it maintains its relative position to
        world_position. 

        Params:
          node (VirgoSceneNode): Node to have the camera follow

        TODO:
           * The if camera_follow_offset is None block is really 
             a "first camera follow init" thing, it probably should not
             go here and conditions be satisfied as part of the camera
             __init__
        """
        if not node:
            msg = f"Unable to follow node {node}. Must derive from VirgoSceneNode"
            raise RuntimeError(msg)
        # Ask the camera for the latest camera offset position from node
        camera_follow_offset = self.get_relative_offset()
        #print(f"DEBUG: camera_follow_offset is {camera_follow_offset}")
        node_pos = node.get_world_position()

        if camera_follow_offset is None:
            if initial_offset:
                camera_follow_offset = np.array(initial_offset)
            else:
                camera_follow_offset = self.automatic_camera_offset(node)
            pos =np.array(node_pos)
            camera_pos = pos + camera_follow_offset
            self.set_position(camera_pos[0], camera_pos[1], camera_pos[2])
            if self.interactor_mode == 'TB':
                self.set_focal_point(pos[0], pos[1], pos[2])
            # Store this initial offset
            self.set_relative_offset(
                 np.array([self.camera.GetPosition()[i] - node_pos[i] for i in range(3)]) )
            self.set_relative_focal_point(
                np.array([self.camera.GetFocalPoint()[i] - node_pos[i] for i in range(3)]))

        pos = np.array(node.get_world_position())
        camera_pos = pos + camera_follow_offset
        # Set camera position
        self.set_position(camera_pos[0], camera_pos[1], camera_pos[2])
        # Set focal point to node's origin if using trackball style 
        if self.interactor_mode == 'TB':
            self.set_focal_point(pos[0], pos[1], pos[2])
            view_up = self.get_view_up()
            self.set_view_up(view_up[0], view_up[1], view_up[2])
        # Otherwise, in first-person style, orient the camera with it's
        # node/parent if it's static, or keep the relative focal point
        # consistent if it's not static
        else:
            if self.is_static():
                # Orient the camera along Node's X axis with +Z up
                # if using static first person style
                self.orient(node)
            else:
                # Set focal point to spacecraft's center + last stored relative
                # focal point if using non-static first person style
                relative_focal_point = self.get_relative_focal_point()
                self.set_focal_point(pos[0] + relative_focal_point[0], 
                                     pos[1] + relative_focal_point[1], 
                                     pos[2] + relative_focal_point[2],
                                     warn=False)

    def automatic_camera_offset(self, node, distance_factor=20.0):
        """
        If no initial offset given, compute it from the bounding box of the node
        """
        # Get the bounding box of the actor
        bounds = node.actor.GetBounds()
        # Bounds are returned as (xmin, xmax, ymin, ymax, zmin, zmax)
        center = [(bounds[0] + bounds[1]) / 2.0,  # x-center
                  (bounds[2] + bounds[3]) / 2.0,  # y-center
                  (bounds[4] + bounds[5]) / 2.0]  # z-center
        # Calculate the size of the bounding box
        size = [bounds[1] - bounds[0],  # x-size
                bounds[3] - bounds[2],  # y-size
                bounds[5] - bounds[4]]  # z-size
        # Determine an offset distance based on the bounding box size
        # For example, place the camera at a distance of 5 times the maximum dimension
        max_dimension = max(size)
        offset_distance = max_dimension * distance_factor
        automatic_offset = np.array([offset_distance, offset_distance/2.0, 0.0])
        return automatic_offset

    @staticmethod
    def get_characteristic_length(vec):
        # Determine a characteristic length of position's floating point values
        largest_value = abs(max(vec))
        smallest_value = abs(min(vec))
        midway_between = (largest_value + smallest_value)/2.0
        if math.isclose(midway_between, 0.0):
            characteristic_length = 1.0
        else:
            characteristic_length = midway_between
        return (characteristic_length)

    def orient(self, node: VirgoSceneNode):
        """
        Orient the active camera so that:
          • Camera looks along the node's world-space +X axis
          • View-up        = assembly's world-space +Z axis
     
        Parameters
        ----------
        node :   the VirgoSceneNode whose frame to adopt
        """
        # Get the world position of the node
        node_pos = np.array(node.get_world_position())
        # Determine a characteristic length of position's floating point values
        characteristic_length = self.get_characteristic_length(node_pos)
        # Add length in +X in the local coordinate system, this is the intended
        # focal point direction of this camera
        node_x_dir = np.array(node.get_world_position(
            local_point=[characteristic_length, 0.0, 0.0]))

        # Add length in +Z in the local coordinate system, this is the intended
        # view up direction of this camera
        node_z_dir = np.array(node.get_world_position(
            local_point=[0.0, 0.0, characteristic_length]))

        if np.allclose(node_pos, node_x_dir):
            msg = f"Unable to orient camera, cannot determine +X direction!"
            raise RuntimeError(msg)
        if np.allclose(node_pos, node_z_dir):
            msg = f"Unable to orient camera, cannot determine +Z direction!"
            raise RuntimeError(msg)

        view_up = node_z_dir - node_pos
        self.set_focal_point(*node_x_dir)
        self.set_view_up(*view_up)

    def azimuth(self, value):
        self.camera.Azimuth(value)


class VirgoCameraFrustum(VirgoSceneNode):
    """
    A VirgoSceneNode that visualizes a VirgoCamera's frustum as a wireframe
    pyramid. Kept as its own node (rather than a bare vtkAssembly living on
    VirgoCamera) so it's a first-class part of the scene hierarchy, per
    Dan's suggestion on the frustum-visualization issue.

    PRECISION: the 8 corner points computed in update_frustum() are
    expressed relative to the camera - direction/right/up scaled by
    near/far distance and half-angle - and never have the camera's
    absolute world position added into them. This node is instead
    translated to the camera's world position via set_pose(pos=...) each
    frame (translation only, confirmed safe against the real
    VirgoSceneNode.set_pose(): with ypr/dcm both None it just calls
    self.local_transform.Translate(*pos) after resetting to Identity, no
    rotation gets applied on top of these already-world-oriented corner
    points). That split - small local geometry + a separate large-
    magnitude translation - is what avoids the precision collapse that
    broke the original vtkFrustumSource-based approach at spacecraft
    scene scale.
    """
    CROSS_PRODUCT_TOLERANCE = 1e-8

    def __init__(
            self, 
            name="Camera Frustum", 
            color=[1.0, 1.0, 1.0], 
            face_opacity=0.2, 
            line_width=2.0):
        self.color = color
        self.line_width = line_width
        self.face_opacity = face_opacity

        # Points created once and mutated in the update function

        self.points = vtkPoints()
        for _ in range(5):
            self.points.InsertNextPoint(0.0, 0.0, 0.0)

        # Wireframe topology
        self.polydata = vtkPolyData()
        self.polydata.SetPoints(self.points)
        lines = vtkCellArray()
        edges = [
            (0, 1), (0, 2), (0, 3), (0, 4),
            (1, 2), (2, 3), (3, 4), (4, 1),
        ]

        for a, b in edges:
            lines.InsertNextCell(2)
            lines.InsertCellPoint(a)
            lines.InsertCellPoint(b)
        self.polydata.SetLines(lines)

        self.mapper = vtkPolyDataMapper()
        self.mapper.SetInputData(self.polydata)
        self.actor = vtkActor()
        self.actor.SetMapper(self.mapper)
        # VirgoSceneNode.__init__() unconditionally calls
        # create_silhouette(), which - once past the pickable check -
        # calls self.actor.get_num_vertices(), a VirgoActor-specific
        # method our plain vtkActor doesn't have. A fresh vtkActor
        # defaults to pickable, so this must be turned off before calling
        # super().__init__() to short-circuit that check. Also makes
        # sense semantically: a frustum overlay shouldn't be selectable.
        self.actor.SetPickable(False)
        self.actor.GetProperty().SetRepresentationToWireframe()
        self.actor.GetProperty().SetColor(self.color)
        self.actor.GetProperty().SetLineWidth(self.line_width)
        self.actor.GetProperty().SetOpacity(0.95)

        # Filled faces
        self.face_polydata = vtkPolyData()
        self.face_polydata.SetPoints(self.points)
        polys = vtkCellArray()
        side_tris = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1)]

        for a, b, c in side_tris:
            polys.InsertNextCell(3)
            polys.InsertCellPoint(a)
            polys.InsertCellPoint(b)
            polys.InsertCellPoint(c)
        polys.InsertNextCell(4)
        for i in (1, 2, 3, 4):
            polys.InsertCellPoint(i)
        self.face_polydata.SetPolys(polys)

        self.face_mapper = vtkPolyDataMapper()
        self.face_mapper.SetInputData(self.face_polydata)
        self.face_actor = vtkActor()
        self.face_actor.SetMapper(self.face_mapper)
        self.face_actor.SetPickable(False)
        self.face_actor.GetProperty().SetRepresentationToSurface()
        self.face_actor.GetProperty().SetColor(self.color)
        self.face_actor.GetProperty().SetLighting(False)
        self.face_actor.GetProperty().BackfaceCullingOff()
        self.face_actor.GetProperty().SetOpacity(self.face_opacity)

        # Initialize SceneNode
        super().__init__(
            name=name,
            actor=self.actor,
            axes=False
        )
        self.assembly.AddPart(self.face_actor)


    def update_frustum(self, camera, window_width, window_height):
        """
        Rebuild frustum geometry from the current camera state and move
        this node to the camera's world position.
        """

        if window_width <= 0.0 or window_height <= 0.0:
            raise ValueError("Window width and height must be a positive real number.")

        vtk_camera = camera.camera

        far = camera.frustum_far_plane

        # Camera parameters
        position = np.array(vtk_camera.GetPosition())
        focal = np.array(vtk_camera.GetFocalPoint())
        view_up = np.array(vtk_camera.GetViewUp())
        angle = vtk_camera.GetViewAngle()

        direction = focal - position
        direction = direction / np.linalg.norm(direction)

        right = np.cross(direction, view_up)
        right_norm = np.linalg.norm(right)
        if right_norm < self.CROSS_PRODUCT_TOLERANCE:
            fallback = np.array([1.0, 0.0, 0.0])
            fallback_norm = np.linalg.norm(np.cross(direction, fallback))
            if fallback_norm < self.CROSS_PRODUCT_TOLERANCE:
                fallback = np.array([0.0, 1.0, 0.0])
            right = np.cross(direction, fallback)
        right = right / np.linalg.norm(right)

        up = np.cross(right, direction)
        up = up / np.linalg.norm(up)

        # Frustum dimensions
        aspect = window_width / window_height
        far_height = 2 * far * np.tan(np.radians(angle) / 2)
        far_width = far_height * aspect

        # Centers, relative to the camera - NOT offset by `position`. The
        # camera's world position is handled entirely by set_pose() below,
        # keeping these point coordinates small regardless of where the
        # camera is in the scene.
        far_center = direction * far

        # 1 apex and 4 points in far clipping plane

        # Apex is the camera's own position
        apex = np.array([0.0, 0.0, 0.0])

        corners = [
            apex,                                                       # 0
            far_center - right * far_width / 2 + up * far_height / 2,   # 1
            far_center + right * far_width / 2 + up * far_height / 2,   # 2
            far_center + right * far_width / 2 - up * far_height / 2,   # 3
            far_center - right * far_width / 2 - up * far_height / 2,   # 4
        ]

        # Mutate existing points in place
        for i, p in enumerate(corners):
            self.points.SetPoint(i, *p)
            self.points.Modified()
            self.polydata.Modified()
            self.face_polydata.Modified()

        # Translate this VirgoSceneNode to the position of camera
        self.set_pose(pos=list(position))
