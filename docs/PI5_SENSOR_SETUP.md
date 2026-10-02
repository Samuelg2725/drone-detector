# Raspberry Pi 5 sensor setup (drone-detector) — Mac, headless, 4 Plutos

A step-by-step build for a Raspberry Pi 5 running as a drone-detection sensor
with **four Pluto (Pluto Sky) SDRs**, set up **headless from a Mac over Wi-Fi**
(no monitor, no keyboard, nothing plugged into the Mac). It follows the lab's
network conventions but points at **this** system's code (`sensor_node.py`
reporting to `drone_dashboard_backend.py`).

This Pi uses:

| Setting | Value |
|---|---|
| Hostname | `revector` |
| Username | `revector` |
| Password | `R3v3ct0r` |
| Pi static IP (Ethernet, for the deployed lab LAN) | `10.70.0.11/24` |
| Gateway / router | `10.70.0.1` |
| Host (laptop running the dashboard) | `10.70.0.2` |
| DNS | `10.70.0.1`, `8.8.8.8` |
| Internet / setup / early testing | over Wi-Fi (`wlan0`) |

> **Two phases.** For **bring-up and testing now**, everything runs over
> **Wi-Fi** — the Pi and your Mac just need to be on the same Wi-Fi, and nothing
> is plugged into the Mac. The `10.70.0.x` **wired** LAN (steps 7–8) is only for
> the real multi-sensor deployment later.

> **Four Plutos = four bands.** With one Pi you get the best result by giving
> each Pluto one band (868, 2.4, 5.2, 5.8). Every band is then watched
> continuously instead of in turn, which removes the duty-cycle gap. (Spreading
> Plutos across different *locations* for positioning comes later, when you have
> more than one Pi.)

---

## 1. Flash the SD card (in Raspberry Pi Imager on your Mac)

Use a **fresh** SD card. Keep the old 4-Pluto card untouched as a backup.

1. Install **Raspberry Pi Imager** (raspberrypi.com/software).
2. Choose:
   - Device: **Raspberry Pi 5**
   - OS: **Raspberry Pi OS Lite (64-bit)** — headless, and 64-bit is required by the SDR libraries.
   - Storage: your SD card.
3. Click **Edit Settings** (the gear) **before** writing, and set:
   - **Hostname:** `revector`
   - **Enable SSH** → "Use password authentication"
   - **Username:** `revector`  **Password:** `R3v3ct0r`
   - **Configure wireless LAN:** your Wi-Fi name + password, and the correct **Wi-Fi country**. (This is what lets the Pi boot straight onto your Wi-Fi with SSH on — no monitor needed.)
   - **Locale:** your timezone/keyboard.
4. Write the card.

---

## 2. Boot headless and SSH in from your Mac

- Put the card in the Pi, plug in **power** (USB-C) and the **four Plutos** (a powered USB hub is wise — four Plutos draw real current). Nothing goes to the Mac.
- Power on and wait ~90 seconds for first boot.
- On your Mac, open **Terminal** and connect:

```bash
ssh revector@revector.local
```

Type `yes` to the fingerprint prompt, then the password `R3v3ct0r`.
(`.local` works natively on macOS. If it doesn't resolve, find the Pi's Wi-Fi
IP with `ping revector.local` or `arp -a | grep -i dc:a6:32`, then
`ssh revector@<that-ip>`.)

> You don't need PuTTY or WinSCP — those were for the Windows SNS host. macOS
> has `ssh` and `scp` built in.

Update the Pi:

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

Wait ~60 s and `ssh revector@revector.local` back in.

---

## 3. Install the tools and Pluto drivers

```bash
sudo apt install -y git python3-numpy libiio-utils python3-libiio
pip install pyadi-iio --break-system-packages
```

---

## 4. Find the four Plutos

With all four plugged in:

```bash
iio_info -s
```

You should see **four** entries. Addressed over USB they look like:

```
    0: 0456:b673 (Analog Devices Inc. PlutoSDR) [usb:1.2.5]
    1: 0456:b673 (Analog Devices Inc. PlutoSDR) [usb:1.3.5]
    2: 0456:b673 (Analog Devices Inc. PlutoSDR) [usb:1.4.5]
    3: 0456:b673 (Analog Devices Inc. PlutoSDR) [usb:1.5.5]
```

**Write down the four `usb:...` strings.** These are what you pass to
`--pluto-uri`.

> **Why `usb:` and not `ip:`?** Every Pluto defaults to `ip:192.168.2.1`, so
> four of them on one Pi would all claim the same address and clash. The
> `usb:...` id is unique per physical port and needs no per-Pluto
> reconfiguration — much simpler with four on one Pi.

If you see fewer than four: try a powered USB hub and the Pi 5's USB-3 ports,
and check `lsusb | grep -i 0456` lists four `Analog Devices` devices.

> **5.8 GHz:** each Pluto that will cover 5.2/5.8 GHz must be unlocked to tune
> that high (the AD9364 change). Your old 4-Pluto rig almost certainly did this
> already, and it lives on the Pluto, not the SD card, so it carries over.

---

## 5. Copy the sensor code onto the Pi

The Pi needs **five** files (plus `drone_signatures.json` only if you
calibrated). Run this **on your Mac**, from inside your drone-detector folder:

```bash
ssh revector@revector.local mkdir -p drone-detector
scp rf_detector.py detector_pipeline.py control_link.py site_baseline.py sensor_node.py \
    revector@revector.local:drone-detector/
```

---

## 6. Run — one process per Pluto, one band each

**On your Mac**, start the dashboard and find your Mac's Wi-Fi IP:

