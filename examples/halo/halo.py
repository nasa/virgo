#!/usr/bin/env python3
import sys, os, argparse, yaml, inspect
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
# Import the only VIRGO class we need
from virgo.VirgoDataPlayback import VirgoDataPlayback

parser = argparse.ArgumentParser(description=
        'Visualize a halo orbit around the moon using VIRGO.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
parser.add_argument("--scene-config", help="YAML config file to load",
                    default=os.path.join(thisFileDir,'scene.yml'))
parser.add_argument("--data-dir", help="Directory to read the CSV data from",
                    default=thisFileDir)
parser.add_argument("--headless", action="store_true",
                    help="Render to video instead of providing an"
                    " interactive window")
parser.add_argument("--video-filename",
                    help="Filename for headless video when --headless given",
                    default=os.path.join(thisFileDir, 'halo.mp4'))
args = parser.parse_args()

class HaloExample:
    def __init__(self):
        with open(args.scene_config) as file:
            scene = yaml.safe_load(file) 
        # VirgoDataPlayback is the VirgoScene we want because it's built
        # to consume TrickPy-compatible data, which log_halo.csv meets
        self.v = VirgoDataPlayback(run_dir=args.data_dir, scene=scene,
                                    scene_yaml_path=args.scene_config,
                                    headless=args.headless,
                                    video_filename=args.video_filename)
        self.v.initialize()
    def execute(self):
        # Start the Virgo 3D scene
        return(self.v.run())

if __name__ == '__main__':
    sys.exit(HaloExample().execute())
