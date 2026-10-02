#!/usr/bin/env python3
"""
Full Drone Detector Test with Mock Hardware and Live Map
Includes real-time drone tracking on interactive map
"""

import asyncio
import json
import time
import random
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="Drone Detector - Mock Mode with Map", version="1.0.0")

# Mock data storage
detections = []
active_drones = {}

# Drone types with their characteristics
DRONE_TYPES = {
    "DJI Mavic 3": {
        "frequency": 2.45e9,
        "bandwidth": 20e6,
        "threat_level": "medium",
        "icon": "🚁",
        "color": "#ffaa00"
    },
    "DJI Mini": {
        "frequency": 2.45e9,
        "bandwidth": 20e6,
        "threat_level": "low",
        "icon": "🪁",
        "color": "#00ff88"
    },
    "FPV Analog": {
        "frequency": 5.8e9,
        "bandwidth": 8e6,
        "threat_level": "medium",
        "icon": "🏎️",
        "color": "#ff6600"
    },
    "FPV Digital": {
        "frequency": 5.8e9,
        "bandwidth": 20e6,
        "threat_level": "high",
        "icon": "⚡",
        "color": "#ff0000"
    },
    "Custom Build": {
        "frequency": 2.45e9,
        "bandwidth": 10e6,
        "threat_level": "high",
        "icon": "🔧",
        "color": "#ff00ff"
    }
}

# Generate random positions around San Francisco
def generate_random_position():
    # Center around San Francisco
    base_lat = 37.7749
    base_lon = -122.4194
    # Add random offset (approximately 1km radius)
    lat_offset = (random.random() - 0.5) * 0.02
    lon_offset = (random.random() - 0.5) * 0.02
    return {
        "lat": base_lat + lat_offset,
        "lon": base_lon + lon_offset,
        "alt": random.randint(50, 200)
    }

# Generate moving position (for tracking)
def generate_moving_position(drone_id):
    if drone_id not in active_drones:
        active_drones[drone_id] = {
            "lat": 37.7749 + (random.random() - 0.5) * 0.02,
            "lon": -122.4194 + (random.random() - 0.5) * 0.02,
            "heading": random.uniform(0, 360),
            "speed": random.uniform(5, 20)
        }
    
    drone = active_drones[drone_id]
    # Move based on heading and speed
    rad = drone["heading"] * 3.14159 / 180
    delta_lat = (drone["speed"] * 0.00001) * random.uniform(0.5, 1.5)
    delta_lon = (drone["speed"] * 0.000015) * random.uniform(0.5, 1.5)
    
    drone["lat"] += delta_lat * random.choice([-1, 1])
    drone["lon"] += delta_lon * random.choice([-1, 1])
    
    # Occasionally change direction
    if random.random() < 0.1:
        drone["heading"] = random.uniform(0, 360)
    
    return {
        "lat": drone["lat"],
        "lon": drone["lon"],
        "alt": random.randint(50, 200)
    }

def generate_mock_detection(drone_type=None):
    if drone_type is None:
        drone_type = random.choice(list(DRONE_TYPES.keys()))
    
    drone_info = DRONE_TYPES[drone_type]
    drone_id = f"drone_{int(time.time() * 1000)}"
    position = generate_moving_position(drone_id)
    
    return {
        "id": f"det_{int(time.time() * 1000)}",
        "drone_id": drone_id,
        "timestamp": datetime.now().isoformat(),
        "drone_type": drone_type,
        "frequency": drone_info["frequency"],
        "bandwidth": drone_info["bandwidth"],
        "confidence": round(0.7 + random.random() * 0.3, 2),
        "threat_level": drone_info["threat_level"],
        "signal_power": round(-70 + random.random() * 30, 1),
        "snr": round(15 + random.random() * 20, 1),
        "position": position,
        "icon": drone_info["icon"],
        "color": drone_info["color"]
    }

# API Endpoints
@app.get("/")
async def root():
    return {
        "message": "Drone Detector API (Mock Mode with Map)",
        "version": "1.0.0",
        "status": "running",
        "mock_enabled": True,
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "detections": "/api/v1/detections",
            "spectrum": "/api/v1/spectrum/live",
            "map": "/map",
            "websocket": "ws://localhost:8888/ws"
        }
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "drone-detector",
        "mock_mode": True,
        "active_drones": len(active_drones),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/detections")
