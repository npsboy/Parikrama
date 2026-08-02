import gc
from machine import UART
import time

gc.collect()

uart = UART(2, baudrate=115200, tx=33, rx=25, timeout=1000)

# ---------- helpers ----------

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

# ---------- run ----------

print("Waiting for module...")
if not wait_for_module():
    print("No response — check wiring/power")
else:
    time.sleep(2)
    flush_uart()

    if not wait_for_sim():
        print("SIM not ready")
    else:
        print("SIM ready")
        flush_uart()
        send_at('AT+COPS=0', wait=10000)

        print("Checking registration...")
        if not wait_for_registration():
            print("Not registered — stopping")
        else:
            print("Registered.\n")

            print("[A] Current context definitions")
            cgdcont = show("CGDCONT?", 'AT+CGDCONT?', wait=2000)
            show("CGACT?", 'AT+CGACT?', wait=2000)

            # Whatever APN the live context is using, mirror it onto CID 1,
            # since the HTTP stack defaults to CID 1 and won't accept a
            # CID parameter on this firmware.
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

            print("\n[D] DNS check (does name resolution work?)")
            show("CDNSGIP", 'AT+CDNSGIP="example.com"', wait=10000)

            print("\n[E] HTTP GET")
            status, body = http_get("http://example.com")

            print("\n=== RESULT ===")
            print("Status:", status)
            print("Body:", body)