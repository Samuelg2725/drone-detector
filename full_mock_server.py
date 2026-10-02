#!/usr/bin/env python3
"""
Full Drone Detector Server with Static File Serving
"""

import asyncio
import json
import time
import random
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

app = FastAPI(title="Drone Detector - Mock Mode", version="1.0.0")

# Mock data storage
detections = []
active_drones = {}

# Drone types
DRONE_TYPES = {
    "DJI Mavic 3": {"frequency": 2.45e9, "bandwidth": 20e6, "threat_level": "medium", "icon": "🚁", "color": "#ffaa00"},
    "DJI Mini": {"frequency": 2.45e9, "bandwidth": 20e6, "threat_level": "low", "icon": "🪁", "color": "#00ff88"},
    "FPV Analog": {"frequency": 5.8e9, "bandwidth": 8e6, "threat_level": "medium", "icon": "🏎️", "color": "#ff6600"},
    "FPV Digital": {"frequency": 5.8e9, "bandwidth": 20e6, "threat_level": "high", "icon": "⚡", "color": "#ff0000"},
    "Custom Build": {"frequency": 2.45e9, "bandwidth": 10e6, "threat_level": "high", "icon": "🔧", "color": "#ff00ff"}
}

def generate_mock_detection(drone_type=None):
    if drone_type is None:
        drone_type = random.choice(list(DRONE_TYPES.keys()))
    
    drone_info = DRONE_TYPES[drone_type]
    drone_id = f"drone_{int(time.time() * 1000)}"
    
    # Generate random position around San Francisco
    base_lat = 37.7749
    base_lon = -122.4194
    lat = base_lat + (random.random() - 0.5) * 0.02
    lon = base_lon + (random.random() - 0.5) * 0.02
    
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
        "position": {"lat": lat, "lon": lon, "alt": random.randint(50, 200)},
        "icon": drone_info["icon"],
        "color": drone_info["color"]
    }

@app.get("/")
async def root():
    return FileResponse("ui/dashboard_mock.html")

@app.get("/dashboard")
async def dashboard():
    return FileResponse("ui/dashboard_mock.html")

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

@app.get("/api/v1/detections/stats")
async def get_stats():
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
    frequencies = list(range(2400, 5850, 25))
    spectrum = []
    
    for freq in frequencies:
        power = -100 + random.random() * 20
        
        for d in detections[-10:]:
            drone_freq_mhz = int(d["frequency"] / 1e6)
            if abs(freq - drone_freq_mhz) < 50:
                power += 35 - abs(freq - drone_freq_mhz) / 5
        
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
            await asyncio.sleep(3 + random.random() * 3)
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

async def background_detection_generator():
    while True:
        await asyncio.sleep(4 + random.random() * 2)
        detection = generate_mock_detection()
        detections.append(detection)
        
        if len(detections) > 500:
            detections.pop(0)
        
        print(f"🎯 {detection['icon']} {detection['drone_type']} | "
              f"Threat: {detection['threat_level'].upper()} | "
              f"Confidence: {detection['confidence']*100:.0f}%")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_detection_generator())
    print("\n" + "="*60)
    print("🚁 DRONE DETECTOR WITH LIVE DASHBOARD - STARTED")
    print("="*60)
    print(f"📡 Dashboard:  http://localhost:8888")
    print(f"🗺️  Alternate:  http://localhost:8888/dashboard")
    print(f"📚 API Docs:   http://localhost:8888/docs")
    print(f"🔌 WebSocket:  ws://localhost:8888/ws")
    print("="*60)
    print("Open http://localhost:8888 in your browser!")
    print("Press Ctrl+C to stop\n")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888,
        log_level="info"
    )
