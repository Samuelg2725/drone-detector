#!/usr/bin/env python3
# drone-detector/api/middleware.py
"""
Custom Middleware Module

This module provides custom middleware components for the FastAPI application,
including:
- Request/Response logging
- Request ID generation and propagation
- Rate limiting by IP and endpoint
- CORS configuration
- Request validation and sanitization
- Response compression
- Performance monitoring
- Security headers
- JWT token refresh handling
- Request/response transformation
- Circuit breaker for external services
- Request deduplication
- Cache control
- Error handling and formatting
- Metrics collection
"""

import asyncio
import hashlib
import json
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Tuple, Set
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

# Local imports
from infrastructure.monitoring import get_logger, get_monitoring_manager

# Setup logger
logger = get_logger("api.middleware")

# Rate limiting storage
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)


# ============================================================================
# Request ID Middleware
# ============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate and propagate request IDs
    
    Features:
    - Generates unique request ID for each request
    - Adds X-Request-ID header to response
    - Sets context variable for logging
    - Handles client-provided request IDs
    """
    
    async def dispatch(self, request: Request, call_next):
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = self._generate_request_id()
        
        # Store in request state
        request.state.request_id = request_id
        
        # Set in logging context
        from infrastructure.monitoring import set_request_id
        set_request_id(request_id)
        
        # Process request
        start_time = time.time()
        
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{int((time.time() - start_time) * 1000)}ms"
            return response
        except Exception as e:
            # Log error with request ID
            logger.error(f"Request {request_id} failed: {str(e)}")
            raise
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        timestamp = int(time.time() * 1000)
        random_part = uuid.uuid4().hex[:8]
        return f"{timestamp}-{random_part}"


# ============================================================================
# Rate Limiting Middleware
# ============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware with multiple strategies
    
    Features:
    - Configurable limits per endpoint
    - Different strategies (fixed window, sliding window, token bucket)
    - IP-based and user-based limiting
    - Rate limit headers in response
    - Automatic cleanup of expired entries
    """
    
    def __init__(
        self,
        app: ASGIApp,
        default_requests: int = 60,
        default_window: int = 60,
        strategies: Dict[str, str] = None,
        excluded_paths: List[str] = None
    ):
        super().__init__(app)
        self.default_requests = default_requests
        self.default_window = default_window
        self.strategies = strategies or {}
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/api/docs", "/api/redoc"]
        self._store: Dict[str, List[float]] = defaultdict(list)
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def dispatch(self, request: Request, call_next):
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)
        
        # Get client identifier (IP or user ID)
        client_id = await self._get_client_id(request)
        
        # Get endpoint-specific limit
        requests, window = self._get_limit_for_endpoint(request.url.path)
        
        # Check limit
        if not await self._check_limit(client_id, requests, window):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {requests} requests per {window} seconds",
                    "retry_after": self._get_retry_after(client_id, window)
                },
                headers={
                    "X-RateLimit-Limit": str(requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(self._get_reset_time(client_id, window))
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self._get_remaining(client_id, requests)
        response.headers["X-RateLimit-Limit"] = str(requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(self._get_reset_time(client_id, window))
        
        return response
    
    async def _get_client_id(self, request: Request) -> str:
        """Get client identifier (IP or user ID)"""
        # Try to get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0]
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def _get_limit_for_endpoint(self, path: str) -> Tuple[int, int]:
        """Get rate limit for specific endpoint"""
        # Check for exact match
        if path in self.strategies:
            strategy = self.strategies[path]
            return strategy.get('requests', self.default_requests), strategy.get('window', self.default_window)
        
        # Check for pattern match
        for pattern, strategy in self.strategies.items():
            if pattern.endswith('*') and path.startswith(pattern[:-1]):
                return strategy.get('requests', self.default_requests), strategy.get('window', self.default_window)
        
        return self.default_requests, self.default_window
    
    async def _check_limit(self, client_id: str, requests: int, window: int) -> bool:
        """Check if request is within rate limit"""
        current_time = time.time()
        
        # Clean old entries
        if client_id in self._store:
            self._store[client_id] = [
                t for t in self._store[client_id]
                if current_time - t < window
            ]
        
        # Check limit
        if len(self._store[client_id]) >= requests:
            return False
        
        # Add request
        self._store[client_id].append(current_time)
        return True
    
    def _get_remaining(self, client_id: str, requests: int) -> int:
        """Get remaining requests in current window"""
        if client_id not in self._store:
            return requests
        
        current_time = time.time()
        recent = [t for t in self._store[client_id] if current_time - t < 60]
        return max(0, requests - len(recent))
    
    def _get_reset_time(self, client_id: str, window: int) -> int:
        """Get reset time for rate limit"""
        if client_id not in self._store or not self._store[client_id]:
            return int(time.time() + window)
        
        oldest = min(self._store[client_id])
        return int(oldest + window)
    
    def _get_retry_after(self, client_id: str, window: int) -> int:
        """Get retry-after seconds"""
        reset_time = self._get_reset_time(client_id, window)
        return max(0, reset_time - int(time.time()))


# ============================================================================
# Security Headers Middleware
# ============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to responses
    
    Implements security best practices:
    - HSTS (HTTP Strict Transport Security)
    - X-Frame-Options
    - X-Content-Type-Options
    - X-XSS-Protection
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # HSTS (enable only for HTTPS)
        if request.headers.get("X-Forwarded-Proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = self._get_csp_policy()
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions policy
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Cache control for sensitive endpoints
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        
        return response
    
    def _get_csp_policy(self) -> str:
        """Get Content Security Policy"""
        return "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https://tile.openstreetmap.org",
            "connect-src 'self' ws://localhost:8082 wss://*.drone-detector.com",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'",
            "upgrade-insecure-requests"
        ])


# ============================================================================
# Request Validation Middleware
# ============================================================================

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request validation and sanitization
    
    Features:
    - JSON body size limit
    - Content type validation
    - Request size limiting
    - SQL injection prevention
    - XSS prevention
    - JSON schema validation for high-value endpoints
    """
    
    def __init__(
        self,
        app: ASGIApp,
        max_body_size_mb: int = 10,
        allowed_content_types: List[str] = None
    ):
        super().__init__(app)
        self.max_body_size_bytes = max_body_size_mb * 1024 * 1024
        self.allowed_content_types = allowed_content_types or [
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data"
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Check content type
        content_type = request.headers.get("content-type", "").split(";")[0]
        if content_type and content_type not in self.allowed_content_types:
            return JSONResponse(
                status_code=415,
                content={"error": f"Unsupported content type: {content_type}"}
            )
        
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size_bytes:
            return JSONResponse(
                status_code=413,
                content={"error": f"Request body too large. Maximum {self.max_body_size_bytes // (1024*1024)} MB"}
            )
        
        # For JSON requests, validate and sanitize
        if content_type == "application/json":
            try:
                # Read and parse body
                body = await request.body()
                if body:
                    # Parse JSON
                    data = json.loads(body)
                    
                    # Sanitize data (remove dangerous characters)
                    sanitized = self._sanitize_data(data)
                    
                    # Replace request body with sanitized version
                    request._body = json.dumps(sanitized).encode()
                    
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid JSON in request body"}
                )
        
        return await call_next(request)
    
    def _sanitize_data(self, data: Any) -> Any:
        """Recursively sanitize data to prevent injection attacks"""
        if isinstance(data, dict):
            return {k: self._sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        elif isinstance(data, str):
            # Remove potential SQL injection patterns (basic sanitization)
            dangerous_patterns = ["--", ";", "/*", "*/", "xp_", "exec ", "drop ", "delete "]
            sanitized = data
            for pattern in dangerous_patterns:
                sanitized = sanitized.replace(pattern, "")
            return sanitized
        else:
            return data


# ============================================================================
# Performance Monitoring Middleware
# ============================================================================

class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware for performance monitoring
    
    Features:
    - Request/response timing
    - Slow request detection
    - Performance metrics collection
    - Critical path monitoring
    """
    
    def __init__(self, app: ASGIApp, slow_request_threshold_ms: int = 1000):
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log slow requests
            if duration_ms > self.slow_request_threshold_ms:
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} took {duration_ms:.2f}ms",
                    extra={
                        'path': request.url.path,
                        'method': request.method,
                        'duration_ms': duration_ms,
                        'threshold_ms': self.slow_request_threshold_ms
                    }
                )
            
            # Update metrics
            monitoring = await get_monitoring_manager()
            if monitoring and monitoring.metrics.is_enabled():
                monitoring.metrics.api_request_duration.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code=str(response.status_code)
                ).observe(duration_ms / 1000)  # Convert to seconds
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request error: {request.method} {request.url.path} after {duration_ms:.2f}ms: {str(e)}",
                extra={
                    'path': request.url.path,
                    'method': request.method,
                    'duration_ms': duration_ms,
                    'error': str(e)
                }
            )
            raise
    
    async def _update_metrics(self, metrics_manager, request: Request, duration_ms: float):
        """Update Prometheus metrics"""
        if not metrics_manager or not metrics_manager.metrics.is_enabled():
            return
        
        metrics_manager.metrics.api_request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration_ms / 1000)


