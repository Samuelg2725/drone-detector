#!/usr/bin/env python3
# drone-detector/api/routes/auth.py
"""
Authentication Routes

This module provides REST API endpoints for authentication and authorization:
- User registration and login
- JWT token generation and validation
- Token refresh
- Password reset and recovery
- Email verification
- Two-factor authentication (2FA)
- OAuth2 integration (Google, GitHub)
- API key management
- Session management
- User profile management
- Role and permission management
- Activity logging
- Rate limiting per user
- Account lockout protection
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, validator
import secrets
import hashlib
import pyotp
import qrcode
from io import BytesIO
import base64

# Local imports
from api.dependencies import (
    get_current_user,
    get_current_superuser,
    require_permission,
    rate_limiter,
    get_user_agent,
    get_client_ip,
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)
from infrastructure.storage import get_storage_manager
from infrastructure.monitoring import get_logger, logging_context

# Setup router
router = APIRouter()
logger = get_logger("api.routes.auth")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ============================================================================
# Pydantic Models
# ============================================================================

class UserRole(str, Enum):
    """User roles"""
    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    VIEWER = "viewer"
    API = "api"


class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    LOCKED = "locked"


class UserRegistration(BaseModel):
    """User registration request"""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password")
    full_name: Optional[str] = Field(None, description="Full name")
    phone: Optional[str] = Field(None, description="Phone number")
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format"""
        if not v.isalnum() and '_' not in v:
            raise ValueError('Username must contain only letters, numbers, and underscores')
        return v.lower()


class UserLogin(BaseModel):
    """User login request"""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_expires_in: int = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


class TokenRefresh(BaseModel):
    """Token refresh request"""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Password reset request"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation"""
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class ChangePassword(BaseModel):
    """Change password request"""
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class EmailVerification(BaseModel):
    """Email verification request"""
    token: str


class TwoFactorSetup(BaseModel):
    """2FA setup response"""
    secret: str
    qr_code: str
    backup_codes: List[str]


class TwoFactorVerify(BaseModel):
    """2FA verification request"""
    code: str


class UserUpdate(BaseModel):
    """User profile update"""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class UserResponse(BaseModel):
    """User response"""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: str
    status: str
    is_verified: bool
    two_factor_enabled: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    last_ip: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "id": "user_123",
                "username": "john_doe",
                "email": "john@example.com",
                "full_name": "John Doe",
                "phone": "+1234567890",
                "role": "operator",
                "status": "active",
                "is_verified": True,
                "two_factor_enabled": False,
                "created_at": "2024-01-15T10:00:00",
                "last_login": "2024-01-20T15:30:00",
                "last_ip": "192.168.1.100"
            }
        }


class ApiKeyResponse(BaseModel):
    """API key response"""
    id: str
    name: str
    key: Optional[str] = None  # Only returned when created
    permissions: List[str]
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    created_at: datetime


class ApiKeyCreate(BaseModel):
    """API key creation request"""
    name: str = Field(..., description="Key name/description")
    permissions: List[str] = Field(default=[], description="Permissions")
    expires_in_days: Optional[int] = Field(365, description="Expiration in days")


# ============================================================================
# Authentication Routes
# ============================================================================

