#!/usr/bin/env python3
"""
Full Drone Detector Test with Mock Hardware
This simulates drone detections without real SDR hardware
"""

import asyncio
import json
import time
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn

# Create FastAPI app
app = FastAPI(title="Drone Detector - Mock Mode", version="1.0.0")

# Mock data storage
detections = []
active_drones = {}

# Mock drone types with their characteristics
DRONE_TYPES = {
    "DJI Mavic 3": {
        "frequency": 2.45e9,
        "bandwidth": 20e6,
        "threat_level": "medium",
        "icon": "🚁"
    },
    "DJI Mini": {
        "frequency": 2.45e9,
        "bandwidth": 20e6,
        "threat_level": "low",
        "icon": "🪁"
    },
    "FPV Analog": {
        "frequency": 5.8e9,
        "bandwidth": 8e6,
        "threat_level": "medium",
        "icon": "🏎️"
    },
    "FPV Digital": {
        "frequency": 5.8e9,
        "bandwidth": 20e6,
        "threat_level": "high",
        "icon": "⚡"
    },
    "Custom Build": {
        "frequency": 2.45e9,
        "bandwidth": 10e6,
        "threat_level": "high",
        "icon": "🔧"
    }
}

# Mock positions (around a central point)
POSITIONS = [
    {"lat": 37.7749, "lon": -122.4194, "alt": 100},
    {"lat": 37.7755, "lon": -122.4185, "alt": 120},
    {"lat": 37.7740, "lon": -122.4200, "alt": 90},
    {"lat": 37.7750, "lon": -122.4190, "alt": 110},
    {"lat": 37.7745, "lon": -122.4188, "alt": 105},
]

# Helper functions
def generate_mock_detection(drone_type=None):
    """Generate a mock drone detection"""
    if drone_type is None:
        drone_type = list(DRONE_TYPES.keys())[
            int(time.time() * 1000) % len(DRONE_TYPES)
        ]
    
    drone_info = DRONE_TYPES[drone_type]
    position = POSITIONS[int(time.time() * 100) % len(POSITIONS)]
    
    return {
        "id": f"det_{int(time.time() * 1000)}",
        "timestamp": datetime.now().isoformat(),
        "drone_type": drone_type,
        "frequency": drone_info["frequency"],
        "bandwidth": drone_info["bandwidth"],
        "confidence": round(0.7 + (time.time() % 30) / 100, 2),
        "threat_level": drone_info["threat_level"],
        "signal_power": round(-70 + (time.time() % 30), 1),
        "snr": round(15 + (time.time() % 20), 1),
        "position": position,
        "icon": drone_info["icon"]
    }

# API Endpoints
@app.get("/")
async def root():
    return {
        "message": "Drone Detector API (Mock Mode)",
        "version": "1.0.0",
        "status": "running",
        "mock_enabled": True,
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "detections": "/api/v1/detections",
            "spectrum": "/api/v1/spectrum/live",
            "websocket": "ws://localhost:8888/ws"
        }
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "drone-detector",
        "mock_mode": True,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/detections")
async def get_detections(limit: int = 50):
    """Get recent detections"""
    return {
        "status": "success",
        "data": detections[-limit:],
        "total": len(detections),
        "mock": True
    }

@app.get("/api/v1/detections/stats")
async def get_stats():
    """Get detection statistics"""
    drone_counts = {}
    threat_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    
    for d in detections:
        drone_counts[d["drone_type"]] = drone_counts.get(d["drone_type"], 0) + 1
        threat_counts[d["threat_level"]] = threat_counts.get(d["threat_level"], 0) + 1
    
    return {
        "status": "success",
        "data": {
            "total_detections": len(detections),
            "unique_drones": len(drone_counts),
            "drone_types": drone_counts,
            "threat_distribution": threat_counts,
            "mock_mode": True
        }
    }

