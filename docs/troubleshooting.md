# Drone Detector System - Troubleshooting Guide

## Overview

This guide covers common issues, diagnostics, and solutions for the Drone Detector system. Use this document to identify and resolve problems quickly.

## Quick Diagnostics

### System Health Check

```bash
# Run complete system diagnostics
python scripts/diagnostics.py

# Quick health check
curl http://localhost:8888/health

# Check all services
docker-compose ps

# View recent errors
tail -100 /var/log/drone-detector/system.log
Diagnostic Script Output
bash
$ python scripts/diagnostics.py

=== Drone Detector Diagnostics ===

System Information:
  OS: Ubuntu 22.04
  Python: 3.11.5
  Docker: 24.0.7
  RAM: 15.6 GB
  CPU: 8 cores

Services Status:
  ✓ API Server (Port 8888): Running
  ✓ WebSocket (Port 8889): Running
  ✓ PostgreSQL: Connected
  ✓ Redis: Connected
  ✓ MinIO: Connected

Hardware Status:
  ✓ HackRF One: Detected (SN: HACKRF000001, FW: 2023.01.1)
  ✗ RTL-SDR: Not detected

ML Model:
  ✓ Model loaded: classifier_v2.pkl
  ✓ Last training: 2024-01-15
  ✓ Accuracy: 94.5%

Recent Errors (last hour):
  12:34:56 - WARNING - High CPU usage (85%)
  12:45:23 - ERROR - Database connection timeout

Recommendations:
  - Reduce sample rate to lower CPU usage
  - Check PostgreSQL connection settings
Installation Issues
Docker Installation Fails
bash
# Problem: Docker daemon not running
sudo systemctl status docker
sudo systemctl start docker

# Problem: Permission denied
sudo usermod -aG docker $USER
# Log out and back in

# Problem: Port conflicts
sudo netstat -tulpn | grep -E '8888|8889|5432|6379'
# Change ports in docker-compose.yml

# Problem: Out of memory
docker system prune -a
# Increase memory limit in Docker Desktop
Python Environment Issues
bash
# Problem: Virtual environment not activating
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Problem: Missing dependencies
pip install -r requirements.txt --upgrade
pip install -r requirements-dev.txt

# Problem: Conflicting packages
pip freeze | grep -i drone
pip uninstall drone-detector
pip install -e .

# Problem: Python version mismatch
python --version  # Need 3.11+
pyenv install 3.11.5
pyenv local 3.11.5
SDR Driver Issues
bash
# Problem: HackRF not detected
lsusb | grep HackRF
sudo hackrf_info
sudo modprobe hackrf
sudo systemctl restart udev

# Problem: RTL-SDR not detected
lsusb | grep RTL
sudo rtl_test -t
# Blacklist DVB-T driver
sudo tee /etc/modprobe.d/rtl-sdr-blacklist.conf << EOF
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF
sudo reboot

# Problem: Permission denied
sudo usermod -a -G plugdev $USER
sudo usermod -a -G dialout $USER
# Create udev rules
sudo tee /etc/udev/rules.d/99-sdr.rules << EOF
SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6089", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE="0666"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
Hardware Issues
SDR Not Detected
bash
# Diagnostic steps
# 1. Check USB connection
lsusb
dmesg | tail -20

# 2. Check driver loading
lsmod | grep -E "hackrf|rtl"
sudo modprobe hackrf

# 3. Test device
hackrf_info
rtl_test -t

# 4. Check USB bandwidth
cat /sys/kernel/debug/usb/devices | grep -A 10 "HackRF"

# Solution: USB port issues
# - Try different USB port
# - Use powered USB hub
# - Use shorter USB cable
# - Disable USB auto-suspend
Poor Signal Quality
bash
# Problem: Low SNR
# Check antenna connection
# Verify antenna is appropriate for frequency
# Check LNA power
# Adjust gain settings

# Problem: Interference
# Identify interference sources
rtl_power -f 0:6e9:1M -g 20 -i 1 -1 interference.csv
python scripts/analyze_interference.py interference.csv

# Solutions
# - Move antenna away from noise sources
# - Add bandpass filters
# - Use shielded cables
# - Change operating frequency

# Problem: Signal distortion
# Check for overload
hackrf_info | grep "Gain"
# Reduce gain if > 30dB
# Check antenna VSWR
Hardware Overheating
bash
# Check temperature
hackrf_info | grep Temperature
# Should be < 60°C

# Solutions
# - Add heatsink
# - Install cooling fan
# - Reduce sample rate
# - Reduce gain
# - Improve ventilation

# Monitor temperature
watch -n 1 'hackrf_info | grep Temperature'

# Automatic cooling script
#!/bin/bash
while true; do
    TEMP=$(hackrf_info | grep Temperature | awk '{print $2}')
    if [ $TEMP -gt 60 ]; then
        echo "High temperature detected: ${TEMP}°C"
        # Reduce gain or sample rate
    fi
    sleep 10
done
Software Issues
API Server Won't Start
bash
# Check logs
docker-compose logs api
# or
journalctl -u drone-api -f

# Common issues
# Port already in use
sudo lsof -i :8888
sudo kill -9 <PID>

# Configuration error
python -c "import yaml; yaml.safe_load(open('config/system.yaml'))"

# Database connection failed
psql -h localhost -U drone_user -d drone_detector -c "SELECT 1"

# Fix database
docker-compose restart postgres
python scripts/migrate.py upgrade head

# Environment variables missing
cat .env
cp .env.example .env
# Edit .env with correct values
WebSocket Connection Fails
bash
# Check WebSocket endpoint
wscat -c ws://localhost:8889

# Browser console errors
# Check CORS settings in config/system.yaml
cors:
  allowed_origins:
    - "http://localhost:3000"
    - "https://your-domain.com"

# Check nginx configuration
# WebSocket requires:
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";

# Increase timeout in nginx
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
Database Issues
bash
# Problem: Connection refused
sudo systemctl status postgresql
netstat -tulpn | grep 5432

# Problem: Database not initialized
createdb -U postgres drone_detector
psql -U postgres -d drone_detector -f schema.sql

# Problem: Migration failed
python scripts/migrate.py current
python scripts/migrate.py downgrade -1
python scripts/migrate.py upgrade head

# Problem: Slow queries
# Enable query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();

# Analyze query performance
EXPLAIN ANALYZE SELECT * FROM detections WHERE timestamp > now() - interval '1 day';

# Create missing indexes
CREATE INDEX CONCURRENTLY idx_detections_timestamp ON detections(timestamp);
CREATE INDEX CONCURRENTLY idx_detections_drone_type ON detections(drone_type);
Redis Issues
bash
# Problem: Redis connection failed
redis-cli ping
sudo systemctl status redis-server

# Problem: Memory full
redis-cli INFO memory
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Problem: Slow operations
redis-cli --latency
redis-cli SLOWLOG GET 10

# Clear cache
redis-cli FLUSHALL

# Check Redis keys
redis-cli KEYS "drone:*"
redis-cli TYPE "drone:detection:123"
MinIO Issues
bash
# Problem: Cannot connect
mc alias set local http://localhost:9000 minioadmin minioadmin123
mc admin info local

# Problem: Bucket not found
mc mb local/iq-recordings
mc mb local/spectrum-data
mc mb local/exports

# Problem: Permission denied
mc policy set download local/exports
mc policy set private local/iq-recordings

# Problem: Disk full
mc admin disk usage local
# Clean old files
mc rm --recursive --older-than 30d local/iq-recordings/
Detection Issues
No Detections
bash
# Check if hardware is working
hackrf_transfer -r /dev/null -f 2450000000 -s 2000000 -n 1000000

# Check noise floor
python scripts/check_noise_floor.py
# Should be < -80 dBm

# Increase sensitivity
# Lower detection threshold
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"detection":{"threshold":5}}'

# Enable mock mode for testing
export USE_MOCK_HARDWARE=true
python run.py --test

# Check logs for errors
tail -f /var/log/drone-detector/detection.log

# Verify frequency band
# DJI drones operate at 2.4GHz or 5.8GHz
# Ensure center frequency is correct
curl http://localhost:8888/api/v1/hardware/status | grep center_frequency
False Positives
bash
# Problem: Wi-Fi interference
# Add Wi-Fi filter or change channel
# Increase detection threshold
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"detection":{"threshold":15}}'

# Problem: RF noise
# Identify noise source
python scripts/identify_noise.py --duration 60
# Move antenna away from noise
# Add shielding

# Problem: Too sensitive
# Adjust peak detection
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"detection":{"peak_threshold":10,"min_confidence":0.8}}'

# Enable machine learning filtering
curl -X POST http://localhost:8888/api/v1/ml/filter/enable

# Review false positives
python scripts/analyze_detections.py --type false_positive
Missed Detections
bash
# Problem: Signal too weak
# Increase gain
curl -X PUT http://localhost:8888/api/v1/hardware/gain/30

# Add LNA between antenna and SDR
# Use higher gain antenna

# Problem: Frequency drift
# Recalibrate SDR
hackrf_cal -f 2450000000 -g 20

# Problem: Fast moving drone
# Increase scan rate
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"detection":{"update_interval_ms":50}}'

# Enable TDOA tracking
curl -X POST http://localhost:8888/api/v1/tdoa/enable

# Problem: New drone type not in database
# Update signature database
python scripts/update_drone_signatures.py
Performance Issues
High CPU Usage
bash
# Identify CPU usage
top -o %CPU
htop

# Check process CPU
ps aux | grep python | grep -E "api|worker"

# Reduce sample rate
curl -X PUT http://localhost:8888/api/v1/hardware/sample_rate/1000000

# Reduce FFT size
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"processing":{"fft_size":512}}'

# Scale worker processes
docker-compose up -d --scale worker=2

# Enable GPU acceleration
export USE_GPU=true
python run.py --gpu

# Profile CPU usage
python -m cProfile -o profile.stats run.py
python -m pstats profile.stats
Memory Leaks
bash
# Monitor memory usage
watch -n 1 'ps aux --sort=-%mem | head -10'

# Check Python memory
pip install memory-profiler
mprof run python run.py
mprof plot

# Check for memory leaks
# Restart services weekly via cron
0 3 * * 0 docker-compose restart api worker

# Set memory limits in docker
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 2G

# Reduce cache sizes
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"cache":{"detection_cache_size":1000,"spectrum_history":100}}'

# Clear caches
curl -X POST http://localhost:8888/api/v1/cache/clear
Slow Response Time
bash
# Measure API latency
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8888/api/v1/detections

# Check database query performance
# Enable slow query logging in PostgreSQL
# Optimize indexes

# Increase worker count
export GUNICORN_WORKERS=8
docker-compose up -d --scale api=3

# Enable response compression
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"api":{"compression":true}}'

# Implement caching
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"cache":{"enabled":true,"ttl_seconds":60}}'

# Profile API endpoints
pip install apache-bench
ab -n 1000 -c 10 http://localhost:8888/api/v1/detections
Disk Space Issues
bash
# Check disk usage
df -h
du -sh /app/data/*

# Clean old data
python scripts/cleanup.py --days 30

# Configure retention policies
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"data_retention":{
    "detections_days":30,
    "recordings_days":7,
    "spectrum_days":1
  }}'

# Compress old IQ data
find /app/data/iq -name "*.iq" -mtime +7 -exec gzip {} \;

# Move to external storage
aws s3 sync /app/data/iq s3://drone-backups/iq/
rm -rf /app/data/iq/old-*

# Configure log rotation
# /etc/logrotate.d/drone-detector
/var/log/drone-detector/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 drone drone
}
Network Issues
WebSocket Disconnections
bash
# Check WebSocket stability
wscat -c ws://localhost:8889 --keepalive=30

# Increase timeout values
# nginx configuration
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
proxy_connect_timeout 75s;

# Client-side reconnect logic
function connectWebSocket() {
    ws = new WebSocket(url);
    ws.onclose = function() {
        setTimeout(connectWebSocket, 1000);
    };
}

# Check network stability
ping -c 100 google.com | grep loss

# Use stable internet connection
# Consider using wired instead of WiFi
API Timeouts
bash
# Increase timeout
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"api":{"timeout_seconds":120}}'

# For large queries, use pagination
curl "http://localhost:8888/api/v1/detections?limit=100&offset=0"

# For exports, use async endpoint
curl -X POST http://localhost:8888/api/v1/exports/detections \
  -d '{"start_time":"2024-01-01","format":"csv"}'
# Poll status endpoint for completion

# Check network latency
mtr google.com

# Optimize for slow networks
# Enable compression
# Reduce response size
# Use protobuf instead of JSON
Remote ID Issues
No Remote ID Detections
bash
# Check Bluetooth adapter
hciconfig -a
sudo hciconfig hci0 up

# Scan for BLE devices
sudo hcitool lescan

# Check Wi-Fi monitor mode
sudo iwconfig wlan0 mode monitor
sudo ip link set wlan0 up

# Verify Remote ID configuration
cat config/remote_id.yaml | grep enabled

# Check RSSI threshold
# Lower threshold to detect weaker signals
curl -X PUT http://localhost:8888/api/v1/remote-id/config \
  -d '{"bluetooth":{"min_rssi":-90}}'

# Test with known Remote ID drone
# Use DJI drone with Remote ID enabled in app
Invalid Remote ID Data
bash
# Check message decoding
python scripts/decode_rid.py --capture /tmp/rid_capture.pcap

# Validate against ASTM F3411-22 spec
# Check for spoofing attempts
python scripts/detect_rid_spoofing.py

# Update Remote ID database
python scripts/update_rid_database.py

# Check time synchronization
timedatectl status
# Ensure NTP is enabled
sudo timedatectl set-ntp true
ML Model Issues
Low Detection Accuracy
bash
# Evaluate model performance
python scripts/evaluate_model.py --model models/classifier.pkl

# Check for class imbalance
python scripts/analyze_dataset.py --check-imbalance

# Retrain with more data
python scripts/train_model.py --epochs 100 --data /path/to/new/data

# Enable ensemble predictions
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"ml":{"ensemble":true}}'

# Adjust confidence threshold
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"detection":{"min_confidence":0.7}}'

# Collect new training data for problematic drone types
python scripts/collect_training_data.py --drone-type DJI_Mavic --duration 300
Model Loading Fails
bash
# Check model file exists
ls -la models/classifier.pkl

# Verify model compatibility
python -c "import joblib; model = joblib.load('models/classifier.pkl')"

# Re-export model
python scripts/export_model.py --input models/classifier_v1.pkl --output models/classifier.pkl

# Check scikit-learn version
pip show scikit-learn
# May need to retrain if version mismatch

# Fallback to default model
cp models/classifier_default.pkl models/classifier.pkl
Security Issues
Unauthorized Access
bash
# Check authentication logs
tail -f /var/log/drone-detector/auth.log

# Enable rate limiting
curl -X PUT http://localhost:8888/api/v1/config \
  -d '{"security":{"rate_limit":100,"rate_limit_window":60}}'

# Update JWT secret
echo "SECRET_KEY=$(openssl rand -base64 32)" >> .env
docker-compose restart api

# Check for brute force attempts
sudo fail2ban-client status drone-detector

# Revoke suspicious tokens
python scripts/revoke_tokens.py --user suspicious_user
SSL/TLS Issues
bash
# Check certificate expiration
openssl x509 -in /etc/ssl/certs/drone-detector.crt -text -noout

# Renew certificate
sudo certbot renew

# Verify SSL configuration
sslscan localhost:443

# Test SSL connection
openssl s_client -connect localhost:443 -servername drone.detector.local

# Fix certificate chain
cat domain.crt intermediate.crt root.crt > fullchain.crt
Troubleshooting Tools
Built-in Tools
bash
# Comprehensive diagnostics
python scripts/diagnostics.py --verbose

# Hardware testing
python scripts/test_hardware.py --device hackrf --test all

# Network testing
python scripts/test_network.py --endpoint localhost:8888 --test all

# Database repair
python scripts/repair_database.py --check --fix

# Log analysis
python scripts/analyze_logs.py --level ERROR --hours 24

# Performance profiling
python scripts/profile_system.py --duration 60 --output report.html
Monitoring Commands
bash
# Real-time monitoring
watch -n 1 'curl -s http://localhost:8888/metrics | grep -E "detection|cpu|memory"'

# Docker monitoring
docker stats --no-stream
docker events --filter event=health_status

# System monitoring
htop
nvidia-smi  # GPU status
iostat -x 1  # Disk I/O

# Log tailing
tail -f /var/log/drone-detector/{system,detection,api,hardware}.log

# Network monitoring
iftop
nethogs
sudo tcpdump -i eth0 port 8888
Logging Configuration
yaml
# config/logging.yaml - Enable debug logging
version: 1
handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    filename: /var/log/drone-detector/debug.log
    
loggers:
  drone_detector:
    level: DEBUG
    handlers: [console, file]
  infrastructure.hardware:
    level: DEBUG
  domain.services:
    level: DEBUG
Recovery Procedures
Service Recovery
bash
# Restart specific service
docker-compose restart api
sudo systemctl restart drone-api

# Full system restart
docker-compose down
docker-compose up -d

# Database recovery
# Restore from backup
gunzip -c backups/drone_db_20240101.sql.gz | psql -U drone_user drone_detector

# Configuration recovery
cp config/system.yaml.bak config/system.yaml
docker-compose restart

# Hardware recovery
sudo modprobe -r hackrf
sudo modprobe hackrf
sudo systemctl restart udev
Emergency Procedures
bash
# Emergency shutdown
curl -X POST http://localhost:8888/api/v1/system/shutdown

# Force stop
docker-compose down --remove-orphans
pkill -f "python.*drone"

# Safe mode startup
python run.py --safe-mode --mock

# Data preservation
tar -czf emergency_backup_$(date +%Y%m%d).tar.gz /app/data/ /app/config/

# Contact support
python scripts/collect_debug_info.py --output debug_info_$(date +%Y%m%d).tar.gz
Getting Help
Self-Help Resources
Documentation: https://docs.drone-detector.com

FAQ: https://docs.drone-detector.com/faq

Knowledge Base: https://support.drone-detector.com

Community Forum: https://community.drone-detector.com

Support Channels
bash
# Generate support bundle
python scripts/support_bundle.py --output support_bundle.tar.gz

# Attach to support ticket
# Includes:
# - Logs (last 7 days)
# - Configuration files
# - Hardware info
# - System metrics
# - Database schema
Reporting Issues
When reporting issues, include:

Description: What happened and expected behavior

Steps to reproduce: Exact commands/actions

System info: OS, Python version, hardware

Logs: Relevant log excerpts

Configuration: Config files (redact secrets)

Screenshots: If applicable
