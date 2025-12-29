#!/usr/bin/env python3
import datetime
import numpy as np

import sys, os, argparse, yaml, inspect
# Add location of VIRGO code to sys.path so we can import classes
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
sys.path.append(os.path.abspath(os.path.join(thisFileDir, '../../')))
# Import the only VIRGO class we need
from Virgo import VirgoScene, VirgoControlCenter
from VirgoNode import VirgoSceneNode

class VirgoScreenSaverControlCenter(VirgoControlCenter):
  """
  Derived class extending the VirgoControlCenter class. This provides
  an example of how to extend the controller mechanism of VIRGO to
  implement custom functionality.
  """
  def __init__(self, renderers, render_window, interactor, scene,
            weather_api_key, zip, world_time=0.0, images_dir=None):
    self.weather_api_key = weather_api_key
    self.zip = zip
    super().__init__(renderers=renderers, render_window=render_window,
                     interactor=interactor, scene=scene)
    self.rotation_speed = 0.05
    self.text_actors = {}
    self.text_actors['thetime'] = self.create_overlay_text_actor()
    self.text_actors['thetime'].GetTextProperty().SetFontFamilyToArial()
    self.text_actors['thetime'].GetTextProperty().SetBold(1)
    self.text_actors['thetime'].GetTextProperty().SetFontSize(50)
    self.text_actors['thetime'].GetTextProperty().SetColor(0.0, 0.4, 0.0)
    self.text_actors['weather'] = self.create_overlay_text_actor()
    self.text_actors['weather'].GetTextProperty().SetFontFamilyToArial()
    self.text_actors['weather'].GetTextProperty().SetFontSize(50)
    self.text_actors['weather'].GetTextProperty().SetColor(0.5, 0.5, 0.5)
    self.text_actors['weather'].GetTextProperty().SetBold(1)
    self.API_KEY = self.weather_api_key
        
  def configure_hud(self):
    """
    Overrides base class to do nothing. This let's a right-click pick still
    work but without the HUD interaction
    """
    pass

  def on_key_press(self, caller, event):
    """
    Overrides base class to provide a more limited key press functionality
    """
    key = self.interactor.GetKeySym()
    print(f'DEBUG: Key pressed: {key}')
    if key == 'a':
        # Turn actor axes on/off
        self.toggle_axes()
    if key == "V":
        # Verbosely print state of all non-text actors
        for n in self.nodes:
            # Call report() on root nodes only since they recurse
            if self.nodes[n].parent == None:
                self.nodes[n].report()
    if key == "c":
        self.toggle_camera_modes()
        self.camera_report()
    if key == 'l':
        # Turn actor axes on/off
        self.toggle_lighting_modes()
    if key == 'equal':
        self.fontsize('up')
    if key == 'minus':
        pass
        self.fontsize('down')
    if key == "space":
        self.handle_pause_button()

  def handle_pause_button(self):
    """
    If paused, go to playing. If playing, go to paused.

    Overrides the base class function.
    """
    if self.mode == 'PAUSED':
      self.mode = 'PLAYING'
    else:
      self.mode = 'PAUSED'

  def initialize(self):
    """
    Overrides base class initialize() to add additional customizations at
    init. Specifically we want to also acquire information about the weather
    when this class initializes.
    """
    super().initialize()
    self.weather = self.get_weather(self.zip)
    # Auto-adjust clipping range. With large bodies in the scene this ensures
    # they'll show up when the scene starts
    self.renderers['foreground'].ResetCameraClippingRange()

  def get_weather(self, zip_code):
    """
    A function that returns a string summarizing the weather for the
    given zip_code. This authenticates with openweathermap.org to
    get the information which requires an API key that can be created
    with a free account.
    """
    import requests
    import json
    country_code = 'US'
    units = 'imperial' # 'imperial' for F, 'metric' for C
    
    # Construct the API URL
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    url = f"{base_url}?zip={zip_code},{country_code}&appid={self.API_KEY}&units={units}"
    
    try:
      # Make the API request
      response = requests.get(url)
      response.raise_for_status() # Raises an error for bad responses (4xx or 5xx)
      # Parse the JSON response
      data = response.json()
      # Extract the relevant weather data
      description = data['weather'][0]['description']
      temp = data['main']['temp']
      humidity = data['main']['humidity']
      wind_speed = data['wind']['speed']
      city_name = data['name']
      # Build the string to return, centering each line in 100-character blocks
      ret_str = (f"{description} in {city_name.lower()}".center(100) + "\n")
      ret_str += (f"{temp}°F @ {humidity} % humidity".center(100) + "\n")
      ret_str += (f"wind @ {wind_speed} mph".center(100))
      return (ret_str)
    
    except requests.exceptions.HTTPError as err:
      ret_str = (f"Weather retrieval error occurred: {err}")
      print(ret_str)
      return(f"{ret_str[:32]}, see console")
    except Exception as e:
      print(f"An error occurred: {e}")

  def display_weather(self):
    """
    Set the weather text actor input text and position it in the lower
    center of the screen
    """
    self.text_actors['weather'].SetInput(self.weather)
    hud_padding = 20 # pixels
    window_width, window_height  = self.render_window.GetSize()
    # Get the text bounding box in display coordinates  [xmin, xmax, ymin, ymax]
    bounds = [0] * 4
    self.text_actors['weather'].GetBoundingBox(self.renderers['foreground'], bounds)
    text_width = bounds[1] - bounds[0] + 1  # Width in pixels
    text_height = bounds[3] - bounds[2] + 1  # Height in pixels
    # Calculate position for bottom-center with padding
    x_pos = (window_width/2.0 - text_width/2.0)  # Right edge minus width
    y_pos = hud_padding  # Bottom edge (20 pixels from bottom)
    self.text_actors['weather'].SetPosition(x_pos, y_pos)

  def display_time(self):
    """
    Get the current time, set the thetime text actor input text and
    position it in the upper center of the screen
    """
    now = datetime.datetime.now()
    # Choose any format you like
    time_str = now.strftime("%I:%M %p")     # 12-h with AM/PM
    date_str = datetime.date.today()
    self.text_actors['thetime'].SetInput(f"{date_str}   {time_str}")
    # Position thetime in the HUD
    hud_padding = 20 # pixels
    window_width, window_height  = self.render_window.GetSize()
    bounds = [0] * 4 # Get the text bounding box in display coordinates  [xmin, xmax, ymin, ymax]
    self.text_actors['thetime'].GetBoundingBox(self.renderers['foreground'], bounds)
    text_width = bounds[1] - bounds[0] + 1  # Width in pixels
    text_height = bounds[3] - bounds[2] + 1  # Height in pixels
    # Calculate position for bottom-right corner with padding
    x_pos = (window_width/2.0 - text_width/2.0)  # Right edge minus width
    y_pos = window_height - text_height - hud_padding  # Bottom edge (20 pixels from bottom)
    self.text_actors['thetime'].SetPosition(x_pos, y_pos)

  def camera_follow(self, node, initial_offset=None):
    """
    Extend the base class camera_follow() function to add a gentle rotation
    about the focal point. The focal point can be changed by right-click
    picking the actor and pressing 'c' to focus the camera on it.
    """
    super().camera_follow(node)
    self.cameras['foreground'].Azimuth(self.rotation_speed)
    if self.camera_follows:
        pos=np.array(self.camera_follows.get_world_position())
        self.cameras['foreground'].SetFocalPoint(pos[0], pos[1], pos[2])
    # Tell the VirgoInteractorStyle instance about our new camera position
    self.interactor.GetInteractorStyle().StoreRelativeCameraInfo(None, None)

  def update(self):
    """
    Overrides the base class update() function to provide a custom main
    update loop. Noteably this skips the standard HUD information and
    adds two custom text overlays - one for time and one for weather
    """
    self.display_time()
    self.display_weather()
    if self.mode == 'PLAYING':
        self.update_nodes()
        self.camera_follow(self.camera_follows)

