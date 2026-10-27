import math
from dataclasses import dataclass

from vtkmodules.vtkRenderingCore import (
    vtkAssembly,
    vtkActor,
    vtkPolyDataMapper,
)
from vtkmodules.vtkFiltersSources import (
    vtkArrowSource,
    vtkLineSource,
)
from vtkmodules.vtkCommonTransforms import (
    vtkTransform,
)

@dataclass
class AxesData:
    xlen: float
    ylen: float
    zlen: float
    origin: tuple = (0, 0, 0)

class VirgoAxes():
    """
    Creates a set of 3D axes (X, Y, Z arrows) in a way superior to vtkAxesActor
    For information on why this is needed, see this thread:
    https://discourse.vtk.org/t/vtkaxesactor-bounding-box-appears-to-be-affected-by-its-world-position/16290

    This class allows for independent scaling of axis lengths and global scaling
    of all axes

    Original Author: Ethan Moss, edits by Dan Jordan
    """
    def __init__(self, xlen=1.0, ylen=1.0, zlen=1.0):
        self.visible = True
        self.origin = AxesData.origin  
        self.style = "cylinder"
        self._valid_styles = ["cylinder", "line"]
        self.enabled = True
        self.minimum_arrow_length = 0.0001  # Absolute minimum size an arrow can be
        self.axes_assembly = vtkAssembly() 
        self.axes_data = AxesData(xlen=xlen, ylen=ylen, zlen=zlen)
        self.x_arrow = None
        self.y_arrow = None
        self.z_arrow = None

        self._generate_arrows()
    
    def set_minimum_arrow_length(self, value):
        """
        Set the minimum arrow length tolerance.
        """
        if value > 0.0:
            self.minimum_arrow_length = value
        else:
            raise ValueError("VirgoAxes.set_minimum_arrow_length() must be a "
                "non-zero positive number. ")
        
    def show(self):
        """
        Shows the three arrows in the render window.
        """
        self.visible = True
        # TODO, self.axes_assembly.SetVisibility() doesn't work here,
        # not sure why, so turn off the actors individually -Jordan 10/2026
        self.x_arrow.SetVisibility(True)
        self.y_arrow.SetVisibility(True)
        self.z_arrow.SetVisibility(True)
        
    def hide(self):
        """
        Hides the three arrows in the render window.
        """
        self.visible = False
        # TODO, self.axes_assembly.SetVisibility() doesn't work here,
        # not sure why, so turn off the actors individually -Jordan 10/2026
        self.x_arrow.SetVisibility(False)
        self.y_arrow.SetVisibility(False)
        self.z_arrow.SetVisibility(False)

    def _generate_arrows(self):
        """
        Generates the arrow actors for the axes using the information in
        self.axes_data.  Adds each arrow part to the self.axes_assembly
        """
        ox, oy, oz = self.origin

        self.x_arrow = self.create_arrow_actor(
            start_point=[ox,oy,oz], 
            end_point=[ox + self.axes_data.xlen, oy, oz],
            colors=[1,0,0]
            )
        self.y_arrow = self.create_arrow_actor(
            start_point=[ox,oy,oz], 
            end_point=[ox, oy + self.axes_data.ylen, oz],
            colors=[0,1,0]
            )
        self.z_arrow = self.create_arrow_actor(
            start_point=[ox,oy,oz], 
            end_point=[ox, oy, oz + self.axes_data.zlen],
            colors=[0,0,1])
        
        self.axes_assembly.AddPart(self.x_arrow)
        self.axes_assembly.AddPart(self.y_arrow)
        self.axes_assembly.AddPart(self.z_arrow)

    def clear(self):
        """
        Remove x,y,z arrow parts from the self.axes_assembly
        """
        self.axes_assembly.RemovePart(self.x_arrow)
        self.axes_assembly.RemovePart(self.y_arrow)
        self.axes_assembly.RemovePart(self.z_arrow)

    def set_enabled(self, is_enabled):
        """
        Turns the axes visibility on or off.
        """
        self.enabled = is_enabled
        if not self.enabled:
            self.hide()  # Turn off (visibility off)
        else:
            self.show()  # Turn on (visibility on)
    
    def get_assembly(self):
        """
        Calls and returns the axes_assembly.
        """
        return self.axes_assembly

    def get_visibility(self):
        """
        Calls and returns the visibility of the axes.
        """
        return self.visible

    def create_arrow_actor(self, start_point, end_point, colors=(1.0, 1.0, 1.0)):
        """
        Create a vtkActor for a single arrow given the two points in space.
        """
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        dz = end_point[2] - start_point[2]
        
        arrow_length = math.sqrt(dx**2 + dy**2 + dz**2)
        
        # Arrow must be of positive length
        if arrow_length <= 0.0:
            print(f"Warning: arrow_length {arrow_length} too small, setting"
                  f" to fallback value {self.minimum_arrow_length}")
            arrow_length = self.minimum_arrow_length

        # --- MODIFIED: Choose the source based on the style ---
        if self.style == "line":
            source = vtkLineSource()
            # The transform expects a source going from 0 to 1 along X
            source.SetPoint1(0.0, 0.0, 0.0)
            source.SetPoint2(1.0, 0.0, 0.0)
        else:
            source = vtkArrowSource()
            source.SetTipLength(0.35) 
            source.SetTipRadius(0.1)     
            source.SetShaftRadius(0.03)  
            source.SetTipResolution(32)
            source.SetShaftResolution(32)
                
        source.Update()
    
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(source.GetOutputPort())
    
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(colors)
        
        # Make lines a bit thicker so they are easy to see
        if self.style == "line":
            actor.GetProperty().SetLineWidth(3.0)
    
        # Transform the Actor
        transform = vtkTransform()
        transform.Translate(start_point)
    
        nx = dx / arrow_length
        nx = max(-1.0, min(1.0, nx)) 
        
        # Rotate the arrow in 3D space per dx,dy,dz
        if nx == -1.0:
            transform.RotateWXYZ(180, 0, 1, 0)
        elif nx != 1.0:
            axis_y = -dz / arrow_length
            axis_z = dy / arrow_length
            angle_degrees = math.degrees(math.acos(nx))
            transform.RotateWXYZ(angle_degrees, 0, axis_y, axis_z)
    
        # Scale the arrow to its final length
        transform.Scale(arrow_length, arrow_length, arrow_length)
        actor.SetUserTransform(transform)
    
        return actor

    def set_length(self, xlen:float=None, ylen:float=None, zlen:float=None):
        """
        Updates the lengths of the axes and forces VTK to regenerate their.
        geometry.  Any values given as None will not be altered.
        """
        if xlen == None and ylen == None and zlen == None:
            raise ValueError("VirgoAxes.set_length() at least one value must be a "
                f"non-zero positive number greater than {self.minimum_arrow_length}")
        if (xlen and xlen < 0.0) or (ylen and ylen < 0.0) or (zlen and zlen < 0.0):
            raise ValueError("VirgoAxes.set_length() values must be non-zero "
                f"positive numbers greater than {self.minimum_arrow_length}")
        
        if xlen != None:
            self.axes_data.xlen = xlen
        if ylen != None:
            self.axes_data.ylen = ylen
        if zlen != None:
            self.axes_data.zlen = zlen

        self.clear()
        self._generate_arrows()  # Regenerate the arrow geometry

    # --- MODIFIED: Implemented set_style ---
    def set_style(self, style="arrow"):
        """
        Sets the style of the axes.
        Valid options: 'arrow', 'line'
        """
        style = style.lower()
        
        if style not in self._valid_styles:
            print(f"Warning: '{style}' is not a valid style. Using 'arrow'.")
            style = "arrow"
            
        self.style = style
        self.clear()
        self._generate_arrows()  # Regenerate the arrow geometry