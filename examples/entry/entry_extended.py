#!/usr/bin/env python3
import sys, yaml

# Import assets from entry.py
from entry import EntryExample, get_args

# Import VIRGO classes we need
from VirgoDataPlayback import VirgoDataPlayback
from VirgoLabel import VirgoLabel
from Virgo import VirgoControlCenter


class VirgoEntryControlCenter(VirgoControlCenter):
    """
    Derived class extending the VirgoControlCenter class. This provides
    an example of how to extend the controller mechanism of VIRGO to
    implement custom functionality. In this case, the custom functionality
    is adding labels to parts of the atmosphere as the spacecraft passes
    through them.
    """
    def __init__(self, renderers, render_window, interactor, scene,
                world_time=0.0, images_dir=None):
        super().__init__(renderers=renderers, render_window=render_window,
                         interactor=interactor, scene=scene)

        self.text_scale_factor = 0.05  # Scale applied to text before it renders
        # Dict of where each atmopshere layer begins (altitude meansured in
        # meters) when approaching the surface of earth from space
        self.altitude_layers = {
            'Thermosphere' : 400000,
            'Mesosphere' : 50000,
            'Stratosphere' : 30000,
            'Troposphere' : 10000,
            'Near Surface' : 100
            }
        # Copy of this dict - will be reduced in key/value pairs as we cross the layers
        self.remaining_altitude_layers = dict(self.altitude_layers)

    def initialize(self):
        """
        Extends base class initialize() to add additional customizations at
        init. Specifically we want to also acquire information about the weather
        when this class initializes.
        """
        super().initialize()
        self.create_altitude_texts()

    def create_altitude_texts(self):
        """
        Create VirgoLabels for each layer of the atmosphere. This just creates them,
        and defines their yaw-pitch-roll orientation relative to world coordinates.
        The labels are positioned in the update_scene() function
        """
        self.altitude_texts = {}
        for l in self.altitude_layers:
          self.altitude_texts[l] = VirgoLabel(name=l,text=f"{l} reached")
          self.altitude_texts[l].set_yaw_pitch_roll([-90, 0, 0])
          self.altitude_texts[l].set_scale(1.0e4) # Default size of text
          self.altitude_texts[l].enable()
          self.renderers['foreground'].AddActor(self.altitude_texts[l].get_follower())

    def update(self):
        """
        Extends the base class update() function to provide a custom main
        update loop which adds additional behavior. The additional behavior is to
        look for the spacecraft crossing particular altitudes and position labels
        at the crossing point.
        """
        super().update()
        current_altitude = self.nodes['satellite'].data_source.get_additional_data('sat_alt')
        remove_this_layer = None
        for l in self.remaining_altitude_layers:
            # If the text hasn't yet been positioned and the satellite node is crossing
            # the boundary where the layer starts, position the label at the current
            # location of the satellite node
            if current_altitude < self.remaining_altitude_layers[l]:
              node_world_position = self.nodes['satellite'].get_world_position()
              print(f"Moved label {l} to {node_world_position}")
              self.altitude_texts[l].set_position(node_world_position)
              text_scale = current_altitude  # Scale the text based on current altitude
              self.altitude_texts[l].set_scale(text_scale*self.text_scale_factor)
              remove_this_layer = l
              break

        # Remove the labeled layer, excluding it from future consideration
        if remove_this_layer:
            del self.remaining_altitude_layers[remove_this_layer]

class EntryDataPlayback(VirgoDataPlayback):
    """
    Extend the VirgoDataPlayback base class to allow the override of the default
    self.controller. Note that although self.controller is set in
    VirgoDataPlayback's base class VirgoScene.__init__(), it's reassigned to a
    custom controller (VirgoEntryControlCenter) defined in this file.
    """
    # Tell the VirgoScene to use a custom class for the self.controller
    # See VirgoScene.controller_class for details
    controller_class = VirgoEntryControlCenter
    def __init__(self, run_dir, scene, verbosity=1, headless=False,
                 images_dir="/tmp/", video_filename="/tmp/virgo.mp4", splash=True):

        super().__init__(run_dir=run_dir, scene=scene, verbosity=verbosity,
                         headless=headless, images_dir=images_dir,
                         video_filename=video_filename, splash=splash)

class ExtendedEntryExample(EntryExample):
    """
    Extend the base class defined in entry.py. This is done only to leverage
    functions defined in that file and also to replace self.v with our custom
    extended EntryDataPlayback instance
    """
    def __init__(self):
        args = get_args()
        self.generate_trajectory()
        with open(args.scene_config) as file:
            scene = yaml.safe_load(file) 
        # VirgoDataPlayback is the VirgoScene we want because it's built
        # to consume TrickPy-compatible data, which log_Satellite.csv meets
        self.v = EntryDataPlayback(run_dir=args.data_dir, scene=scene,
                                    headless=args.headless,
                                    video_filename=args.video_filename)
        self.v.initialize()

if __name__ == '__main__':
    sys.exit(ExtendedEntryExample().execute())
