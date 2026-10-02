#!/usr/bin/env python3
# drone-detector/app/workers.py
"""
Background task workers for Drone Detection System

This module handles asynchronous background tasks including:
- IQ data processing
- Batch detection jobs
- Data export and archiving
- Database cleanup and maintenance
- Notification dispatching
- Metrics aggregation
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
import traceback

import numpy as np
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Application imports
from domain.algorithms.fft import compute_fft
from domain.algorithms.psd import compute_psd
from domain.algorithms.peak_detection import detect_peaks
from domain.algorithms.ml_classifier import MLClassifier
from domain.entities.detection import DetectionEvent, ThreatLevel
from infrastructure.storage.database import DatabaseManager
from infrastructure.messaging.event_bus import EventBus
from infrastructure.monitoring.logger import get_logger

# Setup logging
logger = get_logger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class WorkerStatus(Enum):
    """Worker status states"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class TaskPriority(Enum):
    """Task priority levels"""
    HIGH = 0
    NORMAL = 1
    LOW = 2
    BACKGROUND = 3


class TaskType(Enum):
    """Types of background tasks"""
    IQ_PROCESSING = "iq_processing"
    DETECTION_BATCH = "detection_batch"
    DATA_EXPORT = "data_export"
    DATABASE_CLEANUP = "database_cleanup"
    NOTIFICATION = "notification"
    METRICS_AGGREGATION = "metrics_aggregation"
    MODEL_RETRAINING = "model_retraining"
    IQ_RECORDING = "iq_recording"
    REPORT_GENERATION = "report_generation"
    SPECTRUM_ANALYSIS = "spectrum_analysis"
    REMOTE_ID_PROCESSING = "remote_id_processing"
    TDOA_CALCULATION = "tdoa_calculation"


@dataclass
class Task:
    """Represents a background task"""
    id: str
    type: TaskType
    priority: TaskPriority
    data: Dict[str, Any]
    callback: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'priority': self.priority.value,
            'data': self.data,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'error': self.error
        }


@dataclass
class WorkerConfig:
    """Configuration for worker pool"""
    max_workers: int = 4
    max_queue_size: int = 100
    thread_pool_size: int = 2
    process_pool_size: int = 1
    task_timeout_seconds: int = 300
    enable_persistent_queue: bool = True
    queue_db_path: str = "data/queue.db"
    monitor_interval_seconds: int = 10


# ============================================================================
# Core Worker Classes
# ============================================================================

class TaskQueue:
    """Priority-based task queue with persistence"""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=config.max_queue_size)
        self._pending_tasks: Dict[str, Task] = {}
        self._running_tasks: Dict[str, Task] = {}
        self._completed_tasks: List[Task] = []
        self._lock = asyncio.Lock()
        
        # Initialize persistent storage if enabled
        if config.enable_persistent_queue:
            self._init_persistent_storage()
    
    def _init_persistent_storage(self):
        """Initialize persistent task storage"""
        try:
            import sqlite3
            self._conn = sqlite3.connect(self.config.queue_db_path)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    priority INTEGER,
                    data TEXT,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            logger.info(f"Persistent task queue initialized at {self.config.queue_db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize persistent queue: {e}")
    
    async def put(self, task: Task):
        """Add task to queue with priority"""
        priority_value = task.priority.value
        await self._queue.put((priority_value, task))
        
        async with self._lock:
            self._pending_tasks[task.id] = task
        
        logger.debug(f"Task {task.id} added to queue (priority: {task.priority.name})")
        
        # Persist if enabled
        if self.config.enable_persistent_queue:
            await self._persist_task(task)
    
    async def get(self) -> Optional[Task]:
        """Get next task from queue"""
        try:
            priority, task = await asyncio.wait_for(
                self._queue.get(), 
                timeout=1.0
            )
            
            async with self._lock:
                if task.id in self._pending_tasks:
                    del self._pending_tasks[task.id]
                self._running_tasks[task.id] = task
            
            task.started_at = datetime.now()
            task.status = "running"
            
            logger.debug(f"Task {task.id} started (priority: {priority})")
            return task
            
        except asyncio.TimeoutError:
            return None
    
    async def complete(self, task: Task, result: Any = None, error: Optional[str] = None):
        """Mark task as complete"""
        task.completed_at = datetime.now()
        task.status = "completed" if error is None else "failed"
        task.result = result
        task.error = error
        
        async with self._lock:
            if task.id in self._running_tasks:
                del self._running_tasks[task.id]
            self._completed_tasks.append(task)
        
        # Limit completed tasks history
        if len(self._completed_tasks) > 1000:
            self._completed_tasks = self._completed_tasks[-1000:]
        
        # Update persistence
        if self.config.enable_persistent_queue:
            await self._update_task_status(task)
        
        # Call callback if provided
        if task.callback:
            try:
                if asyncio.iscoroutinefunction(task.callback):
                    await task.callback(task)
                else:
                    task.callback(task)
            except Exception as e:
                logger.error(f"Callback failed for task {task.id}: {e}")
        
        logger.debug(f"Task {task.id} completed in {(task.completed_at - task.started_at).total_seconds():.2f}s")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        async with self._lock:
            return {
                'queue_size': self._queue.qsize(),
                'pending_tasks': len(self._pending_tasks),
                'running_tasks': len(self._running_tasks),
                'completed_tasks': len(self._completed_tasks),
                'max_queue_size': self.config.max_queue_size
            }
    
    async def _persist_task(self, task: Task):
        """Persist task to database"""
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO tasks (id, type, priority, data, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task.id, task.type.value, task.priority.value, json.dumps(task.data), 
                 task.status, task.created_at.isoformat(), datetime.now().isoformat())
            )
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist task {task.id}: {e}")
    
    async def _update_task_status(self, task: Task):
        """Update task status in persistent storage"""
        try:
            self._conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (task.status, datetime.now().isoformat(), task.id)
            )
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to update task {task.id}: {e}")

    async def shutdown(self):
        """Shutdown queue and cleanup"""
        if hasattr(self, '_conn'):
            self._conn.close()


