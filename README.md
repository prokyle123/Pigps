![image](https://github.com/user-attachments/assets/65514fc7-084d-43fe-b352-edba6cbf91f7)

*****In early development*****

Raspberry Pi Zero 2 W GPS Logger with e-Paper Display and Fan Control
This project is a GPS logger and monitoring system for the Raspberry Pi Zero 2 W, designed to record GPS data, control a PWM fan based on CPU temperature, and display real-time information on a Waveshare e-Paper screen.

Features
GPS Logging: Logs GPS coordinates, altitude, speed, satellite data, and fix status to KML and CSV files for easy viewing and analysis.
Adaptive Fan Control: Adjusts a PWM fan speed based on CPU temperature to optimize performance and prevent overheating.
Real-Time Display: Shows GPS and system stats, including CPU temperature, fan speed, and distance traveled on a Waveshare 2.13-inch e-Paper display.
Stable GPS Fix Handling: Begins logging only after confirming a stable GPS fix, with built-in logic to stop logging if the GPS fix is lost.
Battery-Friendly Design: Includes power-saving features and uses an e-Paper display for minimal energy consumption.
Hardware Requirements
Raspberry Pi Zero 2 W
Compatible GPS Module (e.g., U-blox 7 or 8 module)
Waveshare 2.13-inch e-Paper Display (V3)
PWM Fan: Connected to GPIO 18 (PWM) and GPIO 23 (tachometer)
MicroSD Card: With Raspberry Pi OS installed
Optional Sensors: Additional sensors (accelerometer, environmental sensors) can be integrated as desired.
Software Requirements
Python 3 and libraries:
GPSD and Python GPS library: gpsd, python3-gps
PIGPIO Library: pigpio, python3-pigpio
Pillow (PIL): For image handling on the e-Paper display
Waveshare e-Paper Library: For display control

Log Files
KML Files: Import into mapping software (e.g., Google Earth).
CSV Files: View detailed GPS data for analysis.
Project Structure
gps_display.py: Main script to control GPS, display, and fan.
data_logger.py: Separate logging module for initializing, saving, and closing log files.
logs/: Directory for saving log files (KML and CSV formats).
Customization
Fan Control Settings: Adjust temperature thresholds in the adjust_fan_speed() function in gps_display.py.
Logging Interval: Change log_interval in data_logger.py to adjust how frequently data is logged.
Display Layout: Customize what information is shown on the e-Paper display in gps_display.py.
