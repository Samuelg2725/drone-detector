#!/usr/bin/env python3
# drone-detector/api/main.py
"""
FastAPI Entry Point - Main Application

This module serves as the main entry point for the Drone Detection System API,
providing:
- REST API endpoints for all system functionality
- WebSocket connections for real-time data
- Static file serving for web dashboard
- CORS middleware for cross-origin requests
- Request/response logging
- Rate limiting
- Authentication and authorization
- API versioning
- OpenAPI documentation (Swagger UI & ReDoc)
- Health check endpoints
- Graceful shutdown handling
"""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# Local imports
from api.routes import (
    spectrum_router,
    detection_router,
    hardware_router,
    system_router,
    map_router,
    analytics_router,
    config_router,
    auth_router
)
from api.schemas.common import ErrorResponse, SuccessResponse
from infrastructure.monitoring import get_logger, setup_logging, get_monitoring_manager
from infrastructure.monitoring.health_check import create_health_routes
from infrastructure.storage import get_storage_manager
from infrastructure.messaging import get_websocket_manager, get_event_bus
from app.services import DetectionService
from config.config_loader import load_config

# Setup logging
logger = get_logger("api.main")


# ============================================================================
# Lifespan Manager
# ============================================================================

class LifespanManager:
    """
    Manages application lifecycle events
    
    Handles startup and shutdown procedures including:
    - Initializing services
    - Starting background tasks
    - Graceful shutdown
    - Resource cleanup
    """
    
    def __init__(self):
        self.start_time = None
        self.background_tasks = []
        self.services = {}
    
    async def startup(self) -> None:
        """Execute startup procedures"""
        logger.info("Starting Drone Detection System API...")
        self.start_time = time.time()
        
        # Load configuration
        logger.info("Loading configuration...")
        self.config = load_config()
        
        # Initialize monitoring
        logger.info("Initializing monitoring...")
        monitoring_config = self.config.get('monitoring', {})
        self.monitoring = await get_monitoring_manager(monitoring_config)
        await self.monitoring.start_metrics_server(
            self.config.get('metrics_port', 8001)
        )
        
        # Initialize storage
        logger.info("Initializing storage...")
        storage_config = self.config.get('storage', {})
        self.storage = await get_storage_manager(storage_config)
        
        # Initialize detection service
        logger.info("Initializing detection service...")
        self.detection_service = DetectionService(self.config.get('detection', {}))
        await self.detection_service.initialize()
        
        # Start background tasks
        logger.info("Starting background tasks...")
        self.background_tasks.append(
            asyncio.create_task(self._metrics_collector_task())
        )
        self.background_tasks.append(
            asyncio.create_task(self._alert_processor_task())
        )
        
        # Store services in app state
        self.services = {
            'config': self.config,
            'monitoring': self.monitoring,
            'storage': self.storage,
            'detection_service': self.detection_service
        }
        
        logger.info(f"API started successfully in {time.time() - self.start_time:.2f}s")
    
    async def shutdown(self) -> None:
        """Execute shutdown procedures"""
        logger.info("Shutting down Drone Detection System API...")
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Close services
        if hasattr(self, 'detection_service'):
            await self.detection_service.shutdown()
        
        if hasattr(self, 'storage'):
            await self.storage.close()
        
        if hasattr(self, 'monitoring'):
            await self.monitoring.shutdown()
        
        logger.info("API shutdown complete")
    
    async def _metrics_collector_task(self):
        """Background task for collecting metrics"""
        while True:
            try:
                if hasattr(self, 'monitoring'):
                    self.monitoring.update_uptime()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
                await asyncio.sleep(10)
    
    async def _alert_processor_task(self):
        """Background task for processing alerts"""
        while True:
            try:
                # Process pending alerts
                event_bus = get_event_bus()
                # Alert processing logic here
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Alert processor error: {e}")
                await asyncio.sleep(1)


# ============================================================================
# Custom Middleware
# ============================================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Generate request ID
        request_id = f"{int(start_time * 1000)}-{id(request)}"
        request.state.request_id = request_id
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.url.path,
                'client': request.client.host if request.client else None
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Log response
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Response: {response.status_code} ({duration_ms:.2f}ms)",
                extra={
                    'request_id': request_id,
                    'status_code': response.status_code,
                    'duration_ms': duration_ms
                }
            )
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {str(e)}",
                extra={
                    'request_id': request_id,
                    'error': str(e),
                    'duration_ms': duration_ms
                }
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._requests = {}
        self._window = 60  # seconds
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old entries
        if client_ip in self._requests:
            self._requests[client_ip] = [
                t for t in self._requests[client_ip]
                if current_time - t < self._window
            ]
        
        # Check rate limit
        if client_ip in self._requests and len(self._requests[client_ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {self.requests_per_minute} requests per minute',
                    'retry_after': self._window
                }
            )
        
        # Add request
        if client_ip not in self._requests:
            self._requests[client_ip] = []
        self._requests[client_ip].append(current_time)
        
        return await call_next(request)


# ============================================================================
# Exception Handlers
# ============================================================================

def register_exception_handlers(app: FastAPI):
    """Register custom exception handlers"""
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="Validation Error",
                message=str(exc.errors()),
                status_code=422
            ).dict()
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(f"HTTP exception: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=exc.detail,
                message=exc.detail,
                status_code=exc.status_code
            ).dict()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="Internal Server Error",
                message="An unexpected error occurred",
                status_code=500
            ).dict()
        )


# ============================================================================
# Dependency Functions
# ============================================================================