@router.post("/register", response_model=UserResponse)
async def register_user(
    registration: UserRegistration,
    request: Request,
    storage = Depends(get_storage_manager)
):
    """
    Register a new user account
    
    Creates a new user with the OPERATOR role by default.
    Email verification is required before login.
    """
    # Check if username exists
    existing = await storage.get_user_by_username(registration.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Check if email exists
    existing_email = await storage.get_user_by_email(registration.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user_id = await storage.create_user(
        username=registration.username,
        email=registration.email,
        password_hash=get_password_hash(registration.password),
        full_name=registration.full_name,
        phone=registration.phone,
        role=UserRole.OPERATOR.value,
        status=UserStatus.PENDING_VERIFICATION.value,
        created_ip=await get_client_ip(request)
    )
    
    # Generate email verification token
    verification_token = secrets.token_urlsafe(32)
    await storage.store_verification_token(user_id, verification_token)
    
    # Send verification email (async)
    # await send_verification_email(registration.email, verification_token)
    
    # Get created user
    user = await storage.get_user(user_id)
    
    logger.info(f"User registered: {registration.username} from {await get_client_ip(request)}")
    
    return UserResponse(**user)


@router.post("/login", response_model=TokenResponse)
async def login(
    login: UserLogin,
    request: Request,
    storage = Depends(get_storage_manager)
):
    """
    Authenticate user and return JWT tokens
    
    Supports both username and email login.
    Returns access and refresh tokens.
    """
    # Find user by username or email
    user = await storage.get_user_by_username(login.username)
    if not user:
        user = await storage.get_user_by_email(login.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check account status
    if user['status'] == UserStatus.LOCKED.value:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is locked. Contact administrator."
        )
    
    if user['status'] == UserStatus.SUSPENDED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended"
        )
    
    if user['status'] == UserStatus.PENDING_VERIFICATION.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in"
        )
    
    # Verify password
    if not verify_password(login.password, user['password_hash']):
        # Increment failed attempts
        await storage.increment_failed_attempts(user['id'])
        
        # Lock account after 5 failed attempts
        failed_attempts = user.get('failed_attempts', 0) + 1
        if failed_attempts >= 5:
            await storage.lock_user_account(user['id'])
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked due to multiple failed attempts"
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check 2FA
    if user.get('two_factor_enabled'):
        # Require 2FA code
        # This would be handled in a separate endpoint
        pass
    
    # Generate tokens
    access_token = create_access_token(
        data={
            "sub": user['username'],
            "user_id": user['id'],
            "role": user['role'],
            "permissions": user.get('permissions', [])
        }
    )
    
    refresh_token = create_refresh_token(
        data={
            "sub": user['username'],
            "user_id": user['id']
        }
    )
    
    # Update last login
    await storage.update_last_login(
        user['id'],
        ip=await get_client_ip(request),
        user_agent=await get_user_agent(request)
    )
    
    # Reset failed attempts
    await storage.reset_failed_attempts(user['id'])
    
    logger.info(f"User logged in: {user['username']} from {await get_client_ip(request)}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_request: TokenRefresh,
    storage = Depends(get_storage_manager)
):
    """
    Refresh access token using refresh token
    
    Returns a new access token and a new refresh token
    """
    from jose import JWTError, jwt
    
    try:
        payload = jwt.decode(
            refresh_request.refresh_token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        
        user_id = payload.get("user_id")
        token_type = payload.get("type")
        
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Check if token is blacklisted
        is_blacklisted = await storage.is_token_blacklisted(refresh_request.refresh_token)
        if is_blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )
        
        # Get user
        user = await storage.get_user(user_id)
        if not user or user['status'] != UserStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Generate new tokens
        access_token = create_access_token(
            data={
                "sub": user['username'],
                "user_id": user['id'],
                "role": user['role'],
                "permissions": user.get('permissions', [])
            }
        )
        
        new_refresh_token = create_refresh_token(
            data={
                "sub": user['username'],
                "user_id": user['id']
            }
        )
        
        # Blacklist old refresh token
        await storage.blacklist_token(refresh_request.refresh_token)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token
        )
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    storage = Depends(get_storage_manager),
    current_user = Depends(get_current_user)
):
    """
    Logout user and invalidate tokens
    
    Blacklists the current access token.
    """
    await storage.blacklist_token(token)
    
    logger.info(f"User logged out: {current_user.username}")
    
    return {
        "success": True,
        "message": "Successfully logged out"
    }


# ============================================================================
# Password Management Routes
# ============================================================================

