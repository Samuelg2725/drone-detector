# Multi-sensor drone detection: setup and testing

```
 [Pi + HackRF] sensor_node.py ──┐
 [Pi + HackRF] sensor_node.py ──┼──► drone_dashboard_backend.py ──► dashboard (browser)
 [Pi + HackRF] sensor_node.py ──┘      (central server)
```

Each sensor sweeps 2.4GHz and 5.8GHz, detects drone links itself, and posts
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

## 2. Each Raspberry Pi sensor

Raspberry Pi 4 or 5 (the 5 is recommended: each sweep does ~28 FFT
batches). Use a powered USB hub or the Pi's own USB 3 port for the HackRF.

```
sudo apt install hackrf python3-numpy
pip install python_hackrf --break-system-packages
# copy rf_detector.py, detector_pipeline.py, sensor_node.py
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

## 3. Where to put sensors

Measured with `simulate_sensors.py --offline` (200m site, 4dB level wobble,
2dB per-sensor gain error, realistic detection range):

| Layout | Median position error | Nearest sensor right |
|---|---|---|
| 4 corners | ~51m | ~77% |
| 8 around the perimeter + 1 in the middle | ~29m | ~72% |

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
- Covered: 2.4GHz hopping video links (calibration-free), 5.8GHz analog FPV
  video (shape rule), flat wideband digital links (flagged "may be WiFi").
  Not yet: 868/915MHz control links (ExpressLRS, Crossfire - very common on
  FPV drones in the UK), 1.2/1.3GHz long-range video, DJI's own protocol, and
  Remote ID / DJI DroneID decoding (which would give the drone's own GPS).
