#!/bin/bash
# A quick way to test all examples locally one after another
cd cannon && ./cannon.py && cd -
cd camera_frustum && ./camera_frustum.py && cd -
cd entry && ./entry.py && ./entry_extended.py && cd -
cd halo && ./halo.py && cd -
cd hello_cube && ./hello_cube.py && cd -
cd launch && ./launch.py && cd -
cd pendulums && ./pendulums.py && cd -
cd satellite && ./satellite.py && ./satellite_extended.py && cd -
cd screensaver && ./screensaver.py && cd -
cd splashdown && ./splashdown.py && cd -
