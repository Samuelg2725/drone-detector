#!/usr/bin/env python3
# drone-detector/api/dependencies.py
"""
FastAPI Dependencies Module

This module provides dependency injection functions for FastAPI endpoints,
including:
- Authentication and authorization
- Database connections
- Service instances
- Request validation
- Rate limiting per endpoint
- User context extraction
- Permission checking
- Query parameter parsing
- Request ID tracking
- Tenant isolation
- Feature flag checking
- Audit logging
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union, Callable
from fastapi import Request, HTTPException, status, Depends, Query, Path, Body, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, validator

# Local imports
from infrastructure.monitoring import get_logger, logging_context, set_request_id, get_request_id
from infrastructure.storage import get_storage_manager
from app.services import DetectionService, HardwareService, SpectrumService

# Setup logger
logger = get_logger("api.dependencies")


# ============================================================================
# Authentication and Security
# ============================================================================

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# JWT settings
SECRET_KEY = "your-secret-key-change-in-production"  # Should come from config
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenData(BaseModel):
    """Token data model"""
    username: Optional[str] = None
    user_id: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []


class User(BaseModel):
    """User model"""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    disabled: bool = False
    roles: List[str] = []
    permissions: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None


class LoginRequest(BaseModel):
    """Login request model"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60


# ============================================================================
# Authentication Functions
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Get password hash"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Get current authenticated user from JWT token
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        User object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        token_type: str = payload.get("type")
        
        if username is None or user_id is None:
            raise credentials_exception
        
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        token_data = TokenData(username=username, user_id=user_id)
        
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    storage = await get_storage_manager()
    user_data = await storage.get_user(token_data.user_id)
    
    if user_data is None:
        raise credentials_exception
    
    user = User(**user_data)
    
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Set user context for logging
    from infrastructure.monitoring import set_user_id
    set_user_id(user.id)
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Get current superuser (requires admin role)"""
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


# ============================================================================
# Permission Checking
# ============================================================================

def require_permission(permission: str):
    """
    Dependency factory for permission checking
    
    Args:
        permission: Required permission (e.g., "detections:read")
        
    Returns:
        Dependency function that checks permission
    """
    async def permission_dependency(current_user: User = Depends(get_current_user)):
        if permission not in current_user.permissions and "admin" not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}"
            )
        return current_user
    return permission_dependency


def require_role(role: str):
    """
    Dependency factory for role checking
    
    Args:
        role: Required role
        
    Returns:
        Dependency function that checks role
    """
    async def role_dependency(current_user: User = Depends(get_current_user)):
        if role not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing role: {role}"
            )
        return current_user
    return role_dependency


# ============================================================================
# Service Dependencies
# ============================================================================

async def get_detection_service() -> DetectionService:
    """
    Get detection service instance
    
    Returns:
        DetectionService instance
    """
    from api.main import lifespan_manager
    service = lifespan_manager.services.get('detection_service')
    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Detection service not available"
        )
    return service


async def get_hardware_service() -> HardwareService:
    """
    Get hardware service instance
    
    Returns:
        HardwareService instance
    """
    from api.main import lifespan_manager
    service = lifespan_manager.services.get('hardware_service')
    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hardware service not available"
        )
    return service


async def get_spectrum_service() -> SpectrumService:
    """
    Get spectrum service instance
    
    Returns:
        SpectrumService instance
    """
    from api.main import lifespan_manager
    service = lifespan_manager.services.get('spectrum_service')
    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spectrum service not available"
        )
    return service


async def get_config() -> Dict[str, Any]:
    """
    Get system configuration
    
    Returns:
        Configuration dictionary
    """
    from api.main import lifespan_manager
    return lifespan_manager.services.get('config', {})


async def get_storage() -> Any:
    """
    Get storage manager instance
    
    Returns:
        Storage manager instance
    """
    from api.main import lifespan_manager
    storage = lifespan_manager.services.get('storage')
    if not storage:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service not available"
        )
    return storage


async def get_monitoring() -> Any:
    """
    Get monitoring manager instance
    
    Returns:
        Monitoring manager instance
    """
    from api.main import lifespan_manager
    return lifespan_manager.services.get('monitoring')


# ============================================================================
# Request Context Dependencies
# ============================================================================

async def get_request_id(request: Request) -> str:
    """
    Get request ID from request state
    
    Args:
        request: FastAPI request object
        
    Returns:
        Request ID string
    """
    request_id = getattr(request.state, 'request_id', None)
    if not request_id:
        request_id = f"{int(datetime.now().timestamp() * 1000)}-{id(request)}"
        set_request_id(request_id)
    return request_id


async def get_client_ip(request: Request) -> str:
    """
    Get client IP address
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0]
    return request.client.host if request.client else "unknown"


