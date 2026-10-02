#!/usr/bin/env python3
"""
Basic Usage Example for Drone Detector System

This example demonstrates the fundamental usage of the Drone Detector API
including authentication, detection retrieval, real-time monitoring,
and system control.

Prerequisites:
    - Drone Detector system running (docker-compose up -d)
    - Python 3.11+ with required packages
    - API access (default: http://localhost:8888)

Installation:
    pip install requests websocket-client

Usage:
    python basic_usage.py
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
import websocket

# ============================================================================
# Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8888/api/v1"
WEBSOCKET_URL = "ws://localhost:8889/ws"
USERNAME = "admin"
PASSWORD = "admin123"  # Change this in production!

# ============================================================================
# Authentication
# ============================================================================

class DroneDetectorClient:
    """Simple client for Drone Detector API"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self.session = requests.Session()
        
    def login(self, username: str, password: str) -> bool:
        """Authenticate and get access token"""
        print(f"\n🔐 Logging in as {username}...")
        
        response = self.session.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()["data"]
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            
            # Set authorization header for all future requests
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })
            
            print(f"✅ Login successful! Token expires in {data['expires_in']}s")
            return True
        else:
            print(f"❌ Login failed: {response.json()}")
            return False
            
    def refresh_auth(self) -> bool:
        """Refresh access token"""
        if not self.refresh_token:
            return False
            
        response = self.session.post(
            f"{self.base_url}/auth/refresh",
            json={"refresh_token": self.refresh_token}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            print("✅ Token refreshed")
            return True
        return False

# ============================================================================
# Detection Operations
# ============================================================================

class DetectionOperations:
    """Operations for managing drone detections"""
    
    def __init__(self, client: DroneDetectorClient):
        self.client = client
        
    def get_recent_detections(self, limit: int = 10) -> List[Dict]:
        """Get recent drone detections"""
        print(f"\n📡 Fetching {limit} most recent detections...")
        
        response = self.client.session.get(
            f"{self.client.base_url}/detections",
            params={"limit": limit, "sort": "-timestamp"}
        )
        
        if response.status_code == 200:
            data = response.json()["data"]
            detections = data["items"]
            
            print(f"✅ Found {len(detections)} detections")
            return detections
        else:
            print(f"❌ Failed: {response.status_code}")
            return []
            
    def get_detection_by_id(self, detection_id: str) -> Optional[Dict]:
        """Get specific detection by ID"""
        print(f"\n🔍 Fetching detection {detection_id}...")
        
        response = self.client.session.get(
            f"{self.client.base_url}/detections/{detection_id}"
        )
        
        if response.status_code == 200:
            detection = response.json()["data"]
            print(f"✅ Found detection")
            return detection
        else:
            print(f"❌ Detection not found")
            return None
            
    def get_detection_stats(self, hours: int = 24) -> Dict:
        """Get detection statistics for time period"""
        print(f"\n📊 Fetching detection stats for last {hours} hours...")
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        response = self.client.session.get(
            f"{self.client.base_url}/detections/stats",
            params={
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
        )
        
        if response.status_code == 200:
            stats = response.json()["data"]
            print(f"✅ Statistics retrieved")
            return stats
        else:
            print(f"❌ Failed: {response.status_code}")
            return {}
            
    def print_detection_summary(self, detection: Dict):
        """Print formatted detection summary"""
        print("\n" + "="*60)
        print(f"🛸 DRONE DETECTION")
        print("="*60)
        print(f"  ID:          {detection.get('id')}")
        print(f"  Timestamp:   {detection.get('timestamp')}")
        print(f"  Drone Type:  {detection.get('drone_type', 'Unknown')}")
        print(f"  Frequency:   {detection.get('frequency', 0)/1e9:.3f} GHz")
        print(f"  Confidence:  {detection.get('confidence', 0)*100:.1f}%")
        print(f"  Threat:      {detection.get('threat_level', 'unknown').upper()}")
        
        if detection.get('position'):
            pos = detection['position']
            print(f"  Position:    {pos.get('latitude'):.6f}, {pos.get('longitude'):.6f}")
            print(f"  Altitude:    {pos.get('altitude', 0):.1f} m")
            
        if detection.get('remote_id'):
            rid = detection['remote_id']
            print(f"  Remote ID:   {rid.get('serial_number', 'N/A')}")
            print(f"  Operator:    {rid.get('operator_id', 'N/A')}")
            
        print("="*60)

# ============================================================================
# System Operations
# ============================================================================

class SystemOperations:
    """Operations for system management"""
    
    def __init__(self, client: DroneDetectorClient):
        self.client = client
        
    def get_system_status(self) -> Dict:
        """Get system health and status"""
        print("\n🏥 Checking system health...")
        
        response = self.client.session.get(
            f"{self.client.base_url}/health"
        )
        
        if response.status_code == 200:
            status = response.json()
            print(f"✅ System status: {status['status']}")
            return status
        else:
            print(f"❌ Health check failed")
            return {}
            
    def get_system_info(self) -> Dict:
        """Get detailed system information"""
        print("\n💻 Fetching system information...")
        
        response = self.client.session.get(
            f"{self.client.base_url}/system/info"
        )
        
        if response.status_code == 200:
            info = response.json()["data"]
            print(f"✅ System info retrieved")
            return info
        else:
            print(f"❌ Failed: {response.status_code}")
            return {}
            
    def print_system_summary(self, info: Dict):
        """Print formatted system summary"""
        print("\n" + "="*60)
        print("🖥️  SYSTEM INFORMATION")
        print("="*60)
        print(f"  Version:        {info.get('version')}")
        print(f"  Environment:    {info.get('environment')}")
        print(f"  Uptime:         {info.get('uptime_seconds', 0)/3600:.1f} hours")
        
        hardware = info.get('hardware', {})
        print(f"\n  Hardware:")
        print(f"    Type:         {hardware.get('type', 'N/A')}")
        print(f"    Sample Rate:  {hardware.get('sample_rate', 0)/1e6:.1f} MHz")
        print(f"    Frequency:    {hardware.get('center_frequency', 0)/1e9:.3f} GHz")
        print(f"    Gain:         {hardware.get('gain', 0)} dB")
        
        resources = info.get('resources', {})
        print(f"\n  Resources:")
        print(f"    CPU:          {resources.get('cpu_percent', 0):.1f}%")
        print(f"    Memory:       {resources.get('memory_mb', 0):.0f} MB")
        print(f"    Disk:         {resources.get('disk_usage_percent', 0):.1f}%")
        print("="*60)

# ============================================================================
# Hardware Operations
# ============================================================================

class HardwareOperations:
    """Operations for SDR hardware control"""
    
    def __init__(self, client: DroneDetectorClient):
        self.client = client
        
    def get_hardware_status(self) -> Dict:
        """Get current hardware status"""
        print("\n📻 Checking hardware status...")
        
        response = self.client.session.get(
            f"{self.client.base_url}/hardware/status"
        )
        
        if response.status_code == 200:
            status = response.json()["data"]
            print(f"✅ Hardware: {status.get('type', 'unknown').upper()}")
            print(f"   Connected: {status.get('connected')}")
            return status
        else:
            print(f"❌ Hardware check failed")
            return {}
            
    def configure_hardware(self, config: Dict) -> bool:
        """Configure hardware parameters"""
        print(f"\n⚙️  Configuring hardware...")
        
        response = self.client.session.post(
            f"{self.client.base_url}/hardware/configure",
            json=config
        )
        
        if response.status_code == 200:
            result = response.json()["data"]
            print(f"✅ Hardware configured")
            print(f"   Sample rate: {result['new_config']['sample_rate']/1e6:.1f} MHz")
            print(f"   Frequency:   {result['new_config']['center_frequency']/1e9:.3f} GHz")
            return True
        else:
            print(f"❌ Configuration failed")
            return False

# ============================================================================
# Alert Operations
# ============================================================================

class AlertOperations:
    """Operations for alert management"""
    
    def __init__(self, client: DroneDetectorClient):
        self.client = client
        
    def get_active_alerts(self) -> List[Dict]:
        """Get currently active alerts"""
        print("\n🚨 Fetching active alerts...")
        
        response = self.client.session.get(
            f"{self.client.base_url}/alerts",
            params={"acknowledged": False}
        )
        
        if response.status_code == 200:
            data = response.json()["data"]
            alerts = data["items"]
            print(f"✅ Found {len(alerts)} active alerts")
            return alerts
        else:
            print(f"❌ Failed: {response.status_code}")
            return []
            
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert"""
        print(f"\n✓ Acknowledging alert {alert_id}...")
        
        response = self.client.session.post(
            f"{self.client.base_url}/alerts/{alert_id}/acknowledge",
            json={"notes": "Acknowledged via API"}
        )
        
        if response.status_code == 200:
            print(f"✅ Alert acknowledged")
        else:
            print(f"❌ Failed to acknowledge")
            
    def print_alert_summary(self, alert: Dict):
        """Print formatted alert summary"""
        severity_colors = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢"
        }
        icon = severity_colors.get(alert.get('severity', 'low'), "⚪")
        
        print(f"\n{icon} {alert.get('severity', 'UNKNOWN').upper()}: {alert.get('title')}")
        print(f"   {alert.get('message')}")
        print(f"   ID: {alert.get('id')}")
        print(f"   Time: {alert.get('timestamp')}")

# ============================================================================
# Spectrum Operations
# ============================================================================

class SpectrumOperations:
    """Operations for spectrum analysis"""
    
    def __init__(self, client: DroneDetectorClient):
        self.client = client
        
    def get_live_spectrum(self) -> Dict:
        """Get real-time spectrum data"""
        print("\n📈 Fetching live spectrum data...")
        
        response = self.client.session.get(
            f"{self.client.base_url}/spectrum/live"
        )
        
        if response.status_code == 200:
            spectrum = response.json()["data"]
            print(f"✅ Spectrum data retrieved")
            print(f"   Center: {spectrum['center_frequency']/1e9:.3f} GHz")
            print(f"   Peaks: {len(spectrum.get('peaks', []))} detected")
            return spectrum
        else:
            print(f"❌ Failed: {response.status_code}")
            return {}
            
    def analyze_spectrum(self, spectrum: Dict):
        """Analyze spectrum data for signals"""
        if not spectrum:
            return
            
        peaks = spectrum.get('peaks', [])
        
        if peaks:
            print(f"\n📡 Detected Signals ({len(peaks)}):")
            for i, peak in enumerate(peaks[:5], 1):
                print(f"   {i}. {peak['frequency']/1e9:.3f} GHz @ {peak['power']:.1f} dBm")
        else:
            print("\n📡 No significant signals detected")

# ============================================================================
# WebSocket Client for Real-time Updates
# ============================================================================

class WebSocketClient:
    """WebSocket client for real-time updates"""
    
    def __init__(self, url: str, token: str):
        self.url = f"{url}?token={token}"
        self.ws = None
        self.running = False
        
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        data = json.loads(message)
        msg_type = data.get('type')
        
        if msg_type == 'detection':
            detection = data.get('data', {})
            print(f"\n🚨 REAL-TIME DETECTION: {detection.get('drone_type', 'Unknown')}")
            print(f"   Confidence: {detection.get('confidence', 0)*100:.1f}%")
            print(f"   Threat: {detection.get('threat_level', 'unknown').upper()}")
            
        elif msg_type == 'alert':
            alert = data.get('data', {})
            print(f"\n⚠️  ALERT: {alert.get('title', 'Unknown')}")
            print(f"   {alert.get('message')}")
            
        elif msg_type == 'spectrum':
            print(f"\n📊 Spectrum update received")
            
        elif msg_type == 'heartbeat':
            # Ignore heartbeats
            pass
            
        else:
            print(f"\n📨 Received: {msg_type}")
            
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"❌ WebSocket error: {error}")
        
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket closure"""
        print("🔌 WebSocket disconnected")
        self.running = False
        
    def on_open(self, ws):
        """Handle WebSocket connection"""
        print("🔌 WebSocket connected")
        print("📡 Listening for real-time events...")
        
        # Subscribe to detection events
        ws.send(json.dumps({
            "type": "subscribe",
            "channel": "detections"
        }))
        
        # Subscribe to alerts
        ws.send(json.dumps({
            "type": "subscribe",
            "channel": "alerts"
        }))
        
    def start(self, duration: int = 30):
        """Start WebSocket connection"""
        self.running = True
        
        websocket.enableTrace(False)
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Run in separate thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
        
        # Wait for duration
        print(f"\n🎧 Listening for {duration} seconds...")
        time.sleep(duration)
        
        # Stop
        self.ws.close()
        
    def stop(self):
        """Stop WebSocket connection"""
        if self.ws:
            self.ws.close()
        self.running = False

# ============================================================================
# Main Application
# ============================================================================

def main():
    """Main example execution"""
    print("="*60)
    print("🚁 DRONE DETECTOR SYSTEM - BASIC USAGE EXAMPLE")
    print("="*60)
    
    # Initialize client
    client = DroneDetectorClient()
    
    # ========================================================================
    # 1. Authentication
    # ========================================================================
    if not client.login(USERNAME, PASSWORD):
        print("Failed to authenticate. Exiting.")
        return
        
    # ========================================================================
    # 2. System Status
    # ========================================================================
    sys_ops = SystemOperations(client)
    system_status = sys_ops.get_system_status()
    system_info = sys_ops.get_system_info()
    sys_ops.print_system_summary(system_info)
    
    # ========================================================================
    # 3. Hardware Status
    # ========================================================================
    hw_ops = HardwareOperations(client)
    hardware_status = hw_ops.get_hardware_status()
    
    # ========================================================================
    # 4. Detection Queries
    # ========================================================================
    det_ops = DetectionOperations(client)
    
    # Get recent detections
    detections = det_ops.get_recent_detections(5)
    for detection in detections:
        det_ops.print_detection_summary(detection)
        
    # Get statistics
    stats = det_ops.get_detection_stats(24)
    if stats:
        print("\n📊 24-HOUR STATISTICS")
        print(f"  Total detections: {stats.get('total_detections', 0)}")
        print(f"  Unique drones: {stats.get('unique_drones', 0)}")
        
        threat_dist = stats.get('threat_distribution', {})
        print(f"  Threat levels:")
        for level, count in threat_dist.items():
            print(f"    {level}: {count}")
            
    # ========================================================================
    # 5. Alert Management
    # ========================================================================
    alert_ops = AlertOperations(client)
    alerts = alert_ops.get_active_alerts()
    
    for alert in alerts:
        alert_ops.print_alert_summary(alert)
        
    # Acknowledge first alert if exists
    if alerts:
        acknowledge = input(f"\nAcknowledge alert {alerts[0]['id']}? (y/n): ")
        if acknowledge.lower() == 'y':
            alert_ops.acknowledge_alert(alerts[0]['id'])
            
    # ========================================================================
    # 6. Spectrum Analysis
    # ========================================================================
    spec_ops = SpectrumOperations(client)
    spectrum = spec_ops.get_live_spectrum()
    spec_ops.analyze_spectrum(spectrum)
    
    # ========================================================================
    # 7. Hardware Configuration (optional)
    # ========================================================================
    config = {
        "sample_rate": 5000000,  # 5 MHz
        "center_frequency": 2450000000,  # 2.45 GHz
        "gain": 24
    }
    
    # Uncomment to actually change hardware config
    # hw_ops.configure_hardware(config)
    
    # ========================================================================
    # 8. Real-time Monitoring via WebSocket
    # ========================================================================
    print("\n" + "="*60)
    print("📡 REAL-TIME MONITORING")
    print("="*60)
    
    if client.access_token:
        ws_client = WebSocketClient(WEBSOCKET_URL, client.access_token)
        ws_client.start(duration=30)  # Listen for 30 seconds
    else:
        print("❌ Cannot start WebSocket: Not authenticated")
        
    # ========================================================================
    # 9. Export Data (optional)
    # ========================================================================
    print("\n" + "="*60)
    print("💾 DATA EXPORT")
    print("="*60)
    
    export_response = client.session.post(
        f"{client.base_url}/exports/detections",
        json={
            "start_time": (datetime.utcnow() - timedelta(days=1)).isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "format": "csv",
            "filename": "detections_export.csv"
        }
    )
    
    if export_response.status_code == 200:
        export_data = export_response.json()["data"]
        print(f"✅ Export initiated: {export_data['export_id']}")
        print(f"   Download URL: {export_data['download_url']}")
    else:
        print("❌ Export failed")
        
    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "="*60)
    print("✅ EXAMPLE COMPLETED")
    print("="*60)
    print("\nNext steps:")
    print("  1. Check the web dashboard at http://localhost:8888")
    print("  2. Review API documentation at http://localhost:8888/docs")
    print("  3. Try advanced examples in /examples directory")
    print("  4. Configure alert rules for your environment")
    print("  5. Set up recording schedules for persistent monitoring")

# ============================================================================
# Additional Helper Functions
# ============================================================================

def get_detection_by_time_range(client: DroneDetectorClient, 
                                hours: int = 24) -> List[Dict]:
    """Get detections within time range"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    response = client.session.get(
        f"{client.base_url}/detections",
        params={
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "sort": "-timestamp"
        }
    )
    
    if response.status_code == 200:
        return response.json()["data"]["items"]
    return []

def get_drone_types(client: DroneDetectorClient) -> List[str]:
    """Get list of detected drone types"""
    response = client.session.get(
        f"{client.base_url}/detections/stats"
    )
    
    if response.status_code == 200:
        stats = response.json()["data"]
        return list(stats.get('drone_types', {}).keys())
    return []

def start_recording(client: DroneDetectorClient, 
                    duration: int = 60) -> Optional[str]:
    """Start IQ recording"""
    response = client.session.post(
        f"{client.base_url}/recordings/start",
        json={
            "duration_seconds": duration,
            "frequency": 2450000000,
            "auto_stop": True
        }
    )
    
    if response.status_code == 200:
        recording = response.json()["data"]
        print(f"Recording started: {recording['recording_id']}")
        return recording['recording_id']
    return None

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Example interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure the Drone Detector system is running:")
        print("  docker-compose up -d")