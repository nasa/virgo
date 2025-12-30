#!/usr/bin/env python3
import sys, os, argparse, yaml, inspect
# Add location of VIRGO code to sys.path so we can import classes
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
sys.path.append(os.path.abspath(os.path.join(thisFileDir, '../../')))
# Import the only VIRGO class we need
from Virgo import VirgoScene

parser = argparse.ArgumentParser(
    description='Hello Cube VIRGO example',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--scene", help="Scene YAML config file to load",
                    default=os.path.join(thisFileDir,'scene.yml'))
args = parser.parse_args()

class HelloCube:
    def __init__(self):
        with open(args.scene) as file:
            scene = yaml.safe_load(file) 
        self.v = VirgoScene(scene=scene)
        # Initialize the scene but do not render yet
        self.v.initialize()
        # Move the red cube to world position [2.0, 0.0, 0.0] units
        self.v.nodes['red_cube'].set_pose([2.0, 0.0, 0.0])

    def run(self):
        # Enter the renderer/interactor loop which creates the VIRGO window
        return(self.v.run())

if __name__ == '__main__':
    sys.exit(HelloCube().run())