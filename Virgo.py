#!/usr/bin/env python3
"""
VIRGO: Versatile Imaging and Rendering for Galactic Operations
A Practical, Analytical, and Hardworking 3D Visualization tool
leveraging python-VTK
"""
from VirgoInteractorStyles import (
  VirgoTrackballInteractorStyle,
  VirgoInteractorStyleFirstPerson
)
from VirgoActor import VirgoActor
from VirgoNode import VirgoSceneNode, VirgoSceneNodeVector
from VirgoSplash import VirgoSplash
from VirgoHud import VirgoHud
from VirgoConsole import VirgoConsole
from VirgoUtils import cprint, timed_debug, time_render_layers
from VirgoRendering import VirgoRendering
from VirgoCamera import VirgoCamera
from VirgoKovizInterface import KovizInterface

import os, sys, inspect, time, tempfile
import math, textwrap
import numpy as np
from typing import Type, Optional, Dict, Any

# --- Modular VTK Imports (Replaces 'import vtk') ---
from vtkmodules.vtkRenderingCore import (
  vtkActor,
  vtkTexture,
  vtkCellPicker,
  vtkInteractorStyle,
  vtkLight,
  vtkPolyDataMapper,
  vtkRenderer,
  vtkRenderWindow,
  vtkRenderWindowInteractor,
  vtkTextActor,
  vtkSkybox,
  vtkWindowToImageFilter,
)
from vtkmodules.vtkInteractionStyle import (
  vtkInteractorStyleTrackballCamera,
)
from vtkmodules.vtkFiltersSources import (
  vtkSphereSource,
)
from vtkmodules.vtkIOImage import (
  vtkJPEGReader,
  vtkPNGWriter,
)
from vtkmodules.vtkRenderingOpenGL2 import (
  vtkCameraPass,
  vtkOverlayPass,
  vtkRenderPassCollection,
  vtkSequencePass,
  vtkShadowMapPass,
  vtkTranslucentPass,
)
from vtkmodules.vtkCommonCore import (
  vtkCommand,
)
# ---------------------------------------------------

thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))

def virgo_console(func: callable) -> callable:
    """
    Define the "console accessible function" decorator. When applied to a function
    in the VirgoControlCenter below, (via @virgo_console above the function
    definition) it can be called by the user directly from the Virgo console,
    neat!
    """
    func.is_console_command = True  # marker attribute
    return func

