import time
import onewire
import ds18x20
from machine import Pin

dat = Pin(4)

ds = ds18x20.DS18X20(onewire.OneWire(dat))

roms = ds.scan()

print("Devices found:", roms)

while True:
    ds.convert_temp()
    time.sleep_ms(750)

    for rom in roms:
        temp = ds.read_temp(rom)
        print("Temperature:", temp)

    time.sleep(1)