import numpy as np
import math
from typing import Self

from vtkmodules.vtkRenderingCore import (
  vtkActor,
  vtkAssembly,
  vtkCamera,
  vtkPolyDataMapper,
)
from vtkmodules.vtkCommonDataModel import (
  vtkPlanes,
)
from vtkmodules.vtkFiltersSources import (
  vtkFrustumSource,
)

from VirgoNode import VirgoSceneNode

class VirgoCamera():
    """
    This class provides the management layer for cameras within the
    VIRGO scene.
    """
    # Frustum visibility modes
    frustum_when_modes = ['always', 'never', 'toggled']
    # Interactor modes: TB: trackball, FP: first-person
    interactor_modes = ['TB', 'FP']
    def __init__(self, name, mode='TB',
                 position=[0.0, 0.0, 0.0],
                 focal_point=[1.0, 0.0, 0.0],
                 view_up=[0.0, 0.0, 1.0],
                 view_angle=30,
                 static=False,
                 frustum_when='toggled',
                 frustum_far_plane=1.0,
                 frustum_color=[1.0, 0.9, 0.1],
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
        self.pos_fp_tolerance = 1e-7
        # Same tolerance but for view_up parallel to view direction
        self.parallel_view_up_tolerance = 1e-6
        self.view_up = view_up
        self.view_angle = view_angle
        self.static = static
        self.set_frustum_mode(frustum_when)
        self.set_frustum_far_plane(frustum_far_plane)
        self.frustum_color = frustum_color
        self.priority = priority
        self.parent = parent
        self.verbosity=1  # TODO make adjustable
        self.camera = self.create_vtk_camera()

        # Frustum specific members - this is TBD forward work
        self.frustum_source = None
        self.frustum_mapper = None
        self.frustum_actor = None
        self.frustum_fill_mapper = None
        self.frustum_fill_actor = None
        self.planes = None
        self.frustum_assembly = None
        if self.frustum_when != 'never':
            # CURRENTLY DISABLED, SEE COMMENT IN 
            # self.create_frustum_assembly()
            pass
            #self.frustum_assembly = self.create_frustum_assembly()
        self.stored_clipping_range = self.store_clipping_range()

        # Parameters describing position relative to a parent, if self.parent != None
        self.relative_offset = list(self.position)
        # Camera GetViewUp() direction when self.relative_offset was stored
        self.relative_view_up = list(self.view_up)
        # Focal point relative to node position, used in first person mode
        self.relative_focal_point = [0,0,0]

        self.original_camera_params = self.store_camera_parameters()

    def update(self, window_width, window_height):
        """
        The main update loop for a camera. Position the camera to follow
        and node (if it has a parent) and update it's frustum information
        """
        if self.frustum_when != 'never':
            self.update_frustum(window_width=window_width, window_height=window_height)
        if self.parent:
            self.follow(node=self.parent)
        # If this is the camera currently being viewed, turn the frustum off
        # so we can see through it without anything blocking the view
        if self.is_active():
            self.set_frustum_invisible()

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

    def create_frustum_assembly(self):
        """
        Create the pyramid volume representation of this camera's frustum
        and return a vtkAssembly containing the actors comprising it

        CURRENTLY DISABLED AND HERE'S WHY:

        The core issue with frustum the way it's done here is that the points
        comprising the frustum always have values near zero, making them
        suck in the foreground (same limitation as vtkAxesActor). See the
        output in the debug print at the bottom of update_frustum()
    
        Need another approach to draw the frustum, likely through a manual
        approach, or by extracting the first 8 points from the frustum
        source and building our own mesh from it.
        """
        self.frustum_source = vtkFrustumSource()
        self.frustum_source.SetShowLines(True)

        self.frustum_mapper = vtkPolyDataMapper()
        self.frustum_mapper.SetInputConnection(self.frustum_source.GetOutputPort())

        self.frustum_actor = vtkActor()
        self.frustum_actor.SetMapper(self.frustum_mapper)
        self.frustum_actor.GetProperty().SetRepresentationToWireframe()
        self.frustum_actor.GetProperty().SetColor(self.frustum_color)   # bright yellow
        self.frustum_actor.GetProperty().SetLineWidth(2.0)
        self.frustum_actor.GetProperty().SetOpacity(0.85)
        # Filled (semi-transparent) frustum faces
        self.frustum_fill_mapper = vtkPolyDataMapper()
        self.frustum_fill_mapper.SetInputConnection(self.frustum_source.GetOutputPort())
        
        self.frustum_fill_actor = vtkActor()
        self.frustum_fill_actor.SetMapper(self.frustum_fill_mapper)
        self.frustum_fill_actor.GetProperty().SetColor(self.frustum_color)
        self.frustum_fill_actor.GetProperty().SetOpacity(0.06)

        self.planes = vtkPlanes()  # Will be used in update_frustum method
        # Put the bounding pyramid and the filled volume into an assembly
        fa = vtkAssembly()
        fa.AddPart(self.frustum_actor)
        fa.AddPart(self.frustum_fill_actor)
        # Call update_frustum once to silence warnings about "6 planes required"
        # We can't know window height/width yet so give it 1x1
        self.update_frustum(1.0, 1.0)

        return fa

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

    def zoom(self):
        """
        TBD function for applying a zoom to the current camera. This
        affects the view angle by a scale factor
        """
        # Unimplemented
        pass


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


    def update_frustum(self, window_width, window_height ):
        """
        Update the geometry of the frustum based on aspect ratio and
        self.frustum_far_plane distance. This doesn't move self.frustum_assembly
        it recomputes the planes that assembly uses to be in world space.

        When calling GetFrustumPlanes, the 6 plane equations are expressed in
        world coordinates — they already encode the camera's position,
        orientation, FOV, and clipping range baked into the plane coefficients.
        vtkFrustumSource (self.frustum_source) then computes the 8 corner
        vertices of the frustum by finding the intersections of those planes,
        and those corners come out as absolute world-space positions.  So the
        "movement" of the frustum isn't actor movement at all — it's the
        geometry itself being recomputed with different vertex positions each
        frame. The actor stays at the origin with no transform, but its
        underlying polydata has completely different coordinates every update.

        TODO: This approach doesn't work well at spacecraft scene scale, see
        the create_frustum_assembly comment
        """
        if self.frustum_assembly == None:
            return

        # Compute aspect ratio of the PRIMARY viewport in pixels
        aspect = window_width / window_height if window_height > 0 else 1.0
    
        # GetFrustumPlanes expects a flat list of 24 floats (6 planes x 4 coefficients)
        plane_coeffs = [0.0] * 24
    
        # Temporarily swap in a shorter far plane for display
        # purposes - so the frustum pyramid doesn't exend impractically far
        near, far = self.camera.GetClippingRange()
        self.camera.SetClippingRange(near, self.frustum_far_plane)
        self.camera.GetFrustumPlanes(aspect, plane_coeffs)
        self.camera.SetClippingRange(near, far)   # restore
    
        # Load coefficients into vtkPlanes
        self.planes.SetFrustumPlanes(plane_coeffs)
    
        self.frustum_source.SetPlanes(self.planes)
        self.frustum_source.Modified()
        pts = self.frustum_source.GetOutput().GetPoints()
        print(f"DEBUG: frustum points are:")
        for i in range(pts.GetNumberOfPoints()):
            print(pts.GetPoint(i))

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
