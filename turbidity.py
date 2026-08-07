from machine import Pin, ADC
import time

# Turbidity sensor connected to GPIO27
sensor = ADC(Pin(27))

# Configure ADC
sensor.atten(ADC.ATTN_11DB)      # 0–3.3V range (approximately)
sensor.width(ADC.WIDTH_12BIT)    # 12-bit resolution (0–4095)

while True:
    value = sensor.read()
    voltage = value * 3.3 / 4095

    print("ADC:", value, "Voltage:", round(voltage, 3), "V")

    time.sleep(1)