#!/usr/bin/env python3
"""
Webhook Integration Example for Drone Detector System

This example demonstrates how to integrate webhooks with the Drone Detector system
for real-time notifications, automation, and third-party system integration.

Topics covered:
    - Receiving webhook events from the drone detector
    - Processing different event types (detections, alerts, system events)
    - Filtering and routing events
    - Sending notifications to external services
    - Creating automated responses
    - Building custom webhook endpoints

Prerequisites:
    - Drone Detector system running
    - Publicly accessible endpoint (or use ngrok for testing)
    - Python 3.11+ with FastAPI/Flask

Usage:
    python webhook_integration.py
"""

import json
import hashlib
import hmac
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import requests
import aiohttp
import aiofiles

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# ============================================================================
# Data Models
# ============================================================================

class EventType(str, Enum):
    """Webhook event types"""
    DETECTION = "detection"
    ALERT = "alert"
    SYSTEM_STATUS = "system_status"
    HARDWARE_STATUS = "hardware_status"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    DRONE_TRACKING = "drone_tracking"
    SPECTRUM_UPDATE = "spectrum_update"
    ML_PREDICTION = "ml_prediction"
    TRAINING_COMPLETED = "training_completed"

class Severity(str, Enum):
    """Event severity levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class WebhookEvent:
    """Webhook event payload"""
    id: str
    type: EventType
    severity: Severity
    timestamp: datetime
    source: str
    data: Dict
    signature: Optional[str] = None
    
@dataclass
class WebhookSubscription:
    """Webhook subscription configuration"""
    id: str
    url: str
    events: List[EventType]
    secret: str
    active: bool = True
    retry_count: int = 3
    retry_delay: int = 5  # seconds
    filters: Dict = field(default_factory=dict)

# ============================================================================
# Webhook Receiver Server
# ============================================================================

app = FastAPI(title="Drone Detector Webhook Receiver")

class WebhookReceiver:
    """Webhook receiver for drone detector events"""
    
    def __init__(self):
        self.subscriptions: Dict[str, WebhookSubscription] = {}
        self.event_history: List[WebhookEvent] = []
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        
    def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify webhook signature for security"""
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
        
    async def process_event(self, event: WebhookEvent):
        """Process incoming webhook event"""
        print(f"\n📨 Received event: {event.type} ({event.severity})")
        print(f"   From: {event.source}")
        print(f"   Time: {event.timestamp}")
        
        # Store in history
        self.event_history.append(event)
        
        # Trim history if too large
        if len(self.event_history) > 10000:
            self.event_history = self.event_history[-10000:]
            
        # Trigger custom handlers
        if event.type in self.event_handlers:
            for handler in self.event_handlers[event.type]:
                await handler(event)
                
        return event
        
    def register_handler(self, event_type: EventType, handler: Callable):
        """Register custom event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        
    def add_subscription(self, subscription: WebhookSubscription):
        """Add webhook subscription"""
        self.subscriptions[subscription.id] = subscription
        print(f"✅ Added subscription: {subscription.id} -> {subscription.url}")
        
    def remove_subscription(self, subscription_id: str):
        """Remove webhook subscription"""
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            print(f"❌ Removed subscription: {subscription_id}")

# Initialize receiver
receiver = WebhookReceiver()

# ============================================================================
# FastAPI Endpoints
# ============================================================================

@app.post("/webhook/drone-detector")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive webhook from drone detector system
    """
    # Get raw payload for signature verification
    payload = await request.body()
    headers = request.headers
    
    # Extract signature
    signature = headers.get("X-Webhook-Signature", "")
    event_type = headers.get("X-Event-Type", "")
    event_id = headers.get("X-Event-ID", "")
    
    # Parse JSON
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    # Find matching subscription based on event type
    subscription = None
    for sub in receiver.subscriptions.values():
        if sub.active and any(e.value == event_type for e in sub.events):
            subscription = sub
            break
            
    # Verify signature if subscription found
    if subscription:
        if not receiver.verify_signature(payload, signature, subscription.secret):
            raise HTTPException(status_code=401, detail="Invalid signature")
            
    # Create event object
    event = WebhookEvent(
        id=event_id,
        type=EventType(event_type) if event_type else EventType.SYSTEM_STATUS,
        severity=Severity(data.get("severity", "info")),
        timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
        source=headers.get("X-Source", "drone-detector"),
        data=data,
        signature=signature
    )
    
    # Process in background to not block
    background_tasks.add_task(receiver.process_event, event)
    
    return JSONResponse(
        status_code=200,
        content={"status": "received", "event_id": event.id}
    )

