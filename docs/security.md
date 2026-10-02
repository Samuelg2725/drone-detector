# Drone Detector System - Security Considerations

## Overview

This document outlines security considerations, best practices, and implementation guidelines for the Drone Detector system. Security is paramount in drone detection as it involves surveillance, data collection, and potential integration with security systems.

## Security Architecture

### Defense in Depth
┌─────────────────────────────────────────────────────────────────────────────┐
│ Security Layers │
│ │
│ Layer 1: Physical Security │
│ ├── Hardware access controls │
│ ├── Tamper detection │
│ └── Secure facility placement │
│ │
│ Layer 2: Network Security │
│ ├── Firewall rules │
│ ├── VLAN isolation │
│ ├── TLS 1.3 encryption │
│ └── Rate limiting │
│ │
│ Layer 3: Application Security │
│ ├── Authentication & Authorization │
│ ├── Input validation │
│ ├── SQL injection prevention │
│ ├── XSS protection │
│ └── CSRF tokens │
│ │
│ Layer 4: Data Security │
│ ├── Encryption at rest (AES-256) │
│ ├── Encryption in transit (TLS) │
│ ├── Key management │
│ └── Data masking │
│ │
│ Layer 5: Operational Security │
│ ├── Audit logging │
│ ├── Monitoring & alerting │
│ ├── Incident response │
│ └── Regular updates │
└─────────────────────────────────────────────────────────────────────────────┘

text

### Threat Model

| Threat | Impact | Likelihood | Mitigation |
|--------|--------|------------|------------|
| Unauthorized access | High | Medium | Authentication, RBAC, MFA |
| Data breach | High | Low | Encryption, access controls |
| DoS attack | Medium | Medium | Rate limiting, load balancing |
| Spoofing | High | Medium | Signal validation, ML filtering |
| Eavesdropping | Medium | Low | TLS encryption |
| Man-in-the-middle | High | Low | Certificate validation |
| Hardware tampering | High | Low | Tamper detection, secure enclaves |
| Insider threat | Medium | Low | Audit logs, least privilege |

## Authentication & Authorization

### API Authentication

