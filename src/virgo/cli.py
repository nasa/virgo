#!/usr/bin/env python3
# A generic VirgoDataPlayback scene loading script, run --help for
# information on how to use it.
import os, argparse, yaml, sys
# Import the only VIRGO class we need
from .VirgoDataPlayback import VirgoDataPlayback


class Vis:
    def __init__(self, args):
        with open(args.scene_config) as file:
            scene = yaml.safe_load(file)
        self.v = VirgoDataPlayback(run_dir=args.data_dir, scene=scene,
                                    scene_yaml_path=args.scene_config,
                                    headless=args.headless,
                                    video_filename=args.video_filename)
        self.v.initialize()

    def execute(self):
        return (self.v.run())


def main():
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
                        default=os.path.join(os.getcwd(), 'vis.mp4'))
    args = parser.parse_args()

    return Vis(args).execute()

def example():
    examples_map = {
        'cannon': ('examples.cannon.cannon', 'CannonExample'),
        'entry': ('examples.entry.entry', 'EntryExample'),
        'halo': ('examples.halo.halo', 'HaloExample'),
        'hello_cube': ('examples.hello_cube.hello_cube', 'HelloCube'),
        'launch': ('examples.launch.launch', 'LaunchVehicleExample'),
        'pendulums': ('examples.pendulums.pendulums', 'PendulumExample'),
        'satellite': ('examples.satellite.satellite', 'SatelliteExample'),
        'screensaver': ('examples.screensaver.screensaver', 'MyScreenSaver'),
        'splashdown': ('examples.splashdown.splashdown', 'SplashdownExample'),
    }

    # Get the example name from sys.argv before any subparser consumes it
    if len(sys.argv) < 2 or sys.argv[1] not in examples_map:
        parser = argparse.ArgumentParser(
            description='Run a VIRGO example',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        parser.add_argument('name', choices=sorted(examples_map.keys()),
                            help='Name of the example to run')
        parser.print_help()
        return 1

    example_name = sys.argv[1]
    # Remove the example name from argv so the example's argparse doesn't see it
    sys.argv.pop(1)

    module_path, class_name = examples_map[example_name]
    module = __import__(module_path, fromlist=[class_name])
    example_class = getattr(module, class_name)

    instance = example_class()
    return instance.run() if hasattr(instance, 'run') else instance.execute()


if __name__ == '__main__':
    sys.exit(main())
