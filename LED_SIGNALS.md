# LED Signals

Four LEDs, left to right:

| Pin | Color  | Meaning        |
|-----|--------|----------------|
| 12  | Red    | SIM / network  |
| 13  | Blue 1 | Temperature / turbidity |
| 14  | Green  | GPS            |
| 15  | Blue 2 | pH             |

Blink states: **off**, **on** (solid), **blink fast**, **blink slow**.

## Red (SIM / network)

| State       | Meaning              |
|-------------|----------------------|
| On          | SIM module detected  |
| Blink fast  | SIM card detected    |
| Blink slow  | Registered on network ("sim working") |

## Blue 1 (temperature / turbidity)

| State       | Meaning                     |
|-------------|------------------------------|
| Blink fast  | Temperature sensor detected |
| Blink slow  | Turbidity sensor detected   |

Both sensors share this LED, so turbidity's "detected" state overrides temperature's once both have initialized.

## Green (GPS)

| State       | Meaning                                   |
|-------------|--------------------------------------------|
| Blink fast  | GPS module detected, no fix yet — or no fix for the last 30 minutes |
| Blink slow  | GPS has a fix                             |

If a fix is lost, the last known location keeps being used, but the LED goes back to blinking fast once 30 minutes have passed without a fresh fix (`NO_FIX_TIMEOUT_MS` in `main.py`). It returns to blinking slow as soon as a new fix comes in.

## Blue 2 (pH)

| State       | Meaning            |
|-------------|--------------------|
| Blink slow  | pH sensor detected |

## Startup / shutdown

All LEDs are forced off at the start of `main.py` and again when the program exits (success, failure, or exception).