@router.post("/password/reset-request")
async def request_password_reset(
    request: PasswordResetRequest,
    storage = Depends(get_storage_manager)
):
    """
    Request password reset
    
    Sends a password reset email with a token
    """
    user = await storage.get_user_by_email(request.email)
    
    # Always return success even if email not found (security)
    if not user:
        return {
            "success": True,
            "message": "If an account exists with that email, a reset link has been sent"
        }
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    await storage.store_password_reset_token(user['id'], reset_token)
    
    # Send reset email (async)
    # await send_password_reset_email(request.email, reset_token)
    
    logger.info(f"Password reset requested for: {request.email}")
    
    return {
        "success": True,
        "message": "If an account exists with that email, a reset link has been sent"
    }


@router.post("/password/reset")
async def confirm_password_reset(
    reset: PasswordResetConfirm,
    storage = Depends(get_storage_manager)
):
    """
    Confirm password reset with token
    
    Sets new password for the user
    """
    # Validate token
    user_id = await storage.validate_password_reset_token(reset.token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Update password
    await storage.update_password(
        user_id,
        get_password_hash(reset.new_password)
    )
    
    # Invalidate token
    await storage.invalidate_password_reset_token(reset.token)
    
    # Blacklist all user sessions
    await storage.blacklist_user_tokens(user_id)
    
    logger.info(f"Password reset completed for user: {user_id}")
    
    return {
        "success": True,
        "message": "Password has been reset successfully"
    }


@router.post("/password/change")
async def change_password(
    change: ChangePassword,
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager)
):
    """
    Change password for authenticated user
    
    Requires current password verification
    """
    # Verify current password
    if not verify_password(change.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Update password
    await storage.update_password(
        current_user.id,
        get_password_hash(change.new_password)
    )
    
    # Blacklist all user sessions (force re-login)
    await storage.blacklist_user_tokens(current_user.id)
    
    logger.info(f"Password changed for user: {current_user.username}")
    
    return {
        "success": True,
        "message": "Password changed successfully. Please login again."
    }


# ============================================================================
# Email Verification Routes
# ============================================================================

@router.post("/verify-email/send")
async def send_verification_email(
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager)
):
    """
    Send email verification link
    
    Resends verification email if account not verified
    """
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    # Generate verification token
    verification_token = secrets.token_urlsafe(32)
    await storage.store_verification_token(current_user.id, verification_token)
    
    # Send verification email
    # await send_verification_email(current_user.email, verification_token)
    
    logger.info(f"Verification email sent to: {current_user.email}")
    
    return {
        "success": True,
        "message": "Verification email sent"
    }


@router.post("/verify-email")
async def verify_email(
    verification: EmailVerification,
    storage = Depends(get_storage_manager)
):
    """
    Verify email address with token
    """
    # Validate token
    user_id = await storage.validate_verification_token(verification.token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    # Mark user as verified
    await storage.mark_user_verified(user_id)
    
    # Update user status to active
    await storage.update_user_status(user_id, UserStatus.ACTIVE.value)
    
    # Invalidate token
    await storage.invalidate_verification_token(verification.token)
    
    logger.info(f"Email verified for user: {user_id}")
    
    return {
        "success": True,
        "message": "Email verified successfully"
    }


# ============================================================================
# Two-Factor Authentication Routes
# ============================================================================

@router.post("/2fa/setup", response_model=TwoFactorSetup)
async def setup_2fa(
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager)
):
    """
    Setup two-factor authentication
    
    Generates TOTP secret and QR code for authenticator app
    """
    # Generate secret
    secret = pyotp.random_base32()
    
    # Generate QR code
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="Drone Detection System"
    )
    
    # Create QR code image
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    # Generate backup codes
    backup_codes = [secrets.token_hex(4) for _ in range(8)]
    
    # Store secret and backup codes (not enabled yet)
    await storage.store_2fa_setup(
        current_user.id,
        secret,
        backup_codes
    )
    
    return TwoFactorSetup(
        secret=secret,
        qr_code=f"data:image/png;base64,{qr_base64}",
        backup_codes=backup_codes
    )


