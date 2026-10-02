#!/usr/bin/env python3
"""One-command launcher for Drone Detection System"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.startup import initialize_system
from app.services import DetectionService
from api.main import create_app
from infrastructure.messaging.websocket_server import start_websocket_server
from infrastructure.monitoring.logger import setup_logging


async def main():
    parser = argparse.ArgumentParser(description="Drone Detection System")
    parser.add_argument("--mode", choices=["live", "mock", "replay"], default="live")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(debug=args.debug)
    
    print("=" * 60)
    print("🛸 DRONE DETECTION SYSTEM v2.0")
    print("=" * 60)
    print(f"Mode: {args.mode.upper()}")
    print(f"API: http://{args.host}:{args.port}")
    print(f"Dashboard: http://{args.host}:{args.port}/ui")
    print("=" * 60)
    
    # Initialize system based on mode
    hardware, config = await initialize_system(mode=args.mode)
    
    # Start detection service
    detection_service = DetectionService(hardware, config)
    asyncio.create_task(detection_service.run())
    
    # Start WebSocket server
    asyncio.create_task(start_websocket_server(port=8082))
    
    # Start FastAPI
    app = create_app(config)
    
    import uvicorn
    config = uvicorn.Config(
        app, 
        host=args.host, 
        port=args.port, 
        log_level="info" if not args.debug else "debug"
    )
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await detection_service.stop()
        hardware.close()


if __name__ == "__main__":
    asyncio.run(main())