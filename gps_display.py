# gps_display.py

import sys
import os
import time
import math
import signal
import atexit
import threading
import traceback
import pigpio
from gps import gps, WATCH_ENABLE
from waveshare_epd import epd2in13_V3
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

# Import DataLogger
from data_logger import DataLogger

# Initialize the e-Paper display
epd = epd2in13_V3.EPD()
epd.init()
epd.Clear(0xFF)  # Clear the screen once at the start

# Initialize GPS
gpsd = gps(mode=WATCH_ENABLE)

# Create an image for the display
font_small = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
image = Image.new('1', (epd.height, epd.width), 255)
draw = ImageDraw.Draw(image)

# Variables for distance tracking and home location
distance_traveled = 0.0  # in miles
last_lat = None
last_lon = None
home_lat = None
home_lon = None
fix_acquired_time = None

# Initialize DataLogger
data_logger = DataLogger(log_directory="/home/pi/logs")

# Variables for GPS fix loss handling
fix_lost_time = None
fix_lost = False
grace_period = 120  # Grace period in seconds

# Fan Control Variables
FAN_GPIO = 18
TACH_GPIO = 23
fan_speed = 0
last_tick = 0
tick_count = 0
rpm = 0
fan_running = True
pi = None

# Initialize pigpio
pi = pigpio.pi()
if not pi.connected:
    print("Failed to connect to pigpio daemon")
    sys.exit(1)
pi.set_mode(TACH_GPIO, pigpio.INPUT)
pi.set_pull_up_down(TACH_GPIO, pigpio.PUD_UP)

# Function to handle tachometer callback
def tach_callback(gpio, level, tick):
    global last_tick, tick_count, rpm
    try:
        if level == 0:
            tick_count += 1
            if tick_count == 2:  # Two pulses per revolution
                dt = pigpio.tickDiff(last_tick, tick)
                rpm = 60000000 / dt if dt > 0 else 0
                tick_count = 0
                last_tick = tick
    except Exception as e:
        print(f"Error in tach callback: {e}")

# Register the tachometer callback
pi.callback(TACH_GPIO, pigpio.FALLING_EDGE, tach_callback)

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8  # Radius of Earth in miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def update_gps_data():
    # Initialize variables
    latitude = None
    longitude = None
    satellites_seen = 0
    satellites_used = 0
    fix_status = 1  # Assume no fix
    speed = 0.0
    altitude = 0.0

    # Read all pending data from gpsd
    while gpsd.waiting(0.1):
        report = gpsd.next()
        if report['class'] == 'TPV':
            latitude = report.get('lat', None)
            longitude = report.get('lon', None)
            speed = report.get('speed', 0.0) or 0.0  # Ensure speed is not None
            speed *= 2.237  # Convert m/s to mph
            altitude = report.get('alt', 0.0) or 0.0
            fix_status = report.get('mode', 1)
        elif report['class'] == 'SKY':
            satellites = report.get('satellites', [])
            satellites_seen = len(satellites)
            satellites_used = sum(1 for sat in satellites if sat.get('used', False))
            # For debugging, print the satellite info
            for sat in satellites:
                print(f"Satellite data: {sat}")
                print(f"PRN: {sat.get('PRN', 'N/A')}, Elevation: {sat.get('el', 'N/A')}, "
                      f"Azimuth: {sat.get('az', 'N/A')}, Signal: {sat.get('ss', 'N/A')}, "
                      f"Used: {'Y' if sat.get('used', False) else 'N'}")

    # Debug output to check data consistency
    print(f"[DEBUG] Fix Status: {fix_status}, Latitude: {latitude}, Longitude: {longitude}, "
          f"Satellites Seen: {satellites_seen}, Satellites Used: {satellites_used}, Speed: {speed:.2f} mph")

    return latitude, longitude, satellites_seen, satellites_used, fix_status, speed, altitude

def get_fix_status_text(fix_status):
    if fix_status == 1:
        return "No Fix"
    elif fix_status == 2:
        return "2D Fix"
    elif fix_status == 3:
        return "3D Fix"
    else:
        return "Unknown"

