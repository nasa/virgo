#!/usr/bin/env python3
import sys, os, argparse, csv, inspect, yaml
import numpy as np
# Add location of VIRGO code to sys.path so we can import classes
thisFileDir = os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda:0)))
sys.path.append(os.path.abspath(os.path.join(thisFileDir, '../../')))
# Import the only VIRGO class we need
from VirgoDataPlayback import VirgoDataPlayback

parser = argparse.ArgumentParser(
    description='Generate cannon data then visualize it with VIRGO',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--scene", help="Scene YAML config file to load",
                    default=os.path.join(thisFileDir,'scene.yml'))
parser.add_argument("--data-dir", help="Directory to write the CSV data to",
                    default=thisFileDir)
parser.add_argument("--headless", action="store_true",
                    help="Render to video instead of providing an"
                    " interactive window")
parser.add_argument("--splash", help="Display VIRGO splash screen",
                    default=True)
parser.add_argument("--video-filename",
                    help="Filename for headless video when --headless given",
                    default=os.path.join(thisFileDir, 'cannon.mp4'))
args = parser.parse_args()

from dataclasses import dataclass

@dataclass
class SimulationParams:
    """Parameters for the cannonball simulation"""
    cannon_length: float = 1.0  # meters
    cannon_angle: float = 70.0  # degrees
    exit_velocity: float = 50.0  # m/s
    ball_mass: float = 5.0  # kg
    ball_radius: float = 0.1  # meters
    drag_coefficient: float = 0.47  # sphere drag coefficient
    air_density: float = 1.225  # kg/m^3
    gravity: float = 9.81  # m/s^2
    bounce_coef: float = 0.7  # coefficient of restitution
    dt: float = 0.01  # time step (seconds)
    max_time: float = 60.0  # maximum simulation time
    cannon_force_time: float = 0.05  # duration of cannon explosion force