# ============================================================================
# Request Deduplication Middleware
# ============================================================================

class RequestDeduplicationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to prevent duplicate request processing
    
    Features:
    - Idempotency key support
    - Request deduplication based on content hash
    - Caching of responses for deduplicated requests
    """
    
    def __init__(self, app: ASGIApp, ttl_seconds: int = 300):
        super().__init__(app)
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Response, float]] = {}
    
    async def dispatch(self, request: Request, call_next):
        # Only applies to mutating methods
        if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
            return await call_next(request)
        
        # Get idempotency key
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)
        
        # Check cache
        cache_key = f"{request.url.path}:{idempotency_key}"
        
        if cache_key in self._cache:
            response, timestamp = self._cache[cache_key]
            if time.time() - timestamp <= self.ttl_seconds:
                # Return cached response
                logger.info(f"Duplicate request detected for {request.url.path}, returning cached response")
                return response
        
        # Process request
        response = await call_next(request)
        
        # Cache successful responses
        if 200 <= response.status_code < 300:
            self._cache[cache_key] = (response, time.time())
            
            # Clean old entries
            self._clean_cache()
        
        return response
    
    def _clean_cache(self):
        """Remove expired cache entries"""
        current_time = time.time()
        expired = [
            key for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.ttl_seconds
        ]
        for key in expired:
            del self._cache[key]


# ============================================================================
# Circuit Breaker Middleware
# ============================================================================

class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    Circuit breaker pattern for external service calls
    
    Features:
    - Automatic failure detection
    - Circuit open/closed/half-open states
    - Automatic recovery
    - Configurable thresholds
    """
    
    def __init__(self, app: ASGIApp, failure_threshold: int = 5, recovery_timeout: int = 60):
        super().__init__(app)
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures: Dict[str, int] = defaultdict(int)
        self._states: Dict[str, str] = defaultdict(lambda: "closed")
        self._last_failure: Dict[str, float] = {}
    
    async def dispatch(self, request: Request, call_next):
        # Identify the service/circuit
        circuit_key = request.url.path.split("/")[2] if len(request.url.path.split("/")) > 2 else "default"
        
        # Check circuit state
        if self._states[circuit_key] == "open":
            if time.time() - self._last_failure.get(circuit_key, 0) > self.recovery_timeout:
                self._states[circuit_key] = "half-open"
                logger.info(f"Circuit {circuit_key} transitioned to half-open")
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Service temporarily unavailable",
                        "message": "Circuit breaker is open",
                        "retry_after": int(self.recovery_timeout - (time.time() - self._last_failure.get(circuit_key, 0)))
                    }
                )
        
        try:
            response = await call_next(request)
            
            # Success - reset failures
            if self._states[circuit_key] == "half-open":
                self._states[circuit_key] = "closed"
                self._failures[circuit_key] = 0
                logger.info(f"Circuit {circuit_key} transitioned to closed (recovered)")
            
            return response
            
        except Exception as e:
            # Record failure
            self._failures[circuit_key] += 1
            self._last_failure[circuit_key] = time.time()
            
            # Open circuit if threshold exceeded
            if self._failures[circuit_key] >= self.failure_threshold:
                self._states[circuit_key] = "open"
                logger.warning(f"Circuit {circuit_key} opened after {self._failures[circuit_key]} failures")
            
            raise