async def get_detections(limit: int = 50):
    return {
        "status": "success",
        "data": detections[-limit:],
        "total": len(detections),
        "active_drones": len(active_drones),
        "mock": True
    }

@app.get("/api/v1/detections/active")
async def get_active_drones():
    """Get currently active drones with their last known positions"""
    active = []
    for drone_id, info in active_drones.items():
        # Find latest detection for this drone
        latest = None
        for d in reversed(detections):
            if d.get("drone_id") == drone_id:
                latest = d
                break
        if latest:
            active.append(latest)
    return {
        "status": "success",
        "data": active,
        "count": len(active)
    }

@app.get("/api/v1/spectrum/live")
async def get_spectrum():
    frequencies = list(range(2400, 2500, 5))
    spectrum = []
    
    for freq in frequencies:
        power = -100 + random.random() * 20
        
        # Add peaks at drone frequencies
        for d in detections[-10:]:
            drone_freq_ghz = int(d["frequency"] / 1e9 * 1000)
            if abs(freq - drone_freq_ghz) < 15:
                power += 35 - abs(freq - drone_freq_ghz) * 1.2
        
        spectrum.append(round(power, 1))
    
    return {
        "status": "success",
        "data": {
            "frequencies": frequencies,
            "spectrum": spectrum,
            "center_frequency": 2.45e9,
            "timestamp": datetime.now().isoformat()
        }
    }

