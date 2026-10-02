# Multi-sensor drone detection: setup and testing

```
 [Pi + HackRF] sensor_node.py ──┐
 [Pi + HackRF] sensor_node.py ──┼──► drone_dashboard_backend.py ──► dashboard (browser)
 [Pi + HackRF] sensor_node.py ──┘      (central server)
```

Each sensor sweeps 868MHz, 2.4GHz, 5.165-5.255GHz and 5.72-5.855GHz (about
1s per sweep), detects drone links itself, and posts
one report per sweep (~1s) to the server: its position, its spectrum (power
per frequency) and its detections with signal levels. The server merges the
same drone seen by several sensors into one track, shows which sensor is
**nearest** (loudest), and **estimates a position** from the relative levels.

## 1. Central server

```
python3 drone_dashboard_backend.py --no-local-sensor
```
Open `http://<server-ip>:8000`. Leave out `--no-local-sensor` if a HackRF
is plugged into the server too (it then counts as sensor `local`).

## 2. Each Raspberry Pi sensor (HackRF or Pluto)

Raspberry Pi 4 or 5 (the 5 is recommended: each sweep does ~28 FFT
batches). Use a powered USB hub or the Pi's own USB 3 port for the HackRF.

```
sudo apt install hackrf python3-numpy
pip install python_hackrf --break-system-packages
# copy rf_detector.py, detector_pipeline.py, control_link.py, sensor_node.py
# (and drone_signatures.json if you calibrated) onto the Pi
python3 sensor_node.py --id north-wall --lat 51.50720 --lon -0.12760 \
                       --server http://192.168.1.50:8000
```
- `--id` must be unique per sensor.
- Position: from a phone GPS app at the antenna, or leave `--lat/--lon` off and
  place it by clicking the dashboard map (pick the sensor in the map header).
- Keep drones off for the first ~25s while each sensor learns its background.
- Use the same `--lna/--vga/--amp` on every sensor, and the same antenna type,
  so their levels are comparable.

### Using a Pluto instead (ADALM-Pluto, Pluto+, "Pluto Sky")

```
sudo apt install libiio-utils python3-libiio
pip install pyadi-iio --break-system-packages
iio_info -s                      # should list the Pluto (usb:... or ip:192.168.2.1)
python3 sensor_node.py --id gate --sdr pluto --pluto-uri ip:192.168.2.1 \
                       --pluto-gain 40 --server http://192.168.1.50:8000
```
The Pluto must be able to tune 5.8GHz (the common "AD9364" firmware unlock).
The single-machine dashboard works the same way:
`python3 drone_dashboard_backend.py --sdr pluto`.

### Several SDRs on one Pi

Run one `sensor_node.py` per SDR, each with its own `--id`:
```
python3 sensor_node.py --id north-hackrf --sdr hackrf --hackrf-serial <serial from hackrf_info> --server ...
python3 sensor_node.py --id north-pluto  --sdr pluto  --pluto-uri ip:192.168.2.1 --server ...
python3 sensor_node.py --id north-pluto2 --sdr pluto  --pluto-uri ip:192.168.3.1 --server ...
```
(Each extra Pluto needs its own IP - set in its config.txt - or use its
`usb:` URI from `iio_info -s`.)

### Matching levels between SDRs (for positioning)

A Pluto and a HackRF - or two antennas - report different levels for the
same drone at the same distance. Detection doesn't care, but positioning
compares levels between sensors, so match them once:
1. Put the drone (transmitting) 5m from sensor A, note its level on the
   dashboard's "Power at each sensor" line.
2. Move it 5m from sensor B, same height and orientation, note the level.
3. Start B with `--level-offset-db <A's level - B's level>`.

To start it at boot, `/etc/systemd/system/drone-sensor.service`:
```
[Unit]
Description=Drone sensor
After=network-online.target
[Service]
WorkingDirectory=/home/pi/drone-detector
ExecStart=/usr/bin/python3 sensor_node.py --id north-wall --lat 51.50720 --lon -0.12760 --server http://192.168.1.50:8000
Restart=always
[Install]
WantedBy=multi-user.target
```
then `sudo systemctl enable --now drone-sensor`.

## What it detects

| Band | Detector | Label on the dashboard |
|---|---|---|
| 868MHz | packet-level hopping detector (control_link.py): packets in 5 of the last 10 sweeps, on 6+ channels over 2+MHz | FHSS control link (868MHz) - ExpressLRS/Crossfire-like |
| 2.4GHz, 5.2GHz, 5.8GHz | calibration-free hopping detector (needs ~25s background learning at start) | Frequency-hopping video link |
| 5.2GHz, 5.8GHz | shape rule (FM taper, >=5MHz wide), boosted on standard FPV channels | Analog FPV video link |
| any | flat 10-40MHz block | Wideband digital link (OFDM - may be WiFi) |
| any | signatures learned with calibrate_detector.py | ... matches calibrated '<name>' |

A control link and a video link seen together by one sensor are marked
"likely FPV drone" and raised to 92%.

**Duty cycle and airtime** decide how much a shape match is trusted:
duty = % of sweeps over 30s the signal's core was busy; airtime = % of
one 6.5ms capture it was transmitting. Continuous (both >= 80%) raises a
shape match; bursty (either < 40%) halves it; the WiFi-channel penalty
only applies to signals that aren't continuous. Every detection on the
dashboard has a "Why it says this" list, and the How It Works page explains
all the rules.

`--bands 5.8wide` sweeps 5.645-5.925GHz instead of 5.72-5.855GHz, which also
catches analog FPV set to channels outside that range (e.g. 5658, 5695,
5880, 5917MHz).