@app.get("/api/v1/spectrum/live")
async def get_spectrum():
    """Get simulated live spectrum data"""
    import random
    frequencies = list(range(2400, 2500, 5))  # 2.4-2.5 GHz in 5MHz steps
    spectrum = []
    
    for freq in frequencies:
        # Add random noise
        power = -100 + random.random() * 20
        
        # Add peaks at drone frequencies
        for d in detections[-5:]:  # Last 5 detections
            drone_freq_ghz = int(d["frequency"] / 1e9 * 1000)
            if abs(freq - drone_freq_ghz) < 10:
                power += 30 - abs(freq - drone_freq_ghz) * 1.5
        
        spectrum.append(round(power, 1))
    
    return {
        "status": "success",
        "data": {
            "frequencies": frequencies,
            "spectrum": spectrum,
            "center_frequency": 2.45e9,
            "timestamp": datetime.now().isoformat(),
            "mock": True
        }
    }

@app.post("/api/v1/mock/inject")
async def inject_drone(drone_type: str = None):
    """Manually inject a drone detection (for testing)"""
    detection = generate_mock_detection(drone_type)
    detections.append(detection)
    
    # Keep only last 1000 detections
    if len(detections) > 1000:
        detections.pop(0)
    
    return {
        "status": "success",
        "data": detection,
        "message": f"Drone injected: {detection['drone_type']}"
    }

