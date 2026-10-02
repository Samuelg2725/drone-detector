from fastapi import APIRouter, WebSocket
from typing import List, Dict
import json

router = APIRouter(prefix="/map", tags=["map"])

# Store active drone positions
active_drones: Dict[str, dict] = {}

@router.get("/positions")
async def get_drone_positions():
    """Return GeoJSON of all detected drones"""
    features = []
    for drone_id, data in active_drones.items():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [data["longitude"], data["latitude"]]
            },
            "properties": {
                "id": drone_id,
                "altitude": data.get("altitude", 0),
                "threat_level": data.get("threat_level", "unknown"),
                "last_seen": data.get("timestamp")
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }

@router.websocket("/live")
async def websocket_map(websocket: WebSocket):
    """WebSocket for live position updates"""
    await websocket.accept()
    try:
        while True:
            # Send current positions every 100ms
            await websocket.send_json({
                "type": "positions",
                "data": active_drones
            })
            await asyncio.sleep(0.1)
    except:
        pass