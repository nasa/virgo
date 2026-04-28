#!/usr/bin/env python3
"""
VIRGO: Versatile Imaging and Rendering for Galactic Operations
A Practical, Analytical, and Hardworking 3D Visualization tool
leveraging python-VTK
"""

import os, inspect
import numpy as np

from vtkmodules.vtkInteractionStyle import (
  vtkInteractorStyleTrackballCamera,
)
from vtkmodules.vtkCommonCore import (
  vtkCommand,
)
from vtkmodules.vtkCommonTransforms import (
  vtkTransform,
)
# ---------------------------------------------------

thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))


class VirgoTrackballInteractorStyle(vtkInteractorStyleTrackballCamera):
    """
    Virgo Interactor Style which adds some capabilities on top of the VTK
    provided vtkInteractorStyleTrackballCamera, mostly to support keeping the
    camera at a relative position to a camera folloiwng a node as that node
    moves
    """
    def __init__(self, renderers):
        super().__init__()
        self.node = None  # Node this camera follows (if defined)
        self.sun = None   # Sun sphere actor to update
        self.renderers = renderers
        self.cameras = None  # Will contain VirgoControlCenter's self.cameras
        self.AddObserver("CharEvent", self.onChar)
        self.AddObserver(vtkCommand.EndInteractionEvent, self.StoreRelativeCameraInfo, 0.0)
        self.relative_offset = None  # Positional offset between camera and followed actor
        self.view_up = None       # Camera GetViewUp() direction when self.relative_offset was stored
        self.relative_focal_point = [0,0,0] # Focal point relative to node position 
        self.focal_point = None
        self.active_camera = None

        self._locked = False

        ## Override the interaction events that move the camera
        self.omm = self.AddObserver("MouseMoveEvent",       self._on_mouse_move)
        self.lbp = self.AddObserver("LeftButtonPressEvent", self._on_left_button_press)
        self.lbr = self.AddObserver("LeftButtonReleaseEvent", self._on_left_button_release)
        self.mbp = self.AddObserver("MiddleButtonPressEvent", self._on_middle_button_press)
        self.mbr = self.AddObserver("MiddleButtonReleaseEvent", self._on_middle_button_release)
        self.rbp = self.AddObserver("RightButtonPressEvent", self._on_right_button_press)
        self.rbr = self.AddObserver("RightButtonReleaseEvent", self._on_right_button_release)
        self.mwf = self.AddObserver("MouseWheelForwardEvent", self._on_mouse_wheel_forward)
        self.mwb = self.AddObserver("MouseWheelBackwardEvent", self._on_mouse_wheel_backward)

    def set_node(self, node):
        self.node = node

    def set_cameras(self, cameras):
        self.cameras = cameras

    def get_active_camera(self):
        """
        TODO: make this safer, right now it only finds the first
        true instance but we need to make sure multiples aren't True
        """
        if self.cameras == None:
            return None

        for cam in self.cameras:
            if self.cameras[cam].is_active():
                return self.cameras[cam]
        return None

    # Override base class onChar to ignore the 'e' key
    def onChar(self, obj, event):
        key = self.GetInteractor().GetKeySym()
        if key != 'e':  # Ignore 'e' key to prevent exit
            super().OnChar()

    def StoreRelativeCameraInfo(self, caller, event):
        '''
        Store off the relative offset between the followed node and the camera
        in the currently active camera in self.cameras . This is called as a
        callback tied to vtkCommand.EndInteractionEvent which lets us store the
        camera information relative to self.node when the interaction with the
        mouse completes

        TODO: I'm not convinced this callback needs to live in the interactor,
            it might be better placed in the bigger Controller class especially
            since we aren't really overriding any methods of
            vtkInteractorStyleTrackballCamera in this approach
        '''
        #print(f"DEBUG: Entered StoreRelativeCameraInfo with event {event}")
        if not self.node or not self.renderers:
            return
        self.active_camera = self.get_active_camera()
        if self.active_camera == None:
            return
        vtk_camera = self.active_camera.get_vtk_camera()

        node_pos =np.array(self.node.get_world_position())

        # Store off the relative offset of camera
        rel_offset = np.array([vtk_camera.GetPosition()[i] - node_pos[i] for i in range(3)]) 
        self.active_camera.set_relative_offset( rel_offset)
        #print(f"DEBUG: STORING vtk_camera relative offset: {rel_offset}")
        rel_focal = np.array([vtk_camera.GetFocalPoint()[i] - node_pos[i] for i in range(3)])
        self.active_camera.set_relative_focal_point(rel_focal)
        #print(f"DEBUG: Finished StoreRelativeCameraInfo with event {event}")

    def is_locked(self) -> bool:
        self.active_camera = self.get_active_camera()
        if self.active_camera.is_static():
            return True
        else:
            return False

    def _on_mouse_move(self, obj, event):
        if not self.is_locked():
            self.OnMouseMove()          # delegate to base class

    def _on_left_button_press(self, obj, event):
        if self.is_locked():
            pass
        else:
            self.OnLeftButtonDown()

    def _on_left_button_release(self, obj, event):
        if not self._locked:
            self.OnLeftButtonUp()

    def _on_middle_button_press(self, obj, event):
        if self.is_locked():
            pass

    def _on_middle_button_release(self, obj, event):
        if not self.is_locked():
            self.OnMiddleButtonUp()

    def _on_right_button_press(self, obj, event):
        if self.is_locked():
            pass

    def _on_right_button_release(self, obj, event):
        if not self.is_locked():
            self.OnRightButtonUp()

    def _on_mouse_wheel_forward(self, obj, event):
        if self.is_locked():
            pass
        else:
            self.OnMouseWheelForward()
    
    def _on_mouse_wheel_backward(self, obj, event):
        if self.is_locked():
            pass
        else:
            self.OnMouseWheelBackward()

