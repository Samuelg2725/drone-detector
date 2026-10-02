# Raspberry Pi 5 sensor setup (drone-detector)

A step-by-step build for one Pi 5 running as a drone-detection sensor with a
Pluto SDR, following the same conventions as the Revector SNS build but pointed
at **this** system's code (`sensor_node.py` reporting to
`drone_dashboard_backend.py`).

This Pi uses:

| Setting | Value |
|---|---|
| Hostname | `revector` |
| Username | `revector` |
| Password | `R3v3ct0r` |
| Pi static IP (Ethernet) | `10.70.0.11/24` |
| Gateway / router | `10.70.0.1` |
| Host laptop (runs the dashboard) | `10.70.0.2` |
| DNS | `10.70.0.1`, `8.8.8.8` |
| Internet | over Wi-Fi (`wlan0`); lab traffic over Ethernet (`eth0`) |

> The host (your laptop) runs `drone_dashboard_backend.py`. The Pi runs
> `sensor_node.py` and reports to the host over HTTP on port **8000**. Unlike
> the old SNS build there is no per-Pi WebSocket port to line up — every sensor
> just POSTs to `http://10.70.0.2:8000`.

---

## 1. Flash the SD card (on your laptop)

Use a **fresh** SD card. Keep the old 4-Pluto card untouched as a backup.

1. Install **Raspberry Pi Imager** (raspberrypi.com/software).
2. Choose:
   - Device: **Raspberry Pi 5**
   - OS: **Raspberry Pi OS Lite (64-bit)** — no desktop; it's a headless sensor, and 64-bit is needed by the SDR libraries.
   - Storage: your SD card.
3. Click **Edit Settings** (the gear) **before** writing:
   - **Hostname:** `revector`
   - **Enable SSH** → "Use password authentication"
   - **Username:** `revector`  **Password:** `R3v3ct0r`
   - **Configure wireless LAN:** your Wi-Fi name + password, and set the correct **Wi-Fi country**. This gives the Pi internet on first boot to install packages.
   - **Locale:** your timezone/keyboard.
4. Write the card.

---

## 2. First boot on a monitor (one time)

Do the first boot with a Micro-HDMI monitor and USB keyboard attached, **not**
over SSH. You're about to change networking, and if you get it wrong over SSH
you'd lock yourself out — on a local screen you can always fix it.

Log in as `revector` / `R3v3ct0r`, then update:

```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

---

## 3. Give the Pi a fixed Ethernet address

Install the networking tools:

```bash
sudo apt install -y git python3-numpy
```

Raspberry Pi OS (Bookworm) uses **NetworkManager**, so set the static address
with `nmcli` (this is the modern replacement for editing `dhcpcd.conf`):

```bash
# find the wired connection name (usually "Wired connection 1")
nmcli connection show

sudo nmcli connection modify "Wired connection 1" \
  ipv4.method manual \
  ipv4.addresses 10.70.0.11/24 \
  ipv4.gateway 10.70.0.1 \
  ipv4.dns "10.70.0.1 8.8.8.8" \
  ipv4.route-metric 200

# keep Wi-Fi as the preferred route for internet (lower metric wins)
sudo nmcli connection modify preconfigured ipv4.route-metric 100 2>/dev/null || true

sudo nmcli connection up "Wired connection 1"
```

> **Why the route-metric lines:** pinning a static IP on Ethernet can steal the
> default route and break the Pi's Wi-Fi internet (which you need for
> installing packages). Giving Wi-Fi the lower metric (100) and Ethernet the
> higher (200) means internet goes over Wi-Fi while lab traffic to
> `10.70.0.x` goes over Ethernet. This is the same problem the SNS "Wi-Fi & IP
> Manager" existed to fix.

Check it:

```bash
ip addr show eth0      # inet should be 10.70.0.11/24
ip route               # default route should be via wlan0
ping -c2 8.8.8.8       # internet still works (over Wi-Fi)
```

---

## 4. Wireless connection

If you set Wi-Fi in the Imager it's already up. To add or change it later:

```bash
sudo nmcli device wifi list
sudo nmcli device wifi connect "YOUR_SSID" password "YOUR_WIFI_PASSWORD"
```

Confirm both links are up at once:

```bash
nmcli -t -f DEVICE,STATE,CONNECTION device   # eth0 and wlan0 both "connected"
```

Keep the Pi's own Wi-Fi radio **on** here — unlike the RNR/DND sensors, a
passive SDR on a separate antenna isn't polluted by the Pi's Wi-Fi, and you
want it for internet and for SSH when Ethernet isn't cabled.

---

## 5. Install the Pluto drivers

```bash
sudo apt install -y libiio-utils python3-libiio
pip install pyadi-iio --break-system-packages
```

Plug **one** Pluto into the Pi over USB (start with one; add the rest later).
Then check the Pi can see it:

```bash
iio_info -s
```

You should see a line like `usb:1.5.5` or `ip:192.168.2.1`. **Note that
address** — it's your `--pluto-uri`.

> **5.8 GHz:** the Pluto must be unlocked to tune 5.8 GHz (the AD9364 firmware
> change). Your old 4-Pluto setup almost certainly did this already, and it
> lives on the Pluto, not the SD card, so it carries over. If the Pi later
> says it can't tune 5.8 GHz, that unlock is missing.

---

## 6. Copy the sensor code onto the Pi

The Pi needs **five** files from your drone-detector project (plus
`drone_signatures.json` only if you calibrated). Run this **on your laptop**,
from inside the project folder:

```bash
ssh revector@10.70.0.11 mkdir -p drone-detector
scp rf_detector.py detector_pipeline.py control_link.py site_baseline.py sensor_node.py \
    revector@10.70.0.11:drone-detector/