class VirgoControlCenter:
    """
    The main control center class for Virgo playback which provides the main
    rendering loop, including features:
      World time: Authoritative scene time
      Navigation: Play/Pause and stepping forward/backward through time and
        playback speed
      Camera: Configuration and node-following capability
      HUD: Heads-up display text bordering the scene
      Picking: The ability to click on objects in the scene to get more info
        about them
      Console: Press ` to open the developer console
    """
    # The order of these are important, must list them back to front
    def __init__(self, renderers, render_window, interactor, scene,
                 world_time=0.0, images_dir=None, koviz_port=64053):
        """
        Initializer of the VirgoControlCenter
        """
        self.huge = 1.0e30   # A huge floating point number used for finding smallest values
        # Current scene world time (not necessarily aligned with sim data time)
        self.world_time = self.world_time_start = world_time 
        self.timeless = False  # Flag for a scene where time doesn't exist
        self.force_node_update = False     # If true, force node update even when paused
        self.wallclock_time = time.time()  # Actual wall clock time in real life
        self.max_sim_time = 0.0            # highest sim time across all dr groups
        self.min_sim_time = self.huge      # lowest  sim time across all dr groups
        self.images_dir = images_dir       # Where pictures go when taken
        if images_dir == None:
            self.images_dir = os.path.expanduser("~/Desktop")
        self.koviz_interface = KovizInterface(port=koviz_port)
        self.mode = 'PLAYING'              # 'PAUSED' or 'PLAYING'
        self.fs = 14      # font size
        self.renderers = renderers
        self.render_window = render_window
        self.cameras = {}
        # Add the cameras from each rendering layer
        for r in self.renderers:
            self.cameras[r] = VirgoCamera(name=r, frustum_when='never')
            self.cameras[r].set_vtk_camera(renderers[r].GetActiveCamera())
            self.cameras[r].store_clipping_range()
        #import pdb; pdb.set_trace()
        self.interactor = interactor
        self.cam_sync_observer_tag = None
        # These interactor above this line will use one of the two styles
        # on the following lines
        self.trackball_style = None  # Trackball interactor instance
        self.first_person_style = None          # First person interactor instance
        self.scene = scene
        self.skybox = self.create_skybox()
        self.actors = {}
        self.vectors={}
        self.frames={}
        self.trails = {}
        self.text_actors={}

        self.help = False  # Display help message when true
        self.picker = vtkCellPicker()
        self.interactor.SetPicker(self.picker)
        self.picked_actor      = None # Currently picked actor or None if not
        self.near_clipping_plane_tolerance = 1e-5
        self.picker_tolerance = 5e-7
        self.last_picked_actor = None
        self.original_colors = {}  # Store original colors for actors

        # TODO: do we need to check this is smaller than minimum delta t in logged data?
        self.callback_rate = 50 # Frame rate for timer callback (millisec)
        # self.dt: Increment time by this amount every timer update (sec)
        self.default_dt = self.dt = self.callback_rate / 1000.0
        self.frame_rate = 1/self.dt
        self.playback_speed = 1.0  # Speed of playback
        # Default playback speeds
        self.available_speeds = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]
        self._initialized = False
        self.sun_light = None   # vtkLight source of the sun
        self.sun_actor = None   # Sphere used to represent sun in the distance
        self.sun_direction = [1.0, 0.0, 0.0]  # Default world vector pointing towards sun
        self.sun_distance = None   # Actual distance to place sun away from camera
        self.sun_driven_by = None  # Node sun vector is driven by
        self.lighting_mode = 'headlight'  # Default lighting mode of the scene
        self.bright_ambient = 0.7  # Default ambient light on all nodes in 'ultrabright'
        self.dark_ambient = 0.1    # Default ambient light on all nodes in 'realistic'
        self.camera_pass = None    # Used for rendering in 'realistic' lighting mode
        self.verbosity = 1
        self.hud = None
        self._labels_toggle = 'on' # Internal flag for tracking labels toggle with 'L'
        self.virgo_console = None
        self.nodes = {}            # Dict of all nodes in the scene
        self.root_nodes = {}       # Dict of all root nodes in the scene (no parent)
        # Distance away from camera where foreground and midground layers end
        self.foreground_far_boundary = 1e5
        self.midground_far_boundary = 1e8
        # Bias/scale factor for celestial objects entering the foreground
        self.celestial_foreground_bias = 1e-2
        # Internal flag for user toggling axes on/off. This is separate from the
        # internal node flags
        self.axes_are_toggled = False

    def set_far_boundary(self, layer, distance):
        if layer == 'foreground':
            self.foreground_far_boundary = distance
        elif layer == 'midground':
            self.midground_far_boundary = distance

    def initialize(self):
        """
        Set up the scene by:
          * Adding all actors to the renderer
          * Adding all renderers to the render window
          * Initializing the cameras
          * Setting skybox, playback speed, and other configurations
          * Initialize lighting
          * Initialize the virgo console
        """
        if not self.actors:
          msg = (f"ERROR: No actors found in {__class__} initialize() function. ")
          raise RuntimeError (msg)

        self.initialize_images_dir()
        self.add_renderers_to_render_window()
        self._determine_max_and_min_sim_time()
        self.init_renderer_options()
        self.initialize_nodes()
        self.initialize_trails()
        self.initialize_text_actors()
        self.initialize_scene_settings()
        self.init_lighting()
        self.initialize_cameras()
        self.add_actors_to_renderers()
        self.init_picker()
        self.initialize_console()
        self.configure_renderers()
        self._initialized = True
        self.render()

    def add_renderers_to_render_window(self):
        """
        Add all renderers to the render window
        """
        for r in self.renderers:
          self.render_window.AddRenderer(self.renderers[r])

    def initialize_images_dir(self):
        """
        Ensure self.images_dir exists, creating it if necessary
        """
        if not os.path.exists(self.images_dir):
          try:
            os.makedirs(self.images_dir, exist_ok=True)
          except Exception as e:
            print("ERROR: Unable to create {self.images_dir}:\n{e}\ntaking "
                  "pictures will not work.")


    def initialize_text_actors(self):
        """
        Create the HUD text actors
        """
        self.text_actors['mode'] = self.create_overlay_text_actor()
        self.text_actors['picked'] = self.create_overlay_text_actor(pos=[10,10])
        self.text_actors['time'] = self.create_overlay_text_actor()
        self.text_actors['help'] = self.create_overlay_text_actor()
        self.text_actors['camera'] = self.create_overlay_text_actor()
        self.text_actors['lighting'] = self.create_overlay_text_actor()
        self.text_actors['koviz'] = self.create_overlay_text_actor()
        self.text_actors['version'] = self.create_overlay_text_actor()

    def initialize_scene_settings(self):
        """
        Read scene settings from the scene dict and apply them by assigning
        internal members
        """
        # TODO these options also need to go in the verifier
        if 'start_mode' in self.scene:
            self.mode = self.scene['start_mode'] # Set start mode
        if 'starfield' in self.scene:
            self.skybox.SetVisibility(bool(self.scene['starfield']))
        if 'playback_speeds' in self.scene:
            self.available_speeds = self.scene['playback_speeds']
        if 'playback_speed' in self.scene:
            # TODO verify self.playback_speed is in self.available_speeds
            self.playback_speed = self.scene['playback_speed']
            self.dt = self.dt * self.playback_speed
        if 'pick' in self.scene and self.scene['pick'] in self.actors:
            self.picked_actor = self.actors[self.scene['pick']]
            self.nodes[self.picked_actor.name].highlight_on()
            self.nodes[self.picked_actor.name].set_currently_picked(True)
            self.last_picked_actor = self.picked_actor

    def add_actors_to_renderers(self):
        """
        TODO the scope of this needs updating as most of this logic has moved
        into the configure_renderers() function. We may choose to make the sun
        dynamic as well and then change this to add_HUD_actors_to_foreground, or
        have the VirgoHud class do it -Jordan 2026
        """
        self.root_nodes = self.get_root_nodes()
        for rn in self.root_nodes:
            layer = self.root_nodes[rn].get_layer()
            self.renderers[layer].AddActor(self.root_nodes[rn].assembly)
        user_facing_cams = self.get_user_facing_cameras()
        for c in user_facing_cams:
            fa = user_facing_cams[c].get_frustum_assembly()
            if fa:
                self.renderers['foreground'].AddActor(fa)
        # Add all HUD actors to the scene
        for t in self.text_actors:
            self.renderers['foreground'].AddActor(self.text_actors[t])
        # Add the sun actor to the scene
        if self.sun_actor:
            self.renderers['sun'].AddActor(self.sun_actor)

    def initialize_console(self, _class=VirgoConsole):
        """
        Create the virgo developer console which operates in the console layer
        """
        self.virgo_console = _class(renderer=self.renderers['foreground'],
                                          interactor=self.interactor,
                                          vcc=self, font_size=self.fs)

    def initialize_hud(self, _class=VirgoHud):
        hud_color = [1.0, 1.0, 1.0]
        if 'hud_color' in self.scene and self.scene['hud_color'] != None:
            hud_color = self.scene['hud_color']
        self.hud = _class(self.render_window, self.renderers,
                          self.text_actors, self.nodes,
                          self.cameras, color=hud_color)

    def _determine_max_and_min_sim_time(self):
        """
        Store off the highest simulation time known across all non-static
        nodes/actors.
        """
        non_static_nodes = []
        for n in self.nodes:
            # Skip any static actors because they never move
            if self.nodes[n].is_static():
                continue
            non_static_nodes.append(n)

        if len(non_static_nodes) == 0:
            print("Warning: all found nodes are static so the play/pause is disabled")
            self.timeless = True

        for n in non_static_nodes:
            last_time_for_actor = self.nodes[n].data_source.get_last_time()
            first_time_for_actor = self.nodes[n].data_source.get_first_time()
            if last_time_for_actor > self.max_sim_time:
                self.max_sim_time = last_time_for_actor
            if first_time_for_actor < self.min_sim_time:
                self.min_sim_time = first_time_for_actor

    def is_initialized(self):
        return self._initialized

    def get_verbosity(self):
        return self.verbosity

    def set_verbosity(self, value):
        if not isinstance(value, int):
            print("ERROR: verbosity must be an integer")
        else:
            self.verbosity = value

    def set_actors(self, actors_dict):
        self.actors = actors_dict

    def set_nodes(self, nodes_dict):
        self.nodes = nodes_dict

    def set_vectors(self, vectors_dict):
        self.vectors = vectors_dict

    def set_frames(self, frames_dict):
        self.frames = frames_dict

    def set_trails(self, trail_actors_dict):
        self.trails = trail_actors_dict

    def create_overlay_text_actor(self, pos=[0, 0]):
        """
        Create a text actor in the virgo default style, with optional
        screen position pos given
        """
        text = vtkTextActor()
        text.GetTextProperty().SetFontFamilyToCourier()
        text.GetTextProperty().SetFontSize(self.fs)
        text.GetTextProperty().SetColor(1, 1, 1)
        text.SetDisplayPosition(pos[0], pos[1])
        return text

    def initialize_nodes(self):
        """
        Run initialize() on all nodes. This is meant to be called when the
        VirgoControlCenter first starts
        """
        for n in self.nodes:
            self.nodes[n].initialize(self.world_time)

    def initialize_trails(self):
        """
        Set values specified by user in the Trail instances
        VirgoControlCenter first starts
        """
        for t in self.trails:
            self.trails[t].set_far_boundary('foreground', self.foreground_far_boundary)
            self.trails[t].set_far_boundary('midground', self.midground_far_boundary)

    def update_nodes(self):
        '''
        Call update() on all nodes in the scene

        Moves nodes/actors into their positions/orientiations associated
        with world_time
        '''
        for n in self.nodes:
            self.nodes[n].update(self.world_time)

    @virgo_console
    def reset_trails(self):
        '''
        Reset all actor trails to no points, no lines

        TODO: when calling this function followed by step(), the trail line
        isn't drawn. We need to set the first point of the line after clearing
        the trail to the last point before clearing the trail... I think. -
        Jordan
        '''
        for n in self.nodes:
            self.nodes[n].reset_trail()

    def update(self):
        """
        The main scene & node update & play/pause control system called
        from the timer callback loop. Updates everything in the scene then
        renders
        """
        if self.mode == 'PLAYING':
          if math.isclose(self.world_time, self.world_time_start):
             self.reset_trails()
          if self.world_time <= self.max_sim_time:
            self.world_time += self.dt
            self.update_scene()
          else:
             if 'end_mode' in self.scene and self.scene['end_mode'] == 'PAUSED':
               self.mode = 'PAUSED'
               self.world_time = self.max_sim_time
             else:
               self.world_time = self.world_time_start
               
        # In some cases we want to update the scene nodes while not playing
        # like if the user manually sets the world time to a new time
        if self.force_node_update:
            self.update_scene()

        self.update_cameras()
        self.configure_renderers()
        self.configure_hud()

        # If we forced an update, deactivate it
        if self.force_node_update:
            self.force_node_update = False
        # The end of the main update loop, render the image
        self.render(time_each_layer=False)

    #@timed_debug()
    def render(self, time_each_layer=False):
        if time_each_layer == False:
            self.render_window.Render()
            #import pdb; pdb.set_trace()
            return
        time_render_layers(self.render_window, self.renderers)

    def remove_all_root_nodes_from_renderers(self):
        root_nodes = self.get_root_nodes()
        for node_name in root_nodes:
            node = root_nodes[node_name]
            layer = node.get_layer()
            if layer == None:
                continue
            self.renderers[layer].RemoveActor(node.assembly)

    def remove_all_root_labels_from_renderers(self):
        for node in self.nodes:
          for label in self.nodes[node].labels:
            if self.nodes[node].labels[label].get_faces_camera() == True:
                layer = self.nodes[node].get_layer()
                if layer == None:
                    continue
                follower = self.nodes[node].labels[label].get_follower()
                #print(f"Removing {node}'s {label} from rendering layer {l}")
                self.renderers[layer].RemoveActor(follower)

    def remove_all_trails_from_renderers(self):
        for a in self.trails:
            for actor, layer in self.trails[a].get_trail_actors_and_their_layers():
                if layer == None or actor == None:
                    continue
                self.renderers[layer].RemoveActor(actor)

    def get_distance_to_node(self, camera_pos, node):
        """
        Get the distance between the camera position camera_pos and the node
        location. If the node is a celestial body, return the estimated distance
        to the front surface of that body, otherwise return the distance to the
        center of node

        TODO: Note this logic uses the bounding box of the celestial body so
        the less spherical the object is the less likely this algorithm is
        to perform as desired.
        """
        # Get assembly position (cheapest approach)
        world_pos = np.array(node.get_world_position())
        distance = 0.0
        if node.is_celestial_body:
            #import pdb; pdb.set_trace()
            distance = np.linalg.norm(camera_pos - world_pos)
            # Assumption: celestial bodies are close to spherical,
            # divide the longest distance by 2.0 to get radius
            distance = distance - (node.bb_longest_length/2.0)
            # Never allow a negative distance by limiting to zero
            if distance < 0:
                distance = 0
        else:
            distance = np.linalg.norm(camera_pos - world_pos)
            #print(f"DEBUG: Camera distance to {node.name}: {distance}")
            #print(f"           cam pos {camera_pos}:")
            #print(f"         world pos {world_pos}:")
            #print(f"  bb_longest_length/2: {(node.bb_longest_length/2.0)}:")
            #print(f"         node: is celestial {node.is_celestial_body}:")
        return(distance)

    #@timed_debug()
    def configure_renderers(self):
        """
        Manage the nodes and rendering layers their actors reside within. This
        helps prevent z-fighting and issues with clipping ranges reaching across
        the single precision depth buffer by moving nodes's actors that are further
        away from the camera into further away layers. Remember layers are
        rendered back to front.
        """
        self.root_nodes = self.get_root_nodes()
        #print(f"  root_nodes: {self.root_nodes}")
        
        # Get the foreground camera position (all cameras share this position)
        main_vtk_camera = self.get_active_vtk_camera()
        main_camera = self.get_active_camera()
        camera_pos = np.array(main_vtk_camera.GetPosition())
        #print(f"  camera_pos: {camera_pos}")
        
        # Calculate distances for all root nodes
        root_node_distances = []
        for node_name, node in self.root_nodes.items():
            assembly = node.assembly
            
            # Calculate distance from camera to node
            distance = self.get_distance_to_node(camera_pos, node)
            root_node_distances.append({
                'name': node_name,
                'node': node,
                'assembly': assembly,
                'distance': distance
            })
        
        # Sort nodes by distance
        root_node_distances.sort(key=lambda x: x['distance'])
        
        self.remove_all_root_labels_from_renderers()
        self.remove_all_trails_from_renderers()
        
        # Assign assemblies to appropriate layers based on distance
        for nd in root_node_distances:
            distance = nd['distance']
            assembly = nd['assembly']
            current_layer = nd['node'].get_layer()
            optimal_layer = self.get_optimal_layer(distance,
                is_celestial=nd['node'].is_celestial_body)
            if current_layer != optimal_layer:
                self.renderers[current_layer].RemoveActor(assembly)
                self.renderers[optimal_layer].AddActor(assembly)
                nd['node'].set_layer(optimal_layer)
        
        # Add all root labels (labels not parented to a node) to their
        # node's layer
        for node in self.nodes:
          for label in self.nodes[node].labels:
            if self.nodes[node].labels[label].get_faces_camera() == True:
                l = self.nodes[node].get_layer()
                follower = self.nodes[node].labels[label].get_follower()
                #print(f"Adding {node}'s {label} to rendering layer {l}")
                self.renderers[l].AddActor(follower)
                follower.SetCamera(self.renderers[l].GetActiveCamera())

        # Tell each trail to optimize which layer their points exist in
        for a in self.trails:
            self.trails[a].configure_layers(main_camera.get_position())
        # Add all trails to their respective layers
        for a in self.trails:
            aatl = self.trails[a].get_trail_actors_and_their_layers()
            for actor, layer in aatl:
                if layer == None or actor == None:
                    continue
                #print(f"DEBUG: adding trail actor {self.trails[a].node.name} to {layer}")
                self.renderers[layer].AddActor(actor)

        # Set the silhoutte polydata to use camera from it's node's layer
        for n in self.nodes:
            l = self.nodes[node].get_layer()
            sp = self.nodes[n].silhouette_polydata 
            if sp != None:
                sp.SetCamera(self.cameras[l].get_vtk_camera())

        # Remove any camera frustums that are too far away. Here we assume
        # frustums can only live in the foreground layer
        ufc = self.get_user_facing_cameras()
        for c in ufc:
            this_cam_pos = ufc[c].get_position()
            fa = ufc[c].get_frustum_assembly()
            distance = np.linalg.norm(camera_pos - this_cam_pos)
            #import pdb; pdb.set_trace()
            if distance > self.foreground_far_boundary:
                self.renderers['foreground'].RemoveActor(fa)
            else:
                if not self.renderers['foreground'].GetActors().IsItemPresent(fa):
                    self.renderers['foreground'].AddActor(fa)

        self.configure_camera_clipping_ranges()

        # This saves significant computational time since we use transparent
        # layers, each layer has a significant cost
        for layer_name, renderer in self.renderers.items():
            num_actors = renderer.GetViewProps().GetNumberOfItems()
            renderer.SetDraw(num_actors > 0)  # Only draw if there are actors
            #if self.verbosity > 3:
            #print(f"  layer {layer_name} has {num_actors} view props"
            #          f" and GetDraw() is {renderer.GetDraw()}")

    def configure_camera_clipping_ranges(self):
        # HACK: when axes are visible the bounding boxes are incorrectly defined
        # and resetting the camera clipping range will pull the close clipping range
        # so far away the followed actor is not visible. This works around the core
        # issue which is described in detail here:
        # https://discourse.vtk.org/t/vtkaxesactor-bounding-box-appears-to-be-affected-by-its-world-position/16290 
        # See also on_clipping_reset() which works with this function
        if not self.axes_are_toggled:
            # Have each renderer decide the clipping range of the props in their layer
            self.adjust_camera_clipping_ranges()
            # Store off the clipping range when axes aren't visible so we can use them when they are
            for layer in self.cameras:
                self.cameras[layer].store_clipping_range()

    def adjust_camera_clipping_ranges(self, obj=None, event=None):
        """
        Adjust the foreground, midground, and background camera clipping ranges.
        Automatic ranges are used except for the case when the camera is very
        close to a celestial body that it enters the foreground. In this case
        the foreground ranges are adjusted to bias objects in the close range
        over the far range.

        Note: this function is called very frequently so computational speed
        should be considered high priority
        """
        # HACK: when axes are visible the bounding boxes are incorrectly defined
        # and resetting the camera clipping range will pull the close clipping range
        # so far away the followed actor is not visible. This works around the core
        # issue which is described in detail here:
        # https://discourse.vtk.org/t/vtkaxesactor-bounding-box-appears-to-be-affected-by-its-world-position/16290 
        # See also configure_camera_clipping_ranges() 
        if self.are_any_axes_visible():
            for layer in self.cameras:
                self.cameras[layer].restore_clipping_range()
            return

        self.renderers['foreground'].ResetCameraClippingRange() 
        main_camera = self.get_active_camera()
        if self.is_any_celestial_node_in_foreground():
            # TODO this bias ratio should maybe be tunable, this was picked
            # based on what "looks right" in entry.py near end of sim -Jordan feb 2025
            bias = 100
            close, far = main_camera.get_clipping_range()
            main_camera.set_clipping_range(close/bias, far/bias)
            #print(f"BIAS CLIPPING ACTIVE, was {close}, {far}", file=sys.stderr)
        self.renderers['midground'].ResetCameraClippingRange() 
        self.renderers['background'].ResetCameraClippingRange() 

    def is_any_celestial_node_in_foreground(self):
        """
        Returns true if any celestial nodes are in the foreground layer
        """
        for node in self.nodes:
            if (self.nodes[node].is_celestial_body and 
                self.nodes[node].get_layer() == 'foreground'):
                return True
        return False

    def get_optimal_layer(self, distance, is_celestial=False):
        """
        Return the optimal layer associated with the distance (from camera)
        given.

        If the distance we are measuring is to a celestial object, apply the
        self.celestial_foreground_bias to make it much harder for objects to
        enter the foreground. Ex: we don't want earth entering the foreground
        until we're very close otherwise it obscures the other objects in the
        scene
        """
        fg_boundary = self.foreground_far_boundary
        if is_celestial: 
            fg_boundary = fg_boundary * self.celestial_foreground_bias
        if distance < fg_boundary:
            return 'foreground'
        elif distance < self.midground_far_boundary:
            return 'midground'
        else:
            return 'background'

    def update_scene(self):
        """
        Update all nodes, update the cameras update
        the sun and it's light.
        """
        self.update_nodes()                      # move nodes
        self.position_sun_light()                # Move sun light
        self.position_sun_actor(None, None)      # Move sun sphere

    def update_cameras(self):
        """
        Call update on all user facing cameras. This positions cameras
        that are parented to nodes and updates other camera-specific
        internals
        """
        ufc = self.get_user_facing_cameras()
        width, height = self.render_window.GetSize()
        for camera in ufc:
            ufc[camera].update(window_width=width, window_height=height)

    def configure_hud(self):
        """
        Interface function to the self.hud object's configure() function
        """
        intstyle = self.interactor.GetInteractorStyle()
        camera_style = 'trackball' if intstyle == self.trackball_style else 'first-person'
        self.hud.configure(mode=self.mode, camera_style=camera_style,
                           camera=self.get_active_camera(),
                           playback_speed=self.playback_speed,
                           picked_actor=self.picked_actor, picker_tolerance=self.picker_tolerance,
                           world_time=self.world_time, min_sim_time=self.min_sim_time,
                           max_sim_time=self.max_sim_time, 
                           near_clipping_plane_tolerance=self.near_clipping_plane_tolerance,
                           lighting_mode=self.lighting_mode,
                           koviz_status=self.koviz_interface.get_state(),
                           help=self.help)

    def on_timer(self, caller, event):
        """
        Main callback for executing the scene update loop. 
        
        1. Sync with koviz and if commanded to go to a particular time,
           set the time in VIRGO to that time.
        2. Enter the normal update loop for the scene which will self-manage
           time if koviz has no time information.
        3. Attempt to send time back to koviz

        Note that if koviz never connects, the koviz logic does nothing.
        """
        self.wallclock_time = time.time()  # Actual wall clock time in real life
        go_to_time = self.koviz_interface.update()
        if go_to_time:
            self.set_time(self.clamp_world_time(go_to_time))
        self.update()
        self.koviz_interface.send_time(self.world_time)

        time_one_frame_took = time.time() - self.wallclock_time
        if time_one_frame_took > self.dt:
            print(f"WARNING: Frame took {time_one_frame_took} sec to complete which is "
                  f"larger than self.dt ({self.dt}). Playback rate may not be accurate")

    def clamp_world_time(self, intime):
        """
        Clamp intime to the valid min/max range of simulation/world time

        Returns a float between self.min_sim_time and self.max_time (inclusive),
            or None if intime is None
        """
        if intime == None:
            return intime
        return(max(self.min_sim_time, min(self.max_sim_time, intime)))

    def pick_this_layer(self, click_pos, layer):
        """
        Perform a pick at click_pos position in given rendering layer
        Returns the picked VirgoActor or None if nothing picked
        """
        self.picker.Pick(click_pos[0], click_pos[1], 0, self.renderers[layer])
        return(self.get_actor_from_picker())

    def pick_all_layers(self, click_pos):
        for layer in ['foreground', 'midground', 'background']:
            picked = self.pick_this_layer(click_pos=click_pos, layer=layer)
            if picked:
                break
        return(picked)

    def on_right_click(self, obj, event):
        """
        Callback for right click actions. This currently provides "picking",
        assigning self.picked_actor to the actor the mouse clicked on,
        highlighting it with a silhoutte outline in the scene, and displaying
        information about it in the HUD
        """
        click_pos = self.interactor.GetEventPosition()
        self.picked_actor = self.pick_all_layers(click_pos)

        # TODO: under what conditions would self.picked_actor NOT be in self.actors?
        if self.picked_actor and self.picked_actor in self.actors.values():
            self.configure_hud()
        if self.last_picked_actor:
            self.nodes[self.last_picked_actor.name].highlight_off()
            self.nodes[self.last_picked_actor.name].set_currently_picked(False)

        if self.picked_actor:
            self.nodes[self.picked_actor.name].highlight_on()
            self.nodes[self.picked_actor.name].set_currently_picked(True)
            # Un-highlight color of the previously picked actor
            if self.last_picked_actor and self.last_picked_actor != self.picked_actor:
                self.nodes[self.last_picked_actor.name].highlight_off()
            
            # Update last picked actor
            self.last_picked_actor = self.picked_actor
            
        self.render()

    def get_root_nodes(self):
        """
        Return a dict of only root nodes in the scene
        """
        root_nodes = {}
        for node in self.nodes:
            if self.nodes[node].parent == None:
                root_nodes[self.nodes[node].name] = self.nodes[node]
        return root_nodes

    def get_actor_from_picker(self):
        """
        Return the picked vtkActor if any, using vtkAssemblyPath inspection.
        Note this currently uses the more computationally intensive
          self.picker = vtkCellPicker()
        But this was the only picker approach I could get to work with the
        vtkAssembly configuration we are using.
        """
        actor = self.picker.GetActor()
        if actor:
            return actor
    
        path = self.picker.GetPath()
        if path:
            last = path.GetLastNode()
            if last:
                vp = last.GetViewProp()
                if vp and issubclass(type(vp), VirgoActor):
                    return vp
        return None

    @virgo_console
    def list(self, thing):
        """List things in the scene: actors, frames, vectors"""
        import pprint
        text = f"Unknown thing to list: {thing}. Try 'actors', 'vectors', 'frames'"
        if thing == 'help':
            return text
        if thing == 'actors':
            text = pprint.pformat(list(self.actors.keys()))
        elif thing == 'frames':
            text = pprint.pformat(list(self.frames.keys()))
        elif thing == 'vectors':
            text = pprint.pformat(list(self.vectors.keys()))
        return text


    @virgo_console
    def toggle_node_labels(self):
        """Turn on/off node labels"""
        if self._labels_toggle == 'on':
          self._labels_toggle = 'off'
        else:
          self._labels_toggle = 'on'

        for n in self.nodes:
            if self._labels_toggle == 'off':
                self.nodes[n].hide_labels()
            else:
                self.nodes[n].show_labels()

    @virgo_console
    def toggle_lighting_modes(self):
        """Cycle between available lighting modes"""
        # TODO: this should iterate over a dict of self.lighting_modes
        # then check for that mode being in self.scene in init_lighting
        if self.lighting_mode == 'realistic':
            self.lighting_mode = 'headlight'
        elif self.lighting_mode == 'headlight':
            self.lighting_mode = 'ultrabright'
        else:
            self.lighting_mode = 'realistic'
        self.set_lighting_mode(self.lighting_mode)
        #print(f"DEBUG: self.renderers['foreground'].GetPass() is {self.renderers['foreground'].GetPass()}")
        return(self.lighting_mode)

    def add_light(self, light):
        for layer in VirgoRendering.user_facing_layers:
            self.renderers[layer].AddLight(light)
    def remove_light(self, light):
        for layer in VirgoRendering.user_facing_layers:
            self.renderers[layer].RemoveLight(light)
    def remove_all_lights(self):
        for layer in VirgoRendering.user_facing_layers:
            self.renderers[layer].RemoveAllLights()
    def set_pass(self, value):
        for layer in VirgoRendering.user_facing_layers:
            self.renderers[layer].SetPass(value)

 
    def set_lighting_mode(self, mode):
        all_lights = self.renderers['foreground'].GetLights()
        num_lights = all_lights.GetNumberOfItems()
        if mode == 'realistic':
            print("(Somewhat) realistic lighting on")
            self.remove_all_lights()
            if self.sun_light and self.sun_light not in all_lights:
                self.add_light(self.sun_light)
            self.set_pass(self.camera_pass)
            self.set_ambient_all_nodes(self.dark_ambient)
        elif mode == 'headlight':
            print("Headlight lighting on")
            if self.sun_light and self.sun_light in all_lights:
                self.remove_light(self.sun_light)
            headlight = vtkLight()
            headlight.SetLightTypeToHeadlight()
            headlight.SetIntensity(1.0)
            self.add_light(headlight)
            self.set_pass(None)
        elif mode == 'ultrabright':
            print("Ultrabright lighting on")
            if self.sun_light in all_lights:
                self.remove_light(self.sun_light)
            self.set_pass(None)
            self.set_ambient_all_nodes(self.bright_ambient)
        #print(f"DEBUG: Number of lights in scene: {num_lights}")

    def set_ambient_all_nodes(self, value):
        for n in self.nodes:
            if self.nodes[n].actor:
                self.nodes[n].actor.GetProperty().SetAmbient(value)
            # TODO: we should probably make all labels self.bright_ambient

    @virgo_console
    def toggle_trails(self):
        """Turn on/off actor trails"""
        for n in self.nodes:
            if self.nodes[n].is_trail_visible():
                self.nodes[n].hide_trail()
            else:
                self.nodes[n].show_trail()

    @virgo_console
    def take_picture(self, filename=None):
        """Drop a .png of every pixel in the VIRGO window right now"""
        if filename == None:
            filename = os.path.join(self.images_dir,
              (f"virgo_pic_{time.strftime('%Y%m%d_%H%M%S')}.png"))
        self.save_frame(filename=filename)
        print(f"Picture taken: {filename}")

    @virgo_console
    def toggle_axes(self):
        """Show node axes and force actors to be translucent"""
        self.axes_are_toggled = True if self.axes_are_toggled == False else False
        for n in self.nodes:
            if self.nodes[n].are_axes_visible():
                self.nodes[n].hide_axes()
                if self.verbosity > 1:
                    print(f'Hiding axes for {n}')
            else:
                self.nodes[n].show_axes()
                if self.verbosity > 1:
                    print(f'Showing axes for {n}')

    def are_any_axes_visible(self):
        """
        Return true if any axes are visible, False otherwise
        """
        for n in self.nodes:
            if self.nodes[n].are_axes_visible():
                return True
        return False

    @virgo_console
    def camera(self, action, *args):
        """Camera commands:
        ex: camera follow <actor>
        """
        help = ("Usage: camera <action> <args>\nExamples:\n"
        "  camera follow <actor_name>\n"
        "  camera free"
        )
        ac = self.get_active_camera()
        if action == 'help':
            return help
        if action == 'follow':
            if len(args) != 1:
                return('too many args to \'camera follow\', give one node name')
            if args[0] in self.nodes:
                new_parent = self.nodes[args[0]]
                #import pdb; pdb.set_trace()
                ac.set_parent(new_parent)
                self.set_interactor_styles_node(new_parent)
                #ac.follow(self.nodes[args[0]])
                return(f"camera now following {ac.get_parent_name()}")
        if action == 'free':
            ac.set_free()
            return(f"camera now free")

        return help

    def toggle_camera_interactors(self):
        """
        Switch the active camera between trackball mode and first-person mode
        """
        active_cam = self.get_active_camera()
        if active_cam == None:
            print("ERROR: Cannot switch interactor mode, no active camera!")
            return
        active_cam_interactor_mode = active_cam.get_interactor_mode()
        if active_cam_interactor_mode == 'TB':
            self.go_first_person()
        else:
            self.go_trackball()

    def go_trackball(self):
        """
        Switch the active camera to trackball mode
        """
        active_cam = self.get_active_camera()
        if active_cam == None:
            print("ERROR: Cannot go to first person interactor mode, no active camera!")
            return
        self.interactor.SetInteractorStyle(self.trackball_style)
        active_cam.set_interactor_mode('TB')
        active_cam_parent = active_cam.get_parent()
        # Restore the camera's relationship to the parent

    def go_first_person(self):
        """
        Switch the active camera to first person mode
        """
        active_cam = self.get_active_camera()
        if active_cam == None:
            print("ERROR: Cannot go to trackball interactor mode, no active camera!")
            return
        active_cam.clear_relative_focal_point()
        self.interactor.SetInteractorStyle(self.first_person_style)
        active_cam.set_interactor_mode('FP')

    def change_active_camera_parent_from_picked_node(self):
        """
        Adjust the parental relationship of the active camera based on
        what node is currently picked, if any.

        If we're already parented to a node, free the camera. If we're already
        free, change the node we're parented to to be the picked node or last
        picked node if no node is picked. If no last node is picked the camera
        will remain free.

        TODO: This function is kinda funky and is called from a keypress by the
        user, originally written before the virgo console existed.  Probably
        should consolidate this with the camera() function that can be called
        from the virgo console so we're using the same approach everywhere.
        -Jordan 4/2026
        """
        active_cam = self.get_active_camera()
        active_cam_parent = active_cam.get_parent()
        # If we're already following a node, free the camera

        #import pdb; pdb.set_trace()
        if active_cam_parent:
            if self.picked_actor:
                new_parent = self.nodes[self.picked_actor.name]
                active_cam.set_parent(new_parent)
                self.set_interactor_styles_node(new_parent)
            else:
                active_cam.set_free()
        # Otherwise change the node we follow to the picked node or last
        # picked node if no node is picked
        else:
            if self.picked_actor:
                new_parent = self.nodes[self.picked_actor.name]
                active_cam.set_parent(new_parent)
                self.set_interactor_styles_node(new_parent)
            elif self.last_picked_actor:
                new_parent = self.nodes[self.last_picked_actor.name]
                active_cam.set_parent(new_parent)
                self.set_interactor_styles_node(new_parent)
            
    def set_interactor_styles_node(self, node):
        """
        Set the node the active camera is parented to for both interactor
        styles
        """
        self.first_person_style.set_node(node)
        self.trackball_style.set_node(node)

    @virgo_console
    def koviz(self, command):
        help = ("Usage: koviz <command>\nExamples:\n"
        "  koviz status\n"
        "  koviz disconnect"
        )
        if command == 'help':
            return help
        if command == 'status':
            return self.koviz_interface.get_state()
        elif command == 'disconnect' or command == 'stop':
            self.koviz_interface.stop()
            return self.koviz_interface.get_state()
        elif command == 'connect' or command == 'start':
            return self.koviz_interface.start()
        else:
           return(f"Unrecognized command {command}")

    @virgo_console
    def fontsize(self, direction='up'):
        """
        Change fontsize in <up|down> direction
        Increment/decrement fontsize of all text actors given the direction
        """
        increment = 2 if direction == 'up' else -2
        for t in self.text_actors:
            self.fs = self.text_actors[t].GetTextProperty().GetFontSize() + increment
            self.text_actors[t].GetTextProperty().SetFontSize(self.fs)

        self.virgo_console.set_font_size(self.virgo_console.get_font_size() + increment)
        # Adjust the fontsize inside the actor instances
        # TODO this should probably be done with a setter rather than straight assignment
        # Also this was intended for axes label size but I never quite got that to work
        for a in self.actors:
            self.actors[a].fs = self.fs
        return self.fs

    def save_frame(self, filename):
        """
        Save the state of self.render_window to a png file named filename
        """
        if not self.render_window:
            msg = (f"ERROR: Cannot save frame to {filename},"
                   " self.render_window is None!")
            raise RuntimeError (msg)
        w2i = vtkWindowToImageFilter()
        w2i.SetInput(self.render_window)
        w2i.Update()
        writer = vtkPNGWriter()
        writer.SetFileName(filename)
        writer.SetInputConnection(w2i.GetOutputPort())
        writer.Write()
        if self.verbosity > 3:
            print(f"Saved image: {filename}")

    def orient_labels_to_camera(self, caller, event):
        # This was an attempt to get labels to face the camera but I never got
        # it working right. We should have all the information we need to orient
        # each label in the direction of the camera. We have the world position
        # and orientation of the camera and the node the label lives inside keeps
        # that same position/orientation information inside self.local_transform
        # I think we need this function to take the world orientation of the label's
        # normal and point it in the direction of the camera relative to the label

        #node = self.nodes['satellite']
        #label = node.get_label('name')
        #mat = vtkMatrix4x4()
        #node.assembly.GetMatrix(mat)  # fill mat with the assembly's world matrix
        #world = [0.0, 0.0, 0.0, 0.0]
        #local_offset = [node.get_local_position()[0], node.get_local_position()[1],node.get_local_position()[2], 1.0]
        #mat.MultiplyPoint(local_offset, world)
        ## world is homogeneous; set follower to world xyz
        #label.get_follower().SetPosition(world[0], world[1], world[2])
        pass

    def on_key_press(self, caller, event):
        key = self.interactor.GetKeySym()
        #print(f'DEBUG: Key pressed: {key}')
        if key == 'equal':
            self.fontsize('up')
        if key == 'minus':
            pass
            self.fontsize('down')
        if key == 'a':
            # Turn actor axes on/off
            self.toggle_axes()
        if key == 'L':
            # Turn actor axes on/off
            self.toggle_node_labels()
        if key == 'l':
            # Turn actor axes on/off
            self.toggle_lighting_modes()
        if key == "p":
            self.take_picture()
        if key == "t":
            self.toggle_trails()
        if key == "s":
            # Cycle through the available playback speeds
            self.cycle_playback_speed()
        if key == "h":
            self.help = True if self.help == False else False
        if key == "d":
            self.toggle_debug()
            self.report_cameras()
        if key == "BackSpace":
            # Toggle skybox visibility
            self.toggle_skybox()
        if key == "v":
            # Dump the info about the picked actor to the terminal
            if self.picked_actor:
                print(self.text_actors['picked'].GetInput())
        if key == "V":
            # Verbosely print state of all non-text actors
            self.report_nodes()
        if key == "j":
            self.decrease_near_clipping_plane_tolerance()
        if key == "k":
            self.increase_near_clipping_plane_tolerance()
        if key == "J":
            self.decrease_picker_tolerance()
        if key == "K":
            self.increase_picker_tolerance()
        if key == "c":
            self.change_active_camera_parent_from_picked_node()
            self.camera_report()
        if key == "C":
            self.toggle_camera_interactors()
        if key == "space":
            self.handle_pause_button()
        if key == "Left" or key =='comma':
            self.step('back')
        if key == "Right" or key == 'period':
            self.step('forward')
        if key == "Up":
            self.switch_cameras('next')
        if key == "Down":
            self.switch_cameras('previous')
        self.update()

    def report_nodes(self):
        for n in self.nodes:
            # Call report() on root nodes only since they recurse
            if self.nodes[n].parent == None:
                    self.nodes[n].report()

    def switch_cameras(self, direction='next'):
        #import pdb; pdb.set_trace()
        active_cam = self.get_active_camera()
        if active_cam == None:
            print("Unable to determine active camera, cannot switch!")
            return
        # Get a list of user facing cameras sorted by their priority attribute
        user_facing_cams = self.get_user_facing_cameras()
        cams_sorted_by_priority = sorted(
            list(user_facing_cams.values()), key=lambda x: x.priority)
        # Get the index of the active camera in this list
        active_cam_idx = cams_sorted_by_priority.index(active_cam)
        new_idx = 0
        if direction == 'next':
            new_idx = active_cam_idx + 1
        elif direction == 'previous':
            new_idx = active_cam_idx - 1
        else:
            msg = f"Unsupported direction {direction} in switch_cameras"
            raise RuntimeError(msg)

        # Handle idx rollover
        if new_idx > len(user_facing_cams) - 1 :
            new_idx = 0
        # Set the active camera to the camera associated with new_idx
        new_cam_name = cams_sorted_by_priority[new_idx].get_name()
        #import pdb; pdb.set_trace()
        self.set_active_camera(cam_name=new_cam_name)
        self.update_cameras()
        self.sync_cameras(None, None)

    def get_user_facing_cameras(self):
        """
        Get a subset of self.cameras dict, ignoring cameras outside of user
        space.
        """
        user_facing_cams = {}
        for cam in self.cameras:
            if self.cameras[cam].get_name() in VirgoRendering.non_user_facing_cameras:
                continue
            user_facing_cams[cam] = self.cameras[cam]
        return user_facing_cams

    def report_cameras(self):
        for cam in self.cameras:
            self.cameras[cam].report(indent='  ')

    def toggle_debug(self):
        """
        Toggle debug information
        """
        value = True if self.hud.get_debug() == False else False
        self.hud.set_debug(value)
        # Color node trail segments
        for node in self.nodes:
            self.nodes[node].toggle_trail_segments_debug_color()

    def toggle_skybox(self):
        """
        Toggle skybox visibility
        """
        self.skybox.SetVisibility(False) if self.skybox.GetVisibility() else self.skybox.SetVisibility(True)

    @virgo_console
    def step(self, direction='forward'):
        """
        Move <forward|backward> through time the smallest resolution possible
        """
        if direction.upper().startswith('F') or direction == '+':
            self.mode = 'PAUSED'
            self.increment_time()
            self.update_scene()
        elif direction.upper().startswith('B') or direction == '-':
            self.mode = 'PAUSED'
            self.decrement_time()
            self.update_scene()
        else:
            msg = ("ERROR: Unrecognized step direction. Must be f/forward/+"
                   " or b/backward/-" )
            raise RuntimeError (msg)

    @virgo_console
    def quit(self):
        """Exit VIRGO"""
        self.interactor.TerminateApp()

    @virgo_console
    def exit(self):
        """Exit VIRGO"""
        self.quit()

    @virgo_console
    def pause(self):
        """Change mode to PAUSED a.k.a stop playback"""
        if self.mode == 'PAUSED':
            return
        else:
            self.handle_pause_button()

    @virgo_console
    def stop(self):
        """Change mode to PAUSED a.k.a stop playback"""
        self.pause()

    @virgo_console
    def play(self):
        """Change mode to PLAYING a.k.a start playback"""
        if self.mode == 'PLAYING':
            return
        else:
            self.handle_pause_button()

    @virgo_console
    def time(self, intime=None):
        """
        Get or set the current world time
        
        TODO: it'd be cool if intime could be a string representing the
        percentage of the total sim time to jump to, for example '50%'
        to go halfway
        """
        if intime != None:
            try:
                intime = float(intime)
            except ValueError:
                msg = f"ERROR: provided time {intime} must be a float"
                raise RuntimeError(msg)
            self.set_time(intime)
        return(self.world_time)

    def set_time(self, time):
        """Move the scene to the given world time"""
        if time > self.max_sim_time or time < self.min_sim_time:
            msg = (f"ERROR: set_time(time) time value {time} must be <="
                   f"{self.max_sim_time} and >= {self.min_sim_time}")
            raise RuntimeError(msg)
        self.world_time = time
        self.force_node_update = True
        # Right now trails can't handle jumping in time, it would
        # be nice to support that though
        self.reset_trails()
        return(self.world_time)

    @virgo_console
    def speed(self, inspeed=None):
        """Get or set playback speed"""
        if inspeed != None:
            self.set_speed(inspeed)
        return(self.playback_speed)

    def set_speed(self, inspeed):
        """
        Directly set the playback speed. Does not care about
        if inspeed is in self.available_speeds
        """
        try:
            inspeed = float(inspeed)
        except ValueError:
            msg = f"ERROR: provided speed {inspeed} must be a float"
            raise RuntimeError(msg)
        self.playback_speed = inspeed
        # Adjust self.dt so the scene runs based on new speed
        self.dt = self.default_dt * self.playback_speed

    def cycle_playback_speed(self):
        """
        Cycle the playback speed by iterating forward in the list of 
        self.available_speeds
        """
        # Find our current speed index in the list of available speeds
        idx = self.available_speeds.index(self.playback_speed)
        if idx < len(self.available_speeds) - 1:
            self.playback_speed = self.available_speeds[idx+1]
        else:
            self.playback_speed = self.available_speeds[0]
        # Adjust self.dt so the scene runs based on new speed
        self.dt = self.default_dt * self.playback_speed
        return self.playback_speed

    def handle_pause_button(self):
        """
        If paused, go to playing. If playing, go to paused.
        If paused and at the end of the sim, reset world time
        to the world time start
        """
        # If there is no time in this scene, do nothing
        if self.timeless:
            return
        if self.mode == 'PAUSED':
            self.mode = 'PLAYING'
            if math.isclose(self.world_time, self.max_sim_time):
                self.set_time(self.world_time_start)
        else:
            self.mode = 'PAUSED'
        # Update the text actor that displays mode
        self.text_actors['mode'].SetInput(self.mode)

    def decrement_time(self):
        """
        Decrement world time by the minimum resolution across all actors logged data

        Across all nodes with a data source, find the time before (to the left of)
        self.world_time that is closest to self.world_time and set self.world_time
        to that value
        """
        largest_time = - self.huge # Negative Huge
        for n in self.nodes:
            if self.nodes[n].data_source == None:
                continue
            pt = self.nodes[n].data_source.get_previous_time(self.world_time)
            if pt is None:
                continue
            if pt > largest_time:
                largest_time = pt
        # Decrease the world time
        if largest_time > - self.huge:
            #print(f"Setting (decrement) world_time to {largest_time}")
            self.world_time = largest_time
            for n in self.nodes:
                if self.nodes[n].data_source == None:
                    return
                self.nodes[n].data_source.set_current_time(self.world_time, strategy='closest')
                
    def increment_time(self):
        """
        Increment world time by the minimum resolution across all actors logged data

        Across all nodes with a data source, find the time after (to the right of)
        self.world_time that is closest to self.world_time and set self.world_time
        to that value
        """
        smallest_time = self.huge # Huge
        for n in self.nodes:
            if self.nodes[n].data_source == None:
                continue
            nt = self.nodes[n].data_source.get_next_time(self.world_time)
            if nt is None:
                continue
            if nt < smallest_time:
                smallest_time = nt
        # Increase the world time
        if smallest_time < self.huge:
            #print(f"Setting (increment) world_time to {smallest_time}")
            self.world_time = smallest_time
            for n in self.nodes:
                if self.nodes[n].data_source == None:
                    continue
                self.nodes[n].data_source.set_current_time(self.world_time, strategy='closest')

    def initialize_cameras(self):
        """
        Initialize all user-defined cameras. Note that self.cameras
        is already populated with non-user-facing cameras
        """
        cameras = {}
        if 'cameras' in self.scene and self.scene['cameras'] != None:
          for c in self.scene['cameras']:
            cameras[c] = {}
            cameras[c] = self.create_camera(name=c, csd=self.scene['cameras'][c])
        # If no default camera specified by the user, create it
        if not cameras or 'default' not in cameras:
            cameras['default'] = {}
            cameras['default'] = self.create_camera(name='default', csd={})

        # Add user cameras to the full camera dictionary
        self.cameras.update(cameras)

        # Set clipping ranges for very far away cameras, the other cameras
        # 'foreground' and 'midground' clipping ranges are dynamic and
        # change with the movement of the camera
        # TODO do we want a user to be able to change this in the yaml file?
        self.cameras['sun'].set_clipping_range(1e10, 1e17)
        self.cameras['background'].set_clipping_range(1e10, 1e17)
        # NOTE this skybox clipping range appears optimal and I'm not sure
        # why, other ranges result in the skybox becoming erratic in scenes
        # with inertial sized bodies and distances
        self.cameras['skybox'].set_clipping_range(1e6, 1e10)

        # Set the active camera to the default cam which is guaranteed to exist
        self.set_active_camera(cam_name='default')

        # If the camera is parented, use the pos: value as the relative offset
        default_cam = self.cameras['default']
        if default_cam.has_parent():
            default_cam.set_relative_offset(self.scene['cameras']['default']['pos'])
        # Foreground position is automatic from renderer, so sync it with
        # the default camera, otherwise foreground camera ends up at [0,0,1]
        # TODO: it'd be nice if this was more intuitive and this explicit
        # call not needed here, but this is downstream of how the non
        # user facing cameras are initialized from defaults coming from
        # GetActiveCamera and that foreground is the only camera layer not
        # sync'd to the active camera
        self.cameras['foreground'].set_parent(default_cam.get_parent())
        self.cameras['foreground'].sync_with(default_cam)
        width, height = self.render_window.GetSize()
        self.cameras['foreground'].update(width, height)

        # Pass the cameras dict into the interactors
        self.trackball_style.set_cameras(self.cameras)
        self.first_person_style.set_cameras(self.cameras)

        self.sync_cameras(None, None)
        #print(f"DEBUG: ACTIVE VTK CAMERA FOR FOREGROUND IS INITIALIZED TO: {hex(id(self.renderers['foreground'].GetActiveCamera()))}")
        #for cam in self.cameras:
        #  print(f"DEBUG: all vtk cams: {cam}: {hex(id(self.cameras[cam].camera))}")


    def set_active_camera(self, cam_name):
        """
        1. Assign the vtkCamera from cam_name to the foreground rendering layer
        2. Set the active flag in the self.cameras instance to True
        3. Deactivate any cameras that were active, and switch interactor
           modes based on the new camera's attribute
        4. Manage Observer callbacks to sync_cameras so it's only called
           for the active camera
        """
        # Deactivate any other cameras that are currently active and remove
        # the camera sync callback from that vtk camera
        # TODO: This works while a single camera can be active at a time
        # but would break if we ever supported multiple cameras rendered
        # at the same time
        active_cam = self.get_active_camera()
        # Already using this camera, do nothing
        if active_cam and active_cam.name == cam_name:
            return
        #import pdb; pdb.set_trace()
        if active_cam != None:
            active_cam.deactivate()
            old_vtk_cam = active_cam.get_vtk_camera()
            old_vtk_cam.RemoveObserver(self.cam_sync_observer_tag)

        new_vtk_cam = self.cameras[cam_name].get_vtk_camera()
        # Assign the new camera to the foreground rendering layer
        self.renderers['foreground'].SetActiveCamera(new_vtk_cam)
        # Register the camera sync callback for the new camera
        self.cam_sync_observer_tag = new_vtk_cam.AddObserver("ModifiedEvent", self.sync_cameras)
        # Mark this camera as currently active
        self.cameras[cam_name].activate()

        #print(f"DEBUG: Active camera is now {cam_name}")

        # Tell the interactors
        new_cam_parent = self.cameras[cam_name].get_parent()
        if new_cam_parent:
            self.set_interactor_styles_node(new_cam_parent)

        if self.cameras[cam_name].get_interactor_mode() == 'FP':
            self.go_first_person()
        elif self.cameras[cam_name].get_interactor_mode() == 'TB':
            self.go_trackball()

    def get_active_vtk_camera(self):
        """
        Get the vtkCamera instance for the active camera. Note this
        assumes self.renderers['foreground'] is always the active camera
        which is currently true.
        """
        return(self.renderers['foreground'].GetActiveCamera())

    def get_active_camera(self):
        """
        Return the VirgoCamera instance that is currently active

        TODO: make this safer, right now it only finds the first
        true instance but we need to make sure multiples aren't True
        """
        for cam in self.cameras:
            if self.cameras[cam].is_active():
                return self.cameras[cam]
        return None

    def create_camera(self, name, csd, _class=None):
        """
        Create and return a VirgoCamera with the info provided

        Params:
          csd: This camera's scene dict
          _class: Used for camera extension (currently untested)
        """
        # Make sure the given class derives from VirgoCamera
        if _class == None:
          _class = VirgoCamera
        elif not issubclass(_class, VirgoCamera):
          msg = (f"ERROR: Improper extension detected: {_class} must derive from" 
                 f"VirgoCamera")
          raise RuntimeError (msg)

        # Default values which can be overridden by info in csd
        mode='TB'
        position=[0.0, 0.0, 0.0]
        focal_point=[1.0, 0.0, 0.0]
        view_up=[0.0, 0.0, 1.0]
        view_angle=30
        static=False
        frustum_when='toggled'
        frustum_far_plane=1.0
        frustum_color=[1.0, 0.9, 0.1]
        priority=0
        parent=None
         
        if 'mode' in csd and csd['mode'] != None:
          mode = csd['mode']
        if 'pos' in csd and csd['pos'] != None:
          position = csd['pos']
        if 'focal_point' in csd and csd['focal_point'] != None:
          focal_point = csd['focal_point']
        if 'view_up' in csd and csd['view_up'] != None:
          view_up = csd['view_up']
        if 'view_angle' in csd and csd['view_angle'] != None:
          view_angle = csd['view_angle']
        if 'static' in csd and csd['static'] != None:
          static = csd['static']
        if 'frustum_when' in csd and csd['frustum_when'] != None:
          frustum_when = csd['frustum_when']
        if 'frustum_far_plane' in csd and csd['frustum_far_plane'] != None:
          frustum_far_plane = csd['frustum_far_plane']
        if 'frustum_color' in csd and csd['frustum_color'] != None:
          frustum_color = csd['frustum_color']
        if 'priority' in csd and csd['priority'] != None:
          priority = csd['priority']
        if 'parent' in csd and csd['parent'] != None:
          parent = self.nodes[csd['parent']]

        camera = VirgoCamera(name=name,
                 mode=mode,
                 position=position,
                 focal_point=focal_point,
                 view_up=view_up,
                 view_angle=view_angle,
                 static=static,
                 frustum_when=frustum_when,
                 frustum_far_plane=frustum_far_plane,
                 frustum_color=frustum_color,
                 priority=priority,
                 parent=parent)
        return(camera)

    def init_renderer_options(self):
      """
      Initialize self.renderers and other internal members with user-provided
      settings
      """
      if 'renderer' in self.scene and self.scene['renderer'] != None:
        if ('foreground_far_boundary' in self.scene['renderer'] and 
            self.scene['renderer']['foreground_far_boundary'] != None):
          self.foreground_far_boundary = self.scene['renderer']['foreground_far_boundary']
        if ('midground_far_boundary' in self.scene['renderer'] and 
            self.scene['renderer']['midground_far_boundary'] != None):
          self.midground_far_boundary = self.scene['renderer']['midground_far_boundary']
        if ('celestial_foreground_bias' in self.scene['renderer'] and 
            self.scene['renderer']['celestial_foreground_bias'] != None):
          self.celestial_foreground_bias = self.scene['renderer']['celestial_foreground_bias']
  
        # NearClippingPlaneTolerance IS CRITICAL, SMALLER NUMBERS (0.00001) MAKE
        # THE BACKGROUND SKYBOX STARS WIGGLE BUT LARGER NUMBERS (0.0001) MAKE
        # SMALLER ACTORS NOT VISIBLE DUE TO CLIPPING.
        if ('near_clipping_plane_tolerance' in self.scene['renderer'] and 
            self.scene['renderer']['near_clipping_plane_tolerance'] != None):
            self.near_clipping_plane_tolerance = float(self.scene['renderer']['near_clipping_plane_tolerance'])

      if self.celestial_foreground_bias == 0.0: 
        print(f"WARNING: celestial_foreground_bias == 0.0, which means no celestial sized "
              f"objects can enter the foreground layer. This may result in unusual clipping "
              f"if the camera gets close to these objects.")

      #TODO make this cleaner if we are keeping the tolerance the same for all layers
      self.renderers['foreground'].SetNearClippingPlaneTolerance(self.near_clipping_plane_tolerance)
      self.renderers['midground'].SetNearClippingPlaneTolerance(self.near_clipping_plane_tolerance)
      self.renderers['background'].SetNearClippingPlaneTolerance(self.near_clipping_plane_tolerance)

    def increase_near_clipping_plane_tolerance(self, multiplier=2.0):
        self.near_clipping_plane_tolerance *= multiplier
        self.renderers['foreground'].SetNearClippingPlaneTolerance(self.near_clipping_plane_tolerance)
        self.renderers['midground'].SetNearClippingPlaneTolerance(self.near_clipping_plane_tolerance)
        self.renderers['background'].SetNearClippingPlaneTolerance(self.near_clipping_plane_tolerance)

    def decrease_near_clipping_plane_tolerance(self, multiplier=2.0):
        self.near_clipping_plane_tolerance /= multiplier
        self.renderers['foreground'].SetNearClippingPlaneTolerance(self.near_clipping_plane_tolerance)
        self.renderers['midground'].SetNearClippingPlaneTolerance(self.near_clipping_plane_tolerance)
        self.renderers['background'].SetNearClippingPlaneTolerance(self.near_clipping_plane_tolerance)

    def increase_picker_tolerance(self, multiplier=2.0):
        self.picker_tolerance *= multiplier
        self.picker.SetTolerance(self.picker_tolerance)

    def decrease_picker_tolerance(self, multiplier=2.0):
        self.picker_tolerance /= multiplier
        self.picker.SetTolerance(self.picker_tolerance)

    def init_picker(self):
        """
        Set configurable parameters for the picker
        """
        if 'picker' in self.scene and  self.scene['picker'] != None:
          if 'tolerance' in self.scene['picker'] and self.scene['picker']['tolerance'] != None:
            self.picker_tolerance = float(self.scene['picker']['tolerance'])
        self.picker.SetTolerance(self.picker_tolerance)

    def camera_report(self):
        """
        Debug function for seeing where the camera is
        """
        for c in self.cameras:
          # Other renderer cameras all sync to foreground so don't show them
          # unless verbosity is high
          if self.verbosity < 3 and not self.cameras[c].is_active():
              continue
          print(f"Camera {c}:")
          self.cameras[c].report(indent=' ')
        print("Renderer info:")
        for r in self.renderers:
          print(f"  {r} NearClippingPlaneTolerance: {self.renderers[r].GetNearClippingPlaneTolerance()} ")

    def set_interactors(self, trackball_style, first_person_style):
        self.trackball_style = trackball_style
        self.first_person_style = first_person_style

    def register_callbacks(self):
        """
        Register all callbacks with the interactor
        """
        active_cam = self.get_active_camera()
        vtk_cam = active_cam.get_vtk_camera()
        self.cam_sync_observer_tag = vtk_cam.AddObserver("ModifiedEvent", self.sync_cameras)
        self.interactor.AddObserver("RightButtonPressEvent", self.on_right_click)
        self.interactor.AddObserver("TimerEvent", self.on_timer)
        self.interactor.AddObserver("KeyPressEvent", self.on_key_press)
        # This call to self.adjust_camera_clipping_ranges is crucial even though
        # AI calls it the "nuclear option". The issue is that
        # vtkInteractorStyleTrackballCamera has internal calls in C++ that end
        # up calling render_window.Render(), which does a camera clipping
        # adjustment automatically, overriding the custom logic we do in
        # adjust_camera_clipping_ranges().  This callback ensures our logic is
        # called right before every Render()
        self.renderers['foreground'].AddObserver("StartEvent", self.adjust_camera_clipping_ranges)
        self.timer_id = self.interactor.CreateRepeatingTimer(self.callback_rate)

    def on_clipping_reset(self, obj, event):
        """
        # HACK: when axes are visible the bounding boxes are incorrectly defined
        # and resetting the camera clipping range will pull the close clipping range
        # so far away the followed actor is not visible. This works around the core
        # issue which is described in detail here:
        # https://discourse.vtk.org/t/vtkaxesactor-bounding-box-appears-to-be-affected-by-its-world-position/16290 
        # See also configure_camera_clipping_ranges() 
        """
        if self.are_any_axes_visible():
            for layer in self.cameras:
                self.cameras[layer].revert_clipping_range()

    def sync_cameras(self, obj, event):
        """
        Sync the params of all cameras to that of the foreground camera
        This is required so that we can use multiple renderers for different
        sized actors in the scene. The cameras have to be in the same place
        for each renderer layer in order to for it to look correct as the
        scenes are composited together. Note that clipping ranges are not
        sync'd on purpose.
        """
        active_vtk_cam = self.renderers['foreground'].GetActiveCamera()
        #print(f"====DEBUG ABOUT TO SYNC EVERYTHING TO  ACTIVE CAM {hex(id(active_vtk_cam))}====")
    
        for cam in VirgoRendering.cameras_to_sync:
            self.cameras[cam].sync_with_vtk_camera(active_vtk_cam)
            #self.cameras[cam].report()
        #print(f"====DONE WITH SYNC EVERYTHING TO  ACTIVE CAM {hex(id(active_vtk_cam))}=========")
        #import pdb; pdb.set_trace()

    def position_sun_actor(self, obj, event):
        """
        Position the sun based on self.sun_direction

        TODO: this is a naiive approach as self.sun_distance is currently
        hardcoded to a value that's true while the camera is near earth.
        """

        if not self.sun_actor:
            return

        cam = self.renderers['foreground'].GetActiveCamera()
        cam_pos = cam.GetPosition()
    
        sun_pos = [
            cam_pos[0] + self.sun_direction[0] * self.sun_distance,
            cam_pos[1] + self.sun_direction[1] * self.sun_distance,
            cam_pos[2] + self.sun_direction[2] * self.sun_distance
        ]
        #print(f"DEBUG: setting sun actor position to {sun_pos}")
        self.sun_actor.SetPosition(sun_pos)

    def position_sun_light(self):
        if self.sun_driven_by:
            # In the case of vector sub-class, assign the sun direction to
            # the vector in world coordinates
            if isinstance(self.sun_driven_by, VirgoSceneNodeVector):
                self.sun_direction = self.sun_driven_by.get_world_vector()
            # In the case of a regular SceneNode, assign the sun direction to
            # the position of that node in world coordinates
            else:
                self.sun_direction = self.sun_driven_by.get_world_position()
        #print(f"DEBUG: self.sun_direction: {self.sun_direction}")
        # Normalize the sun direction
        sun_magnitude = math.sqrt(sum(c**2 for c in self.sun_direction))
        sun_dir_norm = [c / sun_magnitude for c in self.sun_direction]
        # Place the light in the direction of the vector 
        # Note that for this directional (SetPositional(False)) light it's
        # distance away from objects doesn't matter
        self.sun_light.SetPosition(sun_dir_norm)
        # Set direction of light to origin
        self.sun_light.SetFocalPoint(0, 0, 0)

    def create_skybox(self):
        """
        Create the skybox of the starfield using images from
        https://svs.gsfc.nasa.gov/4851

        TODO: This should probably live in another class and we just
        retrieve it here
        """
        texture_reader = vtkJPEGReader()
        texture_reader.SetFileName(
            os.path.join(thisFileDir,"images/space/starmap_2020_8k.jpg"))
        texture_reader.Update()
        
        texture = vtkTexture()
        texture.SetInputConnection(texture_reader.GetOutputPort())
        texture.MipmapOn()
        texture.InterpolateOn()
        texture.RepeatOn()
        
        # Create the skybox
        skybox = vtkSkybox()
        skybox.SetTexture(texture)
        skybox.SetProjectionToSphere()  # For equirectangular maps
        skybox.SetVisibility(False)     # Off by default

        self.renderers['skybox'].AddActor(skybox)
        return skybox

    def init_lighting(self):
        # TODO more verifier needed here
        if 'lighting' in self.scene and self.scene['lighting']:
            if 'start_mode' in self.scene['lighting']:
                self.lighting_mode = self.scene['lighting']['start_mode']
            if 'dark_ambient' in self.scene['lighting']:
                self.dark_ambient = self.scene['lighting']['dark_ambient']
            if 'bright_ambient' in self.scene['lighting']:
                self.bright_ambient = self.scene['lighting']['bright_ambient']
        # Initialize the sun light source
        self.init_sun()

        # Configure the 'realisitc' lighting mode with shadow pass
        # by building up self.camera_pass which the renderer will use
        shadows = vtkShadowMapPass()
        seq = vtkSequencePass()
        passes = vtkRenderPassCollection()
        # Baker pass provides inter-actor shadows but there's a major
        # bug that prevents us from using it. See details here:
        #bp = shadows.GetShadowMapBakerPass()
        #bp.SetResolution(4096)
        # https://discourse.vtk.org/t/invalid-shadow-shape-affected-by-the-aspect-ratio-of-the-window/12000/2
        #passes.AddItem(bp)
        passes.AddItem(shadows)
        # Add overlay and translucent passes, this is needed for text_actors
        # and actors with less than 1.0 opacity to render when more realisitic
        # lighting is on
        passes.AddItem(vtkTranslucentPass())
        passes.AddItem(vtkOverlayPass())
        seq.SetPasses(passes)
        self.camera_pass = vtkCameraPass()
        self.camera_pass.SetDelegatePass(seq)

        self.set_lighting_mode(self.lighting_mode)

    def get_node(self, name):
        if name not in self.nodes:
            return None
        return self.nodes.get(name)

    def init_sun(self):
        """
        Create and initialize the sun sphere and light source
        """
        sun_scale=1.0
        if 'sun' in self.scene and self.scene['sun'] != None:
          if ('direction' in self.scene['sun'] and
              self.scene['sun']['direction'] != None):
            self.sun_direction = self.scene['sun']['direction']
          if ('scale' in self.scene['sun'] and 
              self.scene['sun']['scale'] != None):
            sun_scale = self.scene['sun']['scale']
          if ('driven_by' in self.scene['sun'] and
               self.scene['sun']['driven_by'] != None):
            n = self.scene['sun']['driven_by']
            self.sun_driven_by = self.get_node(n)
            if not self.sun_driven_by:
                msg = (f"ERROR: sun: driven_by: {n} is not a "
                       "valid node in the scene")
                raise RuntimeError (msg)

        # Create the light coming from the sun 
        self.sun_light = vtkLight()
        self.sun_light.SetLightTypeToSceneLight()
        self.sun_light.SetPositional(False)
        self.sun_light.SetDirectionAngle(0, 0)  # placeholder, we’ll set manually below
        self.sun_light.SetColor(1.0, 0.95, 0.8)
        self.sun_light.SetIntensity(0.8)
        
        self.position_sun_light()

        # Create the sun actor - this sphere is not a normal actor
        # but will be placed at a fixed distance relative to the camera
        # to make it appear to be very far away
        sun_sphere = vtkSphereSource()
        sun_size = 6.957e8  # Radius in meters
        sun_sphere.SetRadius(sun_size)
        sun_sphere.SetThetaResolution(32)
        sun_sphere.SetPhiResolution(32)
    
        sun_mapper = vtkPolyDataMapper()
        sun_mapper.SetInputConnection(sun_sphere.GetOutputPort())
    
        self.sun_actor = vtkActor()
        self.sun_actor.SetMapper(sun_mapper)
        self.sun_actor.GetProperty().SetColor(1.0, 1.0, 0.0) # Yellow
        self.sun_actor.GetProperty().SetLighting(False)  # always bright (emissive)
        self.sun_actor.SetPickable(False)
        self.sun_actor.SetScale(sun_scale, sun_scale, sun_scale)
        # TODO: this assumes we're near earth, need a more flexible solution
        # for missions further away
        self.sun_distance = 1.4959e11
        # If the user didn't specify a sun, hide the sphere
        if self.scene['sun'] == None:
            self.sun_actor.SetVisibility(False)

        self.position_sun_actor(None, None)

