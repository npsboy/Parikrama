from machine import UART
import time

# GPS on GPIO32 (RX)
gps = UART(1, baudrate=9600, rx=32)

def convert(coord):
    value = float(coord)
    degrees = int(value / 100)
    minutes = value - (degrees * 100)
    return degrees + (minutes / 60)

while True:
    line = gps.readline()

    if line:
        try:
            if isinstance(line, str):
                text = line.strip()
            else:
                text = line.decode().strip()

            if text.startswith('$GPRMC') or text.startswith('$GNRMC'):
                data = text.split(',')

                # Ignore incomplete or malformed NMEA sentences.
                if len(data) < 7:
                    continue

                # Check for valid GPS fix
                if data[2] == 'A' and data[3] and data[5]:
                    lat = convert(data[3])
                    lon = convert(data[5])

                    if data[4] == 'S':
                        lat = -lat

                    if data[6] == 'W':
                        lon = -lon

                    print("Latitude :", lat)
                    print("Longitude:", lon)
                    print()

                else:
                    print("Waiting for GPS fix...")

        except Exception as e:
            print("Error:", e)

    time.sleep(0.1)