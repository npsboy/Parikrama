from machine import Pin
import time
import _thread

# 12: Red
# 13: Blue 1
# 14: Green
# 15: Blue 2
RED = 12
BLUE1 = 13
GREEN = 14
BLUE2 = 15

LED_PINS = [RED, BLUE1, GREEN, BLUE2]  # in order left -> right

OFF = 0
ON = 1
BLINK_FAST = 2
BLINK_SLOW = 3

_FAST_HALF_PERIOD_MS = 150
_SLOW_HALF_PERIOD_MS = 500

_pins = {pin_num: Pin(pin_num, Pin.OUT) for pin_num in LED_PINS}
_states = {pin_num: OFF for pin_num in LED_PINS}
_lock = _thread.allocate_lock()
_running = False


def _blink_loop():
    last_toggle = {pin_num: time.ticks_ms() for pin_num in LED_PINS}
    on_flag = {pin_num: False for pin_num in LED_PINS}

    while _running:
        now = time.ticks_ms()
        _lock.acquire()
        states_snapshot = dict(_states)
        _lock.release()

        for pin_num, state in states_snapshot.items():
            pin = _pins[pin_num]
            if state == OFF:
                pin.off()
            elif state == ON:
                pin.on()
            else:
                half_period = (_FAST_HALF_PERIOD_MS if state == BLINK_FAST
                               else _SLOW_HALF_PERIOD_MS)
                if time.ticks_diff(now, last_toggle[pin_num]) >= half_period:
                    on_flag[pin_num] = not on_flag[pin_num]
                    pin.value(on_flag[pin_num])
                    last_toggle[pin_num] = now

        time.sleep_ms(20)


def start():
    global _running
    if _running:
        return
    _running = True
    _thread.start_new_thread(_blink_loop, ())


def stop():
    global _running
    _running = False


def set_state(pin_num, state):
    _lock.acquire()
    _states[pin_num] = state
    _lock.release()


def all_off():
    _lock.acquire()
    for pin_num in LED_PINS:
        _states[pin_num] = OFF
    _lock.release()
    for pin_num in LED_PINS:
        _pins[pin_num].off()


if __name__ == "__main__":
    all_off()
    start()
    set_state(RED, BLINK_FAST)
    set_state(BLUE1, BLINK_SLOW)
    set_state(GREEN, ON)
    try:
        while True:
            time.sleep(1)
    finally:
        all_off()