class CannonballSimulation:
    def __init__(self, params: SimulationParams):
        self.params = params
        self.reset()
        
    def reset(self):
        """Initialize simulation state"""
        # Convert angle to radians
        angle_rad = np.radians(self.params.cannon_angle)
        
        # Initial position at cannon exit
        self.pos = np.array([
            self.params.cannon_length * np.cos(angle_rad),
            0.0,
            self.params.cannon_length * np.sin(angle_rad)
        ])
        
        # Initial velocity at cannon exit
        self.vel = np.array([
            self.params.exit_velocity * np.cos(angle_rad),
            0.0,
            self.params.exit_velocity * np.sin(angle_rad)
        ])
        
        self.time = 0.0
        self.data = []
        self.in_cannon = True
        self.cannon_start_time = 0.0
        
    def calculate_forces(self):
        """Calculate all forces acting on the cannonball"""
        forces = {
            'cannon': np.zeros(3),
            'gravity': np.zeros(3),
            'drag': np.zeros(3),
            'bounce': np.zeros(3)
        }
        
        # Cannon explosion force (only during initial firing)
        if self.in_cannon and self.time < self.params.cannon_force_time:
            # Calculate required force to accelerate ball to exit velocity
            # F = m * a, where a = v / t
            target_accel = self.params.exit_velocity / self.params.cannon_force_time
            angle_rad = np.radians(self.params.cannon_angle)
            forces['cannon'] = self.params.ball_mass * target_accel * np.array([
                np.cos(angle_rad), 0.0, np.sin(angle_rad)
            ])
        else:
            self.in_cannon = False
        
        # Gravity (always acting downward in -Z direction)
        forces['gravity'] = np.array([0.0, 0.0, -self.params.ball_mass * self.params.gravity])
        
        # Air drag: F_drag = -0.5 * rho * Cd * A * v^2 * v_hat
        if not self.in_cannon:
            speed = np.linalg.norm(self.vel)
            if speed > 0:
                cross_section = np.pi * self.params.ball_radius**2
                drag_magnitude = 0.5 * self.params.air_density * self.params.drag_coefficient * cross_section * speed**2
                forces['drag'] = -drag_magnitude * (self.vel / speed)
        
        dist_to_ground = abs(self.pos[2] - self.params.ball_radius) 
        # Ground bounce force. TODO: this if clause was hacked together quickly
        # as the rest of this class was written by AI but it just couldn't get the
        # bounce force to work. The "close enough to ground" check isn't super
        # accurate but good enough for this demonstration -Jordan Jan 2026
        if dist_to_ground < 1.0 and self.vel[2] < 0:
            # Apply bounce force (impulse-based)
            # This is a simplified model - applying force over one timestep
            delta_v = -(1 + self.params.bounce_coef) * self.vel[2]
            forces['bounce'] = np.array([0.0, 0.0, self.params.ball_mass * delta_v / self.params.dt])
            #print(f"Bounce force: {forces['bounce']}")
        
        return forces
    
    def step(self):
        """Perform one simulation step"""
        forces = self.calculate_forces()
        
        # Total force
        total_force = sum(forces.values())
        
        # Acceleration: F = ma => a = F/m
        accel = total_force / self.params.ball_mass
        
        # Update velocity and position (Euler integration)
        self.vel += accel * self.params.dt
        self.pos += self.vel * self.params.dt
        
        # Ensure ball doesn't go below ground
        if self.pos[2] < self.params.ball_radius:
            self.pos[2] = self.params.ball_radius
            # If velocity is still downward after bounce, set to small upward value
            if self.vel[2] < 0:
                self.vel[2] = 0
        
        # Record data
        self.data.append({
            'time': self.time,
            'pos': self.pos.copy(),
            'vel': self.vel.copy(),
            'forces': {k: v.copy() for k, v in forces.items()}
        })
        
        self.time += self.params.dt
        
    def should_continue(self):
        """Check if simulation should continue"""
        # Stop if max time reached
        if self.time >= self.params.max_time:
            return False
        
        # Stop if ball has settled (low velocity near ground)
        if (self.pos[2] <= self.params.ball_radius + 0.01 and 
            np.linalg.norm(self.vel) < 0.1 and 
            self.time > 5.0):
            return False
        
        return True
    
    def run(self):
        """Run the complete simulation"""
        while self.should_continue():
            self.step()
        return self.data
    
    def save_to_csv(self, filename='log_cannonball.csv'):
        """Save simulation data to CSV file"""
        with open(filename, 'w', newline='') as csvfile:
            # Create header
            header = [
                'time {s}',
                'pos[0] {m}', 'pos[1] {m}', 'pos[2] {m}',
                'vel[0] {m/s}', 'vel[1] {m/s}', 'vel[2] {m/s}',
                'F_cannon[0] {N}', 'F_cannon[1] {N}', 'F_cannon[2] {N}',
                'F_gravity[0] {N}', 'F_gravity[1] {N}', 'F_gravity[2] {N}',
                'F_drag[0] {N}', 'F_drag[1] {N}', 'F_drag[2] {N}',
                'F_bounce[0] {N}', 'F_bounce[1] {N}', 'F_bounce[2] {N}'
            ]
            
            writer = csv.writer(csvfile)
            writer.writerow(header)
            
            # Write data rows
            for point in self.data:
                row = [
                    f"{point['time']:.6f}",
                    f"{point['pos'][0]:.6f}", f"{point['pos'][1]:.6f}", f"{point['pos'][2]:.6f}",
                    f"{point['vel'][0]:.6f}", f"{point['vel'][1]:.6f}", f"{point['vel'][2]:.6f}",
                    f"{point['forces']['cannon'][0]:.6f}", f"{point['forces']['cannon'][1]:.6f}", f"{point['forces']['cannon'][2]:.6f}",
                    f"{point['forces']['gravity'][0]:.6f}", f"{point['forces']['gravity'][1]:.6f}", f"{point['forces']['gravity'][2]:.6f}",
                    f"{point['forces']['drag'][0]:.6f}", f"{point['forces']['drag'][1]:.6f}", f"{point['forces']['drag'][2]:.6f}",
                    f"{point['forces']['bounce'][0]:.6f}", f"{point['forces']['bounce'][1]:.6f}", f"{point['forces']['bounce'][2]:.6f}"
                ]
                writer.writerow(row)
        
        print(f"Simulation data saved to {filename}")
        print(f"Total simulation time: {self.time:.2f} seconds")
        print(f"Total data points: {len(self.data)}")
        print(f"Final position: ({self.pos[0]:.2f}, {self.pos[1]:.2f}, {self.pos[2]:.2f}) meters")


class CannonExample:
    def __init__(self):
        self.params = SimulationParams()
        self.sim = CannonballSimulation(self.params)
        
        print("Starting cannonball simulation...")
        print(f"Cannon angle: {self.params.cannon_angle}°")
        print(f"Exit velocity: {self.params.exit_velocity} m/s")
        print(f"Bounce coefficient: {self.params.bounce_coef}")


    def run(self):
        # Enter the renderer/interactor loop which creates the VIRGO window
        
        # Run simulation
        self.sim.run()
        
        # Save results
        self.sim.save_to_csv()

        # VirgoDataPlayback is the VirgoScene we want because it's built
        # to consume TrickPy-compatible data, which log_cannonball.csv meets
        with open(args.scene) as file:
            scene = yaml.safe_load(file) 
        self.v = VirgoDataPlayback(run_dir=args.data_dir, scene=scene,
                                    headless=args.headless,
                                    video_filename=args.video_filename, splash=args.splash)
        # Initialize the scene but do not render yet
        self.v.initialize()
        self.v.run()

if __name__ == '__main__':
    sys.exit(CannonExample().run())
