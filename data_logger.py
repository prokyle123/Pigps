# data_logger.py

import os
from datetime import datetime

class DataLogger:
    def __init__(self, log_directory="/home/pi/logs"):
        self.logging_active = False
        self.log_file_kml = None
        self.log_file_csv = None
        self.logged_points = 0
        self.last_log_time = 0
        self.log_interval = 10  # Log points every 10 seconds
        self.log_directory = log_directory

        # Ensure the log directory exists
        os.makedirs(self.log_directory, exist_ok=True)

    def start_logging(self):
        if not self.logging_active:
            self.logging_active = True
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log_file_kml = os.path.join(self.log_directory, f"gps_log_{timestamp}.kml")
            self.log_file_csv = os.path.join(self.log_directory, f"gps_log_{timestamp}.csv")
            try:
                # Initialize KML file
                with open(self.log_file_kml, "w") as f:
                    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                    f.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
                    f.write('<Document>\n')
                    f.write('<name>GPS Journey</name>\n')
                    f.write('<Placemark>\n')
                    f.write('<LineString>\n')
                    f.write('<coordinates>\n')
                # Initialize CSV file with headers
                with open(self.log_file_csv, "w") as f:
                    f.write("Timestamp,Latitude,Longitude,Altitude(m),Speed(mph),Satellites Seen,Satellites Used,Fix Status\n")
            except Exception as e:
                print("Error starting logging:", e)

    def log_coordinate(self, lat, lon, altitude, speed, sats_seen, sats_used, fix_status):
        import time
        current_time = time.time()
        if current_time - self.last_log_time >= self.log_interval and self.logging_active:
            try:
                closing_tags = '</coordinates>\n</LineString>\n</Placemark>\n</Document>\n</kml>\n'
                # Log to KML file
                with open(self.log_file_kml, "a") as f_kml:
                    f_kml.write(f"{lon},{lat},{altitude}\n")
                    f_kml.write(closing_tags)
                # Remove the closing tags to prepare for the next coordinate
                with open(self.log_file_kml, "rb+") as f_kml:
                    f_kml.seek(-len(closing_tags.encode('utf-8')), os.SEEK_END)
                    f_kml.truncate()
                # Log to CSV file
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open(self.log_file_csv, "a") as f_csv:
                    f_csv.write(f"{timestamp},{lat},{lon},{altitude},{speed},{sats_seen},{sats_used},{fix_status}\n")
                self.logged_points += 1
                self.last_log_time = current_time
            except Exception as e:
                print("Error logging coordinate:", e)

    def stop_logging(self):
        if self.logging_active:
            self.logging_active = False
            try:
                with open(self.log_file_kml, "a") as f:
                    f.write('</coordinates>\n')
                    f.write('</LineString>\n')
                    f.write('</Placemark>\n')
                    f.write('</Document>\n')
                    f.write('</kml>\n')
            except Exception as e:
                print("Error stopping logging:", e)