```bash
python drone_dashboard_backend.py        # leave this running
ipconfig getifaddr en0                    # your Mac's Wi-Fi IP, e.g. 192.168.1.50
```

Open `http://localhost:8000` on the Mac.

**On the Pi** (over SSH), start four sensors — swap in the four `usb:...` ids
from step 4 and your Mac's IP. Run each in its own `tmux` window or background
them with `&`:

```bash
cd drone-detector
MAC=192.168.1.50          # <-- your Mac's Wi-Fi IP

python3 sensor_node.py --id revector-11-868 --sdr pluto --pluto-uri usb:1.2.5 \
        --bands 868 --server http://$MAC:8000 &
python3 sensor_node.py --id revector-11-24  --sdr pluto --pluto-uri usb:1.3.5 \
        --bands 2.4 --server http://$MAC:8000 &
python3 sensor_node.py --id revector-11-52  --sdr pluto --pluto-uri usb:1.4.5 \
        --bands 5.2 --server http://$MAC:8000 &
python3 sensor_node.py --id revector-11-58  --sdr pluto --pluto-uri usb:1.5.5 \
        --bands 5.8 --server http://$MAC:8000 &
```

- Each `--id` must be unique; the suffix says which band that Pluto covers.
- **Keep drones off** for the first ~30 s while each learns its background, then while the 10-minute site baseline builds (detection still runs during the baseline — the **System status** card shows progress for all four).
- Within a few seconds all four should appear on the dashboard's System status card.

Set the location by clicking the map on the dashboard (or add `--lat`/`--lon`).
For four Plutos at the **same** spot, give them the same position.

---

## 7. (Deployment only) Fixed wired IP on the lab LAN

Do this **only** when you move to the wired `10.70.0.x` network. Because it
changes `eth0` while you're connected over Wi-Fi (`wlan0`), it won't drop your
SSH session.

Raspberry Pi OS (Bookworm) uses **NetworkManager**, so use `nmcli` (not
`dhcpcd.conf`):

```bash
nmcli connection show                    # find the wired name, usually "Wired connection 1"

sudo nmcli connection modify "Wired connection 1" \
  ipv4.method manual \
  ipv4.addresses 10.70.0.11/24 \
  ipv4.gateway 10.70.0.1 \
  ipv4.dns "10.70.0.1 8.8.8.8" \
  ipv4.route-metric 200

# keep Wi-Fi as the preferred internet route (lower metric wins)
sudo nmcli connection modify preconfigured ipv4.route-metric 100 2>/dev/null || true

sudo nmcli connection up "Wired connection 1"
```

Check:

```bash
ip addr show eth0      # inet 10.70.0.11/24
ip route               # default route via wlan0 (internet over Wi-Fi)
```

> **Why the metrics:** pinning a static Ethernet IP can steal the default route
> and kill Wi-Fi internet. Giving Wi-Fi the lower metric (100) keeps internet on
> `wlan0` while lab traffic to `10.70.0.x` goes over `eth0`. This is the trap the
> old "Wi-Fi & IP Manager" existed to fix.

On the wired LAN, point the sensors at the host at `10.70.0.2` instead of your
Mac's Wi-Fi IP (`--server http://10.70.0.2:8000`).

---

## 8. Match levels between sensors (for positioning, later)

Positioning and the **Power by Sensor** page compare levels **between
locations on the same band**, so when you have more than one Pi, each must read
the same drone at the same distance as the same level.

1. Put the transmitting drone ~5 m from Pi A; note its level on the **Power by Sensor** page.
2. Move it ~5 m from Pi B, same height/orientation; note the level.
3. If B reads 4 dB lower, start B's sensors with `--level-offset-db 4`.

Use the same gain and antenna type everywhere to keep this small.

---

## 9. Run headless on boot (optional)

To auto-start all four on boot, create one systemd service per Pluto, e.g. for
the 2.4 GHz one:

```bash
sudo tee /etc/systemd/system/drone-24.service >/dev/null <<'EOF'
[Unit]
Description=Drone sensor 2.4GHz
After=network-online.target
Wants=network-online.target

[Service]
User=revector
WorkingDirectory=/home/revector/drone-detector
ExecStart=/usr/bin/python3 sensor_node.py --id revector-11-24 --sdr pluto \
          --pluto-uri usb:1.3.5 --bands 2.4 --server http://10.70.0.2:8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now drone-24
journalctl -u drone-24 -f        # watch it
```

Repeat for `drone-868`, `drone-52`, `drone-58` with their own `usb:` ids and
`--bands`.

> `usb:` ids can change if you move a Pluto to a different port. If that becomes
> a nuisance for the boot services, give each Pluto a distinct static IP in its
> own `config.txt` and use `ip:` URIs instead.

---

## Troubleshooting

- **Can't SSH to `revector.local`:** the Pi may not have joined Wi-Fi (wrong password or country in the Imager). Re-flash and double-check those, or find its IP with `arp -a | grep -i dc:a6:32`.
- **Fewer than 4 Plutos in `iio_info -s`:** power — use a powered USB hub and the Pi 5's USB-3 ports. `lsusb | grep -i 0456` should list four.
- **A sensor not on the dashboard:** from the Pi, `curl http://$MAC:8000/api/sensors`. If that fails, the Mac's firewall is blocking port 8000 (System Settings → Network → Firewall).
- **Can't tune 5.2/5.8 GHz:** that Pluto's AD9364 unlock is missing (step 4 note).
- **One Pluto wedges under load:** Pluto Sky's own watchdog handles USB drops; if a `sensor_node` process dies, the systemd service in step 9 restarts it.