```

(If you SSH in for the first time it asks to confirm the fingerprint — type
`yes`, then the password `R3v3ct0r`.)

> You can also `git clone` the branch onto the Pi instead of copying files, if
> the Pi has access to your repo.

---

## 7. Run it

**On the laptop (the host)** — start the dashboard, and give the host its own
matching static address on the lab LAN (`10.70.0.2/24`, mask `255.255.255.0`)
on its Ethernet adapter:

```bash
python drone_dashboard_backend.py
```

Open `http://10.70.0.2:8000` in a browser.

**On the Pi** — over SSH:

```bash
ssh revector@10.70.0.11
cd drone-detector
python3 sensor_node.py --id revector-11 --sdr pluto --pluto-uri ip:192.168.2.1 \
                       --pluto-gain 40 --server http://10.70.0.2:8000 \
                       --lat <your latitude> --lon <your longitude>
```

- Use the `--pluto-uri` address from step 5.
- `--id` must be unique per sensor. Keep it aligned to the unit number, e.g. `revector-11` for `10.70.0.11`.
- Position: from a phone GPS app at the antenna, or leave `--lat/--lon` off and click the sensor's spot on the dashboard map.
- **Keep drones off** for the first ~30 s while it learns the background, then while it builds the 10-minute site baseline (detection still runs during the baseline — the System status card shows progress).

Within a few seconds `revector-11` should appear on the dashboard's **System
status** card.

---

## 8. Several Plutos on one Pi

Run one `sensor_node.py` per Pluto, each with its own `--id` and `--pluto-uri`:

```bash
python3 sensor_node.py --id revector-11a --sdr pluto --pluto-uri ip:192.168.2.1 --server http://10.70.0.2:8000
python3 sensor_node.py --id revector-11b --sdr pluto --pluto-uri ip:192.168.3.1 --server http://10.70.0.2:8000
```

Each extra Pluto needs its own IP (set in its `config.txt`) or its own `usb:`
URI from `iio_info -s`. On a Pi 5 run each in its own terminal (or `tmux`
window, or a systemd service — see below).

> **Splitting bands for full coverage:** instead of every Pluto sweeping every
> band, you can dedicate each to a band with `--bands`, e.g. one on `2.4` and
> one on `5.8`. Each band then gets continuous coverage, which is the real
> answer to the duty-cycle concern.

---

## 9. Match levels between sensors (for positioning)

Positioning and the **Power by Sensor** page compare signal levels between
sensors, so two sensors must read the same drone at the same distance as the
same level. Detection doesn't care, but positioning does.

1. Put the transmitting drone ~5 m from sensor A; note its level on the **Power by Sensor** page.
2. Move it ~5 m from sensor B, same height and orientation; note the level.
3. If B reads, say, 4 dB lower, start B with `--level-offset-db 4`.

Use the same gains and antenna type on every sensor to keep this small.

---

## 10. Run headless on boot (optional)

To make the sensor start automatically and restart if it dies, create a
systemd service on the Pi:

```bash
sudo tee /etc/systemd/system/drone-sensor.service >/dev/null <<'EOF'
[Unit]
Description=Drone detector sensor
After=network-online.target
Wants=network-online.target

[Service]
User=revector
WorkingDirectory=/home/revector/drone-detector
ExecStart=/usr/bin/python3 sensor_node.py --id revector-11 --sdr pluto \
          --pluto-uri ip:192.168.2.1 --pluto-gain 40 \
          --server http://10.70.0.2:8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now drone-sensor
systemctl status drone-sensor          # check it's running
journalctl -u drone-sensor -f          # watch its output
```

---

## Troubleshooting

- **Sensor not on the dashboard:** check the Pi can reach the host —
  `ping 10.70.0.2` and `curl http://10.70.0.2:8000/api/sensors`. If ping works
  but curl doesn't, the laptop's firewall is blocking port 8000.
- **Lost internet after the static IP:** the Ethernet route stole the default
  route. Re-check the route metrics in step 3 (`ip route` — default should be
  via `wlan0`).
- **`iio_info -s` shows nothing:** the Pluto isn't enumerating. Try a different
  USB cable/port (use the Pi 5's USB 3 ports), and `lsusb` should list
  `Analog Devices` (`0456:b673`/`b674`).
- **Can't tune 5.8 GHz:** the Pluto's AD9364 unlock is missing (see step 5).
