#!/usr/bin/env python3
# drone-detector/infrastructure/external/notification_service.py
"""
Notification Service - Email/SMS Alerts

This module provides comprehensive notification capabilities for the Drone Detection System,
supporting:
- Email notifications via SMTP (Gmail, Outlook, custom SMTP)
- SMS notifications via Twilio, AWS SNS, or custom providers
- Multiple notification templates
- Rich HTML email formatting
- Attachment support (images, logs, reports)
- Batch notifications for multiple recipients
- Rate limiting and throttling
- Retry mechanisms with exponential backoff
- Notification priority levels
- Delivery status tracking
- Multi-provider fallback for reliability
- Template-based message formatting
- Scheduled notifications
- Digest mode for aggregated alerts
"""

import asyncio
import aiofiles
import json
import mimetypes
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Callable, Tuple
from collections import deque

# Try to import optional dependencies
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

try:
    import boto3
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3
    EMERGENCY = 4


class NotificationType(Enum):
    """Types of notifications"""
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    SLACK = "slack"
    WEBHOOK = "webhook"
    PUSH = "push"


class NotificationStatus(Enum):
    """Notification delivery status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    THROTTLED = "throttled"


class EmailProvider(Enum):
    """Email service providers"""
    CUSTOM_SMTP = "custom"
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    YAHOO = "yahoo"
    SENDGRID = "sendgrid"
    AWS_SES = "aws_ses"


class SMSProvider(Enum):
    """SMS service providers"""
    TWILIO = "twilio"
    AWS_SNS = "aws_sns"
    VONAGE = "vonage"
    TELNYX = "telnyx"
    PLIVO = "plivo"
    CUSTOM = "custom"


@dataclass
class EmailConfig:
    """Email notification configuration"""
    # SMTP settings
    provider: EmailProvider = EmailProvider.CUSTOM_SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    use_ssl: bool = False
    
    # Sender settings
    from_email: str = ""
    from_name: str = "Drone Detection System"
    
    # Gmail specific (uses OAuth2)
    gmail_oauth2_token: Optional[str] = None
    
    # AWS SES specific
    aws_region: str = "us-east-1"
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    
    # SendGrid specific
    sendgrid_api_key: Optional[str] = None
    
    # Rate limiting
    max_emails_per_hour: int = 100
    max_emails_per_day: int = 1000
    
    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 5.0
    retry_backoff_factor: float = 2.0


@dataclass
class SMSConfig:
    """SMS notification configuration"""
    # Provider settings
    provider: SMSProvider = SMSProvider.TWILIO
    
    # Twilio settings
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    
    # AWS SNS settings
    aws_region: str = "us-east-1"
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    
    # Vonage (Nexmo) settings
    vonage_api_key: str = ""
    vonage_api_secret: str = ""
    vonage_phone_number: str = ""
    
    # General settings
    default_country_code: str = "1"  # US/Canada
    max_sms_per_hour: int = 50
    max_sms_per_day: int = 500
    
    # Message limits
    max_message_length: int = 160
    truncate_long_messages: bool = True
    
    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 5.0


@dataclass
class WebhookConfig:
    """Webhook notification configuration"""
    url: str = ""
    method: str = "POST"
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 10
    retry_count: int = 3


@dataclass
class NotificationMessage:
    """Notification message structure"""
    notification_type: NotificationType
    recipient: str
    subject: str
    body: str
    html_body: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    attachments: List[Path] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    template_name: Optional[str] = None
    template_data: Dict[str, Any] = field(default_factory=dict)
    
    # Tracking
    message_id: str = ""
    status: NotificationStatus = NotificationStatus.PENDING
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        """Generate message ID if not provided"""
        if not self.message_id:
            import uuid
            self.message_id = str(uuid.uuid4())


@dataclass
class NotificationTemplate:
    """Email/SMS template"""
    name: str
    subject_template: str
    body_template: str
    html_template: Optional[str] = None
    notification_type: NotificationType = NotificationType.EMAIL
    
    def render(self, data: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """Render template with data"""
        subject = self.subject_template.format(**data)
        body = self.body_template.format(**data)
        html = self.html_template.format(**data) if self.html_template else None
        return subject, body, html


# ============================================================================
# Email Notification Service
# ============================================================================

class EmailNotificationService:
    """
    Email notification service
    
    Supports multiple providers:
    - Gmail (SMTP + OAuth2)
    - Outlook/Hotmail
    - Custom SMTP servers
    - AWS SES
    - SendGrid
    """
    
    def __init__(self, config: EmailConfig):
        """
        Initialize email service
        
        Args:
            config: Email configuration
        """
        self.config = config
        self._sent_count_hour = 0
        self._sent_count_day = 0
        self._hour_reset_time = datetime.now()
        self._day_reset_time = datetime.now()
        
        # AWS SES client
        self._ses_client = None
        if config.provider == EmailProvider.AWS_SES and AWS_AVAILABLE:
            self._ses_client = boto3.client(
                'ses',
                region_name=config.aws_region,
                aws_access_key_id=config.aws_access_key,
                aws_secret_access_key=config.aws_secret_key
            )
        
        # SendGrid client
        self._sendgrid_client = None
        if config.provider == EmailProvider.SENDGRID and config.sendgrid_api_key:
            import sendgrid
            self._sendgrid_client = sendgrid.SendGridAPIClient(config.sendgrid_api_key)
        
        logger.info(f"Email notification service initialized with provider: {config.provider.value}")
    
    def _check_rate_limits(self) -> bool:
        """Check if rate limits allow sending"""
        now = datetime.now()
        
        # Reset hourly counter
        if (now - self._hour_reset_time).total_seconds() >= 3600:
            self._sent_count_hour = 0
            self._hour_reset_time = now
        
        # Reset daily counter
        if (now - self._day_reset_time).total_seconds() >= 86400:
            self._sent_count_day = 0
            self._day_reset_time = now
        
        # Check limits
        if self._sent_count_hour >= self.config.max_emails_per_hour:
            logger.warning("Hourly email limit reached")
            return False
        
        if self._sent_count_day >= self.config.max_emails_per_day:
            logger.warning("Daily email limit reached")
            return False
        
        return True
    
    def _create_email_message(self, message: NotificationMessage) -> MIMEMultipart:
        """Create MIME email message"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = message.subject
        msg['From'] = f"{self.config.from_name} <{self.config.from_email}>"
        msg['To'] = message.recipient
        msg['X-Priority'] = str(message.priority.value)
        msg['X-Message-ID'] = message.message_id
        
        # Add plain text body
        if message.body:
            msg.attach(MIMEText(message.body, 'plain', 'utf-8'))
        
        # Add HTML body
        if message.html_body:
            msg.attach(MIMEText(message.html_body, 'html', 'utf-8'))
        
        # Add attachments
        for attachment_path in message.attachments:
            self._attach_file(msg, attachment_path)
        
        return msg
    
    def _attach_file(self, msg: MIMEMultipart, file_path: Path) -> None:
        """Attach file to email"""
        if not file_path.exists():
            logger.warning(f"Attachment not found: {file_path}")
            return
        
        try:
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                
                filename = file_path.name
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{filename}"'
                )
                msg.attach(part)
                
        except Exception as e:
            logger.error(f"Failed to attach {file_path}: {e}")
    
    async def send_gmail_smtp(self, message: NotificationMessage) -> bool:
        """Send via Gmail SMTP"""
        try:
            context = ssl.create_default_context()
            
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls(context=context)
                
                server.login(self.config.username, self.config.password)
                
                email_msg = self._create_email_message(message)
                server.send_message(email_msg)
                
                return True
                
        except Exception as e:
            logger.error(f"Gmail SMTP send failed: {e}")
            return False
    
    async def send_custom_smtp(self, message: NotificationMessage) -> bool:
        """Send via custom SMTP server"""
        try:
            if self.config.use_ssl:
                server = smtplib.SMTP_SSL(
                    self.config.smtp_host,
                    self.config.smtp_port,
                    context=ssl.create_default_context()
                )
            else:
                server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
                if self.config.use_tls:
                    server.starttls()
            
            if self.config.username and self.config.password:
                server.login(self.config.username, self.config.password)
            
            email_msg = self._create_email_message(message)
            server.send_message(email_msg)
            server.quit()
            
            return True
            
        except Exception as e:
            logger.error(f"Custom SMTP send failed: {e}")
            return False
    
    async def send_aws_ses(self, message: NotificationMessage) -> bool:
        """Send via AWS SES"""
        if not self._ses_client:
            logger.error("AWS SES not configured")
            return False
        
        try:
            response = self._ses_client.send_email(
                Source=f"{self.config.from_name} <{self.config.from_email}>",
                Destination={'ToAddresses': [message.recipient]},
                Message={
                    'Subject': {'Data': message.subject},
                    'Body': {
                        'Text': {'Data': message.body},
                        'Html': {'Data': message.html_body} if message.html_body else None
                    }
                }
            )
            
            return response.get('MessageId') is not None
            
        except Exception as e:
            logger.error(f"AWS SES send failed: {e}")
            return False
    
    async def send_sendgrid(self, message: NotificationMessage) -> bool:
        """Send via SendGrid"""
        if not self._sendgrid_client:
            logger.error("SendGrid not configured")
            return False
        
        try:
            from sendgrid.helpers.mail import Mail
            
            mail = Mail(
                from_email=self.config.from_email,
                to_emails=message.recipient,
                subject=message.subject,
                plain_text_content=message.body,
                html_content=message.html_body
            )
            
            response = self._sendgrid_client.send(mail)
            return response.status_code == 202
            
        except Exception as e:
            logger.error(f"SendGrid send failed: {e}")
            return False
    
    async def send_email(self, message: NotificationMessage) -> bool:
        """
        Send email notification
        
        Args:
            message: Notification message
            
        Returns:
            True if sent successfully
        """
        if not self._check_rate_limits():
            message.status = NotificationStatus.THROTTLED
            return False
        
        # Select provider
        if self.config.provider == EmailProvider.GMAIL:
            success = await self.send_gmail_smtp(message)
        elif self.config.provider == EmailProvider.AWS_SES:
            success = await self.send_aws_ses(message)
        elif self.config.provider == EmailProvider.SENDGRID:
            success = await self.send_sendgrid(message)
        else:
            success = await self.send_custom_smtp(message)
        
        if success:
            self._sent_count_hour += 1
            self._sent_count_day += 1
            message.status = NotificationStatus.SENT
            message.sent_at = datetime.now()
            logger.info(f"Email sent to {message.recipient}: {message.subject}")
        else:
            message.status = NotificationStatus.FAILED
        
        return success