@app.get("/webhook/events")
async def get_events(limit: int = 100, event_type: Optional[str] = None):
    """Get recent events"""
    events = receiver.event_history[-limit:]
    
    if event_type:
        events = [e for e in events if e.type.value == event_type]
        
    return {
        "events": [
            {
                "id": e.id,
                "type": e.type.value,
                "severity": e.severity.value,
                "timestamp": e.timestamp.isoformat(),
                "source": e.source,
                "data": e.data
            }
            for e in events
        ],
        "total": len(events)
    }

@app.post("/webhook/subscribe")
async def subscribe_webhook(subscription: WebhookSubscription):
    """Subscribe to webhook events"""
    receiver.add_subscription(subscription)
    return {"status": "subscribed", "id": subscription.id}

@app.delete("/webhook/subscribe/{subscription_id}")
async def unsubscribe_webhook(subscription_id: str):
    """Unsubscribe from webhook events"""
    receiver.remove_subscription(subscription_id)
    return {"status": "unsubscribed", "id": subscription_id}

# ============================================================================
# Custom Event Handlers
# ============================================================================

class EventHandlers:
    """Custom event handlers for different event types"""
    
    @staticmethod
    async def handle_detection(event: WebhookEvent):
        """Handle drone detection events"""
        detection = event.data.get("detection", {})
        
        print(f"\n🎯 DRONE DETECTED!")
        print(f"   Type: {detection.get('drone_type', 'Unknown')}")
        print(f"   Confidence: {detection.get('confidence', 0)*100:.1f}%")
        print(f"   Threat: {detection.get('threat_level', 'unknown').upper()}")
        
        if detection.get('position'):
            pos = detection['position']
            print(f"   Location: {pos.get('latitude'):.6f}, {pos.get('longitude'):.6f}")
            
        # Check for high threat
        if detection.get('threat_level') in ['high', 'critical']:
            print(f"   ⚠️  HIGH THREAT DETECTED!")
            await EventHandlers.send_alert_notification(event)
            
    @staticmethod
    async def handle_alert(event: WebhookEvent):
        """Handle alert events"""
        alert = event.data.get("alert", {})
        
        severity_icons = {
            "critical": "🔴",
            "high": "🟠", 
            "medium": "🟡",
            "low": "🟢"
        }
        icon = severity_icons.get(alert.get("severity", "info"), "⚪")
        
        print(f"\n{icon} ALERT: {alert.get('title', 'Unknown Alert')}")
        print(f"   Message: {alert.get('message', 'No message')}")
        
    @staticmethod
    async def handle_system_status(event: WebhookEvent):
        """Handle system status updates"""
        status = event.data.get("system", {})
        
        print(f"\n💻 SYSTEM STATUS UPDATE")
        print(f"   Status: {status.get('status', 'unknown')}")
        print(f"   Uptime: {status.get('uptime_seconds', 0)/3600:.1f} hours")
        print(f"   CPU: {status.get('cpu_percent', 0):.1f}%")
        print(f"   Memory: {status.get('memory_mb', 0):.0f} MB")
        
    @staticmethod
    async def handle_hardware_status(event: WebhookEvent):
        """Handle hardware status updates"""
        hardware = event.data.get("hardware", {})
        
        print(f"\n📻 HARDWARE STATUS")
        print(f"   Device: {hardware.get('type', 'unknown')}")
        print(f"   Connected: {hardware.get('connected', False)}")
        print(f"   Temperature: {hardware.get('temperature_c', 0):.1f}°C")
        print(f"   Sample Rate: {hardware.get('sample_rate', 0)/1e6:.1f} MHz")
        
        # Alert on high temperature
        if hardware.get('temperature_c', 0) > 60:
            print(f"   ⚠️  HIGH TEMPERATURE DETECTED!")
            
    @staticmethod
    async def handle_recordings(event: WebhookEvent):
        """Handle recording events"""
        recording = event.data.get("recording", {})
        
        action = "STARTED" if event.type == EventType.RECORDING_STARTED else "STOPPED"
        print(f"\n💾 RECORDING {action}")
        print(f"   ID: {recording.get('recording_id', 'unknown')}")
        print(f"   Duration: {recording.get('duration_seconds', 0)}s")
        print(f"   Size: {recording.get('file_size_mb', 0):.1f} MB")
        
    @staticmethod
    async def send_alert_notification(event: WebhookEvent):
        """Send alert to external notification service"""
        # Example: Send to Slack
        await EventHandlers.send_slack_notification(event)
        
        # Example: Send to Email
        await EventHandlers.send_email_notification(event)
        
        # Example: Send to PagerDuty
        await EventHandlers.send_pagerduty_alert(event)
        
    @staticmethod
    async def send_slack_notification(event: WebhookEvent):
        """Send notification to Slack"""
        webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
        
        detection = event.data.get("detection", {})
        
        slack_message = {
            "attachments": [{
                "color": "danger" if detection.get('threat_level') in ['high', 'critical'] else "warning",
                "title": "🚁 Drone Detection Alert",
                "fields": [
                    {
                        "title": "Drone Type",
                        "value": detection.get('drone_type', 'Unknown'),
                        "short": True
                    },
                    {
                        "title": "Confidence",
                        "value": f"{detection.get('confidence', 0)*100:.1f}%",
                        "short": True
                    },
                    {
                        "title": "Threat Level",
                        "value": detection.get('threat_level', 'unknown').upper(),
                        "short": True
                    },
                    {
                        "title": "Location",
                        "value": f"{detection.get('position', {}).get('latitude', 'N/A')}, "
                                f"{detection.get('position', {}).get('longitude', 'N/A')}",
                        "short": True
                    }
                ],
                "footer": "Drone Detector System",
                "ts": event.timestamp.timestamp()
            }]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(webhook_url, json=slack_message)
            print("   ✓ Slack notification sent")
        except Exception as e:
            print(f"   ✗ Failed to send Slack notification: {e}")
            
    @staticmethod
    async def send_email_notification(event: WebhookEvent):
        """Send email notification"""
        # Example using SMTP
        import smtplib
        from email.mime.text import MimeText
        
        detection = event.data.get("detection", {})
        
        subject = f"Drone Detection Alert - {detection.get('drone_type', 'Unknown')}"
        body = f"""
        Drone Detection Alert
        
        Time: {event.timestamp}
        Drone Type: {detection.get('drone_type', 'Unknown')}
        Confidence: {detection.get('confidence', 0)*100:.1f}%
        Threat Level: {detection.get('threat_level', 'unknown').upper()}
        
        Location:
        Latitude: {detection.get('position', {}).get('latitude', 'N/A')}
        Longitude: {detection.get('position', {}).get('longitude', 'N/A')}
        
        This is an automated alert from the Drone Detector System.
        """
        
        # Configure email settings
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "alerts@drone-detector.com"
        sender_password = "your_password"
        recipient_email = "security@example.com"
        
        try:
            msg = MimeText(body)
            msg['Subject'] = subject
            msg['From'] = sender_email
            msg['To'] = recipient_email
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            print("   ✓ Email notification sent")
        except Exception as e:
            print(f"   ✗ Failed to send email: {e}")
            
    @staticmethod
    async def send_pagerduty_alert(event: WebhookEvent):
        """Send alert to PagerDuty"""
        pagerduty_key = "YOUR_PAGERDUTY_INTEGRATION_KEY"
        
        detection = event.data.get("detection", {})
        
        payload = {
            "routing_key": pagerduty_key,
            "event_action": "trigger",
            "dedup_key": event.id,
            "payload": {
                "summary": f"Drone Detection: {detection.get('drone_type', 'Unknown')}",
                "severity": detection.get('threat_level', 'warning'),
                "source": "drone-detector",
                "timestamp": event.timestamp.isoformat(),
                "custom_details": {
                    "Drone Type": detection.get('drone_type'),
                    "Confidence": detection.get('confidence'),
                    "Threat Level": detection.get('threat_level'),
                    "Frequency": detection.get('frequency'),
                    "Position": detection.get('position')
                }
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload
                )
            print("   ✓ PagerDuty alert sent")
        except Exception as e:
            print(f"   ✗ Failed to send PagerDuty alert: {e}")

# ============================================================================
# Automation Workflows
# ============================================================================

class AutomationWorkflows:
    """Automated workflows triggered by webhooks"""
    
    def __init__(self):
        self.active_workflows = {}
        
    async def auto_record_on_detection(self, event: WebhookEvent):
        """Automatically start recording when high-confidence drone detected"""
        detection = event.data.get("detection", {})
        
        if detection.get('confidence', 0) > 0.8:
            print("\n📹 Auto-recording triggered by detection")
            
            # Call drone detector API to start recording
            async with aiohttp.ClientSession() as session:
                await session.post(
                    "http://localhost:8888/api/v1/recordings/start",
                    json={
                        "duration_seconds": 60,
                        "frequency": detection.get('frequency', 2.45e9),
                        "auto_stop": True
                    }
                )
                
    async def auto_alert_escalation(self, event: WebhookEvent):
        """Escalate alerts based on severity and frequency"""
        alert = event.data.get("alert", {})
        severity = alert.get('severity', 'low')
        
        # Track alerts per drone
        drone_id = alert.get('drone_id')
        if not drone_id:
            return
            
        if drone_id not in self.active_workflows:
            self.active_workflows[drone_id] = {
                'alerts': [],
                'escalation_level': 0
            }
            
        workflow = self.active_workflows[drone_id]
        workflow['alerts'].append({
            'timestamp': event.timestamp,
            'severity': severity
        })
        
        # Clean old alerts (last 10 minutes)
        cutoff = datetime.now() - timedelta(minutes=10)
        workflow['alerts'] = [a for a in workflow['alerts'] 
                              if a['timestamp'] > cutoff]
        
        # Escalate based on alert frequency
        if len(workflow['alerts']) >= 3:
            print(f"\n📢 Alert escalation triggered for drone {drone_id}")
            
            # Send to multiple channels
            await EventHandlers.send_slack_notification(event)
            await EventHandlers.send_pagerduty_alert(event)
            
            # Notify security team
            await self.notify_security_team(event)
            
    async def notify_security_team(self, event: WebhookEvent):
        """Notify security team via multiple channels"""
        detection = event.data.get("detection", {})
        
        message = f"""
        🚨 ESCALATED ALERT: Persistent drone activity detected
        
        Drone Type: {detection.get('drone_type', 'Unknown')}
        Threat Level: {detection.get('threat_level', 'unknown').upper()}
        Time: {event.timestamp}
        
        Multiple alerts received in short period.
        Immediate attention required.
        """
        
        # In production, this would integrate with actual notification systems
        print(f"   📞 Security team notified")
        print(f"   Message: {message}")
        
    async def auto_mitigation(self, event: WebhookEvent):
        """Automated mitigation actions for confirmed threats"""
        detection = event.data.get("detection", {})
        
        if detection.get('threat_level') == 'critical':
            print("\n🛡️ INITIATING AUTOMATED MITIGATION")
            
            # 1. Alert nearby personnel
            await self.alert_ground_crew(event)
            
            # 2. Log evidence
            await self.capture_evidence(event)
            
            # 3. Notify authorities
            await self.notify_authorities(event)
            
    async def alert_ground_crew(self, event: WebhookEvent):
        """Send alert to ground crew"""
        position = event.data.get("detection", {}).get("position", {})
        print(f"   📱 Alerting ground crew at {position.get('latitude')}, {position.get('longitude')}")
        
    async def capture_evidence(self, event: WebhookEvent):
        """Capture and preserve evidence"""
        print(f"   📸 Capturing evidence (screenshots, recordings)")
        
        # Take screenshot of dashboard
        async with aiohttp.ClientSession() as session:
            await session.post("http://localhost:8888/api/v1/exports/evidence")
            
    async def notify_authorities(self, event: WebhookEvent):
        """Notify local authorities"""
        print(f"   👮 Notifying local authorities")
        # In production, integrate with local law enforcement APIs

# ============================================================================
# Webhook Sender (Client)
# ============================================================================

class WebhookSender:
    """Send webhooks to configured endpoints"""
    
    def __init__(self):
        self.subscriptions = []
        
    def add_subscription(self, url: str, events: List[str], secret: str):
        """Add webhook subscription"""
        self.subscriptions.append({
            'url': url,
            'events': events,
            'secret': secret
        })
        
    def generate_signature(self, payload: bytes, secret: str) -> str:
        """Generate HMAC signature"""
        return hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
    async def send_event(self, event: WebhookEvent):
        """Send event to all subscribed webhooks"""
        payload = json.dumps({
            "id": event.id,
            "type": event.type.value,
            "severity": event.severity.value,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data
        }).encode()
        
        for subscription in self.subscriptions:
            if event.type.value not in subscription['events']:
                continue
                
            signature = self.generate_signature(payload, subscription['secret'])
            
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Event-Type": event.type.value,
                "X-Event-ID": event.id,
                "X-Source": "drone-detector"
            }
            
            # Retry logic
            for attempt in range(3):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            subscription['url'],
                            data=payload,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as response:
                            if response.status == 200:
                                print(f"✓ Sent to {subscription['url']}")
                                break
                            else:
                                print(f"✗ Failed to send to {subscription['url']}: {response.status}")
                                
                except Exception as e:
                    print(f"✗ Error sending to {subscription['url']}: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff

# ============================================================================
# Example Webhook Client
# ============================================================================

class ExampleWebhookClient:
    """Example client that sends webhooks to the receiver"""
    
    def __init__(self, webhook_url: str = "http://localhost:8888/webhook/drone-detector"):
        self.webhook_url = webhook_url
        self.secret = "your_shared_secret"
        
    def generate_signature(self, payload: bytes) -> str:
        """Generate webhook signature"""
        return hmac.new(
            self.secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
    async def send_detection_event(self, detection_data: Dict):
        """Send detection event via webhook"""
        event = {
            "id": f"det_{datetime.now().timestamp()}",
            "type": "detection",
            "severity": detection_data.get('threat_level', 'info'),
            "timestamp": datetime.now().isoformat(),
            "data": {
                "detection": detection_data
            }
        }
        
        payload = json.dumps(event).encode()
        signature = self.generate_signature(payload)
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Event-Type": "detection",
            "X-Event-ID": event['id'],
            "X-Source": "example-client"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.webhook_url,
                data=payload,
                headers=headers
            ) as response:
                return response.status == 200
                
    async def simulate_detections(self):
        """Simulate sending detection events"""
        sample_detections = [
            {
                "drone_type": "DJI Mavic 3",
                "confidence": 0.95,
                "threat_level": "high",
                "frequency": 2.45e9,
                "position": {
                    "latitude": 37.7749,
                    "longitude": -122.4194,
                    "altitude": 100
                }
            },
            {
                "drone_type": "FPV Analog",
                "confidence": 0.85,
                "threat_level": "medium",
                "frequency": 5.8e9,
                "position": {
                    "latitude": 37.7750,
                    "longitude": -122.4195,
                    "altitude": 80
                }
            },
            {
                "drone_type": "Custom Build",
                "confidence": 0.75,
                "threat_level": "low",
                "frequency": 2.45e9
            }
        ]
        
        for detection in sample_detections:
            success = await self.send_detection_event(detection)
            if success:
                print(f"✓ Sent detection: {detection['drone_type']}")
            else:
                print(f"✗ Failed to send detection")
            await asyncio.sleep(2)

# ============================================================================
# Main Execution
# ============================================================================

async def run_receiver():
    """Run the webhook receiver server"""
    print("="*70)
    print("🔌 DRONE DETECTOR WEBHOOK INTEGRATION EXAMPLE")
    print("="*70)
    
    # Register custom event handlers
    receiver.register_handler(EventType.DETECTION, EventHandlers.handle_detection)
    receiver.register_handler(EventType.ALERT, EventHandlers.handle_alert)
    receiver.register_handler(EventType.SYSTEM_STATUS, EventHandlers.handle_system_status)
    receiver.register_handler(EventType.HARDWARE_STATUS, EventHandlers.handle_hardware_status)
    receiver.register_handler(EventType.RECORDING_STARTED, EventHandlers.handle_recordings)
    receiver.register_handler(EventType.RECORDING_STOPPED, EventHandlers.handle_recordings)
    
    # Setup automation workflows
    workflows = AutomationWorkflows()
    receiver.register_handler(EventType.DETECTION, workflows.auto_record_on_detection)
    receiver.register_handler(EventType.ALERT, workflows.auto_alert_escalation)
    receiver.register_handler(EventType.DETECTION, workflows.auto_mitigation)
    
    # Add subscriptions
    subscription = WebhookSubscription(
        id="security-team",
        url="https://your-security-system.com/webhook",
        events=[EventType.DETECTION, EventType.ALERT],
        secret="your_secret_here",
        active=True
    )
    receiver.add_subscription(subscription)
    
    # Start the FastAPI server
    print("\n🚀 Starting webhook receiver on http://localhost:8000")
    print("\nAvailable endpoints:")
    print("  POST /webhook/drone-detector - Receive webhook events")
    print("  GET  /webhook/events - View recent events")
    print("  POST /webhook/subscribe - Add webhook subscription")
    print("  DELETE /webhook/subscribe/{id} - Remove subscription")
    print("\n" + "="*70)
    
    # Run server
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    # Run client simulator in background
    asyncio.create_task(run_client_simulator())
    
    await server.run()

async def run_client_simulator():
    """Run the webhook client simulator"""
    await asyncio.sleep(2)  # Wait for server to start
    
    print("\n" + "="*70)
    print("📤 SIMULATING WEBHOOK CLIENT")
    print("="*70)
    
    client = ExampleWebhookClient()
    
    print("\nSending sample detection events...")
    await client.simulate_detections()
    
    print("\n✅ Client simulation complete")

async def run_standalone_client():
    """Run just the client (without server)"""
    print("="*70)
    print("📤 WEBHOOK CLIENT EXAMPLE")
    print("="*70)
    
    client = ExampleWebhookClient("http://localhost:8000/webhook/drone-detector")
    
    print("\nSending detection events to webhook receiver...")
    await client.simulate_detections()
    
    print("\n✅ Client completed")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--client":
        # Run just the client
        asyncio.run(run_standalone_client())
    else:
        # Run the full webhook receiver
        asyncio.run(run_receiver())