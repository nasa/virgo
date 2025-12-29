## Screensaver Example

This directory provides an example of how the VIRGO python classes can be extended to alter the behavior of the core framework.  Instead of ingesting information from a data source and displaying it to the user, this scene simply adds the moon and earth at realistic distances and slowly rotates the camera about the moon, providing a peaceful screensaver like scene.  Additionally, the current local time and weather are displayed on the screen.

* `scene.yml`: YAML scene file representing the `dict` VIRGO needs to build the 3D scene
* `screensaver.py`: Script that launches the classes extending VIRGO and using information in `scene.yml`

## Additional Dependencies Specific to this Example

This example uses the pip package `requests` in addition to the core VIRGO dependencies provided by `requirements.txt`. To install this, simply source the virtual environment (details in `../../README.md`) and run `pip install requests`.

## TBD more info goes here