class VirgoScene:
    """
    Class used as entrypoint for all VIRGO rendered scenes

    Expects to consume a dict describing the scene dict and populates
    self.nodes (the main scene graph) and other internal members
    """
    controller_class: Type[VirgoControlCenter] = VirgoControlCenter
    interactor_class: Type[vtkInteractorStyle] = VirgoTrackballInteractorStyle

    def __init__(self, scene, verbosity=1, headless=False, stop_time=None,
                 images_dir="/tmp/", video_filename="/tmp/virgo.mp4",
                 splash=True, scene_yaml_path=None, koviz_port=64053,
                 controller_class: Optional[Type[VirgoControlCenter]] = None,
                 controller_kwargs: Optional[Dict[str, Any]] = None,
                 interactor_class: Optional[Type[vtkInteractorStyle]] = None,
                 interactor_kwargs: Optional[Dict[str, Any]] = None,
                 **kwargs,  # other manager-specific args
                 ):
        # The controller_class allows override of the default VirgoControlCenter
        controller_class = controller_class or self.__class__.controller_class
        controller_kwargs = controller_kwargs or {}
        # The interactor_class allows override of the default VirgoTrackballInteractorStyle
        interactor_class = interactor_class or self.__class__.interactor_class
        interactor_kwargs = interactor_kwargs or {}

        self.scene = scene # Dict of scene info from YAML file
        self.verbosity = verbosity
        self.splash = splash
        # Optional path to the YAML file associated with self.scene
        self.scene_yaml_path = scene_yaml_path
        self.koviz_port = koviz_port
        self.headless = headless
        # TODO: consider using stop_time in interactive mode as well
        self.stop_time = stop_time  # For headless mode, stop at this time
        self.images_dir = images_dir
        self.video_filename = video_filename
        self.fs = 14      # font size
        self.max_sim_time = 0.0
        self._verify_scene()
        self.nodes = {}    # Scene graph dict of VirgoSceneNode instances

        self.background_color = [0.0, 0.0, 0.05]
        self.highlight_color = [1.0, 1.0, 0.0]
        self.description = "Untitled VIRGO Window"
        self.name = "Untitled VIRGO Scene"
        self.window_width = 800
        self.window_height = 600
        # TODO: this checking can be removed once the dict verifier is in place
        if 'background_color' in self.scene:
            self.background_color = self.scene['background_color']
        if 'highlight_color' in self.scene:
            self.highlight_color = self.scene['highlight_color']
        if 'description' in self.scene:
            self.description = self.scene['description']
        if 'name' in self.scene:
            self.name = self.scene['name']
        if 'resolution' in self.scene:
            self.window_width, self.window_height = map(int, self.scene['resolution'].split('x'))
        if 'splash' in self.scene:
            self.splash = self.scene['splash']

        self.render_window = vtkRenderWindow()
        self.renderers = self.setup_renderers(self.background_color)
        self.render_window.SetNumberOfLayers(len(self.renderers.keys()))
        self.interactor = vtkRenderWindowInteractor()
    
        self.trackball_style = interactor_class(renderers=self.renderers,
                                                 **interactor_kwargs)
        # TODO should this also be override-able?
        self.first_person_interactor_style = VirgoInteractorStyleFirstPerson(renderers=self.renderers,
                                                 **interactor_kwargs)
        self.controller = controller_class(renderers=self.renderers,
                                           render_window=self.render_window,
                                           interactor=self.interactor,
                                           scene=self.scene,
                                           koviz_port=self.koviz_port,
                                             **controller_kwargs)


        self.initialized = False

    @staticmethod
    def setup_renderers(bg_color):
        """
        Create a dictionary of renderers, one for each layer in the scene
        and return it

        We have multiple renderers to help overcome single precision depth buffer issues.
        Each renderer operates in it's own layer composited on top of the last,
        background first ending with foreground

        Returns: dict of vtkRenderer instances
        """
        rs = {}
        rs['skybox'] = vtkRenderer()  # For actors at infinity
        rs['skybox'].SetLayer(0)
        rs['skybox'].InteractiveOff()
        rs['skybox'].SetBackground(bg_color)
        rs['sun'] = vtkRenderer()  # For actors 1e10 -> 1e17
        rs['sun'].SetLayer(1)
        rs['sun'].InteractiveOff()
        rs['sun'].SetBackground(bg_color)
        rs['background'] = vtkRenderer()  # For actors 1e10 -> 1e17
        rs['background'].SetLayer(2)
        rs['background'].SetBackground(bg_color)
        rs['midground'] = vtkRenderer()  # For actors 1e5 -> 1e12
        rs['midground'].SetLayer(3)
        rs['midground'].SetBackground(bg_color)
        rs['foreground'] = vtkRenderer()  # For actors 1e-2 -> 1e5
        rs['foreground'].SetLayer(4)
        rs['foreground'].SetBackground(bg_color)

        return rs

    def initialize(self):
        """
        Initialize this instance by:
        1. Initializing all actors found in the scene
        2. Configuring the controller, renderer, and interactor
        """
        self.initialize_nodes()   # Load all actors from the self.scene info
        # Initialize the heads-up-display

        self.render_window.SetSize(self.window_width, self.window_height)
        self.render_window.SetWindowName(self.name)

        # Set custom interactor style
        self.interactor.SetInteractorStyle(self.trackball_style)
        
        if self.headless:
            print("Running in headless (non-interactive) mode.")
            self.render_window.OffScreenRenderingOn()    
        else:
            print("Running in interactive mode.")
            self.interactor.SetRenderWindow(self.render_window)
            self.interactor.Initialize()
    
        # Create controller
        self.controller.set_interactors(trackball_style=self.trackball_style,
                                        first_person_style=self.first_person_interactor_style)
        self.controller.set_verbosity(self.verbosity)

        self.controller.initialize()
        self.controller.register_callbacks()
        self.controller.initialize_hud()
        self.initialized = True

    def add_node(self, node, parent_name=None):
        """
        Add a node to the scene graph represented by self.nodes dict
        """
        self.nodes[node.name] = node
        if parent_name is not None:
            parent = self.nodes[parent_name]
            parent.add_child(node)


    def _verify_scene(self):
        """
        Call the VirgoDictVerifier to ensure the given scene dictionary
        is a valid schema
        """
        from VirgoDictVerifier import VirgoDictVerifier
        vdv = VirgoDictVerifier(scene_dict=self.scene, yaml_file=self.scene_yaml_path)
        self.scene = vdv.verify()

    def create_actor(self, actor_name, actor_scene_dict=None,):
        """
        Given a single scene's actors: sub-entry, return a
        VirgoActor instance built from that information

        TODO all this checking for dict/YAML validity needs to be safer, i.e.
        checked in a YAML verifier before getting here similar to what
        TrickOps does with TrickWorkflowYamlVerifier. See VirgoDataPlayback.
        _verify_scene()

        Returns: VirgoActor 
        """
        offset_pos=[0.0, 0.0, 0.0]
        offset_ypr=[0.0, 0.0, 0.0]
        scale = 1.0
        opacity = 1.0
        if 'pos' in actor_scene_dict:
            offset_pos=actor_scene_dict['pos']
        if 'ypr' in actor_scene_dict:
            offset_ypr=actor_scene_dict['ypr']
        if 'scale' in actor_scene_dict:
            scale=actor_scene_dict['scale']
        if 'opacity' in actor_scene_dict:
            opacity=actor_scene_dict['opacity']
        # Create the Actor
        if self.verbosity > 1:
            print(f"Constructing VirgotDataPlaybackActor {actor_name} ...")
        actor = VirgoActor(
            mesh=actor_scene_dict['mesh'],
            offset_pos=offset_pos,
            offset_ypr=offset_ypr,
            name=actor_name,
            fontsize=self.fs
            )
        # TODO: create SceneNode here and add actor to it!
        if self.verbosity > 0:
            print(f"Initializing {actor_name} ...")

        actor.SetScale(scale)
        actor.GetProperty().SetOpacity(opacity)
        if 'color' in actor_scene_dict and actor_scene_dict['color'] != None:
            actor.GetProperty().SetColor(actor_scene_dict['color'])
        if 'pickable' in actor_scene_dict and actor_scene_dict['pickable'] == 0:
            actor.PickableOff()
        if 'backface_culling' in actor_scene_dict and actor_scene_dict['backface_culling'] != None:
            actor.set_backface_culling(actor_scene_dict['backface_culling'])

        return actor


    def create_vector(self, vector_name, vector_scene_dict=None):
        """
        Creates a VirgoActor with a VIRGO_PREFAB:arrow mesh
        from the information in the vector_scene_dict
        """
        # The vector fields are similar to actor, but mesh isn't repected
        # Force the arrow mesh then create the vector actor
        vector_scene_dict['mesh'] = 'VIRGO_PREFAB:arrow'
        vector = self.create_actor(actor_name=vector_name, actor_scene_dict=vector_scene_dict)
        if 'tip_length' in vector_scene_dict:
            vector.source.SetTipLength(vector_scene_dict['tip_length'])
        if 'tip_radius' in vector_scene_dict:
            vector.source.SetTipRadius(vector_scene_dict['tip_radius'])
        if 'tip_resolution' in vector_scene_dict:
            vector.source.SetTipResolution(vector_scene_dict['tip_resolution'])
        if 'shaft_radius' in vector_scene_dict:
            vector.source.SetShaftRadius(vector_scene_dict['shaft_radius'])
        if 'shaft_resolution' in vector_scene_dict:
            vector.source.SetShaftResolution(vector_scene_dict['shaft_resolution'])

        return vector

    def create_node(self, actor, actor_scene_dict=None, _class=None):
        """
        Creates a VirgoSceneNode associated with actor from the information
        in actor_scene_dict. 

        Args:
          _class (cls): Class to instantiate, must be or derive from VirgoSceneNode
                        or be None which means use VirgoSceneNode

        Returns: Tuple of (VirgoSceneNode, parent_name [str])
        """
        # Make sure the given class derives from VirgoSceneNode
        if _class == None:
          _class = VirgoSceneNode
        elif not issubclass(_class, VirgoSceneNode):
          msg = (f"ERROR: Improper extension detected: {_class} must derive from" 
                 f"VirgoSceneNode")
          raise RuntimeError (msg)

        name = None
        if actor:
          name = actor.name
        node = _class(name=name, actor=actor)
        node.set_highlight_color(self.highlight_color)
        parent_name=None
        if 'scale' in actor_scene_dict and actor_scene_dict['scale'] != None:
          node.set_user_scale(actor_scene_dict['scale'])
        if 'parent' in actor_scene_dict and actor_scene_dict['parent'] != None:
          parent_name=actor_scene_dict['parent']

        if issubclass(_class, VirgoSceneNodeVector):
          if 'mode' in actor_scene_dict and actor_scene_dict['mode'] != None:
            node.set_mode(actor_scene_dict['mode'])

        if 'axes' in actor_scene_dict and  actor_scene_dict['axes'] != None: 
          if ('affect_opacity' in actor_scene_dict['axes'] and 
              actor_scene_dict['axes']['affect_opacity'] != None): 
              node.set_axes_affect_opacity(actor_scene_dict['axes']['affect_opacity'])
          if 'style' in actor_scene_dict['axes']  and actor_scene_dict['axes']['style'] != None: 
              node.set_axes_style(actor_scene_dict['axes']['style'])
          if 'length' in actor_scene_dict['axes']  and actor_scene_dict['axes']['length'] != None: 
              node.set_axes_length(actor_scene_dict['axes']['length'])
          # Note 'when' is deliberately last since it can be affected by the above settings
          if 'when' in actor_scene_dict['axes']  and actor_scene_dict['axes']['when'] != None: 
              node.set_axes_when(actor_scene_dict['axes']['when'])

        # If labels: are provided for the node/actor, 
        if 'labels' in actor_scene_dict:
          labels = actor_scene_dict['labels']
          for label in labels:
            if labels[label] == None:
                continue
            position = [0.0, 0.0, 0.0]
            ypr = [0.0, 0.0, 0.0]
            scale = 0.3
            color = [1.0, 1.0, 1.0]
            when = 'always'
            if 'text' in labels[label]  and labels[label]['text'] != None:
              text = labels[label]['text']
            if 'pos' in labels[label]  and labels[label]['pos'] != None:
              position = labels[label]['pos']
            if 'scale' in labels[label]  and labels[label]['scale'] != None:
              scale = labels[label]['scale']
            if 'ypr' in labels[label]  and labels[label]['ypr'] != None:
              ypr = labels[label]['ypr']
            if 'color' in labels[label]  and labels[label]['color'] != None:
              color = labels[label]['color']
            if 'faces_camera' in labels[label]  and labels[label]['faces_camera'] != None:
              faces_camera = labels[label]['faces_camera']
            if 'when' in labels[label]  and labels[label]['when'] != None:
              when = labels[label]['when']
            # Add the label to the node
            label = node.add_label(
                name=label,
                text=text,
                position=position,
                ypr=ypr,
                scale=scale,
                color=color,
                faces_camera=faces_camera,
                when=when
                )

        return node, parent_name

    def create_trail(self, node, actor_scene_dict=None):
        """Create a trail for node and assign it

        Creates a trail_actor (which also stores it inside node)
        """
        trail = None
        if 'trail' in actor_scene_dict and actor_scene_dict['trail'] != None:
          if 'enabled' in actor_scene_dict['trail'] and actor_scene_dict['trail']['enabled']:
            color = [1.0, 1.0, 1.0]
            thickness = 2
            opacity = 1.0
            if 'color' in actor_scene_dict['trail']:
              color=actor_scene_dict['trail']['color']
            if 'thickness' in actor_scene_dict['trail']:
              thickness=actor_scene_dict['trail']['thickness']
            if 'opacity' in actor_scene_dict['trail']:
              opacity=actor_scene_dict['trail']['opacity']
            trail = node.create_trail(color=color, thickness=thickness,
                                      opacity=opacity)
        return trail

    def initialize_nodes(self, fncc=VirgoSceneNode, ancc=VirgoSceneNode,
                         vncc=VirgoSceneNodeVector):
        """
        Create the actors and VirgoSceneNodes associated with entries in
        the scene dictionary and initialize their configurable parameters. Then
        add them all to self.nodes and pass them into self.controller so that
        they can be accessed at runtime.

        Params:

        fncc: "Frame Node Custom Class". A python class inheriting from
              SceneNode to instantiate instead of the default. This is used
              for extending SceneNode functionality.

        ancc: "Actor Node Custom Class". A python class inheriting from
              SceneNode to instantiate instead of the default. This is used
              for extending SceneNode functionality.

        vncc: "Vector Node Custom Class". A python class inheriting from
              SceneNode to instantiate instead of the default. This is used
              for extending SceneNode functionality.
        """
        nodes_to_add = []
        frames = {}
        if 'frames' in self.scene and self.scene['frames'] != None:
          for f in self.scene['frames']:
            frames[f] = {} # Frames have no actor
            node, parent_name = self.create_node(actor=None,
                                actor_scene_dict=self.scene['frames'][f],
                                _class=fncc)
            node.set_name(f)
            node.set_axes_pickable_on()

            pos=[0.0, 0.0, 0.0]
            ypr=[0.0, 0.0, 0.0]
            if 'pos' in self.scene['frames'][f]:
                pos=self.scene['frames'][f]['pos']
            if 'ypr' in self.scene['frames'][f]:
                ypr=self.scene['frames'][f]['ypr']
            # A frame's origin is moved to the pos/ypr given. Note that this
            # is different than the pos/ypr of an actor which is a static offset
            # of the mesh relative to it's node.
            node.set_pose(pos=pos, ypr=ypr)
            nodes_to_add.append( (node, parent_name) )

        actors = {}
        trails = {}
        if 'actors' in self.scene and self.scene['actors'] != None:
          for a in self.scene['actors']:
            actors[a] = self.create_actor(actor_name=a, actor_scene_dict=self.scene['actors'][a])
            actors[a].initialize()
    
            node, parent_name = self.create_node(actor=actors[a],
                                                 actor_scene_dict=self.scene['actors'][a],
                                                 _class=ancc)
            nodes_to_add.append( (node, parent_name) )
            trail = self.create_trail(node, actor_scene_dict=self.scene['actors'][a])
            if trail:
                trails[a] = trail

        vectors = {}
        if 'vectors' in self.scene and self.scene['vectors'] != None:
          for v in self.scene['vectors']:
            vectors[v] = self.create_vector(vector_name=v, vector_scene_dict=self.scene['vectors'][v])
            vectors[v].initialize()
            node, parent_name = self.create_node(actor=vectors[v],
                                                 actor_scene_dict=self.scene['vectors'][v],
                                                 _class=vncc)
            # A vector is a special VIRGO_PREFAB:arrow actor that cannot specify rotations
            if node.data_source._rotations is not None:
                msg = (f"ERROR: vector {v} should not specify rotations as they are computed automatically")
                raise RuntimeError (msg)
            nodes_to_add.append( (node, parent_name) )

        self.populate_nodes(nodes_to_add)

        # Pass the nodes/actors into the controller for runtime use
        self.controller.set_actors(actors)
        self.controller.set_vectors(vectors)
        self.controller.set_frames(frames)
        self.controller.set_nodes(self.nodes)
        self.controller.set_trails(trails)

    def populate_nodes(self, nodes_to_add):
        """
        Add nodes to self.nodes in root to leaf order

        nodes_to_add is a list of  [ (node, parent_name of that node), ... ]

        Nodes must be added to self.nodes in root-to-leaf order, otherwise
        parent nodes might not exist when the internal add_child() call runs
        """
        pending = list(nodes_to_add)
        added = set()

        while pending:
            progress = False
            for (node, parent_name) in pending[:]:
                if parent_name is None or parent_name in self.nodes:
                    self.add_node(node, parent_name)
                    added.add(node.name)
                    pending.remove((node, parent_name))
                    progress = True
            if not progress:
                raise RuntimeError(
                    f"Could not resolve parents for nodes: "
                    f"{[n.name for n, _ in pending]}"
                )

    def run(self):
        """
        The entrypoint for starting up a rendered window
        """

        if not self.controller.is_initialized():
            print("ERROR: Scene is not properly initialized. Exiting.")
            return(1)
        if self.verbosity > 0:
            self.report()
    
        if self.headless:
            self.run_headless(stop_time=self.stop_time)
        else:
            if self.verbosity > 0:
                print("Entering render window and interactor loop...")

            if self.splash == True:
                splash = VirgoSplash(self.render_window, self.interactor)
                splash.show_splash()

            self._run_interactive()

        self.tear_down()
        return 0

    def report(self):
        # Get some diagnostics about how much RAM we are using
        cprint(f"Scene: {self.name}", bold=True)
        cprint(f"Description:", bold=True)
        cprint(textwrap.indent(f"{self.description}", "  "), bold=True)
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 ** 2  # RSS = Resident Set Size
            cprint(f"Current RAM usage: {memory_mb:.2f} MB")
        except Exception as e:
            pass

    def _run_interactive(self):
        self.render_window.Render()
        self.interactor.Start()

    def run_headless(self, stop_time=None):
        if not stop_time:
            stop_time = self.controller.max_sim_time 
        if self.controller.world_time >= stop_time:
            print(f"Nothing to render in headless mode. Starting world time "
                  f"{self.controller.world_time} >= stop time {stop_time}. "
                  f"This is often caused by all actors/nodes being static "
                  f"(no driven_by: section) in the scene dict.")
            return
        self.controller.mode = 'PLAYING' # Force playing
        finished = False
        frame_num = 0
        percent_complete = 0.0
        # Dump frames for the scene
        sys.stdout.write(f'Generating frames:')
        tmp_dir = tempfile.mkdtemp()
        while not finished:
          percent_complete = self.controller.world_time / stop_time * 100.0
          #import pdb; pdb.set_trace()
          sys.stdout.write(f'\rGenerating frames in {tmp_dir}: {percent_complete:8.2f}%')
          sys.stdout.flush()  # Ensure it updates immediately
          self.controller.update()
          filename = os.path.join(tmp_dir,
                                f"frame_{frame_num:07d}.png")
          self.controller.save_frame(filename=filename)
          frame_num += 1
          if math.isclose(self.controller.world_time, stop_time):
            finished = True
        percent_complete=100.0
        sys.stdout.write(f'\rGenerating frames in {tmp_dir}: {percent_complete:8.2f}%\n')

        # Render an mp4 video file
        try:
          import imageio
        except Exception as e:
          msg = (f"ERROR: imageio not found in virtual environment, cannot render"
                 f" images in {tmp_dir} to video file {self.video_filename}.")
          print(msg)
          raise(e)
        print(f"Rendering {self.video_filename} ...")
        frames = [imageio.imread(f"{tmp_dir}/frame_{i:07d}.png")
                   for i in range(frame_num)]
        imageio.mimsave(self.video_filename, frames, fps=self.controller.frame_rate)
        print(f"Done.")


    def tear_down(self):
        # TODO: do we need to RemoveAllObservers() for the self.camera too?
        #self.cameras['foreground'].AddObserver("ModifiedEvent", self.sync_cameras)
        # TODO: do we need to destroy the timer? with self.interactor.DestroyTimer(self.timer_id)
        #self.timer_id = self.interactor.CreateRepeatingTimer(self.callback_rate)

        # David Gobbi from VTK team recommends "call
        # interactor.DestroyTimer(timerId) for every timer that you create
        # before the interactor goes out of scope and destructs"
        if self.controller.timer_id:
            self.interactor.DestroyTimer(self.controller.timer_id)
        #for camera in self.controller.cameras:
        #    self.controller.cameras[camera].RemoveAllObservers()

        #sys.stderr.write(f'\nDEBUG: Removing all observers for interactor...')
        #self.interactor.RemoveAllObservers()
        #sys.stderr.write(f'Done.')
        #for renderer in self.renderers:
        #    sys.stderr.write(f'\nDEBUG: Removing all observers for renderer {renderer}...')
        #    self.renderers[renderer].RemoveAllObservers()
        #    sys.stderr.write(f'Done.')

        ## Mark for deletion
        #del self.interactor
        #self.interactor = None
        #for renderer in self.renderers:
        #    del renderer
