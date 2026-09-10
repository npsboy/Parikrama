from machine import Pin
import time

LED_PINS = [12, 13, 14, 15] #in order left -> right
SELECTED_PIN = 15

led = Pin(SELECTED_PIN, Pin.OUT)

for pin_num in LED_PINS:
    if pin_num != SELECTED_PIN:
        Pin(pin_num, Pin.OUT).off()

while True:
    led.on()
    time.sleep(1)
    led.off()
    time.sleep(1)