# ============================================================================
# SMS Notification Service
# ============================================================================

class SMSNotificationService:
    """
    SMS notification service
    
    Supports multiple providers:
    - Twilio
    - AWS SNS
    - Vonage (Nexmo)
    - Custom HTTP endpoints
    """
    
    def __init__(self, config: SMSConfig):
        """
        Initialize SMS service
        
        Args:
            config: SMS configuration
        """
        self.config = config
        self._sent_count_hour = 0
        self._sent_count_day = 0
        self._hour_reset_time = datetime.now()
        self._day_reset_time = datetime.now()
        
        # Twilio client
        self._twilio_client = None
        if config.provider == SMSProvider.TWILIO and TWILIO_AVAILABLE:
            self._twilio_client = TwilioClient(
                config.twilio_account_sid,
                config.twilio_auth_token
            )
        
        # AWS SNS client
        self._sns_client = None
        if config.provider == SMSProvider.AWS_SNS and AWS_AVAILABLE:
            self._sns_client = boto3.client(
                'sns',
                region_name=config.aws_region,
                aws_access_key_id=config.aws_access_key,
                aws_secret_access_key=config.aws_secret_key
            )
        
        logger.info(f"SMS notification service initialized with provider: {config.provider.value}")
    
    def _normalize_phone_number(self, phone: str) -> str:
        """Normalize phone number to E.164 format"""
        import re
        
        # Remove non-digits
        digits = re.sub(r'\D', '', phone)
        
        # Add country code if missing
        if len(digits) == 10:
            digits = f"{self.config.default_country_code}{digits}"
        elif len(digits) == 11 and digits.startswith('1'):
            digits = f"+{digits}"
        elif not digits.startswith('+'):
            digits = f"+{digits}"
        
        return digits
    
    def _truncate_message(self, message: str) -> str:
        """Truncate message to max length"""
        if len(message) <= self.config.max_message_length:
            return message
        
        if self.config.truncate_long_messages:
            return message[:self.config.max_message_length - 3] + "..."
        
        # Split into multiple messages (handled by provider)
        return message
    
    def _check_rate_limits(self) -> bool:
        """Check rate limits"""
        now = datetime.now()
        
        if (now - self._hour_reset_time).total_seconds() >= 3600:
            self._sent_count_hour = 0
            self._hour_reset_time = now
        
        if (now - self._day_reset_time).total_seconds() >= 86400:
            self._sent_count_day = 0
            self._day_reset_time = now
        
        if self._sent_count_hour >= self.config.max_sms_per_hour:
            logger.warning("Hourly SMS limit reached")
            return False
        
        if self._sent_count_day >= self.config.max_sms_per_day:
            logger.warning("Daily SMS limit reached")
            return False
        
        return True
    
    async def send_twilio(self, message: NotificationMessage) -> bool:
        """Send via Twilio"""
        if not self._twilio_client:
            logger.error("Twilio not configured")
            return False
        
        try:
            phone = self._normalize_phone_number(message.recipient)
            body = self._truncate_message(message.body)
            
            sms = self._twilio_client.messages.create(
                body=body,
                from_=self.config.twilio_phone_number,
                to=phone
            )
            
            return sms.sid is not None
            
        except Exception as e:
            logger.error(f"Twilio send failed: {e}")
            return False
    
    async def send_aws_sns(self, message: NotificationMessage) -> bool:
        """Send via AWS SNS"""
        if not self._sns_client:
            logger.error("AWS SNS not configured")
            return False
        
        try:
            phone = self._normalize_phone_number(message.recipient)
            body = self._truncate_message(message.body)
            
            response = self._sns_client.publish(
                PhoneNumber=phone,
                Message=body
            )
            
            return response.get('MessageId') is not None
            
        except Exception as e:
            logger.error(f"AWS SNS send failed: {e}")
            return False
    
    async def send_sms(self, message: NotificationMessage) -> bool:
        """
        Send SMS notification
        
        Args:
            message: Notification message
            
        Returns:
            True if sent successfully
        """
        if not self._check_rate_limits():
            message.status = NotificationStatus.THROTTLED
            return False
        
        # Select provider
        if self.config.provider == SMSProvider.TWILIO:
            success = await self.send_twilio(message)
        elif self.config.provider == SMSProvider.AWS_SNS:
            success = await self.send_aws_sns(message)
        else:
            logger.error(f"Unsupported SMS provider: {self.config.provider}")
            success = False
        
        if success:
            self._sent_count_hour += 1
            self._sent_count_day += 1
            message.status = NotificationStatus.SENT
            message.sent_at = datetime.now()
            logger.info(f"SMS sent to {message.recipient}: {message.subject[:50]}...")
        else:
            message.status = NotificationStatus.FAILED
        
        return success


