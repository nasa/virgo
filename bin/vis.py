#!/usr/bin/env python3
# A generic VirgoDataPlayback scene loading script, run --help for
# information on how to use it.
import sys, os, argparse, yaml, inspect
# Add location of VIRGO code to sys.path so we can import classes
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
sys.path.append(os.path.abspath(os.path.join(thisFileDir, '../')))
# Import the only VIRGO class we need
from VirgoDataPlayback import VirgoDataPlayback

parser = argparse.ArgumentParser(description=
        'Visualize arbitrary scene and data. Pass in a scene YAML file '
        'and trickpy compliant data directory and VIRGO will display '
        'it using VirgoDataPlayback.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
parser.add_argument("scene_config", help="YAML config file to load")
parser.add_argument("data_dir", help="Directory to read the CSV data from")
parser.add_argument("--headless", action="store_true",
                    help="Render to video instead of providing an"
                    " interactive window")
parser.add_argument("--video-filename",
                    help="Filename for headless video when --headless given",
                    default=os.path.join(thisFileDir, 'vis.mp4'))
args = parser.parse_args()

class Vis:
    def __init__(self):
        with open(args.scene_config) as file:
            scene = yaml.safe_load(file) 
        self.v = VirgoDataPlayback(run_dir=args.data_dir, scene=scene,
                                    scene_yaml_path=args.scene_config,
                                    headless=args.headless,
                                    video_filename=args.video_filename)
        self.v.initialize()
    def execute(self):
        return(self.v.run())

if __name__ == '__main__':
    sys.exit(Vis().execute())
