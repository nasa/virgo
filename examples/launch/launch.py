#!/usr/bin/env python3
import math
import numpy as np
import csv
from datetime import datetime
import sys, os, argparse, yaml, inspect
# Add location of VIRGO code to sys.path so we can import classes
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
sys.path.append(os.path.abspath(os.path.join(thisFileDir, '../../')))
# Import the only VIRGO class we need
from VirgoDataPlayback import VirgoDataPlayback

parser = argparse.ArgumentParser(description=
        'Visualize the launch vehcile data in log_lv.csv using VIRGO.',
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
                    default=os.path.join(thisFileDir, 'launch.mp4'))
args = parser.parse_args()


class LaunchVehicleSimulator:
    """
    Big ole' warning on this class as AI wrote it as an estimation of
    the Artemis I launch using SLS mass and thrust. 

    TODO: Although this function does a pitch over the orientation of the
    vehicle is not computed as a DCM that VIRGO can consume and at the time of
    writing this example there's no time to implement that as we're focusing
    on core features and not the physical accuracy of these examples.
    """

    def __init__(self):
        self.run_simulation()

    def compute_eci_to_ecef_dcm(self, t):
        """
        Compute the DCM that transforms from ECI to ECEF frame.
        This represents Earth's rotation about its polar axis.

        ECEF rotates with the Earth, ECI is inertial (non-rotating).
        The transformation is a simple rotation about the Z-axis.
        """
        self.OMEGA_EARTH = 7.2921159e-5  # Earth rotation rate (rad/s)
        # Calculate Earth rotation angle at time t
        theta = self.OMEGA_EARTH * t

        # Rotation matrix about Z-axis (ECI to ECEF)
        # R_ECI_to_ECEF rotates coordinates from ECI to ECEF
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)

        R_ECI_to_ECEF = np.array([
            [cos_theta,  sin_theta, 0],
            [-sin_theta, cos_theta, 0],
            [0,          0,         1]
        ])

        return R_ECI_to_ECEF

    def run_simulation(self, duration=150):
        # ======================
        # Physical Constants
        # ======================
        g0 = 9.80665  # m/s^2

        # ======================
        # SLS Artemis I Approx
        # ======================
        initial_mass = 2_600_000.0  # kg (SLS Block 1 at liftoff)
        dry_mass = 300_000.0        # kg (post-burn, rough)
        thrust = 39_000_000.0       # N (SRBs + core combined)
        burn_time = 480.0           # seconds (SRB + core overlap approx)

        # ======================
        # Simulation Parameters
        # ======================
        dt = 0.1  # time step (seconds)
        pitch_start = 10.0   # seconds
        pitch_end = 150.0    # seconds
        final_pitch_deg = 85.0  # degrees downrange

        # ======================
        # Initial State
        # ======================
        t = 0.0
        mass = initial_mass

        x = y = z = 0.0
        vx = vy = vz = 0.0

        # ======================
        # Output CSV
        # ======================
        with open("log_lv.csv", "w", newline="") as f:
            writer = csv.writer(f)

            # Header with units
            writer.writerow([
                "time {s}",
                "pos[0] {m}",
                "pos[1] {m}",
                "pos[2] {m}",
                "altitude {m}",
                "ECI_TO_ECEF[0][0] {--}",
                "ECI_TO_ECEF[0][1] {--}",
                "ECI_TO_ECEF[0][2] {--}",
                "ECI_TO_ECEF[1][0] {--}",
                "ECI_TO_ECEF[1][1] {--}",
                "ECI_TO_ECEF[1][2] {--}",
                "ECI_TO_ECEF[2][0] {--}",
                "ECI_TO_ECEF[2][1] {--}",
                "ECI_TO_ECEF[2][2] {--}",
            ])

            while t <= duration:

                ECI_TO_ECEF = self.compute_eci_to_ecef_dcm(t)
                # ======================
                # Thrust & Mass Flow
                # ======================
                if t <= burn_time and mass > dry_mass:
                    current_thrust = thrust
                    mdot = (initial_mass - dry_mass) / burn_time
                    mass -= mdot * dt
                else:
                    current_thrust = 0.0

                # ======================
                # Pitch Program
                # ======================
                if t < pitch_start:
                    pitch = 0.0
                elif t < pitch_end:
                    frac = (t - pitch_start) / (pitch_end - pitch_start)
                    pitch = math.radians(frac * final_pitch_deg)
                else:
                    pitch = math.radians(final_pitch_deg)

                # ======================
                # Force Components
                # ======================
                thrust_z = current_thrust * math.cos(pitch)
                thrust_x = current_thrust * math.sin(pitch)

                ax = thrust_x / mass
                ay = 0.0
                az = (thrust_z / mass) - g0

                # ======================
                # Integrate Motion
                # ======================
                vx += ax * dt
                vy += ay * dt
                vz += az * dt

                x += vx * dt
                y += vy * dt
                z += vz * dt

                altitude = max(z, 0.0)

                # ======================
                # Log Data
                # ======================
                writer.writerow([
                    round(t, 3),
                    x,
                    y,
                    z,
                    altitude,
                    ECI_TO_ECEF[0][0],
                    ECI_TO_ECEF[0][1],
                    ECI_TO_ECEF[0][2],
                    ECI_TO_ECEF[1][0],
                    ECI_TO_ECEF[1][1],
                    ECI_TO_ECEF[1][2],
                    ECI_TO_ECEF[2][0],
                    ECI_TO_ECEF[2][1],
                    ECI_TO_ECEF[2][2],
                ])

                t += dt

        print("Simulation complete. Output written to log_lv.csv")

class LaunchVehicleExample:
    def __init__(self):
        sim = LaunchVehicleSimulator()
        with open(args.scene_config) as file:
            scene = yaml.safe_load(file) 
        # VirgoDataPlayback is the VirgoScene we want because it's built
        # to consume TrickPy-compatible data, which log_Satellite.csv meets
        self.v = VirgoDataPlayback(run_dir=args.data_dir, scene=scene,
                                    scene_yaml_path=args.scene_config,
                                    headless=args.headless,
                                    video_filename=args.video_filename)
        self.v.initialize()
    def execute(self):
        # Start the Virgo 3D scene
        return(self.v.run())

if __name__ == '__main__':
    sys.exit(LaunchVehicleExample().execute())