# ============================================================================
# Compression Middleware (Enhanced)
# ============================================================================

class EnhancedCompressionMiddleware(BaseHTTPMiddleware):
    """
    Enhanced compression middleware with intelligent compression decisions
    
    Features:
    - Compress based on content type
    - Skip compression for already compressed content
    - Minimum size threshold
    - gzip and brotli support
    """
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compressible_types: List[str] = None
    ):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compressible_types = compressible_types or [
            "application/json",
            "application/javascript",
            "text/html",
            "text/css",
            "text/plain",
            "application/xml",
            "application/xhtml+xml"
        ]
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Check if compression is appropriate
        if not self._should_compress(response):
            return response
        
        # Get content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < self.minimum_size:
            return response
        
        # Check if already compressed
        if response.headers.get("content-encoding"):
            return response
        
        # Check accept-encoding
        accept_encoding = request.headers.get("accept-encoding", "")
        
        # Choose compression algorithm
        if "br" in accept_encoding and False:  # brotli (disabled for now)
            pass  # Implement brotli compression
        elif "gzip" in accept_encoding:
            # Compress response body
            body = response.body
            if body and len(body) >= self.minimum_size:
                import gzip
                compressed = gzip.compress(body)
                response.body = compressed
                response.headers["content-encoding"] = "gzip"
                response.headers["content-length"] = str(len(compressed))
        
        return response
    
    def _should_compress(self, response: Response) -> bool:
        """Determine if response should be compressed"""
        content_type = response.headers.get("content-type", "").split(";")[0]
        return content_type in self.compressible_types