The 868MHz detector is tested on simulated ExpressLRS-like packets and
realistic decoys (alarm on 868.3, smart meter on 868.95 every second,
LoRaWAN on 8 channels every 2s, a constant carrier): decoys gave no
detections, the link was flagged from the 5th sweep. **It has not yet seen a
real ExpressLRS/Crossfire link** - test it with a real one before relying on it.

## Speed, priority and the site baseline

**Measure your SDR's retune time once** (stop the dashboard first; needs an
FM radio station - they're everywhere):
```
python3 measure_retune.py              # HackRF
python3 measure_retune.py --sdr pluto  # Pluto
```
It saves `sdr_timing.json`; every program then waits exactly as long as
your SDR needs after each retune instead of the cautious 26ms default.

- Each band is sent to the dashboard as soon as it is swept.
- A band with suspicious activity automatically gets an extra visit per
  cycle until it goes quiet. Fixed priority: `--band-reps 2.4=2`.
- `--samples 65536` halves the listening time per slice (~2x faster,
  slightly rougher noise floor; default 131072).

**Site baseline** - record once per sensor, with no drones flying:
```
python3 drone_dashboard_backend.py --baseline-minutes 10
python3 sensor_node.py --id north-wall ... --baseline-minutes 10
```
Saved to `site_baseline.json` and loaded automatically next time (no 25s
learning). Per MHz it keeps average/peak level, variance, occupancy, burst
length, on/off changes, typical width, persistent and periodic emitters.
Signals on normally-busy frequencies are marked down (x0.3 at >=80%,
x0.7 at 20-80%), on normally-quiet ones marked new (+5%). Re-record when
the site's equipment changes. `--no-baseline` ignores it.

**Dual-band correlation** (Chris's F7/F9) runs automatically on 2.4 + 5GHz.

## 3. Where to put sensors

Measured with `simulate_sensors.py --offline` (200m site, 4dB level wobble,
2dB per-sensor gain error, realistic detection range):

| Layout | Median position error | Nearest sensor right |
|---|---|---|
| 4 corners | ~51m | ~77% |
| 8 around the perimeter + 1 in the middle | ~29m | ~72% |

Over a full simulated flight (in from outside, hover, out) with the 9-sensor
layout: median error 20m, 90% within 91m, the true position inside the
shown +/- 86% of the time, inside/outside the perimeter right 78% of the
time. Outside the sensor ring it only reports "OUTSIDE, to the SW" etc. The
worst errors happen as a drone crosses the wall - that is the limit of
signal-strength positioning, not something more filtering fixes (a stronger
filter was tried and made it worse).

- Sensors on the perimeter **plus at least one inside** remove most of the
  "is it just inside or well outside the wall?" ambiguity.
- Spacing must be within detection range. A small 2.4GHz toy drone measured
  ~36dB above noise at ~3m; the detector needs ~15dB, so expect tens of
  metres to ~100m for weak drones, more for FPV video transmitters
  (25mW-1W). Measure it on site (below) before choosing spacing.
- Mount antennas high with a clear view; walls and buildings both block
  signal and make the position estimate worse.

## 4. Testing the position ("GPS") estimate

**Dry run, no hardware:**
```
python3 drone_dashboard_backend.py --no-local-sensor     # terminal 1
python3 simulate_sensors.py --lat <site lat> --lon <site lon>   # terminal 2
```
Nine virtual sensors appear on the map and a virtual drone flies in, hovers
over the middle and leaves; the script prints the real error each second.

**Field test (the one that matters):**
1. Put 3+ sensors out at known positions.
2. Hover the drone at marked spots (e.g. each sensor, the middle, outside the
   fence) for ~30s each, noting the spot's GPS position from a phone.
3. Note the dashboard's estimated position and ± for each spot.
4. Also find the range: walk the drone away from one sensor until it shows
   GONE - that distance sets your sensor spacing.

## Limits

- Signal-strength positioning gives tens of metres, not GPS precision. Walls,
  drone orientation and reflections move levels by several dB.
- Two drones on the same band at once are currently merged into one track.
- "Signal rising/falling" is relative to whichever sensor hears it best, not
  to the site.
- Covered: 2.4GHz hopping video links (calibration-free), 5.8GHz analog FPV
  video (shape rule), flat wideband digital links (flagged "may be WiFi").
  868MHz FHSS control links (not yet tested on a real one). Not yet: 915MHz
  (US) and 2.4GHz ExpressLRS control links, 1.2/1.3GHz long-range video,
  DJI's own protocol, and Remote ID / DJI DroneID decoding (which would give
  the drone's own GPS).

## Per-band thresholds (thresholds.json)

Every band uses the same hopping-detector thresholds until you have data saying
otherwise. To change one band only, create `thresholds.json` next to
`rf_detector.py` (it's per site, so it isn't in git):

```json
{
  "5.8GHz": {"hop_min_db": 18},
  "2.4GHz": {"hop_min_new_channels": 4, "hop_window_s": 6}
}
```

Settings not listed keep their defaults. Restart the server or sensor to apply.
The table on the dashboard's **How It Works** page shows the values in use,
and changed values are highlighted. Base changes on recordings (drone off and
drone on, at that site), not guesses.

## Power by Sensor page

This page shows every 1 MHz of a band, each sensor's level (dB above its own
noise, plus `--level-offset-db`) and the strongest reading in the last 5 s.
**Closest** marks the loudest sensor when it is at least 6 dB above the median
of the others. Rows on a current detection's frequencies are highlighted. Each
drone on the dashboard also shows this check ("closest by power"). It needs at
least two sensors that cover the same band.
