import time
import onewire
import ds18x20
from machine import ADC, Pin

# pH sensor on GPIO 34
ph = ADC(Pin(34))
ph.atten(ADC.ATTN_11DB)

# DS18B20 temperature sensor on GPIO 4
dat = Pin(4)
ds = ds18x20.DS18X20(onewire.OneWire(dat))
roms = ds.scan() or []
print("Temperature devices found:", roms)

def read_sensors():
    ph_value = ph.read()
    ds.convert_temp()
    time.sleep_ms(750)
    temps = [ds.read_temp(rom) for rom in roms]
    return ph_value, temps

NUM_READINGS = 20

def ph_from_adc(adc, temp_c):
    # slope fitted from your measurements
    slope = -0.00579 + 0.000035 * temp_c

    # intercept fitted from your measurements
    intercept = 17.78 - 0.073 * temp_c

    return slope * adc + intercept

def average_temperature(temps):
    valid_temps = [temp for temp in temps if temp is not None]
    if not valid_temps:
        return None
    return sum(valid_temps) / len(valid_temps)

def choose_mode():
    while True:
        print("\nType avg for 20-reading average, or normal for normal display.")
        choice = input("> ").strip().lower()
        if choice in ("avg", "a", "average"):
            return "avg"
        if choice in ("normal", "n", "display"):
            return "normal"
        print("Please type avg or normal.")

def record_and_show_average():
    print("\nRecording {} readings...".format(NUM_READINGS))
    ph_readings = []
    temp_readings = [[] for _ in roms]

    for i in range(NUM_READINGS):
        print("  Recording {}/{}".format(i + 1, NUM_READINGS))
        ph_val, temps = read_sensors()
        ph_readings.append(ph_val)
        for j, temp in enumerate(temps):
            temp_readings[j].append(temp)
        time.sleep_ms(250)

    print("\n--- Averages over {} readings ---".format(NUM_READINGS))
    avg_adc = sum(ph_readings) / len(ph_readings)
    print("  Avg pH ADC value:    {:.1f}".format(avg_adc))

    avg_temps = []
    for j, readings in enumerate(temp_readings):
        if readings:
            avg_temp = average_temperature(readings)
            if avg_temp is None:
                print("  Avg Temperature {}:   unavailable".format(j + 1))
            else:
                avg_temps.append(avg_temp)
                print("  Avg Temperature {}:   {:.2f} C".format(j + 1, avg_temp))

    avg_temp_c = average_temperature(avg_temps)
    if avg_temp_c is None:
        print("  Predicted pH:           unavailable (no temperature reading)")
    else:
        actual_ph = ph_from_adc(avg_adc, avg_temp_c)
        print("  Predicted pH:           {:.2f}".format(actual_ph))

mode = choose_mode()

if mode == "avg":
    record_and_show_average()
else:
    while True:
        print("___________________________")
        adc_value, temps = read_sensors()
        temp_c = average_temperature(temps)
        print("pH ADC value:", adc_value)
        if temp_c is None:
            print("Predicted pH: unavailable (no temperature reading)")
        else:
            print("Predicted pH: {:.2f}".format(ph_from_adc(adc_value, temp_c)))
        for temp in temps:
            print("Temperature:", temp)
        time.sleep(1)
