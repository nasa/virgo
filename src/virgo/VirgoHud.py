import math, os, inspect
from .Virgo import VirgoSceneNodeVector
from .VirgoActor import VirgoActor

class VirgoHud:
    """
    Default Heads Up Display showing text around the border of the Virgo
    Window. This class is in charge of positioning text in screen coordinates
    associated with overlays.  This includes information about picked actors,
    world time, playback mode, camera/lighting, etc.
    """
    def __init__(self, render_window, renderers, text_actors,
                 nodes, cameras, color=[1.0, 1.0, 1.0]):
        # References to structures provided by VirgoControlCenter
        self.render_window = render_window
        self.renderers = renderers
        self.text_actors = text_actors
        self.nodes = nodes
        self.cameras = cameras
        self.color = color
        self.set_color(self.color)
        # Will be copied once per configure() call from the calling class
        self.mode = None
        self.node_camera_follows = None
        self.playback_speed = None
        self.picked_actor = None
        self.near_clipping_plane_tolerance = None
        self.world_time = None
        self.max_sim_time = None
        self.picked_actor = None
        self.picker_tolerance = None
        self.lighting_mode = None
        self.help = None
        self.debug = False
        self.version = f"alpha {self.get_version()}"

    def set_color(self, color):
        for ta in self.text_actors:
            self.text_actors[ta].GetTextProperty().SetColor(color[0], color[1], color[2])

    def set_debug(self, value):
        self.debug = value

    def get_debug(self):
        return(self.debug)

    def get_version(self):
        version="UNKNOWN"
        try:
            from . import __version__ as version
        except Exception as e:
            msg = (f"ERROR: Cannot determine VIRGO version\n{e}")
            raise RuntimeError (msg)
        return version

    def configure_picked_info(self, window_width, window_height, hud_padding=20):
        """
        Configure HUD information for the picked actor (lower left)
        """
        actor = self.picked_actor
        if actor:
            if not isinstance(actor, VirgoActor) and not issubclass(actor, VirgoActor):
              msg = (f"ERROR: Expected picked actor: {actor} to be of type "
                f"VirgoActor but got {type(actor)} instead. Cannot render "
                f"picked actor in HUD")
              raise RuntimeError (msg)
            text=""
            parent=""
            node_curr_time=""
            label="Node driven position"
            # TODO: not sure if the distinction between current_position and
            # world_position is clear enough here.
            node = self.nodes[actor.name]
            if not node.is_static():
                node_curr_time=f" @ t={node.data_source.get_current_time()}"
            if node.parent:
                parent = f" (parent: {node.parent.name})"
            pos = node.get_current_position()
            if not pos:
                label="Node world position "
                pos = self.nodes[actor.name].get_world_position()
            if isinstance(node, VirgoSceneNodeVector):
                label="vector tip position "
            name = actor.name
            text+=f"{name}{parent}\n {label}: {pos[0]:<10.5f}, {pos[1]:<10.5f}, {pos[2]:<10.5f} units {node_curr_time}"
            if node.parent:
                label = "Node  local position"
                pos = self.nodes[actor.name].get_local_position()
                text+=f"\n {label}: {pos[0]:<10.5f}, {pos[1]:<10.5f}, {pos[2]:<10.5f} units {node_curr_time}"
                label = "Actor local position"
                pos = actor.GetPosition()
                text+=f"\n {label}: {pos[0]:<10.5f}, {pos[1]:<10.5f}, {pos[2]:<10.5f} units {node_curr_time}"
            self.text_actors['picked'].SetInput(text)
        else:
            self.text_actors['picked'].SetInput("")

    def configure_mode(self, window_width, window_height, hud_padding=20):
        """
        Configure HUD information for the playback mode (upper right)
        """
        top_right=f"{self.mode} {self.playback_speed}X"
        top_right+=f"\nNCPT:{self.near_clipping_plane_tolerance:.2e}"
        top_right+=f"\nPT:  {self.picker_tolerance:.2e}"
        self.text_actors['mode'].SetInput(top_right)
        bounds = [0] * 4 # Get the text bounding box in display coordinates  [xmin, xmax, ymin, ymax]
        self.text_actors['mode'].GetBoundingBox(self.renderers['foreground'], bounds)
        text_width = bounds[1] - bounds[0] + 1  # Width in pixels
        text_height = bounds[3] - bounds[2] + 1  # Height in pixels
        # Calculate position for bottom-right corner with padding
        x_pos = window_width - text_width - hud_padding  # Right edge minus width
        y_pos = window_height - text_height - hud_padding  # Bottom edge (20 pixels from bottom)
        self.text_actors['mode'].SetPosition(x_pos, y_pos)

    def configure_time_lighting_koviz(self, window_width, window_height, hud_padding=20):
        """
        Configure HUD with the time information (upper right)
        """
        # Time
        bounds = [0] * 4
        self.text_actors['time'].GetBoundingBox(self.renderers['foreground'], bounds)
        text_height = bounds[3] - bounds[2] + 1  # Height in pixels
        y_pos = window_height - text_height - hud_padding
        self.text_actors['time'].SetPosition(hud_padding, y_pos)
        if math.isclose(self.max_sim_time, 0.0):
            percent_complete = f"???"
        else:
            percent_complete = f"{self.world_time / (self.max_sim_time - self.min_sim_time) * 100:<4.2f}"
        self.text_actors['time'].SetInput(
            f"World time: {self.world_time:<10.5f} / {self.max_sim_time} sec [{percent_complete} %]"
            )

        # Lighting
        lighting_info = f"Lighting: {self.lighting_mode}" 
        self.text_actors['lighting'].SetInput(f"{lighting_info}")
        bounds_lighting = [0] * 4 # Get the text bounding box in display coordinates  [xmin, xmax, ymin, ymax]
        self.text_actors['lighting'].GetBoundingBox(self.renderers['foreground'], bounds_lighting)
        lighting_text_width = bounds_lighting[1] - bounds_lighting[0] + 1  # Width in pixels
        lighting_text_height = bounds_lighting[3] - bounds_lighting[2] + 1  # Height in pixels
        self.text_actors['lighting'].SetPosition(hud_padding, y_pos-lighting_text_height)

        # koviz
        koviz_info = f"koviz: {self.koviz_status}" 
        self.text_actors['koviz'].SetInput(f"{koviz_info}")
        bounds_koviz = [0] * 4
        self.text_actors['koviz'].GetBoundingBox(self.renderers['foreground'], bounds_koviz)
        koviz_text_width = bounds_koviz[1] - bounds_koviz[0] + 1  # Width in pixels
        koviz_text_height = bounds_koviz[3] - bounds_koviz[2] + 1  # Height in pixels
        self.text_actors['koviz'].SetPosition(hud_padding, y_pos - lighting_text_height - koviz_text_height)

    def configure_camera(self, window_width, window_height, hud_padding=20):
        """
        Configure HUD with camera information (top center right-ish)
        """
        camera_info = f"Camera: {self.camera.get_name()}\n{self.camera_style}"
        camera_info += f", static" if self.camera.is_static() else "" 
        camera_info += f"\nparent: {self.camera.get_parent_name()}"
        self.text_actors['camera'].SetInput(f"{camera_info}")
        # Compute the bounding boxes of the camera and lighting text actors
        bounds_camera = [0] * 4 # Get the text bounding box in display coordinates  [xmin, xmax, ymin, ymax]
        self.text_actors['camera'].GetBoundingBox(self.renderers['foreground'], bounds_camera)
        camera_text_width = bounds_camera[1] - bounds_camera[0] + 1  # Width in pixels
        camera_text_height = bounds_camera[3] - bounds_camera[2] + 1  # Height in pixels
        # Calculate position for bottom-right corner with padding
        camera_x_pos = (window_width - camera_text_width - hud_padding)/1.5  # 2/3ish the way over on right side
        camera_y_pos = window_height - camera_text_height - hud_padding  # Top edge (20 pixels from bottom)
        self.text_actors['camera'].SetPosition(camera_x_pos, camera_y_pos)

        #import pdb; pdb.set_trace()

    def configure_help(self, window_width, window_height, hud_padding=20):
        """
        Configure HUD with help information if self.help is true, (bottom right)
        """
        if self.help == True:
            #self.text_actors['help'].SetDisplayPosition(window_width - 600, 40)
            self.text_actors['help'].SetInput(
                f"\nMOUSE"
                f"\n L-click drag: Rotate"
                f"\n Shift+L-click: Pan"
                f"\n Ctrl+L-click: Roll"
                f"\n Scroll wheel: Dolly In/Out"
                f"\n R-click: Pick Actor"
                f"\n"
                f"\nKEYBOARD"
                f"\n SPACE: Pause/Play"
                f"\n p: Take Picture"
                f"\n s: Cycle playback speeds"
                f"\n t: Toggle trails"
                f"\n <- -> : Step back/forward in time"
                f"\n -  + : Adjust HUD text size"
                f"\n a: Toggle Axes Visibility"
                f"\n d: Toggle debug info in HUD"
                f"\n up/down : Switch cameras"
                f"\n C: Toggle cam trackball/first-person"
                f"\n c: Parent/unparent camera to picked"
                f"\n f: Toggle Camera Frustums"
                f"\n l: Toggle Lighting Mode"
                f"\n L: Toggle Node Label Visibility"
                f"\n v: Print picked node info in terminal"
                f"\n BackSpace: Toggle starfield"
                f"\n h: Toggle this help message"
                f"\n j/k: Near Clipping Plane Tolerance"
                f"\n J/K: Picker Tolerance"
                f"\n `: Toggle Developer console"
                f"\n Q: Quit"
                )
            # Get the text bounding box in display coordinates  [xmin, xmax, ymin, ymax]
            bounds = [0] * 4
            self.text_actors['help'].GetBoundingBox(self.renderers['foreground'], bounds)
            text_width = bounds[1] - bounds[0] + 1  # Width in pixels
            # Calculate position for bottom-right corner with 20-pixel padding
            x_pos = window_width - text_width - hud_padding    # Right edge minus width
            y_pos = hud_padding  # Bottom edge (20 pixels from bottom)
            self.text_actors['help'].SetPosition(x_pos, y_pos)
        else:
            self.text_actors['help'].SetInput("")

    def add_debug_text(self, text):
        """Add renderer and camera info to version text box for debugging"""
        for r in self.renderers:
            clipping_range = self.renderers[r].GetActiveCamera().GetClippingRange()
            num_props = self.renderers[r].GetViewProps().GetNumberOfItems()
            tol = self.renderers[r].GetNearClippingPlaneTolerance()
            text += f"\n{r}:{clipping_range},{tol:E},{num_props}"
        for n in self.nodes:
            if self.nodes[n].parent == None:
                n = self.nodes[n].name
                l = self.nodes[n].get_layer()
                text += f"\n{n}:{l}"
            if self.nodes[n].trail:
                t = self.nodes[n].trail
                aatl = t.get_trail_actors_and_their_layers()
                for a, l in aatl:
                  text += f"\ntrail:{n}:{l}"
        for c in self.cameras:
            n = self.cameras[c].name
            p = self.cameras[c].get_position()
            text += f"\ncam-{n}:{p}"
        return(text)

    def configure_version(self, window_width, window_height, hud_padding=20):
        """
        Configure HUD with version information
        """
        version_text = f"VIRGO {self.version}"

        if self.debug:
            version_text = self.add_debug_text(version_text)

        bounds = [0] * 4 # Get the text bounding box in display coordinates  [xmin, xmax, ymin, ymax]
        self.text_actors['picked'].GetBoundingBox(self.renderers['foreground'], bounds)
        text_height = bounds[3] - bounds[2] + 1  # Height in pixels
        self.text_actors['version'].GetTextProperty().SetColor(0.7, 0.7, 0.7)
        self.text_actors['version'].SetPosition(hud_padding, text_height + hud_padding)
        self.text_actors['version'].SetInput(version_text)

    def configure(self, mode, camera_style, camera, playback_speed,
                  picked_actor, picker_tolerance, world_time, min_sim_time,
                  max_sim_time, near_clipping_plane_tolerance, lighting_mode,
                  koviz_status, help):
        """
        Configure the heads-up-display.  Calls functions for each logical
        section of the HUD. Does not render.

        Parameters passed in are needed to compute info in the HUD
        """
        self.mode = mode
        self.camera_style = camera_style
        self.camera = camera
        self.playback_speed = playback_speed
        self.picked_actor = picked_actor
        self.picker_tolerance = picker_tolerance
        self.near_clipping_plane_tolerance  = near_clipping_plane_tolerance
        self.world_time = world_time
        self.min_sim_time = min_sim_time
        self.max_sim_time = max_sim_time
        self.lighting_mode = lighting_mode
        self.koviz_status = koviz_status
        self.help = help

        ww, wh  = self.render_window.GetSize()
        self.configure_picked_info(window_width=ww, window_height=wh)
        self.configure_mode(window_width=ww, window_height=wh)
        self.configure_time_lighting_koviz(window_width=ww, window_height=wh)
        self.configure_camera(window_width=ww, window_height=wh)
        self.configure_help(window_width=ww, window_height=wh)
        self.configure_version(window_width=ww, window_height=wh)
        
