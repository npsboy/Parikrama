import gc
import time

import onewire
import ds18x20
from machine import UART, ADC, Pin

from secrets import THINGSPEAK_API_KEY

gc.collect()

uart = UART(2, baudrate=115200, tx=33, rx=25, timeout=1000)

UPDATE_INTERVAL_S = 20   # stay above ThingSpeak's 15s free-tier limit
NUM_SAMPLES = 5          # readings averaged per upload

# ---------- AT / UART helpers ----------

def flush_uart():
    while uart.any():
        uart.read(256)

def send_at(cmd, wait=1000, bufsize=1024):
    uart.write(cmd + '\r\n')
    time.sleep_ms(wait)
    data = uart.read(bufsize)
    gc.collect()
    if data:
        try:
            return data.decode()
        except UnicodeError:
            return str(data)
    return None

def show(label, cmd, wait=1000):
    flush_uart()
    resp = send_at(cmd, wait=wait)
    print(f"  {label}:", (resp or 'no response').replace('\r\n', ' ').strip())
    time.sleep_ms(300)
    return resp

def wait_for_module(retries=15):
    for _ in range(retries):
        if (send_at('AT') or '').find('OK') >= 0:
            return True
        time.sleep(1)
    return False

def wait_for_sim(retries=10):
    for _ in range(retries):
        flush_uart()
        if '+CPIN: READY' in (send_at('AT+CPIN?', wait=1000) or ''):
            return True
        time.sleep(1)
    return False

def parse_cereg(resp):
    if not resp or '+CEREG:' not in resp:
        return None
    try:
        line = resp.split('+CEREG:')[1].split('\r')[0].strip()
        return int([p.strip() for p in line.split(',')][1])
    except Exception:
        return None

def wait_for_registration(retries=20):
    for i in range(retries):
        flush_uart()
        stat = parse_cereg(send_at('AT+CEREG?', wait=1000))
        print(f"  CEREG {i}: stat={stat}")
        if stat in (1, 5):
            return True
        time.sleep(2)
    return False

# ---------- context discovery ----------

def get_apn_for_cid(resp, want_cid):
    """Pull the APN string out of an AT+CGDCONT? response for a given CID."""
    if not resp or '+CGDCONT:' not in resp:
        return None
    for chunk in resp.split('+CGDCONT:')[1:]:
        line = chunk.split('\r')[0].strip()
        parts = [p.strip().strip('"') for p in line.split(',')]
        if len(parts) < 3:
            continue
        try:
            cid = int(parts[0])
        except ValueError:
            continue
        if cid == want_cid:
            return parts[2]      # <APN>
    return None

# ---------- HTTP ----------

def parse_httpaction(text):
    if not text or '+HTTPACTION:' not in text:
        return None, None
    try:
        line = text.split('+HTTPACTION:')[1].split('\n')[0].strip()
        p = [x.strip() for x in line.split(',')]
        return int(p[1]), int(p[2])
    except Exception:
        return None, None

def http_get(url, timeout_ms=20000):
    flush_uart()
    send_at('AT+HTTPTERM')
    time.sleep_ms(300)
    flush_uart()

    print("  HTTPINIT:", (send_at('AT+HTTPINIT', wait=1000) or '').strip())
    time.sleep_ms(300)
    flush_uart()
    print("  URL:", (send_at(f'AT+HTTPPARA="URL","{url}"',
                             wait=1000) or '').strip())
    time.sleep_ms(300)
    flush_uart()

    action = send_at('AT+HTTPACTION=0', wait=5000, bufsize=2048)
    print("  ACTION:", (action or '').replace('\r\n', ' ').strip())

    status, length = parse_httpaction(action)

    body = None
    if status == 200 and length:
        flush_uart()
        body = send_at(f'AT+HTTPREAD=0,{min(length, 1024)}',
                       wait=2000, bufsize=2048)

    send_at('AT+HTTPTERM')
    return status, body

# ---------- sensors ----------

# DS18B20 temperature sensor on GPIO 4
ds = ds18x20.DS18X20(onewire.OneWire(Pin(4)))
roms = ds.scan() or []
print("Temperature devices found:", roms)

# pH sensor on GPIO 34
ph = ADC(Pin(34))
ph.atten(ADC.ATTN_11DB)          # full 0-3.3V range

# Turbidity sensor on GPIO 27
turbidity = ADC(Pin(27))
turbidity.atten(ADC.ATTN_11DB)   # 0-3.3V range (approximately)
turbidity.width(ADC.WIDTH_12BIT) # 12-bit resolution (0-4095)