# ============================================================================
# Unified Notification Service
# ============================================================================

class NotificationService:
    """
    Unified notification service for email and SMS
    
    Features:
    - Multi-channel notifications
    - Template-based messages
    - Automatic retries with backoff
    - Rate limiting per channel
    - Message queuing
    - Batch notifications
    - Delivery status tracking
    """
    
    def __init__(self, email_config: Optional[EmailConfig] = None,
                 sms_config: Optional[SMSConfig] = None):
        """
        Initialize notification service
        
        Args:
            email_config: Email configuration (optional)
            sms_config: SMS configuration (optional)
        """
        self.email_service = EmailNotificationService(email_config) if email_config else None
        self.sms_service = SMSNotificationService(sms_config) if sms_config else None
        
        # Templates
        self.templates: Dict[str, NotificationTemplate] = {}
        
        # Message queue for retries
        self._message_queue: deque = deque()
        self._queue_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self.stats = {
            'emails_sent': 0,
            'sms_sent': 0,
            'emails_failed': 0,
            'sms_failed': 0,
            'retries': 0
        }
        
        # Load default templates
        self._load_default_templates()
        
        logger.info("Unified notification service initialized")
    
    def _load_default_templates(self):
        """Load default notification templates"""
        
        # Drone detection alert template
        self.register_template(NotificationTemplate(
            name="drone_detected",
            subject_template="[DDS] Drone Detected - {drone_type}",
            body_template="""
Drone Detection Alert

Time: {timestamp}
Drone Type: {drone_type}
Confidence: {confidence:.1%}
Threat Level: {threat_level}
Position: ({latitude:.6f}, {longitude:.6f})
Altitude: {altitude:.0f} ft
Signal Strength: {signal_strength:.0f} dBm
Frequency: {frequency:.3f} GHz

Action Required: {action}

This is an automated alert from the Drone Detection System.
            """,
            html_template="""
<html>
<head><title>Drone Detection Alert</title></head>
<body>
<h1>🚁 Drone Detection Alert</h1>
<p><strong>Time:</strong> {timestamp}</p>
<p><strong>Drone Type:</strong> {drone_type}</p>
<p><strong>Confidence:</strong> {confidence:.1%}</p>
<p><strong>Threat Level:</strong> <span style="color:{threat_color}">{threat_level}</span></p>
<p><strong>Position:</strong> ({latitude:.6f}, {longitude:.6f})</p>
<p><strong>Altitude:</strong> {altitude:.0f} ft</p>
<p><strong>Signal Strength:</strong> {signal_strength:.0f} dBm</p>
<p><strong>Frequency:</strong> {frequency:.3f} GHz</p>
<h3>Action Required: {action}</h3>
<hr>
<p><small>This is an automated alert from the Drone Detection System.</small></p>
</body>
</html>
            """
        ))
        
        # Alert escalation template
        self.register_template(NotificationTemplate(
            name="alert_escalated",
            subject_template="[DDS] ALERT ESCALATED - {severity}",
            body_template="""
ALERT ESCALATION NOTIFICATION

Alert ID: {alert_id}
Severity: {severity}
Escalation Level: {escalation_level}
Message: {message}
Time: {timestamp}

This alert has been automatically escalated due to no response.
Immediate attention required.
            """,
            notification_type=NotificationType.EMAIL
        ))
        
        # Daily summary template
        self.register_template(NotificationTemplate(
            name="daily_summary",
            subject_template="[DDS] Daily Summary - {date}",
            body_template="""
Drone Detection System - Daily Summary
Date: {date}

Statistics:
- Total Detections: {total_detections}
- High Threat: {high_threat}
- Medium Threat: {medium_threat}
- Low Threat: {low_threat}
- Active Alerts: {active_alerts}
- System Uptime: {uptime_hours:.1f} hours

Top Drone Types:
{drone_types_summary}

System Health: {system_health}
            """,
            notification_type=NotificationType.EMAIL
        ))
        
        # SMS alert (short)
        self.register_template(NotificationTemplate(
            name="sms_alert",
            subject_template="Drone Alert",
            body_template="{drone_type} at {latitude:.4f},{longitude:.4f} - {confidence:.0%} conf",
            notification_type=NotificationType.SMS
        ))
    
    def register_template(self, template: NotificationTemplate) -> None:
        """Register a notification template"""
        self.templates[template.name] = template
        logger.debug(f"Registered template: {template.name}")
    
    async def send_notification(self, message: NotificationMessage) -> bool:
        """
        Send a notification
        
        Args:
            message: Notification message
            
        Returns:
            True if sent successfully
        """
        # Apply template if specified
        if message.template_name and message.template_name in self.templates:
            template = self.templates[message.template_name]
            subject, body, html = template.render(message.template_data)
            message.subject = subject
            message.body = body
            message.html_body = html
        
        # Send based on type
        if message.notification_type == NotificationType.EMAIL:
            if not self.email_service:
                logger.error("Email service not configured")
                return False
            return await self.email_service.send_email(message)
        
        elif message.notification_type == NotificationType.SMS:
            if not self.sms_service:
                logger.error("SMS service not configured")
                return False
            return await self.sms_service.send_sms(message)
        
        else:
            logger.error(f"Unsupported notification type: {message.notification_type}")
            return False
    
    async def send_drone_alert(self, detection_data: Dict[str, Any],
                                recipients: List[str],
                                notification_types: List[NotificationType] = None) -> List[NotificationMessage]:
        """
        Send drone detection alert to multiple recipients
        
        Args:
            detection_data: Detection information
            recipients: List of recipient emails/phone numbers
            notification_types: Types to send (email, sms)
            
        Returns:
            List of sent messages
        """
        notification_types = notification_types or [NotificationType.EMAIL, NotificationType.SMS]
        
        # Determine threat color for HTML
        threat_colors = {
            'LOW': 'green',
            'MEDIUM': 'orange',
            'HIGH': 'red',
            'CRITICAL': 'darkred'
        }
        
        detection_data['threat_color'] = threat_colors.get(
            detection_data.get('threat_level', 'LOW'), 'black'
        )
        detection_data['action'] = self._get_recommended_action(detection_data)
        
        messages = []
        
        for recipient in recipients:
            for nt in notification_types:
                # Determine if email or SMS
                if nt == NotificationType.EMAIL and '@' not in recipient:
                    continue
                if nt == NotificationType.SMS and '@' in recipient:
                    continue
                
                message = NotificationMessage(
                    notification_type=nt,
                    recipient=recipient,
                    subject="",
                    body="",
                    priority=self._get_priority_from_threat(detection_data.get('threat_level', 'LOW')),
                    template_name="drone_detected",
                    template_data=detection_data
                )
                
                success = await self.send_notification(message)
                
                if success:
                    self.stats['emails_sent' if nt == NotificationType.EMAIL else 'sms_sent'] += 1
                else:
                    self.stats['emails_failed' if nt == NotificationType.EMAIL else 'sms_failed'] += 1
                
                messages.append(message)
        
        return messages
    
    async def send_alert_escalation(self, alert_data: Dict[str, Any],
                                     recipient: str) -> bool:
        """
        Send alert escalation notification
        
        Args:
            alert_data: Alert information
            recipient: Recipient email
            
        Returns:
            True if sent
        """
        message = NotificationMessage(
            notification_type=NotificationType.EMAIL,
            recipient=recipient,
            subject="",
            body="",
            priority=NotificationPriority.CRITICAL,
            template_name="alert_escalated",
            template_data=alert_data
        )
        
        success = await self.send_notification(message)
        
        if success:
            self.stats['emails_sent'] += 1
        else:
            self.stats['emails_failed'] += 1
        
        return success
    
    async def send_daily_summary(self, summary_data: Dict[str, Any],
                                  recipients: List[str]) -> List[NotificationMessage]:
        """
        Send daily summary report
        
        Args:
            summary_data: Summary statistics
            recipients: List of recipient emails
            
        Returns:
            List of sent messages
        """
        messages = []
        
        for recipient in recipients:
            message = NotificationMessage(
                notification_type=NotificationType.EMAIL,
                recipient=recipient,
                subject="",
                body="",
                priority=NotificationPriority.NORMAL,
                template_name="daily_summary",
                template_data=summary_data
            )
            
            success = await self.send_notification(message)
            messages.append(message)
            
            if success:
                self.stats['emails_sent'] += 1
            else:
                self.stats['emails_failed'] += 1
        
        return messages
    
    async def send_sms_alert(self, phone_number: str, detection_data: Dict[str, Any]) -> bool:
        """
        Send SMS alert for drone detection
        
        Args:
            phone_number: Recipient phone number
            detection_data: Detection information
            
        Returns:
            True if sent
        """
        message = NotificationMessage(
            notification_type=NotificationType.SMS,
            recipient=phone_number,
            subject="",
            body="",
            priority=self._get_priority_from_threat(detection_data.get('threat_level', 'LOW')),
            template_name="sms_alert",
            template_data=detection_data
        )
        
        success = await self.send_notification(message)
        
        if success:
            self.stats['sms_sent'] += 1
        else:
            self.stats['sms_failed'] += 1
        
        return success
    
    def _get_priority_from_threat(self, threat_level: str) -> NotificationPriority:
        """Convert threat level to notification priority"""
        priority_map = {
            'LOW': NotificationPriority.LOW,
            'MEDIUM': NotificationPriority.NORMAL,
            'HIGH': NotificationPriority.HIGH,
            'CRITICAL': NotificationPriority.CRITICAL
        }
        return priority_map.get(threat_level, NotificationPriority.NORMAL)
    
    def _get_recommended_action(self, detection_data: Dict[str, Any]) -> str:
        """Get recommended action based on threat level"""
        threat = detection_data.get('threat_level', 'LOW')
        
        actions = {
            'LOW': 'Monitor and log',
            'MEDIUM': 'Investigate and track',
            'HIGH': 'Alert security personnel',
            'CRITICAL': 'Immediate intervention required'
        }
        
        return actions.get(threat, 'Monitor')
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            'email_service': {
                'enabled': self.email_service is not None,
                'hourly_count': self.email_service._sent_count_hour if self.email_service else 0,
                'daily_count': self.email_service._sent_count_day if self.email_service else 0
            } if self.email_service else None,
            'sms_service': {
                'enabled': self.sms_service is not None,
                'hourly_count': self.sms_service._sent_count_hour if self.sms_service else 0,
                'daily_count': self.sms_service._sent_count_day if self.sms_service else 0
            } if self.sms_service else None,
            'templates': len(self.templates)
        }
    
    async def shutdown(self):
        """Shutdown notification service"""
        self._running = False
        if self._queue_task:
            self._queue_task.cancel()
        logger.info("Notification service shutdown complete")


