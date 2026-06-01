from machine import ADC, Pin
from time import sleep

ph = ADC(Pin(34))

# Full ESP32 ADC range
ph.atten(ADC.ATTN_11DB)

while True:
    value = ph.read()
    print("pH sensor value:", value)
    sleep(1)