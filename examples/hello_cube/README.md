# Hello Cube Example

This directory provides the smallest possible example of VIRGO rendering a cube in space with no motion. This is intended to be the first VIRGO example a new user runs and allows them to look at the basics of navigating the scene. Files of importance:

* `hello_cube.py`: Renders a simple VIRGO scene with two cubes
* `scene.yml`: YAML scene file representing the `dict` VIRGO needs to build the 3D scene
* `tutorial/`: Directory containing information for the tutorial section below

Please take a look at these files as there's extensive comments explaining the configuration.

# Tutorial

This section is intended to teach the user how to perform certain actions in VIRGO. Follow along as directed and feel free to reference completed scene files under `tutorial/`.

## Navigating a VIRGO scene

Press 'h' to toggle help while the scene is active to see how to use the controls.  The most important controls are:

* Left-click-hold and drag to rotate around the focal point
* Shift-Left-click-hold or middle-mouse-hold to pan
* Mouse-wheel up/down to dolly in/out respectively
* Ctrl (command on mac)-left-click-hold to roll the camera
* Right-click on an actor to pick/select it
* Press `c` on a picked actor to have the camera follow it. When a camera follows an actor, the camera's focal point is moved to that actor's origin.

You will notice that several keys will not do anything because this scene is so minimal some features aren't active.  A few of of the features *not* enabled in this scene:

1. Pause/Play: All actors in this scene are *static* which means there's no data source describing their motion. Since there's nothing to play or pause, the scene playing/paused mode shows up as "None" and spacebar does nothing.
1. Step:  Similar to pause/play with no motion in the scene step does nothing.
1. Trails:  Similarly with no motion of nodes there are no trails to display so 't' does nothing.
1. Labels: No labels are defined in this scene so 'L' does nothing. Continue reading the next section to define labels.



## Defining `labels:`

Text can be rendered directly in the scene by adding one or more **Virgo Labels**. This can be static text or contain data from a **VIRGO data source**, but in this example there is no data source so we provide two examples of static text that moves with the actor. Add these sub-sections to this directory's `scene.yml` file:

```yaml
    # Add this sub-section under the green_cube: indented section
    labels:
      name:
        text: A green cube
        pos: [-1.0, 0, 0.8]
        ypr: [0, 0, 90]
        color: [0.133, 0.408, 0.173]   # Color this label 'virgo green'
        scale: 0.2

    # Add this sub-section under the red_cube: indented section
    labels:
      name:
        text: A red cube
        pos: [-1.0, 0, -1.5]
        ypr: [0, 0, 90]
        color: [1.0, 0.0, 0.0 ] # Color this label red
        scale: 0.3
```
Alternatively you can use `./hello_cube.py --scene tutorial/scene_with_labels.yml` where this scene alteration is already committed.  Now when the scene starts, you should be able to press `L` to turn labels on. When you do you'll see the labels positioned like so:

![with_labels](images/hello_cube_with_labels.png)

Take a closer look at the `pos:` and `ypr:` values for each label. They represent the position and yaw-pitch-roll ordered Euler rotation of the text relative to the actor's origin. You can see the origin of an actor at any time by pressing `a` to toggle the axes of the actor. When you do, the actors become transparent and the axes are visible:

![with_labels](images/hello_cube_with_axes_and_labels.png)

Notice here the axes are colored red (x),  green (y), and blue (z) - these visible axes are actually a VTK provided [vtkAxesActor](https://vtk.org/doc/nightly/html/classvtkAxesActor.html) and the red-x, green-y, and blue-z conventions are respected consistently across VIRGO. When positioning labels it's important to keep these axes in mind as the labels are moved to the value given by `pos:`, then an **intrinsic ordered Z-Y-X (yaw-pitch-roll) Euler rotation** is performed on the label to rotate it. You'll notice the each `ypr:` section performs positive X-rotation of 90 degrees so that the label faces the camera when the scene starts.

To understand how `pos:` and `ypr:` influence the position of labels, we suggest you zero out these values and then play with them in `scene.yml`. You'll notice that by default, **labels start at the origin of the actor, reading left-to-right in the +X direction with the top of the text pointing in +Y**.

For more examples on labels, see the other `examples/*` in VIRGO, especially `examples/satellite/` which demonstrates how to display data from a **VIRGO data source** directly in a actor's label.

## Actor offset

TBD - Demonstration of `pos:` and `ypr:` for actors goes here.