def get_cpu_temperature():
    try:
        res = os.popen('vcgencmd measure_temp').readline()
        temp_c = float(res.replace("temp=", "").replace("'C\n", ""))
        temp_f = temp_c * 9.0 / 5.0 + 32.0  # Convert to Fahrenheit
        return temp_f
    except Exception as e:
        print("Error getting CPU temperature:", e)
        return 0.0

def adjust_fan_speed(cpu_temp_f):
    """
    Adjusts the fan speed based on the CPU temperature.
    - Fan off below 122°F (50°C)
    - Linear increase from 122°F to 158°F (50°C to 70°C)
    - Fan at maximum speed above 158°F (70°C)
    """
    if cpu_temp_f < 122:
        return 0  # Fan off below 122°F
    elif cpu_temp_f >= 158:
        return 255  # Full speed at 158°F and above
    else:
        # Calculate fan speed proportionally between 122°F and 158°F
        min_temp = 122.0  # 50°C
        max_temp = 158.0  # 70°C
        temp_range = max_temp - min_temp
        temp_offset = cpu_temp_f - min_temp
        # Calculate fan speed (0 to 255)
        speed = int((temp_offset / temp_range) * 255)
        return speed

def set_fan_speed(speed):
    global fan_speed
    try:
        fan_speed = speed
        if pi:
            pi.set_PWM_dutycycle(FAN_GPIO, speed)
    except Exception as e:
        print("Error setting fan speed:", e)

def handle_exit(signum, frame):
    global fan_running
    print(f"Received signal {signum}, stopping logging and fan.")
    fan_running = False  # Signal the fan control thread to stop
    data_logger.stop_logging()
    if pi:
        pi.set_PWM_dutycycle(FAN_GPIO, 0)  # Turn off the fan
        pi.stop()
    epd.sleep()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_exit)   # Handle Ctrl+C
signal.signal(signal.SIGTERM, handle_exit)  # Handle termination signal

# Register data_logger.stop_logging to be called on exit
atexit.register(data_logger.stop_logging)

# Start the fan control thread
def fan_control_loop():
    global fan_running
    while fan_running:
        try:
            cpu_temp_f = get_cpu_temperature()
            new_fan_speed = adjust_fan_speed(cpu_temp_f)
            if new_fan_speed != fan_speed:
                set_fan_speed(new_fan_speed)
            time.sleep(2)
        except Exception as e:
            print(f"Error in fan control loop: {e}")

fan_thread = threading.Thread(target=fan_control_loop, daemon=True)
fan_thread.start()