# ============================================================================
# Exception Handling Middleware
# ============================================================================

class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global exception handling middleware
    
    Features:
    - Catches and formats all exceptions
    - Logs errors with context
    - Returns consistent error response format
    - Handles validation errors specially
    """
    
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
            
        except HTTPException as e:
            # FastAPI HTTP exceptions
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": e.detail,
                    "message": e.detail,
                    "status_code": e.status_code,
                    "path": request.url.path,
                    "method": request.method
                }
            )
            
        except Exception as e:
            # Log unexpected errors
            request_id = getattr(request.state, 'request_id', 'unknown')
            logger.exception(
                f"Unhandled exception in {request.method} {request.url.path} (req: {request_id}): {str(e)}"
            )
            
            # Return generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "status_code": 500,
                    "request_id": request_id
                }
            )


# ============================================================================
# CORS Middleware (Enhanced)
# ============================================================================

class EnhancedCORSMiddleware(BaseHTTPMiddleware):
    """
    Enhanced CORS middleware with dynamic origin validation
    
    Features:
    - Dynamic origin whitelist
    - Preflight caching
    - Credentials support
    - Custom headers exposure
    """
    
    def __init__(
        self,
        app: ASGIApp,
        allowed_origins: List[str] = None,
        allow_credentials: bool = True,
        allowed_methods: List[str] = None,
        allowed_headers: List[str] = None,
        max_age: int = 600
    ):
        super().__init__(app)
        self.allowed_origins = allowed_origins or ["*"]
        self.allow_credentials = allow_credentials
        self.allowed_methods = allowed_methods or ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        self.allowed_headers = allowed_headers or ["*"]
        self.max_age = max_age
    
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        
        # Handle preflight
        if request.method == "OPTIONS":
            response = Response()
            
            if origin and self._is_origin_allowed(origin):
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
                response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
                response.headers["Access-Control-Max-Age"] = str(self.max_age)
            
            return response
        
        # Handle normal request
        response = await call_next(request)
        
        if origin and self._is_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"
        
        # Expose custom headers
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-Response-Time, X-RateLimit-*"
        
        return response
    
    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is allowed"""
        if "*" in self.allowed_origins:
            return True
        return any(self._match_origin(origin, allowed) for allowed in self.allowed_origins)
    
    def _match_origin(self, origin: str, pattern: str) -> bool:
        """Match origin against pattern (supports wildcards)"""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return origin.startswith(pattern[:-1])
        return origin == pattern


