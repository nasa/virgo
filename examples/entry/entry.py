#!/usr/bin/env python3
import numpy as np
import csv, math

import sys, os, argparse, yaml, inspect
# Add location of VIRGO code to sys.path so we can import classes
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
sys.path.append(os.path.abspath(os.path.join(thisFileDir, '../../')))

# Import the only VIRGO class we need
from VirgoDataPlayback import VirgoDataPlayback

def get_args():
    parser = argparse.ArgumentParser(description=
            'Generated then visualize data for an entry scenario.',
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
                        default=os.path.join(thisFileDir, 'satellite.mp4'))
    return(parser.parse_args())

class EntryExample:
    def __init__(self):
        args = get_args()
        self.generate_trajectory()
        with open(args.scene_config) as file:
            scene = yaml.safe_load(file) 
        # VirgoDataPlayback is the VirgoScene we want because it's built
        # to consume TrickPy-compatible data, which log_Satellite.csv meets
        self.v = VirgoDataPlayback(run_dir=args.data_dir, scene=scene,
                                    headless=args.headless,
                                    video_filename=args.video_filename)
        self.v.initialize()
    def execute(self):
        # Start the Virgo 3D scene
        return(self.v.run())

    def generate_trajectory(self):
        """
        Big 'ole warning on this baby Google Gemini AI wrote this function
        in October 2025 and I was at best, reasonably happy. Wouldn't it be
        a shame for us to not leave this example to future historians when
        in 3000 years they wonder - "I wonder what the dumbest AI was like?"
        Well here it is. A solid C-.

        The purpose of this function is to roughly simulate a spacecraft
        re-entry and write log_trajectory.csv with the data from that
        simulation. Don't get hung up on the accuracy of this simulation,
        the point is to generate data VIRGO can display.
        """
        # --- 1. Constants ---
        MU_EARTH = 3.986004418e14  # Earth's gravitational parameter (m^3/s^2)
        R_EARTH = 6378137.0          # Earth equatorial radius
        FILENAME = "log_trajectory.csv"
        
        # Atmospheric drag parameters
        M_SPACECRAFT = 5000.0       # (kg) Mass of the vehicle
        C_D = 2.0                   # (--) Drag coefficient (simplified constant)
        A_REF = 10.0                # (m^2) Reference area
        RHO_0 = 1.225               # (kg/m^3) Sea-level atmospheric density
        H_SCALE = 8500.0            # (m) Atmospheric scale height
        
        # Attitude control parameters
        ENTRY_ALTITUDE = 120000.0   # (m) Altitude to activate controller
        TARGET_AOA_RAD = 0.0 * (math.pi / 180.0) # 45-degree target angle of attack
        
        # --- 2. Initial State ---
        t = 0.0
        dt = 1.0  # Time step (s)
        
        # Initial state vectors in ECI frame
        pos = np.array([6867500.0, 0.0, 0.0])  # Initial position (m)
        vel_angle = 45 # degrees
        vel_mag = 7150.0
        vel_y = vel_mag*math.cos(vel_angle*math.pi/180)
        vel_z = vel_mag*math.sin(vel_angle*math.pi/180)
        vel = np.array([0.0, vel_y, vel_z])  # Initial velocity (m/s)
        
        # Initial orientation (Body to ECI)
        # This will now be updated by the "controller"
        R = np.identity(3)
        
        # --- 3. Setup CSV Output ---
        header = [
            "time {s}",
            "position[0] {m}", "position[1] {m}", "position[2] {m}",
            "R[0][0] {--}", "R[0][1] {--}", "R[0][2] {--}",
            "R[1][0] {--}", "R[1][1] {--}", "R[1][2] {--}",
            "R[2][0] {--}", "R[2][1] {--}", "R[2][2] {--}",
            "altitude {m}", "drag_force {N}"
        ]
        
        print(f"Starting simulation... writing to {FILENAME}")
        
        with open(FILENAME, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write the header row
            writer.writerow(header)
        
            # --- 4. Simulation Loop ---
            entry_interface_reached = False
            while True:
                
                # --- 5. Calculate Current State Variables ---
                radius = np.linalg.norm(pos)
                altitude = radius - R_EARTH
                
                # --- 6. Kinematic Attitude Controller ---
                # Assume a perfect controller that activates at entry interface
                # and instantly orients vehicle at a 45 degree angle of attack
                # and keeps it there
                if not entry_interface_reached and altitude < ENTRY_ALTITUDE:
                    entry_interface_reached = True
                    print(f"Passed through entry interface at t: {t} seconds")

                if entry_interface_reached:
                    # We will define the body frame relative to the aerodynamic frame
                    
                    # Aerodynamic frame axes in ECI
                    v_rel = vel # Assuming ECI velocity is relative velocity
                    v_norm = np.linalg.norm(v_rel)
                    
                    # Handle potential divide-by-zero if velocity is zero
                    if v_norm > 1e-6:
                        # 1. Aerodynamic "x-axis" (velocity direction)
                        i_vel = v_rel / v_norm
                        
                        # 2. Aerodynamic "y-axis" (orbit normal)
                        h_vec = np.cross(pos, v_rel) # Angular momentum vector
                        h_norm = np.linalg.norm(h_vec)
                        
                        if h_norm > 1e-6:
                            i_orbit_norm = h_vec / h_norm
                        else:
                            # Handle radial case (e.g., use ECI y-axis as fallback)
                            i_orbit_norm = np.array([0.0, 1.0, 0.0])
                            
                        # 3. Aerodynamic "z-axis" (lift direction)
                        i_lift = np.cross(i_vel, i_orbit_norm)
                        
                        # This matrix transforms ECI -> Aerodynamic Frame
                        R_I_to_A = np.array([i_vel, i_orbit_norm, i_lift])
        
                        # Now, define the 45-deg AoA rotation (pitch)
                        # This matrix transforms Aerodynamic -> Body Frame
                        c = math.cos(TARGET_AOA_RAD)
                        s = math.sin(TARGET_AOA_RAD)
                        R_A_to_B = np.array([
                            [c, 0, s],
                            [0, 1, 0],
                            [-s, 0, c]
                        ])
                        
                        # The final ECI -> Body matrix is the combination
                        # R = R_A_to_B * R_I_to_A
                        R = np.dot(R_A_to_B, R_I_to_A)
                        
                    else:
                        # Velocity is zero, keep R as is
                        pass 
                else:
                    # Above entry altitude, stay at identity
                    R = np.identity(3)
        
                # --- 7. Calculate Forces ---
                
                # a) Gravitational acceleration
                acc_grav = -MU_EARTH * pos / (radius**3)
                
                # b) Atmospheric drag acceleration
                try:
                    rho = RHO_0 * math.exp(-altitude / H_SCALE)
                except OverflowError:
                    rho = 0.0 # Altitude is too high, density is effectively zero
                    
                v_mag = np.linalg.norm(vel)
                
                if v_mag > 1e-6:
                    b_inv = (C_D * A_REF) / M_SPACECRAFT # Inverse of Ballistic Coefficient
                    acc_drag = -0.5 * rho * v_mag * b_inv * vel
                else:
                    acc_drag = np.array([0.0, 0.0, 0.0])
        
                # c) Total acceleration
                acc_total = acc_grav + acc_drag
                
                # --- 8. Write Data to CSV ---
                R_flat = R.flatten()
                F_drag_mag = np.linalg.norm(acc_drag) * M_SPACECRAFT # F=m*a
                
                row = [
                    t, pos[0], pos[1], pos[2],
                    *R_flat,
                    altitude, F_drag_mag
                ]
                writer.writerow(row)
                
                # --- 9. Check Stop Condition ---
                if altitude <= 0:
                    print(f"Simulation complete. Reached Earth's surface at t={t} s. (altitude: {altitude})")
                    break
                    
                # --- 10. Propagate Dynamics ---
                vel = vel + acc_total * dt
                pos = pos + vel * dt
                t = t + dt

if __name__ == '__main__':
    sys.exit(EntryExample().execute())
