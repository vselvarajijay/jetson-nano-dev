#!/usr/bin/env python3
"""
8BitDo Pro 3 Controller -> RoArm-M2-S Control
Maps gamepad inputs to robotic arm movements via JSON commands
"""

import pygame
import serial
import json
import time
import sys
import argparse
from datetime import datetime

class RobotArmController:
    def __init__(self, serial_port, baudrate=115200):
        # Initialize serial connection
        self.ser = serial.Serial(serial_port, baudrate, timeout=0.5)
        time.sleep(2)  # Wait for connection to stabilize
        
        # Movement settings
        self.speed = 2.0  # mm per update
        self.rotation_speed = 0.05  # radians per update
        
        # Deadzone for analog sticks (increased to prevent drift)
        self.deadzone = 0.25
        
        # Torque state
        self.torque_on = True
        
        # LED brightness (0-255)
        self.led_brightness = 100
        
        print("🤖 Robot Arm Controller initialized")
        
        # Enable torque
        self.send_command({"T": 210, "cmd": 1})
        time.sleep(0.5)
        
        # Set initial LED brightness
        self.set_led_brightness(100)
        
        # Get current position from robot
        print("📍 Reading current robot position...")
        self.send_command({"T": 1041, "x": 0, "y": 0, "z": 220, "t": 0.73})
        time.sleep(0.3)
        
        # Read the response to get actual position
        response = self.read_response()
        if response:
            self.x = response.get('x', 0)
            self.y = response.get('y', 0)
            self.z = response.get('z', 220)
            self.t = response.get('t', 0.73)
            print(f"📍 Current position: X={self.x:.2f}, Y={self.y:.2f}, Z={self.z:.2f}, T={self.t:.2f}")
        else:
            # Fallback to default
            self.x = 0
            self.y = 0
            self.z = 220
            self.t = 0.73
            print(f"⚠️  Could not read position, using default: X={self.x}, Y={self.y}, Z={self.z}")
    
    def read_response(self):
        """Read and parse JSON response from robot"""
        try:
            # Clear any old data
            self.ser.reset_input_buffer()
            
            # Wait for response
            time.sleep(0.2)
            
            if self.ser.in_waiting:
                response = self.ser.readline().decode('utf-8').strip()
                if response:
                    print(f"📥 {response}")
                    return json.loads(response)
        except Exception as e:
            print(f"⚠️  Error reading response: {e}")
        return None
    
    def send_command(self, command):
        """Send JSON command to robot arm"""
        json_str = json.dumps(command) + "\n"
        self.ser.write(json_str.encode())
        print(f"📤 {datetime.utcnow().isoformat()}Z | {command}")
    
    def move_to_position(self):
        """Send current position to robot arm"""
        command = {
            "T": 1041,  # Direct XYZ control
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "z": round(self.z, 2),
            "t": round(self.t, 2)
        }
        self.send_command(command)
    
    def apply_deadzone(self, value):
        """Apply deadzone to analog stick values"""
        if abs(value) < self.deadzone:
            return 0
        return value
    
    def toggle_torque(self):
        """Toggle torque lock on/off"""
        self.torque_on = not self.torque_on
        cmd_value = 1 if self.torque_on else 0
        self.send_command({"T": 210, "cmd": cmd_value})
        print(f"🔒 Torque: {'ON' if self.torque_on else 'OFF'}")
    
    def reset_position(self):
        """Reset to home position"""
        print("🏠 Returning to home position...")
        self.x = 0
        self.y = 0
        self.z = 220
        self.t = 0.73  # Mid-position
        self.move_to_position()
    
    def open_gripper(self):
        """Open gripper/end effector"""
        print("✋ Opening gripper")
        self.t = 1.08
        self.move_to_position()
    
    def close_gripper(self):
        """Close gripper/end effector"""
        print("🤏 Closing gripper")
        self.t = 3.14
        self.move_to_position()
    
    def set_led_brightness(self, brightness):
        """Set LED brightness (0-255)"""
        self.led_brightness = max(0, min(255, brightness))
        command = {"T": 114, "led": self.led_brightness}
        self.send_command(command)
        print(f"💡 LED brightness: {self.led_brightness}/255")
    
    def increase_speed(self):
        """Increase movement speed"""
        self.speed = min(self.speed + 0.5, 10.0)
        print(f"⚡ Speed: {self.speed} mm/update")
    
    def decrease_speed(self):
        """Decrease movement speed"""
        self.speed = max(self.speed - 0.5, 0.5)
        print(f"🐌 Speed: {self.speed} mm/update")
    
    def close(self):
        """Clean up and close connection"""
        self.ser.close()
        print("👋 Connection closed")