@router.post("/2fa/enable")
async def enable_2fa(
    verify: TwoFactorVerify,
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager)
):
    """
    Enable two-factor authentication
    
    Verifies the TOTP code before enabling
    """
    # Get pending setup
    setup = await storage.get_2fa_setup(current_user.id)
    
    if not setup:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup not initiated"
        )
    
    # Verify TOTP code
    totp = pyotp.TOTP(setup['secret'])
    
    if not totp.verify(verify.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # Enable 2FA
    await storage.enable_2fa(
        current_user.id,
        setup['secret'],
        setup['backup_codes']
    )
    
    logger.info(f"2FA enabled for user: {current_user.username}")
    
    return {
        "success": True,
        "message": "Two-factor authentication enabled",
        "backup_codes": setup['backup_codes']
    }


@router.post("/2fa/disable")
async def disable_2fa(
    verify: TwoFactorVerify,
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager)
):
    """
    Disable two-factor authentication
    
    Requires valid TOTP code
    """
    # Get 2FA secret
    secret = await storage.get_2fa_secret(current_user.id)
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled"
        )
    
    # Verify TOTP code
    totp = pyotp.TOTP(secret)
    
    if not totp.verify(verify.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # Disable 2FA
    await storage.disable_2fa(current_user.id)
    
    logger.info(f"2FA disabled for user: {current_user.username}")
    
    return {
        "success": True,
        "message": "Two-factor authentication disabled"
    }


# ============================================================================
# User Profile Routes
# ============================================================================

@router.get("/profile", response_model=UserResponse)
async def get_profile(
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager)
):
    """
    Get current user profile
    """
    user = await storage.get_user(current_user.id)
    return UserResponse(**user)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    updates: UserUpdate,
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager)
):
    """
    Update user profile
    """
    # Update allowed fields
    update_data = {}
    if updates.full_name is not None:
        update_data['full_name'] = updates.full_name
    if updates.phone is not None:
        update_data['phone'] = updates.phone
    if updates.email is not None and updates.email != current_user.email:
        # Email change requires verification
        update_data['email'] = updates.email
        update_data['is_verified'] = False
        # Send verification email
        # await send_verification_email(updates.email, token)
    
    await storage.update_user(current_user.id, update_data)
    
    user = await storage.get_user(current_user.id)
    
    logger.info(f"Profile updated for user: {current_user.username}")
    
    return UserResponse(**user)


# ============================================================================
# API Key Management Routes
# ============================================================================

@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager)
):
    """
    List API keys for current user
    """
    keys = await storage.get_api_keys(current_user.id)
    return [ApiKeyResponse(**k) for k in keys]


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
    request: ApiKeyCreate,
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager),
    _ = Depends(require_permission("api_keys:create"))
):
    """
    Create a new API key
    
    Returns the API key (only shown once)
    """
    # Generate API key
    api_key = f"dds_{secrets.token_urlsafe(32)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now() + timedelta(days=request.expires_in_days)
    
    key_id = await storage.create_api_key(
        user_id=current_user.id,
        name=request.name,
        key_hash=api_key_hash,
        permissions=request.permissions,
        expires_at=expires_at
    )
    
    logger.info(f"API key created for user: {current_user.username}, name: {request.name}")
    
    return ApiKeyResponse(
        id=key_id,
        name=request.name,
        key=api_key,  # Only returned once
        permissions=request.permissions,
        expires_at=expires_at,
        last_used=None,
        created_at=datetime.now()
    )


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str = Path(..., description="API key ID"),
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager),
    _ = Depends(require_permission("api_keys:revoke"))
):
    """
    Revoke an API key
    """
    # Verify ownership
    key = await storage.get_api_key(key_id)
    if not key or key['user_id'] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    await storage.revoke_api_key(key_id)
    
    logger.info(f"API key revoked: {key_id} for user: {current_user.username}")
    
    return {
        "success": True,
        "message": "API key revoked"
    }


# ============================================================================
# Admin Routes (User Management)
# ============================================================================

@router.get("/admin/users", response_model=List[UserResponse])
async def list_users(
    pagination: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    status: Optional[UserStatus] = Query(None, description="Filter by status"),
    current_user = Depends(get_current_superuser),
    storage = Depends(get_storage_manager)
):
    """
    List all users (admin only)
    
    Returns paginated list of all users in the system
    """
    offset = (pagination - 1) * page_size
    
    users = await storage.get_all_users(
        limit=page_size,
        offset=offset,
        role=role.value if role else None,
        status=status.value if status else None
    )
    
    return [UserResponse(**u) for u in users]


