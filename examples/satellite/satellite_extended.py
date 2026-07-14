#!/usr/bin/env python3
import sys, os, argparse, yaml, inspect
# Add location of VIRGO code to sys.path so we can import classes
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
sys.path.append(os.path.abspath(os.path.join(thisFileDir, '../../')))
# Import the only VIRGO class we need
from VirgoDataPlayback import VirgoDataPlayback
from VirgoHud import VirgoHud
from Virgo import VirgoControlCenter

# These VTK modules are needed to build the crosshair for the custom HUD
from vtkmodules.vtkRenderingCore import (
  vtkCoordinate,
  vtkActor2D,
)
from vtkmodules.vtkCommonCore import (
  vtkPoints,
)
from vtkmodules.vtkCommonDataModel import (
  vtkPolyData,
  vtkCellArray,
  vtkLine
)
from vtkmodules.vtkRenderingCore import (
  vtkPolyDataMapper2D,
)
from vtkmodules.vtkRenderingCore import (
  vtkCoordinate,
  vtkPolyDataMapper2D,
)

parser = argparse.ArgumentParser(description=
        'Visualize the satellite data in log_Satellite.csv using VIRGO.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
parser.add_argument("--scene-config", help="YAML config file to load",
                    default=os.path.join(thisFileDir,'scene.yml'))
parser.add_argument("--data-dir", help="Directory to read the CSV data from",
                    default=thisFileDir)
parser.add_argument("--headless", action="store_true",
                    help="Render to video instead of providing an"
                    " interactive window")
parser.add_argument("--video-filename",
                    help="Filename for headless video when --headless given",
                    default=os.path.join(thisFileDir, 'satellite.mp4'))
args = parser.parse_args()


class MyCustomHud(VirgoHud):
    """
    A class that inherits from the standard VirgoHud but adds capability
    on top. In this example, the HUD renders a crosshair at the center
    of the camera only when 'onboard_cam' is the active camera
    """
    def __init__(self, render_window, renderers, text_actors,
                 nodes, cameras, color=[1.0,1.0,1.0]):
        super().__init__(render_window, renderers, text_actors,
                 nodes, cameras, color=color)
        self.points = vtkPoints()
        self.arm_length = 40  # Length of crosshair arm - pixels center to tip
        self.line_width = 2.0 # Width of crosshair line
        self.crosshair_color = [1.0, 1.0, 1.0]  # White
        self.window_width, self.window_height = self.render_window.GetSize()
        self.crosshair_actor = self.create_crosshair_actor()
        self.renderers['foreground'].AddActor(self.crosshair_actor)
 
    def create_crosshair_actor(self):
        """
        Create a 2D crosshair actor centered in the window.
     
        The crosshair is built from two lines in Display (pixel) coordinates so it
        always sits on top of any 3D scene and never gets projected/clipped.
     
        Returns:
            vtkActor2D ready to be added to a renderer.
        """
        cx = self.window_width  // 2   # centre x in display coords
        cy = self.window_height // 2   # centre y in display coords
     
        # ── Geometry ──────────────────────────────────────────────────────────────
        # Horizontal arm
        self.points.InsertNextPoint(cx - self.arm_length, cy, 0)  # 0 – left
        self.points.InsertNextPoint(cx + self.arm_length, cy, 0)  # 1 – right
        # Vertical arm
        self.points.InsertNextPoint(cx, cy - self.arm_length, 0)  # 2 – bottom
        self.points.InsertNextPoint(cx, cy + self.arm_length, 0)  # 3 – top
     
        lines = vtkCellArray()
        for (a, b) in [(0, 1), (2, 3)]:
            line = vtkLine()
            line.GetPointIds().SetId(0, a)
            line.GetPointIds().SetId(1, b)
            lines.InsertNextCell(line)
     
        polydata = vtkPolyData()
        polydata.SetPoints(self.points)
        polydata.SetLines(lines)
     
        # ── Coordinate system: Display (pixel) coords ──────────────────────────
        # vtkCoordinate with DISPLAY system maps point values directly to pixels.
        coord = vtkCoordinate()
        coord.SetCoordinateSystemToDisplay()
     
        # ── Mapper ────────────────────────────────────────────────────────────────
        mapper = vtkPolyDataMapper2D()
        mapper.SetInputData(polydata)
        mapper.SetTransformCoordinate(coord)   # tell the mapper to use pixel coords
     
        # ── Actor ─────────────────────────────────────────────────────────────────
        actor = vtkActor2D()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(self.crosshair_color)   # bright green
        actor.GetProperty().SetLineWidth(self.line_width)
     
        return actor


    def configure(self, mode, camera_style, camera, playback_speed,
                  picked_actor, picker_tolerance, world_time, min_sim_time,
                  max_sim_time, near_clipping_plane_tolerance, lighting_mode,
                  koviz_status, help):
        """
        The main update loop for the HUD which is called automatically from the
        underlying VIRGO framework. Calls the base class configure() function
        which populates the info in the corners, then positions the crosshair in
        the center of the render window
        """
        super().configure(mode, camera_style, camera, playback_speed,
                  picked_actor, picker_tolerance, world_time, min_sim_time,
                  max_sim_time, near_clipping_plane_tolerance, lighting_mode,
                  koviz_status, help)
        if camera.get_name() == 'onboard_cam':
            self.enable_crosshair()
            self.reposition_crosshair()
        else:
            self.disable_crosshair()


    def disable_crosshair(self):
        """Turn the crosshair off"""
        self.crosshair_actor.SetVisibility(0)

    def enable_crosshair(self):
        """Turn the crosshair on"""
        self.crosshair_actor.SetVisibility(1)

    def reposition_crosshair(self):
        """
        Move the crosshair to the new window centre by updating the four
        existing points in-place, then marking the vtkPoints as modified so
        VTK knows to re-render with the new coordinates.
        """
        # Get the updated window width/height
        self.window_width, self.window_height = self.render_window.GetSize()

        cx = self.window_width  // 2
        cy = self.window_height // 2
     
        self.points.SetPoint(0, cx - self.arm_length, cy, 0)  # left
        self.points.SetPoint(1, cx + self.arm_length, cy, 0)  # right
        self.points.SetPoint(2, cx, cy - self.arm_length, 0)  # bottom
        self.points.SetPoint(3, cx, cy + self.arm_length, 0)  # top
     
        # Tell the pipeline the data has changed so it re-renders correctly.
        self.points.Modified()


class MyCustomControlCenter(VirgoControlCenter):
    """
    Derived class extending the VirgoControlCenter class. This provides
    an example of how to extend the controller mechanism of VIRGO to
    implement custom functionality. In this case, the custom functionality
    is adding a custom HUD by calling the base class initialize_hud() with
    a custom class definition: MyCustomHud
    """
    def __init__(self, renderers, render_window, interactor, scene,
                world_time=0.0, images_dir=None, koviz_port=64054):
        super().__init__(renderers=renderers, render_window=render_window,
                         interactor=interactor, scene=scene)

    def initialize_hud(self):
        super().initialize_hud(_class=MyCustomHud)



class CustomizedDataPlayback(VirgoDataPlayback):
    """
    Extend the VirgoDataPlayback base class to allow the override of the default
    self.controller. Note that although self.controller is set in
    VirgoDataPlayback's base class VirgoScene.__init__(), it's reassigned to a
    custom controller (MyCustomControlCenter) defined in this file.
    """
    # Tell the VirgoScene to use a custom class for the self.controller
    # See VirgoScene.controller_class for details
    controller_class = MyCustomControlCenter
    def __init__(self, run_dir, scene, verbosity=1, headless=False,
                 images_dir="/tmp/", video_filename="/tmp/virgo.mp4", splash=True):

        super().__init__(run_dir=run_dir, scene=scene, verbosity=verbosity,
                         headless=headless, images_dir=images_dir,
                         video_filename=video_filename, splash=splash)

class SatelliteCustomHudExample:
    """
    The entrypoint class for the user of this script. Creates a
    CustomizedDataPlayback instance and starts it up.
    """
    def __init__(self):
        with open(args.scene_config) as file:
            scene = yaml.safe_load(file) 
        # VirgoDataPlayback is the VirgoScene we want because it's built
        # to consume TrickPy-compatible data, which log_Satellite.csv meets
        self.v = CustomizedDataPlayback(run_dir=args.data_dir, scene=scene,
                                    headless=args.headless,
                                    video_filename=args.video_filename)
        self.v.initialize()
        # The moon isn't driven by data, so let's rotate it to face
        # the earth the "correct way"
        self.v.nodes['moon'].set_pose(ypr=[180, 0, 0])

    def execute(self):
        # Start the Virgo 3D scene
        return(self.v.run())

if __name__ == '__main__':
    sys.exit(SatelliteCustomHudExample().execute())