class VirgoScreenSaver(VirgoScene):
  """
  Derived class extending the VirgoScene base class. This provides
  an example of how to extend the Scene mechanism of VIRGO to
  implement custom functionality. In this particular use-case,
  we just need to replace the controller with a custom controller
  we define (VirgoScreenSaverControlCenter).
  """
  # Tell the VirgoScene to use a custom class for the self.controller
  controller_class = VirgoScreenSaverControlCenter
  def __init__(self, scene, weather_api_key, zip, verbosity=2):
    """
    Override the base class initializer to add some weather
    functionality
    """
    self.weather_api_key = weather_api_key
    self.zip = zip
    # controller_kwargs is optional, but if specified these additional
    # arguments are passed to self.controller's construction
    controller_kwargs = {'weather_api_key':self.weather_api_key,
                         'zip':self.zip}
    super().__init__(scene=scene, verbosity=verbosity,
                     controller_kwargs=controller_kwargs)

  def initialize_nodes(self):
    """
    Overrides the base class initialize_nodes() by calling that
    same function with a custom scene node type defined in this
    file. This tells Virgo to instantiate ScreenSaverNodes for
    all actors in the node tree instead of the default SceneNodes
    """
    super().initialize_nodes(ancc=ScreenSaverNode)
    # Move the earth to a realistic distance away in Y-dir
    self.nodes['earth'].set_pose([0.0, 384000000, 0.0])