def main():
    parser = argparse.ArgumentParser(description='Control RoArm-M2-S with 8BitDo Pro 3')
    parser.add_argument('port', type=str, help='Serial port (e.g., /dev/ttyUSB0 or COM3)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baudrate (default: 115200)')
    args = parser.parse_args()
    
    # Initialize pygame and controller
    pygame.init()
    pygame.joystick.init()
    
    if pygame.joystick.get_count() == 0:
        print("❌ No controller detected!")
        sys.exit(1)
    
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    print("=" * 70)
    print(f"🎮 Controller: {joystick.get_name()}")
    print(f"🔌 Serial Port: {args.port}")
    print("=" * 70)
    print("\n📖 CONTROLS:")
    print("  Left Stick          → Move X/Y (horizontal plane)")
    print("  Right Stick Up/Down → Move Z (height)")
    print("  Right Stick Right   → Close gripper")
    print("  Right Stick Left    → Open gripper")
    print("  L1 (hold)           → Decrease LED brightness")
    print("  R1 (hold)           → Increase LED brightness")
    print("  Ctrl+C              → Exit")
    print("=" * 70)
    print()
    
    # Initialize robot arm controller
    try:
        robot = RobotArmController(args.port, args.baudrate)
    except Exception as e:
        print(f"❌ Failed to connect to robot arm: {e}")
        sys.exit(1)
    
    clock = pygame.time.Clock()
    running = True
    
    try:
        while running:
            # Process events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            
            pygame.event.pump()
            
            # Read analog sticks
            left_x = robot.apply_deadzone(joystick.get_axis(0))   # Left stick X
            left_y = robot.apply_deadzone(joystick.get_axis(1))   # Left stick Y
            right_x = robot.apply_deadzone(joystick.get_axis(2))  # Right stick X (rotation)
            right_y = robot.apply_deadzone(joystick.get_axis(3))  # Right stick Y (Z axis)
            
            # Update position based on stick input
            movement_occurred = False
            old_x, old_y, old_z, old_t = robot.x, robot.y, robot.z, robot.t
            
            if left_x != 0:
                robot.y -= left_x * robot.speed  # Stick left/right controls Y (inverted)
                robot.y = max(-291.94, min(297.53, robot.y))  # Actual Y range
            
            if left_y != 0:
                robot.x -= left_y * robot.speed  # Stick forward/back controls X (inverted)
                robot.x = max(-474.27, min(481.06, robot.x))  # Actual X range
            
            if right_y != 0:
                robot.z -= right_y * robot.speed  # Inverted for intuitive control
                robot.z = max(-103.72, min(423.18, robot.z))  # Actual Z range
            
            if right_x != 0:
                robot.t += right_x * robot.rotation_speed  # Right opens, left closes gripper
                robot.t = max(-1.91, min(3.37, robot.t))  # Actual gripper range
            
            # Only send command if position changed significantly (>0.1mm or >0.01 radians)
            if (abs(robot.x - old_x) > 0.1 or abs(robot.y - old_y) > 0.1 or 
                abs(robot.z - old_z) > 0.1 or abs(robot.t - old_t) > 0.01):
                movement_occurred = True
            
            # Send position update if movement occurred
            if movement_occurred:
                robot.move_to_position()
            
            # LED control with L1 and R1 (held buttons)
            # L1 (button 4) - decrease brightness
            if joystick.get_button(4):
                new_brightness = robot.led_brightness - 3
                if new_brightness != robot.led_brightness:
                    robot.set_led_brightness(new_brightness)
            
            # R1 (button 5) - increase brightness
            if joystick.get_button(5):
                new_brightness = robot.led_brightness + 3
                if new_brightness != robot.led_brightness:
                    robot.set_led_brightness(new_brightness)
            
            # Limit update rate
            clock.tick(20)  # 20 FPS - slower updates prevent flooding the robot
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    
    finally:
        # Return to home before closing
        print("\n🏠 Returning to home position...")
        robot.reset_position()
        time.sleep(1)
        robot.close()
        pygame.quit()
        print("✅ Shutdown complete")


if __name__ == "__main__":
    main()