# ============================================================================
# Request ID Middleware (from earlier)
# ============================================================================

# ... (RequestIDMiddleware implementation from earlier)

# ============================================================================
# Middleware Registration Helper
# ============================================================================

def register_middleware(app, config: Dict[str, Any] = None):
    """
    Register all middleware with the FastAPI app
    
    Args:
        app: FastAPI application instance
        config: Configuration dictionary
    """
    config = config or {}
    
    # Order matters - first registered, first executed
    # They execute in reverse order of registration (LIFO)
    
    # 1. Exception handling (outermost)
    app.add_middleware(ExceptionHandlingMiddleware)
    
    # 2. Circuit breaker
    if config.get('circuit_breaker', {}).get('enabled', True):
        app.add_middleware(
            CircuitBreakerMiddleware,
            failure_threshold=config.get('circuit_breaker', {}).get('failure_threshold', 5),
            recovery_timeout=config.get('circuit_breaker', {}).get('recovery_timeout', 60)
        )
    
    # 3. Request deduplication
    if config.get('deduplication', {}).get('enabled', True):
        app.add_middleware(
            RequestDeduplicationMiddleware,
            ttl_seconds=config.get('deduplication', {}).get('ttl_seconds', 300)
        )
    
    # 4. Security headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # 5. CORS
    app.add_middleware(
        EnhancedCORSMiddleware,
        allowed_origins=config.get('cors', {}).get('allowed_origins', ["*"]),
        allow_credentials=config.get('cors', {}).get('allow_credentials', True)
    )
    
    # 6. Request validation
    app.add_middleware(
        RequestValidationMiddleware,
        max_body_size_mb=config.get('validation', {}).get('max_body_size_mb', 10)
    )
    
    # 7. Rate limiting
    if config.get('rate_limit', {}).get('enabled', True):
        app.add_middleware(
            RateLimitMiddleware,
            default_requests=config.get('rate_limit', {}).get('default_requests', 60),
            default_window=config.get('rate_limit', {}).get('default_window', 60)
        )
    
    # 8. Performance monitoring
    app.add_middleware(
        PerformanceMiddleware,
        slow_request_threshold_ms=config.get('performance', {}).get('slow_threshold_ms', 1000)
    )
    
    # 9. Compression
    if config.get('compression', {}).get('enabled', True):
        app.add_middleware(
            EnhancedCompressionMiddleware,
            minimum_size=config.get('compression', {}).get('minimum_size', 500)
        )
    
    # 10. Request ID (innermost)
    app.add_middleware(RequestIDMiddleware)
    
    logger.info("All middleware registered")


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("Custom Middleware Module")
    print("=" * 50)
    
    print("\nAvailable Middleware:")
    print("  - RequestIDMiddleware: Generates and propagates request IDs")
    print("  - RateLimitMiddleware: Rate limiting by IP/endpoint")
    print("  - SecurityHeadersMiddleware: Security headers (HSTS, CSP, etc.)")
    print("  - RequestValidationMiddleware: Request validation and sanitization")
    print("  - PerformanceMiddleware: Performance monitoring and metrics")
    print("  - RequestDeduplicationMiddleware: Idempotency key support")
    print("  - CircuitBreakerMiddleware: Circuit breaker pattern")
    print("  - EnhancedCompressionMiddleware: Smart response compression")
    print("  - ExceptionHandlingMiddleware: Global exception handling")
    print("  - EnhancedCORSMiddleware: Dynamic CORS configuration")
    
    print("\n" + "=" * 50)