def average(values):
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def read_temperature():
    """Average of all DS18B20s on the bus, or None if none responded."""
    if not roms:
        return None
    ds.convert_temp()
    time.sleep_ms(750)
    temps = []
    for rom in roms:
        try:
            temps.append(ds.read_temp(rom))
        except Exception as e:
            print("  temp read failed:", e)
    return average(temps)


def ph_from_adc(adc, temp_c):
    """Temperature-compensated fit from predict_ph.py."""
    slope = -0.00579 + 0.000035 * temp_c
    intercept = 17.78 - 0.073 * temp_c
    return slope * adc + intercept


def turbidity_percent(adc):
    """Map the sensor's 0-3.3V output linearly onto 0-100%."""
    voltage = adc * 3.3 / 4095
    pct = voltage / 3.3 * 100
    return max(0.0, min(100.0, pct))


def read_all():
    """Sample every sensor NUM_SAMPLES times and return the averaged values."""
    temps = []
    ph_adcs = []
    turb_adcs = []

    for _ in range(NUM_SAMPLES):
        temps.append(read_temperature())
        ph_adcs.append(ph.read())
        turb_adcs.append(turbidity.read())
        time.sleep_ms(250)

    temp_c = average(temps)
    ph_adc = average(ph_adcs)
    turb_adc = average(turb_adcs)

    ph_value = None if temp_c is None else ph_from_adc(ph_adc, temp_c)

    print("  temp: {} C | pH ADC: {:.1f} | turbidity ADC: {:.1f}".format(
        "n/a" if temp_c is None else "{:.2f}".format(temp_c),
        ph_adc, turb_adc))

    return temp_c, ph_value, turbidity_percent(turb_adc)


# ---------- ThingSpeak ----------

def build_thingspeak_url(temp_c, ph_value, turb_pct):
    """field1=temperature, field2=predicted pH, field3=turbidity %.

    Fields that are None are left out so ThingSpeak keeps the previous
    value rather than writing a bogus one.
    """
    url = "http://api.thingspeak.com/update?api_key={}".format(THINGSPEAK_API_KEY)
    for field, value in (("field1", temp_c),
                         ("field2", ph_value),
                         ("field3", turb_pct)):
        if value is not None:
            url += "&{}={:.2f}".format(field, value)
    return url


# ---------- one-time network init ----------

def network_init():
    print("Waiting for module...")
    if not wait_for_module():
        print("No response — check wiring/power")
        return False

    time.sleep(2)
    flush_uart()

    if not wait_for_sim():
        print("SIM not ready")
        return False
    print("SIM ready")
    flush_uart()
    send_at('AT+COPS=0', wait=10000)

    print("Checking registration...")
    if not wait_for_registration():
        print("Not registered — stopping")
        return False
    print("Registered.\n")

    print("[A] Current context definitions")
    cgdcont = show("CGDCONT?", 'AT+CGDCONT?', wait=2000)
    show("CGACT?", 'AT+CGACT?', wait=2000)

    apn = get_apn_for_cid(cgdcont, 2)
    print(f"\n[B] APN on CID 2: {apn!r}")

    if apn:
        print("Mirroring that APN onto CID 1 and activating...")
        show("CGDCONT=1", f'AT+CGDCONT=1,"IP","{apn}"')
        show("CGACT=1,1", 'AT+CGACT=1,1', wait=5000)
    else:
        print("Couldn't read CID 2's APN — trying to activate CID 1 as-is")
        show("CGACT=1,1", 'AT+CGACT=1,1', wait=5000)

    print("\n[C] Context state after activation")
    show("CGACT?", 'AT+CGACT?', wait=2000)
    show("CGPADDR", 'AT+CGPADDR', wait=2000)

    return True


# ---------- main loop ----------

def main():
    if not network_init():
        print("Network init failed — not entering upload loop.")
        return

    print("\nEntering upload loop...\n")
    while True:
        print("=== READ ===")
        temp_c, ph_value, turb_pct = read_all()

        url = build_thingspeak_url(temp_c, ph_value, turb_pct)
        status, body = http_get(url)

        print("=== UPLOAD ===")
        print("  field1 temp:      ", "n/a" if temp_c is None
              else "{:.2f} C".format(temp_c))
        print("  field2 pH:        ", "n/a" if ph_value is None
              else "{:.2f}".format(ph_value))
        print("  field3 turbidity: ", "{:.2f} %".format(turb_pct))
        print("Status:", status, "| Entry ID:", body)
        print()

        gc.collect()
        time.sleep(UPDATE_INTERVAL_S)


if __name__ == "__main__":
    main()