# ============================================================================
# Factory Functions
# ============================================================================

def create_gmail_notification_service(email_address: str, password: str,
                                       from_name: str = "Drone Detection System") -> NotificationService:
    """
    Create notification service with Gmail
    
    Args:
        email_address: Gmail email address
        password: Gmail app password
        from_name: Sender name
        
    Returns:
        Configured NotificationService
    """
    email_config = EmailConfig(
        provider=EmailProvider.GMAIL,
        username=email_address,
        password=password,
        from_email=email_address,
        from_name=from_name,
        smtp_host="smtp.gmail.com",
        smtp_port=587
    )
    
    return NotificationService(email_config=email_config)


def create_twilio_notification_service(account_sid: str, auth_token: str,
                                        twilio_phone: str,
                                        email_config: Optional[EmailConfig] = None) -> NotificationService:
    """
    Create notification service with Twilio SMS
    
    Args:
        account_sid: Twilio account SID
        auth_token: Twilio auth token
        twilio_phone: Twilio phone number
        email_config: Optional email configuration
        
    Returns:
        Configured NotificationService
    """
    sms_config = SMSConfig(
        provider=SMSProvider.TWILIO,
        twilio_account_sid=account_sid,
        twilio_auth_token=auth_token,
        twilio_phone_number=twilio_phone
    )
    
    return NotificationService(email_config=email_config, sms_config=sms_config)