async def get_user_agent(request: Request) -> str:
    """
    Get user agent string
    
    Args:
        request: FastAPI request object
        
    Returns:
        User agent string
    """
    return request.headers.get("User-Agent", "unknown")


# ============================================================================
# Query Parameter Dependencies
# ============================================================================

class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Query(1, ge=1, description="Page number")
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Query(None, description="Sort field")
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database query"""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """Get limit for database query"""
        return self.page_size


class DateRangeParams(BaseModel):
    """Date range parameters"""
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)")
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate date range"""
        if v and values.get('start_date') and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    @property
    def start_datetime(self) -> datetime:
        """Get start datetime with default"""
        return self.start_date or datetime.now() - timedelta(days=30)
    
    @property
    def end_datetime(self) -> datetime:
        """Get end datetime with default"""
        return self.end_date or datetime.now()


class DetectionFilterParams(BaseModel):
    """Detection filter parameters"""
    drone_type: Optional[str] = Query(None, description="Filter by drone type")
    threat_level: Optional[str] = Query(None, description="Filter by threat level (LOW, MEDIUM, HIGH, CRITICAL)")
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence")
    max_confidence: float = Query(1.0, ge=0.0, le=1.0, description="Maximum confidence")
    source: Optional[str] = Query(None, description="Detection source")
    has_remote_id: Optional[bool] = Query(None, description="Has Remote ID")
    in_restricted_zone: Optional[bool] = Query(None, description="In restricted zone")
    
    @validator('max_confidence')
    def validate_confidence_range(cls, v, values):
        """Validate confidence range"""
        if v < values.get('min_confidence', 0):
            raise ValueError('max_confidence must be >= min_confidence')
        return v


class SpectrumFilterParams(BaseModel):
    """Spectrum filter parameters"""
    center_freq_min: Optional[float] = Query(None, description="Minimum center frequency (Hz)")
    center_freq_max: Optional[float] = Query(None, description="Maximum center frequency (Hz)")
    min_snr: Optional[float] = Query(None, description="Minimum SNR (dB)")
    has_detection: Optional[bool] = Query(None, description="Has associated detection")


class AlertFilterParams(BaseModel):
    """Alert filter parameters"""
    severity: Optional[str] = Query(None, description="Alert severity (INFO, WARNING, ALERT, CRITICAL, EMERGENCY)")
    acknowledged: Optional[bool] = Query(None, description="Acknowledged status")
    resolved: Optional[bool] = Query(None, description="Resolved status")
    category: Optional[str] = Query(None, description="Alert category")


# ============================================================================
# Rate Limiting Dependencies
# ============================================================================

class RateLimiter:
    """
    Rate limiter for endpoints
    
    Usage:
        @app.get("/endpoint", dependencies=[Depends(rate_limiter(requests=100, window=60))])
    """
    
    def __init__(self):
        self._requests = {}
    
    def __call__(self, requests: int = 60, window: int = 60):
        async def rate_limit_dependency(request: Request):
            client_ip = await get_client_ip(request)
            current_time = datetime.now().timestamp()
            
            # Clean old entries
            if client_ip in self._requests:
                self._requests[client_ip] = [
                    t for t in self._requests[client_ip]
                    if current_time - t < window
                ]
            
            # Check limit
            if client_ip in self._requests and len(self._requests[client_ip]) >= requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {requests} requests per {window} seconds."
                )
            
            # Add request
            if client_ip not in self._requests:
                self._requests[client_ip] = []
            self._requests[client_ip].append(current_time)
            
            return True
        
        return rate_limit_dependency


# Global rate limiter instance
rate_limiter = RateLimiter()


# ============================================================================
# Feature Flag Dependencies
# ============================================================================