```yaml
# config/security.yaml
authentication:
  # JWT Configuration
  jwt:
    enabled: true
    algorithm: RS256  # Use RSA for production
    access_token_expiry: 3600  # 1 hour
    refresh_token_expiry: 86400  # 24 hours
    issuer: "drone-detector.example.com"
    audience: ["drone-api", "drone-websocket"]
    
  # API Keys
  api_keys:
    enabled: true
    prefix: "dk_live_"
    length: 32
    hash_algorithm: sha256
    
  # OAuth2 / OIDC
  oauth2:
    enabled: false
    providers:
      - google
      - microsoft
      - okta
    allow_existing_users: true
    
  # Multi-factor Authentication
  mfa:
    enabled: true
    methods:
      - totp  # Google Authenticator
      - sms
      - email
    required_for_roles: ["admin", "operator"]
Role-Based Access Control (RBAC)
yaml
# config/rbac.yaml
roles:
  viewer:
    permissions:
      - detections:read
      - map:view
      - alerts:view
    mfa_required: false
    
  operator:
    permissions:
      - detections:read
      - detections:export
      - alerts:acknowledge
      - recordings:play
      - hardware:view
    mfa_required: false
    
  analyst:
    permissions:
      - detections:*  # All detection permissions
      - analytics:*
      - reports:generate
      - ml:view
    mfa_required: true
    
  admin:
    permissions:
      - *  # All permissions
    mfa_required: true
    ip_whitelist:
      - "10.0.0.0/8"
      - "192.168.0.0/16"
      
  auditor:
    permissions:
      - logs:read
      - audit:*
    read_only: true
    mfa_required: true
Authentication Implementation
python
# infrastructure/auth/jwt_auth.py
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

class JWTAuthenticator:
    """JWT-based authentication with RSA signing"""
    
    def __init__(self):
        # Load RSA private key
        with open("config/private_key.pem", "rb") as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
            
        # Load RSA public key
        with open("config/public_key.pem", "rb") as f:
            self.public_key = serialization.load_pem_public_key(
                f.read(),
                backend=default_backend()
            )
            
    def create_token(self, user_id: str, role: str, expiry: int = 3600) -> str:
        """Create JWT token with claims"""
        payload = {
            "sub": user_id,
            "role": role,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=expiry),
            "jti": str(uuid.uuid4()),
            "iss": "drone-detector.example.com"
        }
        
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256"
        )
        return token
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                issuer="drone-detector.example.com"
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")
Data Security
Encryption at Rest
python
# infrastructure/encryption/data_encryption.py
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64

class DataEncryption:
    """Encrypt sensitive data at rest"""
    
    def __init__(self, master_key: bytes):
        # Derive encryption key from master key
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._get_salt(),
            iterations=100000,
        )
        self.key = base64.urlsafe_b64encode(kdf.derive(master_key))
        self.cipher = Fernet(self.key)
        
    def encrypt_sensitive_data(self, data: dict) -> bytes:
        """Encrypt sensitive fields"""
        sensitive_fields = [
            "operator_contact",
            "operator_address",
            "remote_id_key",
            "authentication_data"
        ]
        
        encrypted_data = {}
        for key, value in data.items():
            if key in sensitive_fields:
                encrypted_data[key] = self.cipher.encrypt(
                    json.dumps(value).encode()
                )
            else:
                encrypted_data[key] = value
                
        return encrypted_data
    
    def decrypt_data(self, encrypted_data: bytes) -> dict:
        """Decrypt previously encrypted data"""
        decrypted = self.cipher.decrypt(encrypted_data)
        return json.loads(decrypted)
    
    def encrypt_iq_data(self, iq_samples: np.ndarray) -> bytes:
        """Encrypt raw IQ samples"""
        # Compress and encrypt
        compressed = zlib.compress(iq_samples.tobytes())
        return self.cipher.encrypt(compressed)
Database Encryption
sql
-- PostgreSQL column encryption
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Encrypt sensitive columns
CREATE TABLE operators (
    id UUID PRIMARY KEY,
    operator_id VARCHAR(50) UNIQUE,
    contact_email VARCHAR(100) ENCRYPTED WITH (COLUMN_ENCRYPTION_KEY=cek1),
    contact_phone VARCHAR(20) ENCRYPTED WITH (COLUMN_ENCRYPTION_KEY=cek1),
    address TEXT ENCRYPTED WITH (COLUMN_ENCRYPTION_KEY=cek1),
    created_at TIMESTAMP
);

-- Transparent Data Encryption (TDE)
ALTER SYSTEM SET encrypted = 'on';
ALTER SYSTEM SET encryption_key = '/secure/key/path';

-- Tablespace encryption
CREATE TABLESPACE secure_ts LOCATION '/secure/data' WITH (encryption = on);
Encryption in Transit
nginx
# nginx SSL configuration
ssl_protocols TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:50m;
ssl_session_tickets off;

# HSTS
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

# OCSP stapling
ssl_stapling on;
ssl_stapling_verify on;
ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;
Network Security
Firewall Configuration
bash
# UFW configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (restricted)
sudo ufw allow from 10.0.0.0/8 to any port 22

# Allow API access (restricted)
sudo ufw allow from 192.168.0.0/16 to any port 8888 proto tcp

# Allow WebSocket (restricted)
sudo ufw allow from 192.168.0.0/16 to any port 8889 proto tcp

# Allow monitoring (internal only)
sudo ufw allow from 127.0.0.1 to any port 9090 proto tcp

# Rate limiting
sudo ufw limit ssh
sudo ufw limit 8888/tcp

# Enable logging
sudo ufw logging on

sudo ufw enable
Network Isolation
yaml
# docker-compose.yml network isolation
networks:
  frontend:
    driver: bridge
    ipam:
      config:
        - subnet: 10.0.1.0/24
    internal: false
    
  backend:
    driver: bridge
    ipam:
      config:
        - subnet: 10.0.2.0/24
    internal: true  # No external access
    
  database:
    driver: bridge
    ipam:
      config:
        - subnet: 10.0.3.0/24
    internal: true

services:
  nginx:
    networks:
      - frontend
      - backend
      
  api:
    networks:
      - backend
      - database
      
  postgres:
    networks:
      - database
      
  redis:
    networks:
      - database
VPN Configuration
bash
# WireGuard VPN for secure remote access
# /etc/wireguard/wg0.conf
[Interface]
Address = 10.0.4.1/24
PrivateKey = <server_private_key>
ListenPort = 51820

[Peer]
PublicKey = <client_public_key>
AllowedIPs = 10.0.4.2/32

# Client configuration
[Interface]
Address = 10.0.4.2/24
PrivateKey = <client_private_key>
DNS = 8.8.8.8

[Peer]
PublicKey = <server_public_key>
Endpoint = vpn.drone-detector.com:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
API Security
Input Validation
python
# api/validation.py
from pydantic import BaseModel, Field, validator
from typing import Optional

class DetectionQuery(BaseModel):
    """Validation for detection query parameters"""
    
    start_time: datetime
    end_time: datetime
    frequency_min: Optional[float] = Field(None, ge=70e6, le=6e9)
    frequency_max: Optional[float] = Field(None, ge=70e6, le=6e9)
    drone_type: Optional[str] = Field(None, min_length=1, max_length=50)
    confidence_min: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    @validator('end_time')
    def validate_time_range(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be after start_time')
        return v
    
    @validator('frequency_max')
    def validate_frequency_range(cls, v, values):
        if v and 'frequency_min' in values:
            if v <= values['frequency_min']:
                raise ValueError('frequency_max must be > frequency_min')
        return v

class HardwareConfig(BaseModel):
    """Validation for hardware configuration"""
    
    sample_rate: int = Field(..., ge=1e5, le=56e6)
    center_frequency: float = Field(..., ge=70e6, le=6e9)
    gain: int = Field(..., ge=0, le=40)
    
    @validator('sample_rate')
    def validate_sample_rate(cls, v):
        # Validate against hardware capabilities
        if v > 20e6:
            raise ValueError('Sample rate exceeds HackRF limit (20MHz)')
        return v
Rate Limiting
python
# api/middleware/rate_limit.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Apply to endpoints
@app.get("/api/v1/detections")
@limiter.limit("100/minute")
async def get_detections(request: Request):
    return await detection_service.list()

# Per-user limits
@limiter.limit(lambda request: f"{get_user_rate_limit(request)}/minute")

# Burst limits
@limiter.limit("10/second", burst=True)

# Custom limits for admin
class RateLimitConfig:
    default = "100/minute"
    authenticated = "1000/minute"
    admin = "5000/minute"
    export = "10/hour"
    auth = "5/minute"
Request Validation
python
# api/middleware/security.py
from fastapi import Request, HTTPException

class SecurityMiddleware:
    """Additional security checks"""
    
    async def validate_request(self, request: Request):
        # Check origin
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            raise HTTPException(403, "Origin not allowed")
            
        # Check content type
        content_type = request.headers.get("content-type")
        if request.method in ["POST", "PUT", "PATCH"]:
            if content_type != "application/json":
                raise HTTPException(415, "Content-Type must be application/json")
                
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_SIZE:
            raise HTTPException(413, "Request too large")
            
        # Validate query parameters
        # No SQL injection patterns
        for key, value in request.query_params.items():
            if self._contains_sql_injection(value):
                raise HTTPException(400, "Invalid query parameter")
Hardware Security
Secure Boot & Trusted Platform Module (TPM)
bash
# Enable Secure Boot in BIOS
# Verify Secure Boot status
bootctl status

# Setup TPM for key storage
sudo apt install tpm2-tools

# Initialize TPM
sudo tpm2_startup
sudo tpm2_clear

# Create RSA key in TPM
sudo tpm2_createprimary -C o -G rsa -c primary.ctx
sudo tpm2_create -C primary.ctx -G rsa -u key.pub -r key.priv

# Store secrets in TPM
echo "database_password" | sudo tpm2_encrypt -c key.ctx -o encrypted.key

# Seal data to PCR state
sudo tpm2_createpolicy --policy-pcr -l sha256:0,1,2,3 -L policy.dat
sudo tpm2_create -C primary.ctx -L policy.dat -u key.pub -r key.priv
Anti-Tamper Measures
python
# hardware/anti_tamper.py
class AntiTamperMonitor:
    """Monitor for hardware tampering"""
    
    def __init__(self):
        self.tamper_pins = [4, 17, 27]  # GPIO pins
        self.enclosure_switch = 22
        self.temperature_sensor = "tmp102"
        
    def setup(self):
        """Initialize tamper detection"""
        for pin in self.tamper_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
        GPIO.setup(self.enclosure_switch, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Register interrupt handlers
        GPIO.add_event_detect(self.enclosure_switch, GPIO.FALLING,
                             callback=self._on_tamper_detected)
                             
    def _on_tamper_detected(self, channel):
        """Handle tamper event"""
        # Log event
        logging.critical(f"Tamper detected on pin {channel}")
        
        # Clear sensitive data
        self._clear_secrets()
        
        # Send alert
        self._send_alert(tamper_type="enclosure_opened")
        
        # Disable hardware
        self._disable_hardware()
        
    def _clear_secrets(self):
        """Clear sensitive data from memory"""
        # Overwrite encryption keys
        # Clear authentication tokens
        # Reset secure storage
        pass
Physical Security Checklist
yaml
physical_security:
  server_room:
    - Access controlled with biometric/MFA
    - 24/7 CCTV surveillance
    - Environmental monitoring (temp, humidity, water)
    - Fire suppression system
    - UPS backup power
    
  hardware_devices:
    - Enclosure tamper switches
    - Anti-tamper screws
    - Security seals
    - GPS tracking (for mobile deployments)
    - Remote wipe capability
    
  network_hardware:
    - Locked network cabinets
    - Port security (MAC filtering)
    - Disable unused ports
    - Monitor for rogue devices
    
  media_handling:
    - Secure disposal of failed drives
    - Encryption of backup media
    - Chain of custody tracking
    - Regular inventory audits
Application Security
Secure Coding Guidelines
python
# Security best practices examples

# 1. Avoid SQL injection
# BAD:
query = f"SELECT * FROM users WHERE username = '{username}'"

# GOOD:
query = "SELECT * FROM users WHERE username = %s"
cursor.execute(query, (username,))

# 2. Avoid command injection
# BAD:
os.system(f"ping {ip_address}")

# GOOD:
subprocess.run(["ping", ip_address], shell=False)

# 3. Secure file operations
# BAD:
with open(user_input, 'r') as f:
    data = f.read()

# GOOD:
safe_path = os.path.join(BASE_DIR, os.path.basename(user_input))
with open(safe_path, 'r') as f:
    data = f.read()

# 4. Logging without sensitive data
logging.info(f"User {user_id} logged in")  # OK
logging.info(f"Password {password}")  # NOT OK - never log passwords

# 5. Secure temporary files
import tempfile
with tempfile.NamedTemporaryFile(delete=True) as tmp:
    tmp.write(data)
    # Automatically deleted

# 6. Use secrets module for tokens
import secrets
token = secrets.token_urlsafe(32)

# 7. Validate redirect URLs
from urllib.parse import urlparse
def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc
Dependency Scanning
bash
# Regular dependency vulnerability scanning

# Using safety
pip install safety
safety check -r requirements.txt

# Using bandit (static analysis)
bandit -r app/ -f html -o bandit_report.html

# Using OWASP dependency-check
docker run --rm \
  -v $(pwd):/src \
  owasp/dependency-check \
  --scan /src \
  --format HTML \
  --out /src/reports

# Using Snyk
snyk test
snyk monitor

# Using pip-audit
pip-audit --requirement requirements.txt
Secret Management
python
# infrastructure/security/secrets.py
from hashicorp import vault

class SecretManager:
    """Centralized secret management with HashiCorp Vault"""
    
    def __init__(self):
        self.vault_client = vault.Client(
            url=os.getenv("VAULT_ADDR", "https://vault.example.com"),
            token=os.getenv("VAULT_TOKEN")
        )
        
    def get_database_password(self) -> str:
        """Retrieve database password from Vault"""
        secret = self.vault_client.secrets.kv.v2.read_secret(
            mount_point="database",
            path="drone-detector"
        )
        return secret["data"]["data"]["password"]
        
    def rotate_secrets(self):
        """Rotate secrets periodically"""
        # Generate new passwords
        new_db_password = secrets.token_urlsafe(32)
        new_api_key = secrets.token_urlsafe(48)
        
        # Update in Vault
        self.vault_client.secrets.kv.v2.create_or_update_secret(
            mount_point="database",
            path="drone-detector",
            secret={"password": new_db_password}
        )
        
        # Update applications
        self._restart_services()
        
    def audit_secret_access(self):
        """Audit all secret access"""
        response = self.vault_client.secrets.kv.v2.read_secret_metadata(
            mount_point="database",
            path="drone-detector"
        )
        return response["data"]["version"]
Logging & Monitoring
Audit Logging
python
# infrastructure/logging/audit.py
import structlog

class AuditLogger:
    """Comprehensive audit logging"""
    
    def __init__(self):
        self.logger = structlog.get_logger("audit")
        
    def log_login(self, user_id: str, success: bool, ip: str):
        """Log authentication attempts"""
        self.logger.info(
            "authentication_attempt",
            user_id=user_id,
            success=success,
            ip_address=ip,
            timestamp=datetime.utcnow().isoformat()
        )
        
    def log_data_access(self, user_id: str, resource: str, action: str):
        """Log data access"""
        self.logger.info(
            "data_access",
            user_id=user_id,
            resource=resource,
            action=action,
            timestamp=datetime.utcnow().isoformat()
        )
        
    def log_config_change(self, user_id: str, config_key: str, old_value: str, new_value: str):
        """Log configuration changes"""
        self.logger.info(
            "config_change",
            user_id=user_id,
            config_key=config_key,
            old_value=old_value,
            new_value=new_value,
            timestamp=datetime.utcnow().isoformat()
        )
        
    def log_admin_action(self, user_id: str, action: str, details: dict):
        """Log administrative actions"""
        self.logger.info(
            "admin_action",
            user_id=user_id,
            action=action,
            details=details,
            timestamp=datetime.utcnow().isoformat()
        )
        
    def log_security_event(self, event_type: str, severity: str, details: dict):
        """Log security events"""
        self.logger.warning(
            event_type,
            severity=severity,
            details=details,
            timestamp=datetime.utcnow().isoformat()
        )
Security Monitoring
yaml
# prometheus/alerts-security.yml
groups:
  - name: security_alerts
    rules:
      - alert: MultipleAuthFailures
        expr: rate(login_failures_total[5m]) > 5
        for: 1m
        annotations:
          severity: critical
          summary: "Multiple authentication failures detected"
          
      - alert: UnusualDataExport
        expr: rate(data_export_total[1h]) > 100
        for: 5m
        annotations:
          severity: high
          summary: "Unusual data export activity"
          
      - alert: APIKeyLeak
        expr: api_key_usage_total{valid="false"} > 0
        for: 1m
        annotations:
          severity: critical
          summary: "Invalid API key usage detected"
          
      - alert: RateLimitExceeded
        expr: rate_limit_violations_total[5m] > 10
        for: 2m
        annotations:
          severity: medium
          summary: "Rate limit exceeded repeatedly"
Incident Response
Incident Response Plan
yaml
incident_response:
  severity_levels:
    critical:
      - Data breach
      - System compromise
      - Unauthorized physical access
    high:
      - Denial of service
      - Authentication bypass
      - Data corruption
    medium:
      - Failed security controls
      - Suspicious activity
      - Policy violation
    low:
      - Attempted scans
      - Minor misconfigurations
      - Informational events
    
  response_teams:
    security_team:
      roles:
        - Incident Commander
        - Technical Lead
        - Communications Lead
        - Forensics Lead
      contact:
        oncall: +1-555-SEC-ONCALL
        pager: security@drone-detector.com
        
    engineering_team:
      roles:
        - Platform Engineer
        - Database Engineer
        - Network Engineer
        
    legal_team:
      roles:
        - Legal Counsel
        - Compliance Officer
        
  response_steps:
    identification:
      - Detect potential incident
      - Classification and severity
      - Initial notification
    
    containment:
      - Isolate affected systems
      - Block access if needed
      - Preserve evidence
    
    eradication:
      - Remove threat
      - Patch vulnerabilities
      - Clean systems
    
    recovery:
      - Restore from backups
      - Verify system integrity
      - Resume operations
    
    lessons_learned:
      - Root cause analysis
      - Update controls
      - Document improvements
Incident Response Scripts
python
# scripts/incident_response.py
class IncidentResponse:
    """Automated incident response actions"""
    
    async def handle_data_breach(self, compromised_data: list):
        """Respond to potential data breach"""
        
        # 1. Log incident
        audit_logger.log_security_event(
            "data_breach",
            "critical",
            {"compromised_data": compromised_data}
        )
        
        # 2. Revoke all tokens
        await self.revoke_all_tokens()
        
        # 3. Rotate all secrets
        await secret_manager.rotate_secrets()
        
        # 4. Isolate affected systems
        await self.isolate_systems(compromised_data)
        
        # 5. Notify security team
        await self.send_alert(
            "data_breach_detected",
            {"severity": "critical"}
        )
        
        # 6. Start forensics capture
        await self.capture_forensics()
        
        # 7. Legal notification
        if "pii" in compromised_data:
            await self.notify_legal("pii_breach")
            
    async def block_suspicious_ip(self, ip_address: str):
        """Block suspicious IP address"""
        
        # Add to firewall block list
        subprocess.run([
            "ufw", "deny", "from", ip_address
        ])
        
        # Update fail2ban configuration
        jail_config = f"""
[drone-detector]
enabled = true
filter = drone-detector
logpath = /var/log/drone-detector/auth.log
maxretry = 3
bantime = 3600
findtime = 600
"""
        with open("/etc/fail2ban/jail.d/drone-detector.conf", "w") as f:
            f.write(jail_config)
            
        # Restart fail2ban
        subprocess.run(["systemctl", "restart", "fail2ban"])
Compliance
GDPR Compliance
python
# infrastructure/compliance/gdpr.py
class GDPRCompliance:
    """GDPR compliance implementation"""
    
    def __init__(self):
        self.data_retention_days = 30  # GDPR requirement
        
    async def delete_user_data(self, user_id: str):
        """Right to be forgotten - delete all user data"""
        
        # Delete from all tables
        await db.execute(
            "DELETE FROM users WHERE id = %s", (user_id,)
        )
        await db.execute(
            "DELETE FROM detections WHERE user_id = %s", (user_id,)
        )
        await db.execute(
            "DELETE FROM alerts WHERE user_id = %s", (user_id,)
        )
        await db.execute(
            "DELETE FROM audit_logs WHERE user_id = %s", (user_id,)
        )
        
        # Anonymize remaining data
        await db.execute(
            "UPDATE analytics SET user_id = NULL WHERE user_id = %s",
            (user_id,)
        )
        
        # Log deletion
        audit_logger.log_admin_action(
            "GDPR deletion",
            user_id,
            {"type": "right_to_be_forgotten"}
        )
        
    async def export_user_data(self, user_id: str) -> dict:
        """Right to data portability"""
        
        # Collect all user data
        user_data = {
            "profile": await self.get_user_profile(user_id),
            "detections": await self.get_user_detections(user_id),
            "alerts": await self.get_user_alerts(user_id),
            "config": await self.get_user_config(user_id),
            "metadata": {
                "export_date": datetime.utcnow().isoformat(),
                "format": "json",
                "version": "1.0"
            }
        }
        
        # Return in portable format
        return user_data
Compliance Checklist
yaml
compliance_checklist:
  data_handling:
    - Data minimization practices
    - Purpose limitation
    - Storage limitation
    - Accuracy and integrity
    - Confidentiality
    
  user_rights:
    - Right to access
    - Right to rectification
    - Right to erasure
    - Right to restrict processing
    - Right to data portability
    - Right to object
    
  security_measures:
    - Encryption at rest
    - Encryption in transit
    - Access controls
    - Audit logging
    - Breach notification procedures
    
  documentation:
    - Data processing records
    - Privacy impact assessments
    - Security policies
    - Incident response plans
    - Vendor agreements
Security Testing
Penetration Testing
bash
# Regular penetration testing commands

# API security scanning
docker run --rm -v $(pwd):/zap/wrk \
  owasp/zap2docker-stable zap-api-scan.py \
  -t http://localhost:8888/openapi.json \
  -f openapi \
  -r report.html

# Network scanning
nmap -sV -sC -p- localhost
nmap --script vuln localhost

# SSL/TLS scanning
docker run --rm -v $(pwd):/opt \
  jumanjihouse/sslscan localhost:443 > ssl_report.txt

# Vulnerability scanning
docker run --rm \
  aquasec/trivy image drone-detector:latest

# Dependency scanning
safety check -r requirements.txt
Continuous Security
yaml
# .github/workflows/security.yml
name: Security Scanning

on:
  push:
    branches: [main, develop]
  pull_request:
  schedule:
    - cron: '0 2 * * 0'  # Weekly

jobs:
  security:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: SAST Scan
        uses: github/codeql-action/init@v1
        with:
          languages: python
          
      - name: Dependency Scan
        run: |
          pip install safety
          safety check -r requirements.txt --full-report
          
      - name: Secret Scan
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          
      - name: Container Scan
        run: |
          docker build -t drone-detector .
          trivy image --severity HIGH,CRITICAL drone-detector
          
      - name: DAST Scan
        run: |
          docker-compose up -d
          sleep 30
          zap-api-scan.py -t http://localhost:8888/openapi.json
Security Updates
Automated Updates
yaml
# docker-compose.yml with Watchtower for automatic updates
services:
  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_POLL_INTERVAL=86400  # Daily
      - WATCHTOWER_MONITOR_ONLY=false
      - WATCHTOWER_INCLUDE_RESTART=true
      - WATCHTOWER_ROLLING_RESTART=true
Update Verification
python
# scripts/verify_updates.py
def verify_security_update():
    """Verify security updates before deployment"""
    
    # 1. Run tests
    subprocess.run(["pytest", "tests/security/"])
    
    # 2. Check for regressions
    subprocess.run(["pytest", "tests/regression/"])
    
    # 3. Verify signatures
    subprocess.run(["cosign", "verify", "image:tag"])
    
    # 4. Check SBOM
    subprocess.run(["syft", "image:tag", "-o", "spdx"])
    
    # 5. Run vulnerability scan
    subprocess.run(["trivy", "image", "--severity", "CRITICAL", "image:tag"])
    
    print("Security verification passed")