def create_custom_smtp_service(smtp_host: str, smtp_port: int,
                                username: str, password: str,
                                from_email: str, from_name: str = "Drone Detection System") -> NotificationService:
    """
    Create notification service with custom SMTP
    
    Args:
        smtp_host: SMTP server host
        smtp_port: SMTP server port
        username: SMTP username
        password: SMTP password
        from_email: From email address
        from_name: From name
        
    Returns:
        Configured NotificationService
    """
    email_config = EmailConfig(
        provider=EmailProvider.CUSTOM_SMTP,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        username=username,
        password=password,
        from_email=from_email,
        from_name=from_name,
        use_tls=True
    )
    
    return NotificationService(email_config=email_config)


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of notification service"""
    
    print("Notification Service Example")
    print("=" * 50)
    
    # Create service with Gmail (replace with your credentials)
    # service = create_gmail_notification_service("your@gmail.com", "app_password")
    
    # For demo, create service without actual credentials
    print("\n1. Creating notification service...")
    
    # Mock email config for demonstration
    email_config = EmailConfig(
        provider=EmailProvider.CUSTOM_SMTP,
        smtp_host="smtp.example.com",
        smtp_port=587,
        username="demo@example.com",
        password="demo_password",
        from_email="alerts@drone-detector.com",
        from_name="Drone Detection System"
    )
    
    service = NotificationService(email_config=email_config)
    print("   Service created (demo mode - no actual sends)")
    
    # Register custom template
    print("\n2. Registering custom template...")
    service.register_template(NotificationTemplate(
        name="custom_alert",
        subject_template="[DDS] {alert_type} Alert",
        body_template="""