async def get_api_config() -> Dict[str, Any]:
    """Dependency to get API configuration"""
    from api.main import lifespan_manager
    return lifespan_manager.services.get('config', {})


async def get_detection_service() -> DetectionService:
    """Dependency to get detection service"""
    from api.main import lifespan_manager
    return lifespan_manager.services.get('detection_service')


async def get_storage() -> Any:
    """Dependency to get storage manager"""
    from api.main import lifespan_manager
    return lifespan_manager.services.get('storage')


async def get_monitoring() -> Any:
    """Dependency to get monitoring manager"""
    from api.main import lifespan_manager
    return lifespan_manager.services.get('monitoring')


# ============================================================================
# WebSocket Manager
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected: {len(self.active_connections)} active")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected: {len(self.active_connections)} active")
    
    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass
    
    async def send_personal(self, message: Dict[str, Any], websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")


# ============================================================================
# Application Factory
# ============================================================================

def create_app(config: Optional[Dict[str, Any]] = None) -> FastAPI:
    """
    Create and configure FastAPI application
    
    Args:
        config: Optional configuration override
        
    Returns:
        Configured FastAPI application
    """
    
    # Create lifespan manager
    global lifespan_manager
    lifespan_manager = LifespanManager()
    
    # Define lifespan context manager
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await lifespan_manager.startup()
        yield
        # Shutdown
        await lifespan_manager.shutdown()
    
    # Create FastAPI app
    app = FastAPI(
        title="Drone Detection System API",
        description="""
        # Drone Detection System REST API
        
        ## Overview
        This API provides access to the Drone Detection System, enabling:
        - Real-time drone detection and tracking
        - Spectrum analysis and visualization
        - Hardware control and configuration
        - System monitoring and health checks
        
        ## Authentication
        API endpoints require authentication using JWT tokens.
        
        ## Rate Limiting
        Default rate limit is 60 requests per minute per IP.
        
        ## WebSocket
        Connect to `/ws` for real-time detection updates.
        """,
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.get('cors_origins', ["*"]) if config else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=config.get('rate_limit', 60) if config else 60)
    
    # Register exception handlers
    register_exception_handlers(app)
    
    # Include routers
    app.include_router(spectrum_router, prefix="/api/spectrum", tags=["Spectrum"])
    app.include_router(detection_router, prefix="/api/detections", tags=["Detections"])
    app.include_router(hardware_router, prefix="/api/hardware", tags=["Hardware"])
    app.include_router(system_router, prefix="/api/system", tags=["System"])
    app.include_router(map_router, prefix="/api/map", tags=["Map"])
    app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])
    app.include_router(config_router, prefix="/api/config", tags=["Configuration"])
    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    
    # Add health routes
    health_routes = create_health_routes(lifespan_manager.monitoring.health_manager)
    app.include_router(health_routes)
    
    # Static file serving for UI
    ui_path = Path(__file__).parent.parent / "ui"
    if ui_path.exists():
        app.mount("/ui", StaticFiles(directory=str(ui_path), html=True), name="ui")
        app.mount("/assets", StaticFiles(directory=str(ui_path / "assets")), name="assets")
    
    # Root endpoint
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Root endpoint - redirect to dashboard"""
        return """
        <html>
            <head>
                <title>Drone Detection System</title>
                <meta http-equiv="refresh" content="0; url=/ui/">
            </head>
            <body>
                <p>Redirecting to <a href="/ui/">dashboard</a>...</p>
            </body>
        </html>
        """
    
    # API info endpoint
    @app.get("/api/info", response_model=SuccessResponse)
    async def api_info():
        """Get API information"""
        return SuccessResponse(
            success=True,
            message="API is operational",
            data={
                'name': 'Drone Detection System API',
                'version': '2.0.0',
                'status': 'operational',
                'uptime_seconds': time.time() - lifespan_manager.start_time if lifespan_manager.start_time else 0,
                'endpoints': {
                    'docs': '/api/docs',
                    'redoc': '/api/redoc',
                    'health': '/health',
                    'websocket': 'ws://localhost:8082'
                }
            }
        )
    
    return app


# ============================================================================
# WebSocket Routes
# ============================================================================

async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates
    
    Handles:
    - Real-time detection streaming
    - Metrics updates
    - Command reception
    """
    connection_manager = ConnectionManager()
    await connection_manager.connect(websocket)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            # Handle different message types
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "get_status":
                # Send system status
                await websocket.send_json({
                    'type': 'status',
                    'data': {
                        'status': 'running',
                        'timestamp': datetime.now().isoformat()
                    }
                })
            elif data.startswith("subscribe:"):
                # Subscribe to specific event types
                event_type = data.split(":")[1]
                logger.info(f"WebSocket subscribed to {event_type}")
            else:
                logger.warning(f"Unknown WebSocket message: {data}")
    
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)


# ============================================================================
# Application Instance
# ============================================================================

# Global lifespan manager instance
lifespan_manager = LifespanManager()

# Create application instance
app = create_app()

# Add WebSocket route
app.add_websocket_route("/ws", websocket_endpoint)
app.add_websocket_route("/ws/live", websocket_endpoint)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for running the API server"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Drone Detection System API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    args = parser.parse_args()
    
    # Configure logging
    setup_logging()
    
    # Run server
    if args.reload:
        uvicorn.run(
            "api.main:app",
            host=args.host,
            port=args.port,
            reload=True,
            log_level="info"
        )
    else:
        uvicorn.run(
            "api.main:app",
            host=args.host,
            port=args.port,
            workers=args.workers,
            log_level="info"
        )


if __name__ == "__main__":
    main()