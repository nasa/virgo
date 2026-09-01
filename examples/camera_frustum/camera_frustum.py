#!/usr/bin/env python3
import sys, os, argparse, yaml, inspect

thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
sys.path.append(os.path.abspath(os.path.join(thisFileDir, '../../')))

from Virgo import VirgoScene

parser = argparse.ArgumentParser(
    description='Camera frustum visualization example',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--scene", help="Scene YAML config file to load",
                    default=os.path.join(thisFileDir, 'scene.yml'))
args = parser.parse_args()


class CameraFrustumExample:
    def __init__(self):
        with open(args.scene) as file:
            scene = yaml.safe_load(file)
        self.v = VirgoScene(scene=scene)
        self.v.initialize()

    def run(self):
        return self.v.run()


if __name__ == '__main__':
    sys.exit(CameraFrustumExample().run())