class WorkerPool:
    """Manages a pool of background workers"""
    
    def __init__(self, config: WorkerConfig, task_queue: TaskQueue):
        self.config = config
        self.task_queue = task_queue
        self.workers: List[BaseWorker] = []
        self.status = WorkerStatus.IDLE
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Thread and process pools for CPU-bound tasks
        self.thread_pool = ThreadPoolExecutor(max_workers=config.thread_pool_size)
        self.process_pool = ProcessPoolExecutor(max_workers=config.process_pool_size)
    
    async def start(self):
        """Start all workers"""
        self.status = WorkerStatus.RUNNING
        
        # Create worker instances
        worker_types = [
            IQProcessingWorker,
            DetectionBatchWorker,
            DataExportWorker,
            DatabaseCleanupWorker,
            NotificationWorker,
            MetricsAggregationWorker,
            ModelRetrainingWorker,
            IQRecordingWorker,
            ReportGenerationWorker,
            SpectrumAnalysisWorker,
            RemoteIDProcessingWorker,
            TDOACalculationWorker
        ]
        
        for worker_class in worker_types:
            for _ in range(self.config.max_workers // len(worker_types)):
                worker = worker_class(self.task_queue, self.thread_pool, self.process_pool)
                self.workers.append(worker)
                asyncio.create_task(worker.run())
        
        # Start monitoring
        self._monitor_task = asyncio.create_task(self._monitor())
        
        logger.info(f"Worker pool started with {len(self.workers)} workers")
    
    async def stop(self):
        """Stop all workers"""
        self.status = WorkerStatus.STOPPED
        
        # Stop all workers
        for worker in self.workers:
            await worker.stop()
        
        # Cancel monitor
        if self._monitor_task:
            self._monitor_task.cancel()
        
        # Shutdown thread/process pools
        self.thread_pool.shutdown(wait=True)
        self.process_pool.shutdown(wait=True)
        
        # Shutdown task queue
        await self.task_queue.shutdown()
        
        logger.info("Worker pool stopped")
    
    async def _monitor(self):
        """Monitor worker pool health"""
        while self.status == WorkerStatus.RUNNING:
            try:
                stats = await self.task_queue.get_stats()
                logger.debug(f"Worker pool stats: {stats}")
                
                # Check for stuck workers
                for worker in self.workers:
                    if worker.status == WorkerStatus.ERROR:
                        logger.warning(f"Worker {worker.__class__.__name__} in error state, restarting...")
                        asyncio.create_task(worker.restart())
                
                await asyncio.sleep(self.config.monitor_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(5)


class BaseWorker:
    """Base class for all workers"""
    
    def __init__(self, task_queue: TaskQueue, thread_pool: ThreadPoolExecutor, process_pool: ProcessPoolExecutor):
        self.task_queue = task_queue
        self.thread_pool = thread_pool
        self.process_pool = process_pool
        self.status = WorkerStatus.IDLE
        self._running = True
        self.current_task: Optional[Task] = None
    
    async def run(self):
        """Main worker loop"""
        self.status = WorkerStatus.RUNNING
        
        while self._running:
            try:
                # Get next task
                task = await self.task_queue.get()
                
                if task is None:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process task
                self.current_task = task
                self.status = WorkerStatus.RUNNING
                
                try:
                    result = await self.process_task(task)
                    await self.task_queue.complete(task, result=result)
                except Exception as e:
                    logger.error(f"Task {task.id} failed: {e}\n{traceback.format_exc()}")
                    await self.task_queue.complete(task, error=str(e))
                
                self.current_task = None
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                self.status = WorkerStatus.ERROR
                await asyncio.sleep(1)
    
    async def stop(self):
        """Stop worker"""
        self._running = False
        self.status = WorkerStatus.STOPPED
    
    async def restart(self):
        """Restart worker"""
        await self.stop()
        self.status = WorkerStatus.IDLE
        self._running = True
        asyncio.create_task(self.run())
    
    async def process_task(self, task: Task) -> Any:
        """Process task - override in subclass"""
        raise NotImplementedError


# ============================================================================
# Specific Worker Implementations
# ============================================================================

class IQProcessingWorker(BaseWorker):
    """Processes IQ samples for spectrum analysis and detection"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process IQ data task"""
        data = task.data
        samples = np.array(data.get('samples', []))
        sample_rate = data.get('sample_rate', 10e6)
        fft_size = data.get('fft_size', 2048)
        
        if len(samples) == 0:
            raise ValueError("No samples provided")
        
        # Run CPU-intensive processing in thread pool
        result = await asyncio.get_event_loop().run_in_executor(
            self.thread_pool,
            self._process_iq_sync,
            samples,
            sample_rate,
            fft_size
        )
        
        return result
    
    def _process_iq_sync(self, samples: np.ndarray, sample_rate: float, fft_size: int) -> Dict[str, Any]:
        """Synchronous IQ processing"""
        # Compute FFT
        fft_result = compute_fft(samples, fft_size)
        
        # Compute PSD
        psd = compute_psd(fft_result, sample_rate)
        
        # Detect peaks
        peaks = detect_peaks(psd, threshold_factor=3.0)
        
        # Calculate statistics
        stats = {
            'mean_power': float(np.mean(psd)),
            'max_power': float(np.max(psd)),
            'min_power': float(np.min(psd)),
            'std_power': float(np.std(psd)),
            'peak_count': len(peaks),
            'signal_present': len(peaks) > 0
        }
        
        return {
            'fft': fft_result.tolist(),
            'psd': psd.tolist(),
            'peaks': peaks,
            'statistics': stats,
            'timestamp': datetime.now().isoformat()
        }


class DetectionBatchWorker(BaseWorker):
    """Processes batches of detections for bulk analysis"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process batch detection task"""
        detections = task.data.get('detections', [])
        batch_id = task.data.get('batch_id', str(uuid.uuid4()))
        
        results = []
        for detection in detections:
            # Process each detection
            processed = await self._process_detection(detection)
            results.append(processed)
        
        # Aggregate results
        summary = {
            'batch_id': batch_id,
            'total': len(results),
            'high_threat': sum(1 for r in results if r.get('threat_level') == 'high'),
            'medium_threat': sum(1 for r in results if r.get('threat_level') == 'medium'),
            'low_threat': sum(1 for r in results if r.get('threat_level') == 'low'),
            'avg_confidence': np.mean([r.get('confidence', 0) for r in results]) if results else 0,
            'drone_types': {}
        }
        
        # Count drone types
        for r in results:
            drone_type = r.get('drone_type', 'unknown')
            summary['drone_types'][drone_type] = summary['drone_types'].get(drone_type, 0) + 1
        
        return {
            'batch_id': batch_id,
            'results': results,
            'summary': summary,
            'processed_at': datetime.now().isoformat()
        }
    
    async def _process_detection(self, detection: Dict[str, Any]) -> Dict[str, Any]:
        """Process individual detection"""
        # Simulate ML classification
        ml_classifier = MLClassifier()
        classification = ml_classifier.predict(detection.get('features', []))
        
        return {
            'detection_id': detection.get('id'),
            'drone_type': classification.get('drone_type', 'unknown'),
            'confidence': classification.get('confidence', 0.5),
            'threat_level': self._calculate_threat(classification),
            'processed_at': datetime.now().isoformat()
        }
    
    def _calculate_threat(self, classification: Dict[str, Any]) -> str:
        """Calculate threat level from classification"""
        confidence = classification.get('confidence', 0)
        drone_type = classification.get('drone_type', '')
        
        if confidence > 0.8 and drone_type in ['DJI Mavic', 'DJI Phantom']:
            return 'high'
        elif confidence > 0.6:
            return 'medium'
        else:
            return 'low'


class DataExportWorker(BaseWorker):
    """Handles data export tasks (CSV, JSON, images)"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process data export task"""
        export_type = task.data.get('export_type', 'json')
        data = task.data.get('data', {})
        format_config = task.data.get('format_config', {})
        
        export_dir = Path(task.data.get('export_dir', 'data/exports'))
        export_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if export_type == 'json':
            filepath = export_dir / f"export_{timestamp}.json"
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
        elif export_type == 'csv':
            filepath = export_dir / f"export_{timestamp}.csv"
            import csv
            if isinstance(data, list) and len(data) > 0:
                with open(filepath, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                    
        elif export_type == 'image':
            filepath = export_dir / f"export_{timestamp}.png"
            # Image export logic here
            pass
        
        return {
            'export_type': export_type,
            'filepath': str(filepath),
            'file_size': filepath.stat().st_size if filepath.exists() else 0,
            'record_count': len(data) if isinstance(data, list) else 1,
            'exported_at': datetime.now().isoformat()
        }


class DatabaseCleanupWorker(BaseWorker):
    """Periodic database cleanup and maintenance"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Run database cleanup"""
        retention_days = task.data.get('retention_days', 30)
        db_manager = DatabaseManager()
        
        cleanup_results = {
            'deleted_detections': 0,
            'deleted_iq_files': 0,
            'deleted_logs': 0,
            'vacuum_performed': False
        }
        
        # Clean old detections
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cleanup_results['deleted_detections'] = await db_manager.delete_old_detections(cutoff_date)
        
        # Clean old IQ files
        iq_dir = Path('data/iq/live')
        if iq_dir.exists():
            for session_dir in iq_dir.iterdir():
                if session_dir.is_dir():
                    modified_time = datetime.fromtimestamp(session_dir.stat().st_mtime)
                    if modified_time < cutoff_date:
                        import shutil
                        shutil.rmtree(session_dir)
                        cleanup_results['deleted_iq_files'] += 1
        
        # Run VACUUM to reclaim space
        if task.data.get('vacuum', False):
            await db_manager.vacuum()
            cleanup_results['vacuum_performed'] = True
        
        return cleanup_results


class NotificationWorker(BaseWorker):
    """Handles notification dispatching (email, webhook, MQTT)"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Send notifications"""
        notification_type = task.data.get('type', 'webhook')
        recipients = task.data.get('recipients', [])
        message = task.data.get('message', '')
        severity = task.data.get('severity', 'info')
        
        results = []
        
        if notification_type == 'webhook':
            # Send webhook notification
            webhook_url = task.data.get('webhook_url')
            if webhook_url:
                result = await self._send_webhook(webhook_url, message, severity)
                results.append(result)
        
        elif notification_type == 'email':
            # Send email notification
            for email in recipients:
                result = await self._send_email(email, message, severity)
                results.append(result)
        
        elif notification_type == 'mqtt':
            # Send MQTT notification
            mqtt_topic = task.data.get('mqtt_topic', 'drone-detector/alerts')
            result = await self._send_mqtt(mqtt_topic, message, severity)
            results.append(result)
        
        elif notification_type == 'telegram':
            # Send Telegram notification
            bot_token = task.data.get('telegram_bot_token')
            chat_id = task.data.get('telegram_chat_id')
            if bot_token and chat_id:
                result = await self._send_telegram(bot_token, chat_id, message)
                results.append(result)
        
        return {
            'notification_type': notification_type,
            'sent_count': len(results),
            'successful': all(results),
            'sent_at': datetime.now().isoformat()
        }
    
    async def _send_webhook(self, url: str, message: str, severity: str) -> bool:
        """Send webhook notification"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    'message': message,
                    'severity': severity,
                    'timestamp': datetime.now().isoformat()
                }) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Webhook failed: {e}")
            return False
    
    async def _send_email(self, email: str, message: str, severity: str) -> bool:
        """Send email notification"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            # Configure your SMTP settings
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            smtp_user = "your-email@gmail.com"
            smtp_password = "your-password"
            
            msg = MIMEText(message)
            msg['Subject'] = f"[{severity.upper()}] Drone Detection Alert"
            msg['From'] = smtp_user
            msg['To'] = email
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"Email failed: {e}")
            return False
    
    async def _send_mqtt(self, topic: str, message: str, severity: str) -> bool:
        """Send MQTT notification"""
        try:
            import paho.mqtt.publish as publish
            publish.single(topic, payload=json.dumps({
                'message': message,
                'severity': severity,
                'timestamp': datetime.now().isoformat()
            }), hostname="localhost")
            return True
        except Exception as e:
            logger.error(f"MQTT failed: {e}")
            return False
    
    async def _send_telegram(self, bot_token: str, chat_id: str, message: str) -> bool:
        """Send Telegram notification"""
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Telegram failed: {e}")
            return False


class MetricsAggregationWorker(BaseWorker):
    """Aggregates system metrics for monitoring"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Aggregate metrics"""
        period = task.data.get('period', 'hourly')  # hourly, daily, weekly
        db_manager = DatabaseManager()
        
        # Get metrics from database
        metrics = await db_manager.get_metrics(
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now()
        )
        
        # Aggregate by period
        aggregated = self._aggregate_metrics(metrics, period)
        
        # Store aggregated metrics
        await db_manager.store_aggregated_metrics(aggregated)
        
        return aggregated
    
    def _aggregate_metrics(self, metrics: List[Dict], period: str) -> Dict[str, Any]:
        """Aggregate metrics by time period"""
        if period == 'hourly':
            interval = timedelta(hours=1)
        elif period == 'daily':
            interval = timedelta(days=1)
        else:
            interval = timedelta(weeks=1)
        
        # Group by interval
        groups = {}
        for metric in metrics:
            time_key = metric['timestamp'].replace(microsecond=0)
            if period == 'hourly':
                time_key = time_key.replace(minute=0, second=0)
            elif period == 'daily':
                time_key = time_key.replace(hour=0, minute=0, second=0)
            elif period == 'weekly':
                time_key = time_key - timedelta(days=time_key.weekday())
                time_key = time_key.replace(hour=0, minute=0, second=0)
            
            if time_key not in groups:
                groups[time_key] = []
            groups[time_key].append(metric)
        
        # Calculate statistics per group
        aggregated = {
            'period': period,
            'intervals': []
        }
        
        for time_key, group_metrics in groups.items():
            interval_data = {
                'timestamp': time_key.isoformat(),
                'detection_count': len(group_metrics),
                'avg_confidence': np.mean([m.get('confidence', 0) for m in group_metrics]),
                'threat_counts': {
                    'high': sum(1 for m in group_metrics if m.get('threat_level') == 'high'),
                    'medium': sum(1 for m in group_metrics if m.get('threat_level') == 'medium'),
                    'low': sum(1 for m in group_metrics if m.get('threat_level') == 'low')
                },
                'avg_processing_time_ms': np.mean([m.get('processing_time_ms', 0) for m in group_metrics])
            }
            aggregated['intervals'].append(interval_data)
        
        return aggregated


class ModelRetrainingWorker(BaseWorker):
    """Handles ML model retraining tasks"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Retrain ML model"""
        training_data_path = task.data.get('training_data_path', 'data/training/')
        model_path = task.data.get('model_path', 'models/classifier.pkl')
        
        # Run training in process pool (CPU-intensive)
        result = await asyncio.get_event_loop().run_in_executor(
            self.process_pool,
            self._train_model_sync,
            training_data_path,
            model_path
        )
        
        return result
    
    def _train_model_sync(self, training_data_path: str, model_path: str) -> Dict[str, Any]:
        """Synchronous model training"""
        import joblib
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        
        # Load training data
        # This is a placeholder - implement actual data loading
        X_train, X_test, y_train, y_test = self._load_training_data(training_data_path)
        
        # Train model
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        
        # Evaluate
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)
        
        # Save model
        joblib.dump(model, model_path)
        
        return {
            'model_path': model_path,
            'train_accuracy': train_score,
            'test_accuracy': test_score,
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'trained_at': datetime.now().isoformat()
        }
    
    def _load_training_data(self, data_path: str):
        """Load training data from disk"""
        # Implement actual data loading logic
        # This is a placeholder
        import numpy as np
        X = np.random.rand(1000, 20)
        y = np.random.randint(0, 3, 1000)
        return train_test_split(X, y, test_size=0.2, random_state=42)


class IQRecordingWorker(BaseWorker):
    """Records IQ samples to disk for later analysis"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Record IQ data"""
        samples = task.data.get('samples', [])
        sample_rate = task.data.get('sample_rate', 10e6)
        center_freq = task.data.get('center_freq', 2.4e9)
        duration = task.data.get('duration', 10)
        
        # Create session directory
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = Path(f"data/iq/live/session_{session_id}")
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save IQ samples
        iq_file = session_dir / f"frame_{int(time.time())}.iq"
        np.array(samples).astype(np.complex64).tofile(iq_file)
        
        # Save metadata
        metadata = {
            'session_id': session_id,
            'sample_rate': sample_rate,
            'center_freq': center_freq,
            'duration': duration,
            'num_samples': len(samples),
            'timestamp': datetime.now().isoformat(),
            'task_id': task.id
        }
        
        json_file = session_dir / f"frame_{int(time.time())}.json"
        with open(json_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            'session_id': session_id,
            'iq_file': str(iq_file),
            'metadata_file': str(json_file),
            'file_size_bytes': iq_file.stat().st_size,
            'recorded_at': datetime.now().isoformat()
        }


class ReportGenerationWorker(BaseWorker):
    """Generates reports from detection data"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Generate report"""
        report_type = task.data.get('report_type', 'daily')
        format = task.data.get('format', 'json')
        
        db_manager = DatabaseManager()
        
        # Get detection data
        if report_type == 'daily':
            start_time = datetime.now() - timedelta(days=1)
        elif report_type == 'weekly':
            start_time = datetime.now() - timedelta(weeks=1)
        elif report_type == 'monthly':
            start_time = datetime.now() - timedelta(days=30)
        else:
            start_time = datetime.now() - timedelta(days=1)
        
        detections = await db_manager.get_detections(
            start_time=start_time,
            end_time=datetime.now()
        )
        
        # Generate report content
        report_content = self._generate_report_content(detections, report_type)
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d")
        report_dir = Path("data/exports/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        if format == 'json':
            report_file = report_dir / f"{report_type}_report_{timestamp}.json"
            with open(report_file, 'w') as f:
                json.dump(report_content, f, indent=2, default=str)
        elif format == 'markdown':
            report_file = report_dir / f"{report_type}_report_{timestamp}.md"
            with open(report_file, 'w') as f:
                f.write(self._generate_markdown_report(report_content))
        elif format == 'pdf':
            report_file = report_dir / f"{report_type}_report_{timestamp}.pdf"
            await self._generate_pdf_report(report_content, report_file)
        
        return {
            'report_type': report_type,
            'format': format,
            'filepath': str(report_file),
            'detection_count': len(detections),
            'generated_at': datetime.now().isoformat()
        }
    
    def _generate_report_content(self, detections: List[Dict], report_type: str) -> Dict[str, Any]:
        """Generate report content from detections"""
        if not detections:
            return {
                'report_type': report_type,
                'total_detections': 0,
                'message': 'No detections in this period'
            }
        
        return {
            'report_type': report_type,
            'period_start': detections[0].get('timestamp', datetime.now()).isoformat(),
            'period_end': datetime.now().isoformat(),
            'total_detections': len(detections),
            'threat_summary': {
                'high': sum(1 for d in detections if d.get('threat_level') == 'high'),
                'medium': sum(1 for d in detections if d.get('threat_level') == 'medium'),
                'low': sum(1 for d in detections if d.get('threat_level') == 'low')
            },
            'drone_types': self._count_drone_types(detections),
            'hourly_distribution': self._calculate_hourly_distribution(detections),
            'peak_detection_time': self._find_peak_time(detections)
        }
    
    def _count_drone_types(self, detections: List[Dict]) -> Dict[str, int]:
        """Count occurrences of each drone type"""
        counts = {}
        for d in detections:
            drone_type = d.get('drone_type', 'unknown')
            counts[drone_type] = counts.get(drone_type, 0) + 1
        return counts
    
    def _calculate_hourly_distribution(self, detections: List[Dict]) -> Dict[int, int]:
        """Calculate detection distribution by hour"""
        distribution = {h: 0 for h in range(24)}
        for d in detections:
            hour = d.get('timestamp', datetime.now()).hour
            distribution[hour] += 1
        return distribution
    
    def _find_peak_time(self, detections: List[Dict]) -> str:
        """Find peak detection time"""
        hourly = self._calculate_hourly_distribution(detections)
        peak_hour = max(hourly, key=hourly.get)
        return f"{peak_hour:02d}:00"
    
    def _generate_markdown_report(self, content: Dict[str, Any]) -> str:
        """Generate markdown formatted report"""
        lines = [
            f"# {content['report_type'].title()} Drone Detection Report",
            f"Period: {content.get('period_start', 'N/A')} to {content.get('period_end', 'N/A')}",
            f"Total Detections: {content.get('total_detections', 0)}",
            "",
            "## Threat Summary",
            f"- High: {content.get('threat_summary', {}).get('high', 0)}",
            f"- Medium: {content.get('threat_summary', {}).get('medium', 0)}",
            f"- Low: {content.get('threat_summary', {}).get('low', 0)}",
            "",
            "## Drone Types Detected",
        ]
        
        for drone_type, count in content.get('drone_types', {}).items():
            lines.append(f"- {drone_type}: {count}")
        
        lines.append(f"\nPeak Detection Time: {content.get('peak_detection_time', 'N/A')}")
        
        return "\n".join(lines)
    
    async def _generate_pdf_report(self, content: Dict[str, Any], output_path: Path):
        """Generate PDF report"""
        # Implement PDF generation with reportlab or weasyprint
        # This is a placeholder
        pass


class SpectrumAnalysisWorker(BaseWorker):
    """Performs advanced spectrum analysis"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Analyze spectrum data"""
        psd_data = task.data.get('psd', [])
        frequencies = task.data.get('frequencies', [])
        
        analysis = {
            'total_power': float(np.sum(psd_data)),
            'peak_frequency': frequencies[np.argmax(psd_data)] if psd_data else 0,
            'peak_power': float(np.max(psd_data)),
            'average_power': float(np.mean(psd_data)),
            'noise_floor': float(np.percentile(psd_data, 10)),
            'signal_to_noise': 0,
            'occupied_bandwidth': 0,
            'channel_power': {},
            'interference_detected': False
        }
        
        # Calculate SNR
        if analysis['noise_floor'] > 0:
            analysis['signal_to_noise'] = analysis['peak_power'] - analysis['noise_floor']
        
        # Detect occupied bandwidth
        threshold = analysis['noise_floor'] + 6  # 6 dB above noise floor
        above_threshold = np.array(psd_data) > threshold
        if np.any(above_threshold):
            indices = np.where(above_threshold)[0]
            analysis['occupied_bandwidth'] = abs(frequencies[indices[-1]] - frequencies[indices[0]])
        
        # Calculate channel power for common drone bands
        drone_bands = {
            '2.4GHz': (2.4e9, 2.4835e9),
            '5.2GHz': (5.15e9, 5.25e9),
            '5.8GHz': (5.725e9, 5.875e9)
        }
        
        for band_name, (start_freq, end_freq) in drone_bands.items():
            band_indices = [i for i, f in enumerate(frequencies) if start_freq <= f <= end_freq]
            if band_indices:
                band_power = sum(psd_data[i] for i in band_indices)
                analysis['channel_power'][band_name] = float(band_power)
                
                # Detect strong interference
                if band_power > analysis['noise_floor'] * len(band_indices) * 10:
                    analysis['interference_detected'] = True
        
        return analysis


class RemoteIDProcessingWorker(BaseWorker):
    """Processes Remote ID packets from drones"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process Remote ID data"""
        raw_packet = task.data.get('packet', b'')
        rssi = task.data.get('rssi', 0)
        frequency = task.data.get('frequency', 0)
        
        # Decode Remote ID packet (simplified)
        decoded = self._decode_remote_id(raw_packet)
        
        if decoded:
            decoded['rssi'] = rssi
            decoded['frequency'] = frequency
            decoded['processed_at'] = datetime.now().isoformat()
            
            # Store in database
            db_manager = DatabaseManager()
            await db_manager.store_remote_id_data(decoded)
        
        return decoded
    
    def _decode_remote_id(self, packet: bytes) -> Optional[Dict[str, Any]]:
        """Decode Remote ID packet (ASTM F3411)"""
        # This is a simplified implementation
        # Real implementation would parse the actual ASTM F3411 message structure
        
        if len(packet) < 20:
            return None
        
        # Check for Remote ID signature
        # OpenDroneID uses specific service UUIDs in BLE advertisements
        signature = packet[4:8]
        
        # Placeholder - implement actual decoding
        return {
            'uas_id': packet[10:30].hex(),
            'latitude': (int.from_bytes(packet[30:34], 'little') / 1e7) if len(packet) > 34 else 0,
            'longitude': (int.from_bytes(packet[34:38], 'little') / 1e7) if len(packet) > 38 else 0,
            'altitude': int.from_bytes(packet[38:40], 'little') if len(packet) > 40 else 0,
            'speed': int.from_bytes(packet[40:42], 'little') / 100 if len(packet) > 42 else 0,
            'heading': int.from_bytes(packet[42:44], 'little') / 100 if len(packet) > 44 else 0,
            'valid': True
        }


class TDOACalculationWorker(BaseWorker):
    """Performs TDOA multilateration for drone positioning"""
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Calculate drone position using TDOA"""
        signals = task.data.get('signals', [])  # List of (timestamp, receiver_position) tuples
        receiver_positions = task.data.get('receiver_positions', [])
        
        if len(signals) < 3:
            return {'error': 'Need at least 3 receivers for TDOA'}
        
        # Run TDOA calculation in process pool (CPU-intensive)
        result = await asyncio.get_event_loop().run_in_executor(
            self.process_pool,
            self._calculate_position_sync,
            signals,
            receiver_positions
        )
        
        return result
    
    def _calculate_position_sync(self, signals: List[tuple], receiver_positions: List[tuple]) -> Dict[str, Any]:
        """Synchronous TDOA position calculation"""
        # This is a simplified TDOA implementation
        # Real implementation would use hyperbolic multilateration
        
        # Placeholder - return estimated position
        import numpy as np
        
        # Calculate time differences
        time_diffs = []
        for i in range(1, len(signals)):
            time_diffs.append(signals[i][0] - signals[0][0])
        
        # Estimate position using intersection of hyperbolas
        # This is a placeholder implementation
        
        estimated_position = (
            np.mean([p[0] for p in receiver_positions]),
            np.mean([p[1] for p in receiver_positions])
        )
        
        return {
            'latitude': estimated_position[0],
            'longitude': estimated_position[1],
            'altitude': 50.0,  # Estimated
            'error_estimate': 10.0,  # Meters
            'num_receivers': len(signals),
            'computed_at': datetime.now().isoformat()
        }


# ============================================================================
# Worker Factory and Manager
# ============================================================================

class WorkerManager:
    """Singleton manager for worker pool"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if WorkerManager._initialized:
            return
        WorkerManager._initialized = True
        
        self.config = WorkerConfig()
        self.task_queue = TaskQueue(self.config)
        self.worker_pool = WorkerPool(self.config, self.task_queue)
        self._started = False
    
    async def start(self):
        """Start the worker manager"""
        if not self._started:
            await self.worker_pool.start()
            self._started = True
            logger.info("Worker manager started")
    
    async def stop(self):
        """Stop the worker manager"""
        if self._started:
            await self.worker_pool.stop()
            self._started = False
            logger.info("Worker manager stopped")
    
    async def submit_task(self, task_type: TaskType, data: Dict[str, Any], 
                         priority: TaskPriority = TaskPriority.NORMAL,
                         callback: Optional[Callable] = None) -> str:
        """Submit a task to the queue"""
        task = Task(
            id=str(uuid.uuid4()),
            type=task_type,
            priority=priority,
            data=data,
            callback=callback
        )
        
        await self.task_queue.put(task)
        return task.id
    
    async def get_status(self) -> Dict[str, Any]:
        """Get worker manager status"""
        return {
            'started': self._started,
            'worker_pool_status': self.worker_pool.status.value,
            'queue_stats': await self.task_queue.get_stats(),
            'worker_count': len(self.worker_pool.workers)
        }


# ============================================================================
# Convenience Functions
# ============================================================================

_worker_manager: Optional[WorkerManager] = None


async def get_worker_manager() -> WorkerManager:
    """Get or create the worker manager singleton"""
    global _worker_manager
    if _worker_manager is None:
        _worker_manager = WorkerManager()
        await _worker_manager.start()
    return _worker_manager


async def submit_background_task(task_type: TaskType, data: Dict[str, Any],
                                priority: TaskPriority = TaskPriority.NORMAL) -> str:
    """Convenience function to submit a background task"""
    manager = await get_worker_manager()
    return await manager.submit_task(task_type, data, priority)


async def shutdown_workers():
    """Shutdown all workers"""
    global _worker_manager
    if _worker_manager:
        await _worker_manager.stop()
        _worker_manager = None


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of using the worker system
    async def example():
        # Create manager
        manager = await get_worker_manager()
        
        # Submit an IQ processing task
        task_id = await manager.submit_task(
            TaskType.IQ_PROCESSING,
            {
                'samples': [1+1j, 2+2j, 3+3j],  # Example samples
                'sample_rate': 10e6,
                'fft_size': 2048
            },
            priority=TaskPriority.HIGH
        )
        
        print(f"Submitted task: {task_id}")
        
        # Check status
        status = await manager.get_status()
        print(f"Worker status: {status}")
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Shutdown
        await shutdown_workers()
    
    # Run example
    asyncio.run(example())