try:
    while True:
        # Get the latest GPS data
        lat, lon, sats_seen, sats_used, fix_status, speed, altitude = update_gps_data()

        current_time = time.time()

        # Calculate time since the fix was acquired
        if fix_acquired_time:
            time_since_fix = (datetime.now() - fix_acquired_time).total_seconds() / 60
        else:
            time_since_fix = 0

        # Check GPS fix status
        if fix_status >= 2 and lat is not None and lon is not None:
            fix_text = get_fix_status_text(fix_status)

            # If we had previously lost the fix, reset the fix_lost flag and fix_lost_time
            if fix_lost:
                fix_lost = False
                fix_lost_time = None
                print("[INFO] GPS fix regained.")

            # Set the home position if it's the first time we get a fix
            if fix_acquired_time is None:
                home_lat = lat
                home_lon = lon
                fix_acquired_time = datetime.now()
                data_logger.start_logging()

            # Start logging if not already active
            if not data_logger.logging_active:
                data_logger.start_logging()

            # Calculate the distance if we have a valid last position
            if last_lat is not None and last_lon is not None:
                distance = haversine(last_lat, last_lon, lat, lon)
                distance_traveled += distance

            # Log the coordinate with all data
            data_logger.log_coordinate(lat, lon, altitude, speed, sats_seen, sats_used, fix_status)

            # Update last known position
            last_lat = lat
            last_lon = lon

        else:
            fix_text = get_fix_status_text(fix_status)

            # If fix is lost and not already marked as lost, mark it and record the time
            if not fix_lost:
                fix_lost = True
                fix_lost_time = current_time
                print("[INFO] GPS fix lost.")

            # Check if the fix has been lost for longer than the grace period
            elif fix_lost and (current_time - fix_lost_time) >= grace_period:
                # Stop logging if it's active
                if data_logger.logging_active:
                    data_logger.stop_logging()
                    print("[INFO] Logging stopped due to extended GPS fix loss.")
                fix_lost = False  # Reset fix_lost flag

        # Get CPU temperature in degrees Fahrenheit
        cpu_temp = get_cpu_temperature()
        if cpu_temp is not None:
            cpu_temp_display = f"{cpu_temp:.1f}°F"
        else:
            cpu_temp_display = "N/A"

        # Calculate fan speed percentage
        fan_speed_percent = fan_speed / 2.55  # Since 255 is 100%
        fan_speed_display = f"{fan_speed_percent:.0f}%"

        # Update the display with the latest information
        draw.rectangle((0, 0, epd.height, epd.width), fill=255)

        # Ensure fix_text is defined
        fix_text = fix_text if 'fix_text' in locals() else "No Fix"

        draw.text((5, 5), f"Fix: {fix_text}", font=font_small, fill=0)
        draw.text((5, 20), f"Sats Seen: {sats_seen}", font=font_small, fill=0)
        draw.text((5, 35), f"Sats Used: {sats_used}", font=font_small, fill=0)
        draw.text((5, 50), f"Speed: {speed:.2f} mph", font=font_small, fill=0)
        draw.text((5, 65), f"Altitude: {altitude:.0f} m", font=font_small, fill=0)
        draw.text((5, 80), f"Dist: {distance_traveled:.2f} mi", font=font_small, fill=0)
        draw.text((5, 95), f"LastFix: {time_since_fix:.1f} min", font=font_small, fill=0)
        draw.text((5, 110), f"Logging: {'ON' if data_logger.logging_active else 'OFF'}", font=font_small, fill=0)

        # Draw latitude and longitude only if they are valid
        if lat is not None and lon is not None:
            draw.text((110, 5), f"Lat: {lat:.6f}", font=font_small, fill=0)
            draw.text((110, 20), f"Lon: {lon:.6f}", font=font_small, fill=0)
        else:
            draw.text((110, 5), "Lat: N/A", font=font_small, fill=0)
            draw.text((110, 20), "Lon: N/A", font=font_small, fill=0)

        draw.text((110, 35), f"Logged Points: {data_logger.logged_points}", font=font_small, fill=0)
        draw.text((110, 50), f"Journey Start:", font=font_small, fill=0)
        journey_start = fix_acquired_time.strftime(
            '%I:%M:%S %p') if fix_acquired_time else 'N/A'
        draw.text((110, 65), f"{journey_start}", font=font_small, fill=0)
        # Remove the "Date/Time" label and move date/time up one line
        current_datetime = datetime.now().strftime('%m/%d/%Y %I:%M:%S %p')
        draw.text((110, 80), f"{current_datetime}", font=font_small, fill=0)
        # Display fan speed on top of the CPU temperature at the bottom
        draw.text((110, 95), f"Fan Speed: {fan_speed_display}", font=font_small, fill=0)
        draw.text((110, 110), f"CPU Temp: {cpu_temp_display}", font=font_small, fill=0)

        # Rotate the image 180 degrees (upside down)
        rotated_image = image.rotate(180)

        # Update the display using partial refresh to avoid flickering
        epd.displayPartial(epd.getbuffer(rotated_image))

        # Sleep for 3 seconds to allow for display refresh rate
        time.sleep(3)

except Exception as e:
    print("An error occurred:", e)
    traceback.print_exc()
    fan_running = False  # Signal the fan control thread to stop
    data_logger.stop_logging()
    if pi:
        pi.set_PWM_dutycycle(FAN_GPIO, 0)  # Turn off the fan
        pi.stop()
    epd.sleep()
    sys.exit(1)
