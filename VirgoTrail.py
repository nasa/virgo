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

class VirgoTrail:
    """
    Management class for VIRGO trails. Trails are lines drawn where an
    actor has previously been.
    """
    def __init__(self, color=[1.0, 1.0, 1.0], thickness=2, opacity=1.0,
                 layer='foreground'):
        self.color = color          # RGB color of line
        self.thickness = thickness  # thickness of line
        self.opacity = opacity      # Opacity of line
        self.layer = layer          # Rendering layer

        self._trail_points = vtkPoints()
        self._trail_lines = vtkCellArray()
        self._trail_polydata = vtkPolyData()
        self._trail_polydata.SetPoints(self._trail_points)
        self._trail_polydata.SetLines(self._trail_lines)

        self._trail_mapper = vtkPolyDataMapper()
        self._trail_mapper.SetInputData(self._trail_polydata)

        self._trail_actor = vtkActor()
        self._trail_actor.SetMapper(self._trail_mapper)
        self._trail_actor.GetProperty().SetColor(color[0], color[1], color[2])
        self._trail_actor.GetProperty().SetLineWidth(thickness)
        self._trail_actor.GetProperty().SetOpacity(opacity)
        self._trail_actor.PickableOff()

        # Maintain a polyline of visited positions
        self._trail_polyline = vtkPolyLine()
        self._trail_polyline.GetPointIds().SetNumberOfIds(0)  # start empty

    def update(self, world_position):
        """
        Add point and connecting line to the trail using the current actor
        position

        TODO: I wonder if drawing the point in "reverse direction" will
        make the wiggling of the newly drawn segment (assumed to be due
        to single floating point precision issues) less visible
        """
        if not self._trail_points:
            return

        pos = world_position
        pid = self._trail_points.InsertNextPoint(pos[0], pos[1], pos[2])
        self._trail_polyline.GetPointIds().InsertNextId(pid)

        # Update line structure
        self._trail_lines.Reset()
        self._trail_lines.InsertNextCell(self._trail_polyline)

        self._trail_points.Modified()
        self._trail_lines.Modified()
        self._trail_polydata.Modified()

    def get_layer(self):
        return self.layer

    def get_actor(self):
        return self._trail_actor

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

    def pop_front(self):
        """
        Remove the most recent line segment from the trail
        """
        pass

    def pop_back(self):
        """
        Remove the oldest line segment from the trail
        """
        pass