class FeatureFlags:
    """Feature flag checker"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def is_enabled(self, feature: str) -> bool:
        """Check if feature is enabled"""
        return self.config.get('features', {}).get(feature, False)
    
    def __call__(self, feature: str):
        async def feature_dependency(config: Dict[str, Any] = Depends(get_config)):
            if not config.get('features', {}).get(feature, False):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Feature '{feature}' is not enabled"
                )
            return True
        return feature_dependency


async def get_feature_flags() -> FeatureFlags:
    """Get feature flags instance"""
    config = await get_config()
    return FeatureFlags(config)


# ============================================================================
# Validation Dependencies
# ============================================================================

async def validate_detection_id(detection_id: str = Path(..., description="Detection ID")) -> str:
    """
    Validate detection ID format
    
    Args:
        detection_id: Detection ID from path
        
    Returns:
        Validated detection ID
    """
    if not detection_id or len(detection_id) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid detection ID format"
        )
    return detection_id


async def validate_alert_id(alert_id: str = Path(..., description="Alert ID")) -> str:
    """Validate alert ID format"""
    if not alert_id or len(alert_id) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid alert ID format"
        )
    return alert_id


async def validate_recording_id(recording_id: str = Path(..., description="Recording ID")) -> str:
    """Validate recording ID format"""
    if not recording_id or len(recording_id) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid recording ID format"
        )
    return recording_id


async def validate_coordinates(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude")
) -> tuple:
    """Validate geographic coordinates"""
    return (latitude, longitude)


# ============================================================================
# Audit Logging Dependency
# ============================================================================

async def audit_log(
    request: Request,
    user: User = Depends(get_current_user),
    action: str = None
) -> None:
    """
    Audit logging dependency
    
    Logs user actions for security auditing
    """
    # This would store audit logs in database
    # Implementation depends on requirements
    logger.info(
        f"Audit: {user.username} performed {action} on {request.url.path}",
        extra={
            'user_id': user.id,
            'username': user.username,
            'action': action,
            'path': request.url.path,
            'method': request.method,
            'ip': await get_client_ip(request),
            'user_agent': await get_user_agent(request)
        }
    )
    return True


# ============================================================================
# Tenant Isolation (for multi-tenant deployments)
# ============================================================================

async def get_tenant_id(request: Request) -> str:
    """
    Get tenant ID from request (for multi-tenant deployments)
    
    Args:
        request: FastAPI request object
        
    Returns:
        Tenant ID
    """
    # Get from header or subdomain
    tenant_id = request.headers.get("X-Tenant-ID")
    
    if not tenant_id:
        # Try to extract from subdomain
        host = request.headers.get("host", "")
        parts = host.split(".")
        if len(parts) > 2:
            tenant_id = parts[0]
    
    if not tenant_id:
        tenant_id = "default"
    
    return tenant_id


async def require_tenant_access(
    tenant_id: str = Depends(get_tenant_id),
    user: User = Depends(get_current_user)
) -> str:
    """
    Check tenant access for multi-tenant deployments
    
    Args:
        tenant_id: Tenant ID
        user: Current user
        
    Returns:
        Tenant ID if authorized
    """
    # Check if user has access to this tenant
    if "admin" not in user.roles and tenant_id not in user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for tenant: {tenant_id}"
        )
    
    return tenant_id


# ============================================================================
# API Versioning
# ============================================================================

async def get_api_version(request: Request) -> str:
    """
    Get API version from Accept header or URL
    
    Args:
        request: FastAPI request object
        
    Returns:
        API version string
    """
    # Check Accept header
    accept = request.headers.get("Accept", "")
    if "application/vnd.drone-detector.v1+json" in accept:
        return "v1"
    elif "application/vnd.drone-detector.v2+json" in accept:
        return "v2"
    
    # Default to latest
    return "v2"


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("FastAPI Dependencies Module")
    print("=" * 50)
    
    print("\nAvailable Dependencies:")
    print("  - Authentication: get_current_user, get_current_superuser")
    print("  - Permissions: require_permission(), require_role()")
    print("  - Services: get_detection_service, get_hardware_service")
    print("  - Query Params: PaginationParams, DateRangeParams")
    print("  - Rate Limiting: rate_limiter()")
    print("  - Validation: validate_coordinates, validate_detection_id")
    print("  - Tenant: get_tenant_id, require_tenant_access")
    
    print("\n" + "=" * 50)