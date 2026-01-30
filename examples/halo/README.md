## Halo Orbit Example

This example usage of VIRGO shows a halo orbit around the moon.

* `log_halo.csv`: Tracked Trickpy-compliant data file representing position data for a halo orbit around the moon
* `scene.yml`: YAML scene file representing the `dict` VIRGO needs to build the 3D scene
* `halo.py`: Script that launches VIRGO using `scene.yml` and `log_halo.csv`

When the scene starts, find the earth and right-click it to pick that actor. Press 'c' to have the camera follow the picked actor. Rotate the view to see the moon and the halo orbit around the moon. Here we can see why it's called a halo orbit - because it looks like a halo around the moon as viewed from the earth. You can pick the moon and press 'c' in the same way. To follow the cube again, open the console with \` and type `camera follow satellite`

## Turning on debugging with 'd'

While watching the visualization press 'd' to turn on debugging information. When toggled the trail segments are shown in different colors. Similarly and the HUD will show additional information about which rendering layers root nodes and trail segments reside within, as well as the clipping range for each rendering layer camera.

## TODO

We should model the rotation of the moon and the movement of the Earth in moon-centered inertial coordinates so that the motion of the halo orbit makes more sense visually. In the last 50% of the visualization the earth should be perpindicular to the orbital plane but right now it isn't because we aren't driving the position of Earth in the scene.