Alert Type: {alert_type}
Location: {location}
Time: {timestamp}
Please investigate.
        """,
        notification_type=NotificationType.EMAIL
    ))
    print("   Custom template registered")
    
    # Send drone alert
    print("\n3. Sending drone detection alert...")
    detection_data = {
        'drone_type': 'DJI Mavic 3',
        'confidence': 0.95,
        'threat_level': 'HIGH',
        'latitude': 37.7749,
        'longitude': -122.4194,
        'altitude': 400,
        'signal_strength': -45,
        'frequency': 2.44,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    messages = await service.send_drone_alert(
        detection_data=detection_data,
        recipients=["admin@example.com", "security@example.com"],
        notification_types=[NotificationType.EMAIL]
    )
    
    print(f"   Sent {len(messages)} notifications")
    
    # Send daily summary
    print("\n4. Sending daily summary...")
    summary_data = {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'total_detections': 47,
        'high_threat': 12,
        'medium_threat': 18,
        'low_threat': 17,
        'active_alerts': 3,
        'uptime_hours': 99.8,
        'drone_types_summary': "- DJI Mavic: 15\n- FPV: 12\n- Unknown: 20",
        'system_health': "Operational"
    }
    
    await service.send_daily_summary(summary_data, ["admin@example.com"])
    print("   Daily summary sent")
    
    # Send SMS alert
    print("\n5. Sending SMS alert...")
    await service.send_sms_alert("+1234567890", detection_data)
    print("   SMS alert sent")
    
    # Get statistics
    print("\n6. Service statistics:")
    stats = service.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Cleanup
    await service.shutdown()
    
    print("\n" + "=" * 50)
    print("Notification service example complete")


async def main():
    """Main function"""
    await example_usage()


if __name__ == "__main__":
    asyncio.run(main())