@app.post("/api/v1/mock/inject")
async def inject_drone(drone_type: str = None):
    detection = generate_mock_detection(drone_type)
    detections.append(detection)
    
    if len(detections) > 500:
        detections.pop(0)
    
    return {
        "status": "success",
        "data": detection,
        "message": f"Drone injected: {detection['drone_type']}"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            await asyncio.sleep(2 + random.random() * 3)
            
            detection = generate_mock_detection()
            detections.append(detection)
            
            if len(detections) > 500:
                detections.pop(0)
            
            await websocket.send_json({
                "type": "detection",
                "data": detection,
                "active_drones": len(active_drones),
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        print(f"WebSocket error: {e}")

# Background task
async def background_detection_generator():
    while True:
        await asyncio.sleep(4 + random.random() * 2)
        detection = generate_mock_detection()
        detections.append(detection)
        
        if len(detections) > 500:
            detections.pop(0)
        
        print(f"🎯 {detection['icon']} {detection['drone_type']} | "
              f"Threat: {detection['threat_level'].upper()} | "
              f"Confidence: {detection['confidence']*100:.0f}% | "
              f"Loc: {detection['position']['lat']:.4f}, {detection['position']['lon']:.4f}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_detection_generator())
    print("\n" + "="*60)
    print("🚁 DRONE DETECTOR WITH LIVE MAP - STARTED")
    print("="*60)
    print(f"📡 API:        http://localhost:8888")
    print(f"🗺️  Map View:   http://localhost:8888/map")
    print(f"📚 Docs:       http://localhost:8888/docs")
    print(f"🔌 WebSocket:  ws://localhost:8888/ws")
    print("="*60)
    print("Drone positions will appear on the map!")
    print("Press Ctrl+C to stop\n")

# Map Dashboard
@app.get("/map", response_class=HTMLResponse)
async def map_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Drone Detector - Live Drone Tracking Map</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #eee; }
            .header {
                background: linear-gradient(135deg, #16213e, #0f0f1a);
                padding: 15px 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 10px;
            }
            .header h1 { color: #00ff88; font-size: 1.5em; }
            .stats {
                display: flex;
                gap: 20px;
            }
            .stat {
                background: #1a1a3e;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.9em;
            }
            .stat-value { color: #00ff88; font-weight: bold; font-size: 1.2em; }
            .container {
                display: flex;
                height: calc(100vh - 70px);
            }
            #map {
                flex: 3;
                height: 100%;
            }
            .sidebar {
                flex: 1;
                background: #16213e;
                padding: 15px;
                overflow-y: auto;
                border-left: 1px solid #2a2a4e;
            }
            .sidebar h3 {
                color: #00ff88;
                margin-bottom: 15px;
            }
            .drone-list {
                list-style: none;
            }
            .drone-item {
                background: #1a1a3e;
                margin: 10px 0;
                padding: 10px;
                border-radius: 8px;
                cursor: pointer;
                transition: transform 0.2s;
                border-left: 3px solid;
            }
            .drone-item:hover { transform: translateX(-5px); }
            .drone-name { font-weight: bold; margin-bottom: 5px; }
            .drone-details { font-size: 0.8em; color: #aaa; }
            .threat-low { border-left-color: #00ff88; }
            .threat-medium { border-left-color: #ffaa00; }
            .threat-high { border-left-color: #ff6600; }
            .threat-critical { border-left-color: #ff0000; }
            .legend {
                position: absolute;
                bottom: 20px;
                right: 20px;
                background: rgba(0,0,0,0.8);
                padding: 10px;
                border-radius: 8px;
                z-index: 1000;
                font-size: 0.8em;
            }
            .legend-item { display: flex; align-items: center; gap: 8px; margin: 5px 0; }
            .legend-color { width: 20px; height: 20px; border-radius: 50%; }
            button {
                background: #00ff88;
                color: #1a1a2e;
                border: none;
                padding: 5px 15px;
                border-radius: 5px;
                cursor: pointer;
                font-weight: bold;
            }
            button:hover { background: #00cc66; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚁 Drone Detector - Live Tracking Map</h1>
            <div class="stats">
                <div class="stat">🎯 Detections: <span id="detectionCount" class="stat-value">0</span></div>
                <div class="stat">🛸 Active Drones: <span id="activeCount" class="stat-value">0</span></div>
                <div class="stat"><button onclick="injectRandomDrone()">💉 Inject Drone</button></div>
            </div>
        </div>
        <div class="container">
            <div id="map"></div>
            <div class="sidebar">
                <h3>📡 Active Drones</h3>
                <div id="droneList">
                    <p style="color: #888;">Waiting for detections...</p>
                </div>
            </div>
        </div>
        <div class="legend">
            <strong>Threat Levels</strong>
            <div class="legend-item"><div class="legend-color" style="background: #00ff88;"></div><span>Low</span></div>
            <div class="legend-item"><div class="legend-color" style="background: #ffaa00;"></div><span>Medium</span></div>
            <div class="legend-item"><div class="legend-color" style="background: #ff6600;"></div><span>High</span></div>
            <div class="legend-item"><div class="legend-color" style="background: #ff0000;"></div><span>Critical</span></div>
        </div>

        <script>
            let map;
            let markers = {};
            let detections = [];
            let ws = null;
            
            // Initialize map centered on San Francisco
            function initMap() {
                map = L.map('map').setView([37.7749, -122.4194], 13);
                L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors',
                    subdomains: 'abcd',
                    maxZoom: 19,
                    minZoom: 3
                }).addTo(map);
            }
            
            // Get threat color
            function getThreatColor(threat) {
                const colors = {
                    'low': '#00ff88',
                    'medium': '#ffaa00',
                    'high': '#ff6600',
                    'critical': '#ff0000'
                };
                return colors[threat] || '#888888';
            }
            
            // Update drone marker on map
            function updateDroneMarker(detection) {
                const droneId = detection.drone_id;
                const pos = detection.position;
                const threatColor = getThreatColor(detection.threat_level);
                
                // Create popup content
                const popupContent = `
                    <div style="min-width: 150px;">
                        <strong>${detection.icon} ${detection.drone_type}</strong><br>
                        <span style="color: ${threatColor}">Threat: ${detection.threat_level.toUpperCase()}</span><br>
                        Confidence: ${(detection.confidence * 100).toFixed(0)}%<br>
                        Freq: ${(detection.frequency / 1e9).toFixed(3)} GHz<br>
                        Alt: ${pos.alt}m<br>
                        <small>${new Date(detection.timestamp).toLocaleTimeString()}</small>
                    </div>
                `;
                
                if (markers[droneId]) {
                    // Update existing marker position
                    markers[droneId].setLatLng([pos.lat, pos.lon]);
                    markers[droneId].setPopupContent(popupContent);
                    // Update marker color by changing icon
                    markers[droneId].setIcon(L.divIcon({
                        className: 'custom-div-icon',
                        html: `<div style="background: ${threatColor}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;"></div>`,
                        iconSize: [16, 16],
                        popupAnchor: [0, -8]
                    }));
                } else {
                    // Create new marker
                    const marker = L.marker([pos.lat, pos.lon], {
                        icon: L.divIcon({
                            className: 'custom-div-icon',
                            html: `<div style="background: ${threatColor}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px ${threatColor};"></div>`,
                            iconSize: [16, 16],
                            popupAnchor: [0, -8]
                        })
                    }).bindPopup(popupContent).addTo(map);
                    
                    markers[droneId] = marker;
                }
            }
            
            // Update drone list in sidebar
            function updateDroneList() {
                const container = document.getElementById('droneList');
                const activeDrones = {};
                
                // Get latest detection per drone
                detections.forEach(d => {
                    if (!activeDrones[d.drone_id] || 
                        new Date(d.timestamp) > new Date(activeDrones[d.drone_id].timestamp)) {
                        activeDrones[d.drone_id] = d;
                    }
                });
                
                const droneArray = Object.values(activeDrones);
                document.getElementById('activeCount').innerHTML = droneArray.length;
                document.getElementById('detectionCount').innerHTML = detections.length;
                
                if (droneArray.length === 0) {
                    container.innerHTML = '<p style="color: #888;">No active drones detected</p>';
                    return;
                }
                
                container.innerHTML = droneArray.map(d => `
                    <div class="drone-item threat-${d.threat_level}" style="border-left-color: ${getThreatColor(d.threat_level)}" onclick="flyToDrone(${d.position.lat}, ${d.position.lon})">
                        <div class="drone-name">${d.icon} ${d.drone_type}</div>
                        <div class="drone-details">
                            Threat: ${d.threat_level.toUpperCase()}<br>
                            Confidence: ${(d.confidence * 100).toFixed(0)}%<br>
                            Alt: ${d.position.alt}m<br>
                            ${new Date(d.timestamp).toLocaleTimeString()}
                        </div>
                    </div>
                `).join('');
            }
            
            // Fly map to drone position
            function flyToDrone(lat, lon) {
                map.flyTo([lat, lon], 15, { duration: 1.5 });
            }
            
            // Connect WebSocket
            function connectWebSocket() {
                ws = new WebSocket('ws://localhost:8888/ws');
                
                ws.onopen = () => {
                    console.log('WebSocket connected');
                };
                
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    if (data.type === 'detection') {
                        detections.unshift(data.data);
                        if (detections.length > 100) detections.pop();
                        updateDroneMarker(data.data);
                        updateDroneList();
                    }
                };
                
                ws.onerror = (error) => {
                    console.log('WebSocket error:', error);
                    setTimeout(connectWebSocket, 3000);
                };
                
                ws.onclose = () => {
                    console.log('WebSocket disconnected, reconnecting...');
                    setTimeout(connectWebSocket, 3000);
                };
            }
            
            // Inject random drone
            async function injectRandomDrone() {
                const types = ["DJI Mavic 3", "DJI Mini", "FPV Analog", "FPV Digital", "Custom Build"];
                const randomType = types[Math.floor(Math.random() * types.length)];
                await fetch(`/api/v1/mock/inject?drone_type=${randomType}`, {method: 'POST'});
            }
            
            // Load active drones on startup
            async function loadActiveDrones() {
                try {
                    const response = await fetch('/api/v1/detections/active');
                    const data = await response.json();
                    if (data.data) {
                        data.data.forEach(detection => {
                            detections.push(detection);
                            updateDroneMarker(detection);
                        });
                        updateDroneList();
                    }
                } catch(e) {
                    console.log('Error loading active drones:', e);
                }
            }
            
            // Initialize
            initMap();
            connectWebSocket();
            loadActiveDrones();
            
            // Refresh active drones periodically
            setInterval(loadActiveDrones, 10000);
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888,
        log_level="info"
    )