@app.get("/api/v1/hardware/status")
async def hardware_status():
    """Get mock hardware status"""
    return {
        "status": "success",
        "data": {
            "type": "mock",
            "connected": True,
            "mock_mode": True,
            "sample_rate": 2000000,
            "center_frequency": 2450000000,
            "gain": 20,
            "temperature_c": 45.2
        }
    }

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            # Send a detection every 3-5 seconds
            await asyncio.sleep(3 + (hash(str(time.time())) % 3))
            
            detection = generate_mock_detection()
            detections.append(detection)
            
            # Keep only last 1000
            if len(detections) > 1000:
                detections.pop(0)
            
            await websocket.send_json({
                "type": "detection",
                "data": detection,
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        print(f"WebSocket error: {e}")

# Background task to generate random detections
async def background_detection_generator():
    """Generate random detections in background"""
    while True:
        await asyncio.sleep(5)  # Generate every 5 seconds
        detection = generate_mock_detection()
        detections.append(detection)
        
        # Keep only last 1000
        if len(detections) > 1000:
            detections.pop(0)
        
        print(f"🎯 Mock Detection: {detection['drone_type']} "
              f"(Confidence: {detection['confidence']*100:.0f}%)")

@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup"""
    asyncio.create_task(background_detection_generator())
    print("\n" + "="*60)
    print("🚁 DRONE DETECTOR (MOCK MODE) - STARTED")
    print("="*60)
    print(f"📡 API:        http://localhost:8888")
    print(f"📚 Docs:       http://localhost:8888/docs")
    print(f"🔌 WebSocket:  ws://localhost:8888/ws")
    print(f"💉 Inject:     POST /api/v1/mock/inject")
    print("="*60)
    print("Mock detections will appear every 5 seconds")
    print("Press Ctrl+C to stop\n")

# Web dashboard HTML
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Drone Detector - Live Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }
            h1 { color: #00ff88; }
            .container { max-width: 1200px; margin: 0 auto; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
            .stat-card { background: #16213e; padding: 15px; border-radius: 10px; text-align: center; }
            .stat-value { font-size: 2em; font-weight: bold; color: #00ff88; }
            .detections { background: #16213e; border-radius: 10px; padding: 20px; }
            .detection { border-bottom: 1px solid #333; padding: 10px; margin: 5px 0; }
            .detection:hover { background: #1a1a3e; }
            .threat-critical { color: #ff0000; }
            .threat-high { color: #ff6600; }
            .threat-medium { color: #ffcc00; }
            .threat-low { color: #00ff00; }
            #spectrum { margin-top: 20px; background: #0f0f1a; border-radius: 10px; padding: 20px; }
            canvas { background: #0a0a15; border-radius: 5px; }
            button { background: #00ff88; color: #1a1a2e; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
            button:hover { background: #00cc66; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚁 Drone Detector - Live Dashboard (Mock Mode)</h1>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value" id="detectionCount">0</div>
                    <div>Total Detections</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="activeDrones">0</div>
                    <div>Active Drones</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="threatLevel">-</div>
                    <div>Current Threat</div>
                </div>
            </div>
            
            <div class="detections">
                <h3>📡 Recent Detections</h3>
                <div id="detectionsList"></div>
            </div>
            
            <div id="spectrum">
                <h3>📊 Live Spectrum</h3>
                <canvas id="spectrumCanvas" width="800" height="200"></canvas>
            </div>
            
            <div style="margin-top: 20px;">
                <button onclick="injectDrone()">💉 Inject Test Drone</button>
                <button onclick="clearDetections()">🗑️ Clear All</button>
            </div>
        </div>
        
        <script>
            let ws = null;
            let detections = [];
            
            function connectWebSocket() {
                ws = new WebSocket('ws://localhost:8888/ws');
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    if (data.type === 'detection') {
                        detections.unshift(data.data);
                        if (detections.length > 20) detections.pop();
                        updateDetections();
                        updateStats();
                        drawSpectrum();
                    }
                };
                
                ws.onerror = function(error) {
                    console.log('WebSocket error:', error);
                    setTimeout(connectWebSocket, 3000);
                };
            }
            
            function updateDetections() {
                const container = document.getElementById('detectionsList');
                container.innerHTML = detections.map(d => `
                    <div class="detection">
                        <strong>${d.icon} ${d.drone_type}</strong>
                        <span class="threat-${d.threat_level}"> (${d.threat_level.toUpperCase()})</span><br>
                        Confidence: ${(d.confidence * 100).toFixed(0)}% | 
                        Freq: ${(d.frequency / 1e9).toFixed(3)} GHz | 
                        Power: ${d.signal_power} dBm
                        <small>${new Date(d.timestamp).toLocaleTimeString()}</small>
                    </div>
                `).join('');
            }
            
            function updateStats() {
                document.getElementById('detectionCount').textContent = detections.length;
                
                if (detections.length > 0) {
                    const threat = detections[0].threat_level;
                    document.getElementById('threatLevel').textContent = threat.toUpperCase();
                    document.getElementById('threatLevel').className = `stat-value threat-${threat}`;
                }
                
                const activeCount = new Set(detections.slice(0, 5).map(d => d.drone_type)).size;
                document.getElementById('activeDrones').textContent = activeCount;
            }
            
            async function drawSpectrum() {
                try {
                    const response = await fetch('/api/v1/spectrum/live');
                    const data = await response.json();
                    const spectrum = data.data.spectrum;
                    
                    const canvas = document.getElementById('spectrumCanvas');
                    const ctx = canvas.getContext('2d');
                    const width = canvas.width;
                    const height = canvas.height;
                    
                    ctx.clearRect(0, 0, width, height);
                    
                    // Draw grid
                    ctx.strokeStyle = '#333';
                    ctx.lineWidth = 0.5;
                    for (let i = 0; i <= 4; i++) {
                        const y = height - (i * height / 4);
                        ctx.beginPath();
                        ctx.moveTo(0, y);
                        ctx.lineTo(width, y);
                        ctx.stroke();
                    }
                    
                    // Draw spectrum
                    if (spectrum) {
                        ctx.beginPath();
                        ctx.strokeStyle = '#00ff88';
                        ctx.lineWidth = 2;
                        
                        const step = width / spectrum.length;
                        for (let i = 0; i < spectrum.length; i++) {
                            const x = i * step;
                            const y = height - ((spectrum[i] + 100) / 60) * height;
                            if (i === 0) {
                                ctx.moveTo(x, y);
                            } else {
                                ctx.lineTo(x, y);
                            }
                        }
                        ctx.stroke();
                    }
                } catch(e) {
                    console.log('Spectrum error:', e);
                }
            }
            
            async function injectDrone() {
                const types = ["DJI Mavic 3", "DJI Mini", "FPV Analog", "FPV Digital", "Custom Build"];
                const randomType = types[Math.floor(Math.random() * types.length)];
                await fetch(`/api/v1/mock/inject?drone_type=${randomType}`, {method: 'POST'});
            }
            
            function clearDetections() {
                detections = [];
                updateDetections();
                updateStats();
            }
            
            connectWebSocket();
            setInterval(drawSpectrum, 2000);
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