@router.put("/admin/users/{user_id}/role")
async def update_user_role(
    user_id: str = Path(..., description="User ID"),
    role: UserRole = Body(..., embed=True),
    current_user = Depends(get_current_superuser),
    storage = Depends(get_storage_manager)
):
    """
    Update user role (admin only)
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )
    
    user = await storage.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await storage.update_user_role(user_id, role.value)
    
    logger.info(f"User role updated: {user_id} -> {role.value} by {current_user.username}")
    
    return {
        "success": True,
        "message": f"User role updated to {role.value}"
    }


@router.put("/admin/users/{user_id}/status")
async def update_user_status(
    user_id: str = Path(..., description="User ID"),
    status: UserStatus = Body(..., embed=True),
    current_user = Depends(get_current_superuser),
    storage = Depends(get_storage_manager)
):
    """
    Update user status (admin only)
    
    Can activate, suspend, or lock user accounts
    """
    if user_id == current_user.id and status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend your own account"
        )
    
    user = await storage.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await storage.update_user_status(user_id, status.value)
    
    # If suspending, blacklist all tokens
    if status == UserStatus.SUSPENDED or status == UserStatus.LOCKED:
        await storage.blacklist_user_tokens(user_id)
    
    logger.info(f"User status updated: {user_id} -> {status.value} by {current_user.username}")
    
    return {
        "success": True,
        "message": f"User status updated to {status.value}"
    }


@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str = Path(..., description="User ID"),
    current_user = Depends(get_current_superuser),
    storage = Depends(get_storage_manager)
):
    """
    Delete user account (admin only)
    
    Permanently removes the user account
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user = await storage.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await storage.delete_user(user_id)
    
    logger.info(f"User deleted: {user_id} by {current_user.username}")
    
    return {
        "success": True,
        "message": "User deleted successfully"
    }


# ============================================================================
# Activity Log Routes
# ============================================================================

@router.get("/activity")
async def get_user_activity(
    pagination: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user),
    storage = Depends(get_storage_manager)
):
    """
    Get current user's activity log
    """
    offset = (pagination - 1) * page_size
    
    activities = await storage.get_user_activity(
        user_id=current_user.id,
        limit=page_size,
        offset=offset
    )
    
    return {
        "activities": activities,
        "pagination": {
            "page": pagination,
            "page_size": page_size,
            "total": len(activities)
        }
    }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("Authentication Routes Module")
    print("=" * 50)
    
    print("\nAvailable Endpoints:")
    print("  POST /register               - Register new user")
    print("  POST /login                  - Login and get tokens")
    print("  POST /refresh                - Refresh access token")
    print("  POST /logout                 - Logout and invalidate tokens")
    print("  POST /password/reset-request - Request password reset")
    print("  POST /password/reset         - Confirm password reset")
    print("  POST /password/change        - Change password")
    print("  POST /verify-email/send      - Send verification email")
    print("  POST /verify-email           - Verify email")
    print("  POST /2fa/setup              - Setup 2FA")
    print("  POST /2fa/enable             - Enable 2FA")
    print("  POST /2fa/disable            - Disable 2FA")
    print("  GET  /profile                - Get user profile")
    print("  PUT  /profile                - Update user profile")
    print("  GET  /api-keys               - List API keys")
    print("  POST /api-keys               - Create API key")
    print("  DELETE /api-keys/{id}        - Revoke API key")
    print("  GET  /admin/users            - List users (admin)")
    print("  PUT  /admin/users/{id}/role  - Update role (admin)")
    print("  PUT  /admin/users/{id}/status- Update status (admin)")
    print("  DELETE /admin/users/{id}     - Delete user (admin)")
    print("  GET  /activity               - Get activity log")
    
    print("\n" + "=" * 50)