class ScreenSaverNode(VirgoSceneNode):
  """
  Derived class extending the VirgoSceneNode base class. This allows
  the user to adjust how individual nodes are created and processed.
  This is how you would add functionality to VirgoSceneNode.update()
  (or other functions) if the core VIRGO functionality is insufficient
  """
  def __init__(self, name=None, actor=None, axes=True):
    super().__init__(name=name, actor=actor, axes=axes)
    self.message_printed = False

  def update(self, world_time):
    """
    Overrides the base class update() function to not execute any real update
    logic. Because our screensaver extension never moves an actor, we can
    simply skip that logic entirely. A print is executed telling the user the
    extension of update() has been reached.
    """
    if not self.message_printed:
      print(f"In {self.name}'s ScreenSaveNode.update() and nothing "
            f"to do, so doing nothing!")
      self.message_printed = True
    return
        

class MyScreenSaver:
  """
  Top level management class for the screensaver application which uses
  VIRGO under the hood
  """
  def __init__(self, args=None):
    self.parse_args(args=args)
    with open(self.args.scene_config) as file:
        scene = yaml.safe_load(file) 
    self.v = VirgoScreenSaver(scene=scene,
                              weather_api_key=self.args.weather_api_key,
                              zip=self.args.zip)
    self.v.initialize()

  def parse_args(self, args=None):
    """
    Parse the command line arguments.  Param: arg defaults to None which
    means parse real cmd-line args, but allowing it to be passed in helps
    with the ability to unit test this class, so it's implemented this way
    as a best practice.
    """
    parser = argparse.ArgumentParser(description=
            'Start up a VIRGO-based screensaver',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
            )
    parser.add_argument("--scene-config", help="YAML config file to load",
                        default=os.path.join(thisFileDir,'scene.yml'))
    parser.add_argument("--zip", help="Zip code to use for weather",
                        default=77058)
    parser.add_argument("--weather-api-key",
                        help="API key for openweathermap.org authenitcation",
                        default='5b3da7d3c5d7003bec78b3a2f20bf711')
    self.args = parser.parse_args(args=args)

  def execute(self):
    """
    Start the Virgo 3D scene
    """
    return(self.v.run())

if __name__ == '__main__':
  sys.exit(MyScreenSaver().execute())
