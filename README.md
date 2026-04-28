# VIRGO

VIRGO: **V**ersatile **I**maging and **R**endering for **G**alactic **O**perations. A practical, analytical, and hardworking engineering visualization tool leveraging python-VTK.  Designed by and for engineers at NASA JSC (Johnson Space Center), VIRGO gives users insight into simulation data when typical 2D plots are insufficient. This project is developed specifically for engineers in the Guidance, Navigation, and Control (GNC) division of the Engineering Directorate but aims to provide functionality for the [Trick](https://github.com.nasa/trick)-using community and beyond. 

![virgo1](images/doc/virgo_example1.png)
![virgo2](images/doc/virgo_example2.png)

VIRGO intends to be an extensible, well-tested, and robustly documented python module which can consume simulation data in different ways. However, **VIRGO is currently in *alpha* status which means it has not yet been verified or validated in any way. Use caution when using VIRGO visualizations to draw conclusions about your engineering application. It is highly recommended that you cross-reference what you are seeing with other plotting or visualization tools before using a VIRGO scene to make an engineering decision.**

## A simple VIRGO example

The simplest data source supported is a typical `*.csv`  (comma-separated-value) text file containing a time history of object positions in 3D space. For example, imagine you had a file `log_state.csv` that describes the motion of a satellite in space and looks like this:

```csv
time {s},  position[0] {m},  position[1] {m},  position[2] {m},
     0.0,              0.0,              0.0,              0.0, 
     1.0,              5.0,              5.0,              5.0, 
     2.0,             10.0,             10.0,             10.0, 
     3.0,             20.0,             20.0,             20.0, 
     4.0,             30.0,             30.0,             30.0, 
```
The first line describes what the variables are and their `{units}`. All other lines provide monotonically increasing time values and position values at those times.  VIRGO can read this file and playback the position of the object described by the `position` array over the timeframe 0.0 - 4.0 seconds. In this example the x-position is `position[0]`, y-position is `position[1]`, and z-position is `position[2]` . In VIRGO terminology this file is considered a simple **data source**.

The **scene** defines what **actors** (the rendered objects) look like and links that object to a **data source**. VIRGO defines scenes using python dictionaries which are easily expressed as YAML files that look like this:

```yaml
# This section defines what objects (actors) are in the scene
# In this example there is only one actor named satellite
actors:
  satellite:           # User-defined name for this actor
    mesh: VIRGO_PREFAB:cube  # 3D representation of the object, a cube
    scale: 1.0         # The cube is 1 unit wide/tall/deep
    # This subsection defines what data source alias drives the actor
    driven_by:
      time: sim_time # Time is defined as sim_time: from section below
      pos: sat_pos   # Position is defined as sat_pos alias in section below

# This section defines what to read from a trickpy data source which is a data
# source supported by VIRGO specifically intended to read simulation data
# provided by https://github.com/nasa/trick simulation, but it also supports
# simple CSV files using the expected Trick format shown above
data_source:
  trickpy:
    sim_time:      # User-defined alias for simulation time
      group: state # 'state' comes from the filename: log_state.csv
      var: time    # The name for time (1st column 1st row of log_state.csv)
    sat_pos:       # User-defined alias for satellite x,y,z position values
      group: state       # 'state' comes from log_state.csv
      var: position[0-2] # Variables comprising sat_pos alias
```
This tiny example gives you a sense of what VIRGO can do. Any integer or floating point data can be consumed and used in VIRGO in various ways. 

## Features

Here are some things you can do with VIRGO:
1. Drive positions and orientations of **VIRGO actors** with respect to inertial space and/or relative to another actor. There is no limit to the number of actors in the scene beyond what your computer hardware can handle.
2. Use prefabricated meshes (cube, sphere, cylinder, etc.) to represent actors or provide your own mesh with `*.stl` or `*.obj` files
3. Visualize vectors that change over time in 3D space using **VIRGO vectors**
4. Display simulation data as text in the 3D scene using **labels**
5. Show where a **VIRGO actor** has been in world space by enabling **VIRGO trails**
6. Play, pause, and adjust playback speed
7. Step forward and backward through data while paused
8. Choose from multiple lighting modes including light from a sun positioned by simulation data

If your use case needs more capabilites, see the [extending virgo](#extending-virgo) section below


## Module Dependencies

This module requires python3.11 or later and the `pip` packages listed in `requirements.txt`. To pull down these packages to a standard python3 virtual environment run the following in the directory you wish to create the `.venv`:
```bash
# Create a python3 virtual environment using python3.11 or later
python3 -m venv .venv && source .venv/bin/activate 
# Install virgo dependencies
pip3 install --upgrade pip && pip3 install -r requirements.txt
```
Once the `.venv` is created, you can source the environment in any shell before running scripts using VIRGO:

```bash
source .venv/bin/activate
```
## Terminology

* **A VIRGO Scene** is a python dictionary (often expressed as a YAML file) that fully articulates the details of the 3D configuration that will be rendered and displayed to the user. This is the main method of configuration provided to the users of VIRGO and includes a list of `actors:`, `vectors:`, `frames:` as well as settings within the scene like lighting, data sources, labels, etc.
* **A VIRGO Interactive Window** is the result of running the VTK Renderer and Interactor loops. This is the primary display for the user showing everything provided in the **VIRGO Scene**. The interactive window responds to various keyboard and mouse inputs from the user. Press 'h' while the window is up for information on keyboard/mouse inputs.
* **VIRGO Actors** are 3D objects rendered in the scene and are defined by the `actors:` section of the scene dictionary. They can be positioned and oriented statically in the scene or driven by data sources.
  * **VIRGO Vectors** are **VIRGO Actors** that must be represented as an arrow in 3D space. Vectors are defined in the `vectors:` section of the scene dictionary and accept a position value which defines the tip of the vector to be drawn. 
  * **VIRGO Frames** are **VIRGO Actors** that have no mesh geometry. You can think of them as a reference frame positioned and oriented relative to some other reference frame or the world coordinates origin if the frame has no parent.
* **World Coordinates** refer to the root 3D reference frame in the VIRGO window provided by VTK. This is akin to "inertial coordinates" in the engineering domain. Note that VTK and therefore VIRGO are unitless, which requires the user to ensure a consistent unit system is used across all actors in the scene.
* **VIRGO Nodes** define the scene graph tree by managing **VIRGO Actors, Frames, and Vectors** as well as their position and orientation with respect to their parent or world coordinates if no parent is defined. Every actor, frame, and vector is automatically assigned and parented to a unique node of the same name. When objects move in a VIRGO scene it's usually because their underlying **VIRGO Node** is moving through space.  
* **Parents** allow nodes containing actors, frames, and vectors, to be defined relative to another actor, frame, or vector, by defining a `parent:` relationship. If a node has a parent that means all transformations on that node will be performed relative to that parent. Nodes and their parental relationships fully define one or more [directed acyclic graph trees](https://en.wikipedia.org/wiki/Tree_(graph_theory)) which contain all the information needed to determine world position/orientation of any actor in the scene.
* **Root nodes** are nodes have no parents and therefore are positioned and oriented with respect to world coordinates (often considered inertial space)
* **Data Sources** provide engineering data associated with actors, frames, and vectors. Typically this amounts to variable values at specific simulation times, for example the position of a cube over a 10 second period can be articulated in a simple comma-separated-value  `*.csv` file. VIRGO data sources can be linked to labels as well.
* **Labels** allow the user to display text positionally within the 3D scene. Each **VIRGO Actor, Vector, and Frame** may optionally define `labels:` to render static text or information from a **data source** as the user sees fit.
* **World Time** refers to the time in the scene shown in the top left of the HUD. Note that this may not perfectly align with data from a **data source**. The lower left HUD shows verbose data from the data source when an actor is picked with right mouse click.

### Actors

Actors, terminology borrowed from VTK itself, are the objects in the 3D scene. A `VirgoActor` inherits from the [vtkActor](https://vtk.org/doc/nightly/html/classvtkActor.html) class provided by VTK, adding some useful functionality to that base class.  Just like in a movie, actors are placed into a scene and have a defined position and orientation relative to the world coordinate origin (0,0,0). Those positions and orientations may or may not change over time, and we only need a time history of these parameters to visualize an animation of an actor in 3D space. There are actually more parameters than just position and orientation - scale (size of the object) and opacity (transparency level between 0.0 and 1.0) are also attributes of an actor that can be set statically, or observed over time using the `driven_by:` clause.

#### `mesh:`

The `mesh:` section of an actor's dictionary defines what the 3D geometry looks like and should either be a named `VIRGO_PREFAB` or a path to a 3D geometry file (`*.stl` or `*.obj`). Tools like [blender](https://www.blender.org/) can be used to create 3D meshes and exported to these supported file formats.

#### VIRGO_PREFAB meshes

One of the most useful user facing features is the list of provided `VIRGO_PREFAB` mesh choices that allow for quick and easy creation of an actor and it's associated 3D geometry. This list and their capabilies are currently under development, but a quick `grep VIRGO_PREFAB VirgoActor.py` will give you a good place to start exploring prefabricated meshes. 

Prefabs should be specified in the `mesh:` section of an actor's dictionary, for example if you wanted a box in your scene represented as a cube, you would specify it like this:

```yaml
actors:
  my_box:                      # User-defined name for this actor
    mesh: VIRGO_PREFAB:cube    # 3D representation of the object, a cube
    scale: 3.0                 # The cube is 3 units wide/tall/deep
    color: [0.54, 0.27, 0.074] # The box is brown (rgb 0.0->1.0)
```

Another example, if you are building a scene in outer space, you might want an earth in your scene, you can do that with a section that looks like this:

```yaml
actors:
  earth:                      # User-defined name for this actor
    mesh: VIRGO_PREFAB:earth  # Use low-resolution earth prefab texture
    scale: 1.0                # The earth is already 6378137 meters big so 
                              # there's no need to change this unless your
                              # scene is using imperial units
```

See also the `examples/` section which uses most if not all of the prefabs available.

#### `driven_by:`

An actor's optional `driven_by:` clause is used to define which data aliases map to which parameters of the actor. This is how you tell an actor how to move over time.  Here's a simple `ball` actor which is configured to have it's position driven by `ball_pos`:
```yaml
actors:
  ball:
    driven_by:
      time: sim_time  # Time is defined as sim_time: from section below
      pos: ball_pos   # Position is defined as sat_pos alias in section below
```
See the [data_source: section](#configure-scenes-with-a-yaml-file) for more information on how `ball_time` and `ball_pos` aliases are defined. This section of the `ball:` actor tells VIRGO that the position of this actor should map to the time history of the `ball_pos` alias which is a 3-array (vector) of floating point values. For a ball moving in the X-direction over 5 seconds, internally the time history data looks something like this:

```csv
time, ball_pos[0], ball_pos[1], ball_pos[2], 
0.0,          0.0,         0.0,         0.0,
1.0,          1.0,         0.0,         0.0,
2.0,          2.0,         0.0,         0.0,
3.0,          3.0,         0.0,         0.0,
4.0,          4.0,         0.0,         0.0,
5.0,          5.0,         0.0,         0.0,
```
See the [driven_by: section of the full yaml file](#configure-scenes-with-a-yaml-file) for all possible `driven_by:` parameters.

#### `parent:`

Parents allow actors to be defined relative to other actors in position and orientation, and the parental relationship is defined in the dictionary using the `parent:` clause which contains the name of the other actor this actor is defined with respect to.  Consider this example - you have a simulation of a common carousel ride you see at theme parks. The entire ride rotates while individual seats move up and down. Let's simplify it and say there's only one seat.

In this example, our simulation provides the rotation of the floor of the carousel as a time history of a rotation matrix which we will assign to the VIRGO data alias `carousel_rot`. The simulation also provides the the position of the seat as a time history of vector of positions relative to the rotating floor, which we will assign to the VIRGO alias `seat_pos`. It is important to note that the simulation **does not provide** the position/orientation of the seat relative to inertial coordinates.

Here's what a VIRGO configuration for this simulation might look like:

```yaml
actors:
  carousel_disc:  # The floor of the ride which rotates
     mesh: VIRGO_PREFAB:cylinder
    driven_by:
      time: sim_time
      rot:  carousel_rot  # Data alias for rotation matrix of floor
  seat1:
    mesh: VIRGO_PREFAB:cube  # Represent the seat as a cube
    driven_by:
      time: sim_time
      pos: seat_pos       # Data alias for position of seat
    parent: carousel_disc
```
In this example, the `parent: carousel_disc` clause tells VIRGO that all `driven_by:` motion from `pos: seat_pos` is defined relative to `carosel_disc`, not in explicit world coordinates. If however the simulation did specify the seat motion (position and orientation) in inertial/world coordinates, this `parent:` relationship is no longer necessary, and this configuration could be used instead:

```yaml
actors:
  carousel_disc:  # The floor of the ride which rotates
     mesh: VIRGO_PREFAB:cylinder
    driven_by:
      time: sim_time
      rot:  carousel_rot  # Data alias for rotation matrix of floor
  seat1:
    mesh: VIRGO_PREFAB:cube  # Represent the seat as a cube
    driven_by:
      time: sim_time
      pos: seat_pos       # Data alias for position of seat
      rot: seat_rot       # Data alias for rotation of seat
```
In the VIRGO framework the `parent:` relationships end up defining [directed acyclic graph trees](https://en.wikipedia.org/wiki/Tree_(graph_theory)) as nested [`vtkAssembly`s](https://vtk.org/doc/nightly/html/classvtkAssembly.html) which allow objects in the scene to move relative to each other. Note that actors can also be parented to frames and vice-versa.

#### `pos:` and `ypr:`

For actors, the `pos:` and `ypr:` clauses allow you to define a position/rotation offset of the actor's mesh relative to the actor's local coordinate system. This can be helpful if the mesh coordinate system isn't correct for your usage and a simple rotation or position offset can fix it.  It's important to understand that driven actors which specify `pos:` and/or `ypr:` will still be `driven_by:` their local coordinate origin, not the new offset location defined by `pos:` and/or `ypr:`. Consider this example where the teapot actor has no `pos:` offset on the left, but a `pos: [3, 0, 0]` offset on the right:

![actor_offset_example](images/doc/actor_offset_example.png)

In both of these cases, the teapot's `driven_by:` clause will move the X-Y-Z coordinate origin.

### Frames

Frames are actors that have no mesh and are often used to define useful engineering coordinates systems associated with data you wish to visualize. These coordinate systems can be nested and referenced relative to each other using the `parent:` clause. Consider the following common aerospace example where an earth-fixed frame (a frame that rotates with the earth rotation) is parented to an earth inertial frame (a frame centered at earth that doesn't rotate):

```yaml
frames:
  # ECI (Earth Centered Inertial) frame - aligns with world coordinates
  eci_frame:
    pos: [0.0,0.0,0.0]  # No offset from world coordinate origin
    ypr: [0.0,0.0,0.0]  # No offset from world coordinate origin

  # ECEF (Earth Centered Earth Fixed) - rotates with the earth
  ecef_frame:
    parent: eci_frame
    driven_by:  # Actor position/rotation driven by these data aliases
      time: time
      rot: earth_rot
```
In this example, the `earth_rot` data alias is setup as a time history of [the RNP (Rotation Nutation Precession) matrix of earth](https://space-geodesy.nasa.gov/multimedia/videos/EarthOrientationAnimations/EOAnimations.html). With this configuration of frames, we can parent an earth actor directly to the `ecef_frame` and we'll see the earth move with that frame even though `earth:` has no `driven_by:` clause!

```yaml
actors:
  earth: 
    mesh: VIRGO_PREFAB:earth
    backface_culling: 1
    scale: 1.0
    pos:   [0.0, 0.0, 0.0]
    ypr:   [0.0, 0.0, 0.0]
    pickable: 0
    parent: ecef_frame
```
Cool beans man!  See `examples/launch/` for this ECI/ECEF frame representation in action.

One more important difference between `frames:` and `actors:` is how `pos:` and `ypr:` are interpretted. For actors, these represent an offset of the `mesh:` from the local origin coordinates of the actor, but for frames these represent the actual location of the frame relative to it's parent or world coordinates if no parent is given. Typically a frame is either specifying a static (non-changing) `pos:`/`ypr:` relative to it's parent **or** a dynamic `driven_by:` clause, not both.

### Vectors

Vectors are actors whose mesh must be a 3D arrow and these are used to represent traditional engineering vectors - typically a direction and a unit or non-unit magnitude.  Parameters for customizing the arrow's visual appearance are provided, see the [`vectors:` section of the YAML reference](#configure-scenes-with-a-yaml-file) for a full list of options.

Other differences specific to vectors and not actors are summarized as follows:
* The `mesh:` clause may not be specified for vectors
* [trail:](#trails) is not supported for vectors
* VIRGO vectors with a `driven_by:` clause may specify `time:` and `pos:` but not `rot:`. Note that `pos:` is the vector's X,Y,Z components relative to it's parent, or world coordiantes if no parent is specified. 

## Data Playback

TBD: Details on the playback rate and showing data at a particular world time go here.

## Trails

Trails are lines drawn between world coordinate points occupied by actors as they are encountered by changing the world time in the interactive scene. They show you where an actor has been in the past (or future if stepping backward) and are very useful for showing spacecraft orbits to end users.  Trails can be enabled/disabled with the `t` key and are completely reset when reaching the start/end boundary of simulation data associated with the scene. Trails are also reset if the world time is commanded to another location via `time <new_time>` in the console.

It's important to note that because VIRGO doesn't necessarily render every time step associated with simulation data, the visible trail may not be displaying all spatial points between two positions. For example if simulation data is provided every 1.0 seconds, but the playback speed is set to 1000X while trails are enabled, many simulation data points will be skipped as the scene renders data points only at the simulation data encountered rendered frame to rendered frame.

Additionally, trails are automatically created as segmented actors in the scene, which means if a trail gets long enough another segment is created until the segment buffer is full. This is still under development but allows for more realistic trails in very large scale scenes as these trail actors interact with the [rendering layers](#rendering-layers).

## Cameras

Currently VIRGO has support for a number of camera modes and the ability to define multiple cameras and switch between them. Cameras can be configured to follow `actors:`, `frames:`, or `vectors:` defined in the VIRGO scene using the `parent:` relationship. This parent relationship is recommended for spacecraft simulations since stationary cameras provide little value when objects are moving at orbital velocities. 

Cameras can be configured to operate in two modes: Trackball `mode: TB` or First-Person (`mode: FP`). In trackball mode, motion from click-dragging the mouse makes the camera orbit around a focal point. If `parent:` given, the focal point is configured to be the parent node. Otherwise use `focal_point:` to define where the camera points. In first-person mode, motion from click-dragging the mouse makes the camera rotate about it's own position in space, meaning the camera will not move allowing you to "look around" from a certain perspective. This mode combined with `static: 1` can simulate the real view from a fixed camera in your simulated scene.

See the [`camera:` section of the YAML reference](#configure-scenes-with-a-yaml-file) below for details on all camera parameters.

While using the interactive window the actor which a non-static camera is following (it's `parent:`) can be re-configured at any time by right-click picking the actor and pressing the `c` key. To unfollow an actor, right-click pick empty space and press `c`. To switch between first-person and trackball modes, press `C`.

## Lighting

While using the interactive window the lighting mode can be seen in the top-right part of the HUD. Lighting modes can be changed by pressing the `l` key - this will cycle between the supported lighting modes.

## Labels

Virgo labels allow the user to display arbitrary text in the 3D scene and can be toggled on/off through label-specific settings and the `L` keyboard shortcut. This can include static text or any simulation data defined in your scene's [data_source: section](#configure-scenes-with-a-yaml-file). See the `labels:` section in `examples/*/scene.yml` and the verbose [`labels:` section of the YAML reference](#configure-scenes-with-a-yaml-file) for details on all label parameters.

## Console

Press \` (backtick) to toggle the console and type `help` to see what commands are available. The console is a terminal-like method to manipulate a VIRGO scene in more complex ways. For example if you want to clear the trails, run `reset_trails`. If you want to jump to a particular time, type `time <value>` to go there. This feature is still under development and commands are likely to change over time, so check `help` for up to date information on using the console.

## Units

VIRGO (and the python-VTK code it's based upon) is unitless in nature which allows the user to work in any consistent units they find most useful.  For example, if you create a cube actor of size 10.0 positioned at (0,0,0) world coordinates, the cube has a width, height, and depth of 10.0 units.  It's on the user of VIRGO to decide what units are applicable and ensure all data entered into VIRGO is consistently represented in those units.

## Rendering layers

VIRGO manages multiple rendering layers behind the scenes as a way to combat [depth buffer](https://en.wikipedia.org/wiki/Z-buffering) [z-fighting](https://en.wikipedia.org/wiki/Z-fighting) and camera clipping constraints in scenes with very large and very small objects. User facing rendering layers are named 'foreground', 'midground', and 'background' and contain objects of appropriate distance away. The movement of these objects between layers is automatic - close objects are in the 'foreground' and as the camera moves further away they enter the 'midground' and 'background' accordingly. 

Trails follow suit but are a bit more tricky to implement as they are actors that can span large distances (the continuous line is a single actor in the VTK framework). Because of this trails are broken into logical segments/actors that can be moved individually between layers as the camera's distance to them changes over time. This provides a much better visual experience but you may find some cases where trails appear on top or behind objects when they aren't. If this happens try manipulating the camera to overcome it. You can see trail segment information by pressing 'd' to toggle debug info in the HUD.

## The Heads Up Display (HUD)

Details TBD

## Headless Mode (render directly to video)

Details TBD

## Examples

Standalone examples can be found under the `examples/` directory.  If you are new to VIRGO we suggest approaching the examples in this order, and be sure to see each directory's `README.md` for more detailed information.

* `hello_cube/` - A very simple static scene showing non-moving cubes used to demonstrate the basics of VIRGO scene navigation.
* `pendulums/` - A two-pendulum example demonstrating how VIRGO can consume data logged at multiple rates for each actor in a scene.
* `cannon/` - A simple cannonball simulation visualization inspired by the example sims in the [Trick tutorial](https://nasa.github.io/trick/tutorial/Tutorial).
* `satellite/` - A simple cube satellite in an equatorial orbit. This example shows how RCS jets firing can be visualized in a scene.
* `launch/` - A simplified launch from Kennedy Space Center (KSC) pad. This example shows the high resolution WGS-84 earth and KSC image/terrain patch mechanisms.
* `halo/` - A simple cube satellite in a halo orbit around the moon. This example provides an example of an orbital motion happening over approximately a week of simulation time.
* `entry/` - A cube satellite entering earth atmosphere and landing in the ocean. This scene provides an example of how the VIRGO framework can be extended with custom functionality.
* `screensaver/` - A simple screensaver example which depicts the earth and moon as well as current time and weather. This provides another example of how VIRGO can be extended with custom functionality.

## Configure Scenes with a YAML file

[YAML](https://yaml.org/) provides a handy way to define python dictionaries and track them as code in a human-readable form. Note that YAML is not required to use VIRGO but you will need to provide VIRGO with a **scene dictionary** which fully defines the scene that will be rendered. The terms **scene**, **yaml file**, and **dictionary** may be used interchangeably in VIRGO documentation - ultimately they all refer to the same thing.

Here we provide a YAML file template which describes in immense detail the sections of the scene dictionary recognized by the VIRGO framework. Use this reference in combination with `examples/*/scene.yml` as a starting point for setting up your scene. If you are unfamiliar with python dictionaries and how YAML can represent nested data structures we recommend you go through [this YAML tutorial](https://www.cloudbees.com/blog/yaml-tutorial-everything-you-need-get-started) before reading further.

```yaml
name:           # Optional string containing name of this scene
description:    # Optional string containing description of this scene
start_mode:     # Optional string, either PAUSED or PLAYING indicating how an 
                #   interactive window should behave when the window comes up
end_mode:       # Optional string, either PAUSED or PLAYING indicating how an 
                #   interactive window should behave when reaching the end of
                #   playback data
background_color:  # Optional list of 3 floats between 0.0-1.0 defining the
                   #   [red, green, blue] values of the background color of
                   #   the scene. Ex: [0.0, 0.0, 0.05] for very dark blue
highlight_color:   # Optional list of 3 floats between 0.0-1.0 defining the
                   #   [red, green, blue] values of the color actors/vectors
                   #   should show when picked/highlighted
hud_color:         # Optional list of 3 floats between 0.0-1.0 defining the
                   #   [red, green, blue] values of the color of the Heads-
                   #   Up-Display (text around the screen)
playback_speeds:   # Optional list of floats defining the playback speeds
                   #   supported by this scene. Ex: [1.0, 2.0, 10.0]
playback_speed:    # Optional float defining the default playback speed of
                   #   the scene when the window starts up
starfield:         # Optional integer 1 or 0 (true or false) for defining if
                   #   the scene should start up with a background starfield
data_source: # A dictionary which holds all data source definitions. Currently
             #   only trickpy: is officially supported
  trickpy:   # The dictionary for trickpy data sources. Each key is an alias
             #   defined by the user and their sub-dict group: and var: values
             #   define the Trick data recording group and variable for this
             #   alias. Three examples are provided below
    time:    # User-defined alias representing simulation time
      group: satellite         # 'satellite' comes from log_satellite.csv
      var: sys.exec.out.time   # Name of the time column in csv file
    sat_pos:                      # This alias represents inertial position
      group: satellite            # 'satellite' comes from log_satellite.csv
      var: dyn.satellite.pos[0-2] # Name of position columns in csv file.
                                  #   [0-2] is a shortcut meaning the 3-vector
                                  #   provided by [ dyn.satellite.pos[0],
                                  #   dyn.satellite.pos[1], dyn.satellite.pos[2]]
    sat_rot:                      # This alias represents inertial rotation
      group: satellite            # 'satellite' comes from log_satellite.csv
      var: R[0-2][0-2]            # Name of rotation matrix columns in csv file.
                                  #   [0-2][0-2] is a shortcut meaning the 3,
                                  #   3-vectors representing a 9-value direction
                                  #   cosine rotation matrix which transforms
                                  #   vectors from inertial coordinates to the
                                  #   actor frame. If using JEOD, this is often
                                  #   the 3x3 matrix named T_parent_this
    sat_vel:                      # This alias represents inertial velocity
      group: satellite            #   'satellite' comes from log_satellite.csv
      var: dyn.satellite.vel[0-2] # Name of velocity columns in csv file.

actors:     # The dictionary which holds all actors in the scene. The
            #   dictionary keys are the actor names. A single actor
            #   'my_actor' is shown here, and all fields under this indented
            #   block apply to all actors defined in your scene
  my_actor: # User-chosen name for actor which acts as the key for
            #   the individual actor sub-dict, defined below
    mesh:   # Required 3D mesh information. This is either a VIRGO supported
            #   prefab mesh or a path to an *.obj or *.stl file. Ex:
            #   VIRGO_PREFAB:sphere
    scale:  # Optional float representing scale applied to mesh equally in
            #   x,y,z. Defaults to 1.0
    pos:    # Optional list of 3 floats defining the position offset of
            #   the mesh within the node this actor is contained within
            #   This is applied before any rotation from ypr: and defaults
            #   to [0, 0, 0]
    ypr:    # Optional list of 3 floats defining the yaw-pitch-roll offset
            #   in degrees of the mesh within the node local origin this
            #   actor is associated with. This list is a Z,Y,X ordered
            #   intrinsic Euler rotation. This is applied after any offset
            #   from pos: and defaults to [0, 0, 0]
    color:  # Optional list of 3 floats between 0.0-1.0 defining the
            #   [red, green, blue] values of the color this actor should be
            #   TODO: Figure out out this works with textured meshes
    pickable: 1  # Optional integer 1 or 0 (true or false) for defining if
                 #  this actor can be picked with right-mouse-click. Defaults
                 #  to 1/true
    backface_culling: 0  # Optional integer 1 or 0 (true or false) for turning
                         #   the render of actors backfaces on or off. Set to
                         #   1 to improve performance, Defaults to 0.
    axes:   # The dictionary which holds information about this actor's axes
      when: # Optional string setting for when interal axes should be
            #   displayed with accepted values as follows:
            #   toggled - show axes when global setting (key:'a') is toggled
            #             This is the default option
            #   picked  - show axes when setting toggled and actor is picked
            #   always  - always show axes
            #   never   - never show axes
      style:  # Optional string setting for style of axes - line or cylinder
      length: # Optional list of 3 floats describing the length of each axis
              #  [x_axis, y_axis, z_axis]
      affect_opacity: # Optional bool (0 or 1) setting for whether opacity
                      #   of the actor should be reduced when axes are shown.
                      #   Defaults to 1 (true).
    trail:  # The dictionary which holds information about this actor's trail
      enabled:   # Integer 1 or 0 (true or false) for turning this trail on
                 #   when the interactive window starts
      color:     # Optional list of 3 floats between 0.0-1.0 defining the
                 #   [red, green, blue] values of the color of this actor's
                 #   trail. Defaults to [1.0, 1.0, 1.0] white.
      thickness: # Optional integer thickness of line. Default: 2.
      opacity:   # Optional float representing opacity of trail line.
                 #   Defaults to 1.0
    parent:      # Optional name of other actor, frame, or vector that this
                 #   actor's movement is defined relative to. If no parent: is
                 #   specified, movement is defined relative to world coordinates
    driven_by:   # The driven_by: sub-dict defines which data_source aliases are
                 #   used to drive this actor's position/rotation. An example is
                 #   shown below which references data_source aliases defined
                 #   above
      time: time    # Required time: key. It is linked to the time: alias above
                    # At least one of the following driven_by parameters must
                    # be given in addition to time:
      pos: sat_pos  # The pos: key represents this actor's position. It is linked
                    #   to the sat_pos alias defined above, meaning the satellite
                    #   actor's position will be driven by the sat_pos alias in
                    #   the scene
      rot: sat_rot  # The rot: key represents this actor's orientation. This must
                    #   be linked to a 3x3 direction cosine matrix defining the
                    #   transformation of a vector expressed in the parent: frame
                    #   to this actor's frame.  For those using JEOD, you want
                    #   this to link to an appropriate T_parent_this alias.
      transpose_rot:  # Optional boolean 1 or 0, when enabled this will transpose
                      #   the 3x3 matrix given by rot: before applying it in VTK.
                      #   This can be helpful as aerospace/robotics tend to use
                      #   passive transformations but VTK expects active 
                      #   transformations. This should be 1 if your rotation
                      #   matrix is a passive transformation. Defaults to 1.
      scale: <alias> # The scale: key represents this actor's size. This must
                     #   be linked to a data_source alias floating point value 
      opacity: <alias> # The opacity: key represents this actor's opacity. This
                       #   must be linked to a data_source alias floating point
                       #   value 
    labels:   # The labels: sub-dict defines text that is rendered in the 3D
              #   scene. These can be static text or reference data_source aliases.
              #   There is no limit to the number of labels an actor can have.
      myname:   # Required string representing user defined name for this label
        color:   # Optional list of 3 floats between 0.0-1.0 defining the
                 #   [red, green, blue] values of the color of this label
                 #   Defaults to white.
        text:    # Required string of text to be displayed. This text can contain
                 #   f-string notation referencing data_source aliases of the
                 #   requrired format {var_alias@time_alias}, for example
                 #   "x velocity is {sat_vel[0]@sat_time:<10.5f}" defines a
                 #   string using data specific to the sat_vel data source
                 #   alias at the sat_time data source alias. At runtime, the
                 #   value of sat_vel[0] closest to world time will be queried
                 #   from the data source and shown as text in the label. If
                 #   referencing the an alias that is an array, the format spec
                 #   of the f-string may not contain numerical output types as
                 #   non-primitive aliases are forcibly converted to string
        pos:    # Optional list of 3 floats defining the position offset of
                #   the label text relative to this actor's node. If faces_camera
                #   is 1, pos is expressed in world coordinates. If faces_camera
                #   is 0, pos is expressed in node local coordiantes
                #   no offset of [0, 0, 0]
        ypr:    # Optional list of 3 floats defining the yaw-pitch-roll offset
                #   in degrees of the label relative to this actor's node.
                #   This list is a Z,Y,X ordered intrinsic Euler rotation.
                #   Defaults to no ypr offset value of [0, 0, 0]. Note that
                #   by default label text is written left-to-right starting at
                #   this actor's node's local origin towards the +X direction
                #   with text facing in the +Z direction. Not allowed when
                #   faces_camera is 1
        faces_camera: # Optional boolean 0 or 1. If 1, the label will always
                      #   face the camera. If 0, the label will be fixed to
                      #   the local node coordinates. Defaults to 0
        when: # Optional string setting for when this label should be
              #   displayed with accepted values as follows:
              #   toggled - show label when global setting (key:'L') is toggled
              #             This is the default option
              #   picked  - show label when setting toggled and actor is picked
              #   always  - always show label
              #   never   - never show label
    provide_aliases: # Optional list of data source alias key names. Additional
                     #   data source aliases to provide to this actor's node's
                     #   self.data_source member. This is an advanced feature
                     #   primarily to support extending VirgoSceneNode capability
    layer:  # Optional rendering layer for this actor. Must be 'foreground',
            #   'midground', or 'background' and only applies to actors with no
            #   parent (root nodes). This can be used to combat Z-fighting in
            #   scenes with large and small objects. Default: 'foreground'

frames:     # The dictionary which holds all frames in the scene. A frame is
            #   an actor with no mesh geometry - typically an oriented X-Y-Z
            #   reference frame located somewhere in the scene or relative
            #   to another actor.
  my_frame: # User-chosen name for frame which acts as the key for this
            #   individual frames's sub-dict. Most fields supported by actors:
            #   are also supported by frames with some caveats explained in
            #   this section.  trail: scale: and mesh: are not supported and
            #   pos: and ypr: have a slightly different meaning explained
            #   below. 
    pos:    # Optional list of 3 floats defining the position offset of
            #   the frame relative to it's parent, or world coordinates if
            #   no parent given. This is applied before any rotation from
            #   ypr: and defaults to [0, 0, 0]
    ypr:    # Optional list of 3 floats defining the yaw-pitch-roll offset
            #   in degrees of the frame relative to it's parent, or world
            #   coordinates if no parent given. This list is a Z,Y,X ordered
            #   intrinsic Euler rotation. This is applied after any offset
            #   from pos: and defaults to [0, 0, 0]

vectors:    # The dictionary which holds all vectors in the scene. A vector is
            #   an actor whose mesh is automatically set to an 3D arrow. 
  my_vec:   # User-chosen name for vector which acts as the key for
            #   this individual vector's sub-dict. The fields supported by vectors
            #   are similar to that of the actors: section above with a few
            #   additions, limitations, and exceptions noted below.
            #   The mesh: and trail: fields are not supported for vectors
            # Params specific to vectors (related to style of the vector arrow):
    tip_length:   # Optional percentage of total vector length occupied by tip
    tip_radius:   # Optional radius of cone base relative to total vector length
    shaft_radius: # Optional radius of cylinder forming vector shaft relative 
                  #   to total vector length
    mode:   # Optional display mode: 'unit', 'absolute', or custom. When 
            #   'unit' the vector's size will be a unit vector scaled by the
            #   scale: parameter for this vector. When 'absolute', the vector's
            #   size will be shown as the true X,Y,Z components of the
            #   driven_by: pos: parameter multiplied by the scale: parameter,
            #   or just the scale: paramemter if no driven_by: pos: is given
            #   'custom' allows classes deriving from VirgoSceneNodeVector
            #   to define their own methodology for scaling the vector
            # Limitations/assumptions of vectors compared to actors:
    driven_by:   # The driven_by: sub-dict is the same as the actors: section
                 #   described above, but only time: and pos: are supported
      time: time    # The time: key is required. It is linked to the time: alias
      pos: sat_pos  # The pos: key represents this vector's X,Y,Z components
                    #   relative to it's parent, or world coordinates if no
                    #   parent is specified. For example, if sat_pos represents
                    #   the position of the satellite in inertial space, a
                    #   vector: with a driven_by: pos: sat_pos with no parent:
                    #   would draw a vector of length 1.0 in the direction of
                    #   the satellite's position, with the vector/arrow base
                    #   located at world coordinate origin. Tip: use scale: to
                    #   make the vector appear larger in the scene and use
                    #   mode: to switch between unit and absolute vectors

lighting:        # Optional dictionary which holds all lighting configuration
  start_mode:    # Optional lighting mode the scene should start with. 
                 #   Valid options are: realistic, headlight, ultrabright
  dark_ambient:  # Optional float between 0-1 describing the ambient light
                 #   value displayed on dark/shadowed surfaces when 'realistic'
                 #   lighting is enabled. 0.0 is pure black, 1.0 is full
                 #   bright. Defaults to 0.1.
  bright_ambient:  # Optional float between 0-1 describing the ambient light
                   #   value displayed on all lit surfaces when 'realistic'
                   #   lighting is enabled. 0.0 is pure black, 1.0 is full
                   #   bright. Defaults to 0.7

sun:          # Optional dictionary which holds information about the sun
              #   such as the direction it should be rendered in the scene
  direction:  # Optional list of 3 floats describing a unit vector [x,y,z]
              #   pointing towards the sun expressed in world coordinates
  driven_by:  # Optional actor, frame, or vector name that the sun's position
              #   is driven by in the scene. Suggest assigning this to
              #   a vector: that is configured to point at the sun via it's
              #   own driven_by: sub-dict

cameras:      # Optional dictionary which defines the camera or cameras
              # in the scene. Cameras are independent and persistent
              # viewpoints in the scene which can be switched to by the
              # user at any time.
  default:    # The default camera is created for you if not specified and
              # this is the camera the scene will start with. The following
              # parameters are valid for all uniquely named cameras the user
              # may optionally define:
    mode:       # Interactor mode for this camera, should be either 'TB' for
                # trackball or 'FP' for first-person. This determines how
                # mouse interaction with the scene affects the view of the
                # camera. Use 'TB' when gods-eye view is desired and 'FP'
                # when a view from the camera is desired. Defaults to 'TB'
    static:     # Boolen flag for whether this camera can move. Use 1 if you
                # want this camera to be fixed, 0 if the camera can be moved
                # by the user with the mouse. Defaults to 0
    pos:        # Optional list of 3 floats describing the initial location of
                #   the camera. If parent is given this is specified relative
                #   to the parent node, otherwise relative to world coords
                #   Defaults to [0, 0, 0]
    focal_point: # Optional list of 3 floats describing the initial point in
                 #   space the camera should look at. Ignored if parent is
                 #   given as the focal_point is the parent's origin in this
                 #   case
    view_up:    # Optional list of 3 floats describing the direction for the
                #   camera's +Z axis. This defines the camera's up direction
    view_angle: # Optional float describing the view angle (angular height of
                #   the camera view) in degrees.  Defaults to 30 degrees.
    parent:     # Optional name of actor/node the camera should follow when 
                #   the scene starts. If parent: given, it's value must be the
                #   key of an actor, vector, or frame defined in the scene
renderer:     # Optional dictionary which defines renderer parameters
  near_clipping_plane_tolerance: # Optional float describing the VTK foreground
                               # camera's  Near Clipping Plane Tolerance.
                               # This trades small actor visiblity with risk
                               # of Z-fighting at the clipping bounds. Defaults
                               # to 0.00005 and can be adjusted with j/k in
                               # the interactive window
  foreground_far_boundary: # Optional float describing the distance away from
                           #   the camera a node must be before it's moved
                           #   from the foreground to the midground layer and
                           #   vice-versa. Reduce this value to combat near
                           #   clipping plane distance issues. Default: 1e5
  midground_far_boundary:  # Optional float describing the distance away from
                           #   the camera a node must be before it's moved
                           #   from the midground to the background layer and
                           #   vice-versa. Must be > foreground_far_boundary.
                           #   Defaults to 1e8
  celestial_foreground_bias: # Optional float scale factor multiplied by
                           #   foreground_far_boundary that applies only
                           #   to celestial sized object when determining
                           #   which layer (foreground or midground) they
                           #   should enter. Value should be >= 0.0 and
                           #   < 1.0. Reduce to make it more difficult for
                           #   celestial objects to enter the foreground
                           #   Use 0.0 to make celestial objects never
                           #   enter the foreground. Defaults to 0.01

picker:       # Optional dictionary which holds information about the picker
  tolerance:  # Optional float threshold for picking (right click) actors
              #   Defaults to 5e-7 and can be adjusted with J/K in the
              #   interactive window
```
It's worth noting that **in this VIRGO alpha release error checking on the fields described above is still a work-in-progress** so there may be strange error messages if entering unexpected types in these dictionary fields.

Custom sections of the dictionary can be defined by users for any purpose they wish as long as they don't conflict with what VIRGO expects in the section above.  

## Extending Virgo

Details TBD. See `examples/entry/` and `examples/screensaver/` for two extension examples

## Contributing

Details TBD

## Getting Help

Details TBD - open an issue in TBD https://github.com/nasa/ project

## Links

* [VTK](https://vtk.org/)
    * The [VTK textbook](https://gitlab.kitware.com/vtk/textbook/raw/master/VTKBook/VTKTextBook.pdf) provides a good overview of VTK capabilities
    * The [VTK Doxygen documentation](https://vtk.org/doc/nightly/html/) provides detailed information on VTK capabilities
    * The [VTK Python Wrappers documentation](https://docs.vtk.org/en/latest/advanced/PythonWrappers.html) describes python bindings to the C++ core framework
    * The [VTK discourse forum](https://discourse.vtk.org/) is a great place to ask the VTK-using community questions.
    * The [VTK source code GitLab project](https://gitlab.kitware.com/vtk/vtk)