class VirgoInteractorStyleFirstPerson(VirgoTrackballInteractorStyle):
    """
    First Person Virgo Interactor Style which augments the Trackball style
    such that left-click dragging moves the view of the camera instead of
    orbiting around a focal point
    """
    def __init__(self, renderers=None):
        super().__init__(renderers=renderers)

        # Remove the left button down observer from the base class, we define our own
        self.RemoveObserver(self.lbp)
        self.RemoveObserver(self.lbr)

        self._last_pos = (0, 0)
        self._rotating = False
        self.rotate_speed = 0.1          # degrees per pixel

        self.lbp = self.AddObserver("LeftButtonPressEvent",   self._on_left_down)
        self.lbr = self.AddObserver("LeftButtonReleaseEvent", self._on_left_up)
        self.mme = self.AddObserver("MouseMoveEvent",         self._on_mouse_move)

    def _on_left_down(self, obj, event):
        #import pdb; pdb.set_trace()
        self._rotating = True
        self._last_pos = self.GetInteractor().GetEventPosition()

    def _on_left_up(self, obj, event):
        self._rotating = False
        #import pdb; pdb.set_trace()

    def _on_mouse_move(self, obj, event):
        if not self._rotating:
            return
        camera   = self.get_active_camera()
        if camera.is_static():
            return
        iren    = self.GetInteractor()
        cx, cy  = iren.GetEventPosition()
        lx, ly  = self._last_pos
        self._last_pos = (cx, cy)

        delta_x = cx - lx   # horizontal -> yaw
        delta_y = cy - ly   # vertical   -> pitch

        vtk_cam = camera.get_vtk_camera()

        cam_pos  = np.array(vtk_cam.GetPosition())    # stays fixed
        focal_pt = np.array(vtk_cam.GetFocalPoint())
        view_up  = np.array(vtk_cam.GetViewUp())

        # Forward direction (unnormalized is fine for TransformPoint)
        forward = focal_pt - cam_pos

        # --- Build transform ---
        t = vtkTransform()
        t.PostMultiply()

        # Move to camera origin
        t.Translate(-cam_pos[0], -cam_pos[1], -cam_pos[2])

        # Yaw: rotate around ViewUp axis
        t.RotateWXYZ(-delta_x * self.rotate_speed,
                     view_up[0], view_up[1], view_up[2])

        # Pitch: rotate around the camera's Right axis
        right = np.cross(forward, view_up)
        mag   = np.linalg.norm(right)
        if mag > 1e-8:
            right /= mag
            t.RotateWXYZ(delta_y * self.rotate_speed,
                         right[0], right[1], right[2])

        # Move back to world space
        t.Translate(cam_pos[0], cam_pos[1], cam_pos[2])

        # Apply to focal point and view-up
        new_focal = np.array(t.TransformPoint(focal_pt.tolist()))
        new_up    = np.array(t.TransformVector(view_up.tolist()))

        camera.set_focal_point(*new_focal)
        camera.set_view_up(*new_up)

        iren.GetRenderWindow().Render()
        self.StoreRelativeCameraInfo(caller=None, event=None)
