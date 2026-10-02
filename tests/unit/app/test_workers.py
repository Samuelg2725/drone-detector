#!/usr/bin/env python3
"""
Unit Tests for Background Workers Module

Tests for async task queue, worker pool, and various worker implementations
including IQ processing, detection batch, data export, notifications, etc.
"""

import asyncio
import json
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from datetime import datetime, timedelta
import tempfile
from pathlib import Path
import numpy as np

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.workers import (
    WorkerManager,
    WorkerPool,
    TaskQueue,
    BaseWorker,
    Task,
    TaskType,
    TaskPriority,
    WorkerStatus,
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
    TDOACalculationWorker,
    get_worker_manager,
    submit_background_task,
    shutdown_workers
)


# ============================================================================
# Test Data Generators
# ============================================================================

class TestDataGenerator:
    """Generate test data for worker tests"""
    
    @staticmethod
    def generate_test_samples(num_samples: int = 1000) -> np.ndarray:
        """Generate test IQ samples"""
        return (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)).astype(np.complex64)
    
    @staticmethod
    def generate_test_detection_batch(batch_size: int = 10) -> list:
        """Generate test detection batch"""
        detections = []
        for i in range(batch_size):
            detections.append({
                'id': f'det_{i:03d}',
                'timestamp': datetime.now().isoformat(),
                'drone_type': 'DJI Mavic 3',
                'confidence': 0.7 + i * 0.02,
                'threat_level': 'HIGH' if i % 3 == 0 else 'MEDIUM',
                'frequency': 2.44e9,
                'signal_strength': -45 + i
            })
        return detections
    
    @staticmethod
    def generate_test_export_data(num_records: int = 100) -> list:
        """Generate test export data"""
        return [
            {
                'id': f'record_{i:04d}',
                'timestamp': datetime.now().isoformat(),
                'value': i * 1.5,
                'category': 'test'
            }
            for i in range(num_records)
        ]
    
    @staticmethod
    def generate_test_notification() -> dict:
        """Generate test notification"""
        return {
            'type': 'email',
            'recipients': ['test@example.com'],
            'message': 'Test notification message',
            'severity': 'info',
            'subject': 'Test Subject'
        }
    
    @staticmethod
    def generate_test_remote_id_packet() -> bytes:
        """Generate test Remote ID packet"""
        # Simplified test packet
        packet = bytearray(50)
        packet[0] = 0x01  # Message type
        packet[1:21] = b'UAS1234567890123456'  # UAS ID
        # Add location data
        packet[21:25] = int(37.7749 * 1e7).to_bytes(4, 'little')
        packet[25:29] = int(-122.4194 * 1e7).to_bytes(4, 'little')
        return bytes(packet)


# ============================================================================
# Task and TaskQueue Tests
# ============================================================================

class TestTask(unittest.TestCase):
    """Test Task data class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.task = Task(
            id="task_001",
            type=TaskType.IQ_PROCESSING,
            priority=TaskPriority.HIGH,
            data={'samples': [1, 2, 3]},
            callback=None
        )
    
    def test_task_creation(self):
        """Test task creation"""
        self.assertEqual(self.task.id, "task_001")
        self.assertEqual(self.task.type, TaskType.IQ_PROCESSING)
        self.assertEqual(self.task.priority, TaskPriority.HIGH)
        self.assertEqual(self.task.status, "pending")
    
    def test_task_to_dict(self):
        """Test task to dictionary conversion"""
        task_dict = self.task.to_dict()
        
        self.assertEqual(task_dict['id'], "task_001")
        self.assertEqual(task_dict['type'], "iq_processing")
        self.assertEqual(task_dict['priority'], 0)  # HIGH = 0
        self.assertEqual(task_dict['status'], "pending")
    
    def test_task_completion(self):
        """Test task completion"""
        self.task.completed_at = datetime.now()
        self.task.status = "completed"
        self.task.result = {"processed": True}
        
        self.assertEqual(self.task.status, "completed")
        self.assertIsNotNone(self.task.result)


class TestTaskQueue(unittest.TestCase):
    """Test TaskQueue functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig
        config = WorkerConfig(
            max_queue_size=10,
            enable_persistent_queue=False
        )
        self.queue = TaskQueue(config)
    
    async def test_put_and_get(self):
        """Test putting and getting tasks"""
        task = Task(
            id="task_001",
            type=TaskType.IQ_PROCESSING,
            priority=TaskPriority.NORMAL,
            data={}
        )
        
        await self.queue.put(task)
        retrieved = await self.queue.get()
        
        self.assertEqual(retrieved.id, task.id)
        self.assertEqual(retrieved.type, task.type)
    
    async def test_priority_queue(self):
        """Test priority queue ordering"""
        low_task = Task(
            id="low",
            type=TaskType.IQ_PROCESSING,
            priority=TaskPriority.LOW,
            data={}
        )
        high_task = Task(
            id="high",
            type=TaskType.IQ_PROCESSING,
            priority=TaskPriority.HIGH,
            data={}
        )
        normal_task = Task(
            id="normal",
            type=TaskType.IQ_PROCESSING,
            priority=TaskPriority.NORMAL,
            data={}
        )
        
        await self.queue.put(low_task)
        await self.queue.put(normal_task)
        await self.queue.put(high_task)
        
        # HIGH priority should come first
        first = await self.queue.get()
        self.assertEqual(first.id, "high")
        
        second = await self.queue.get()
        self.assertEqual(second.id, "normal")
        
        third = await self.queue.get()
        self.assertEqual(third.id, "low")
    
    async def test_queue_size_limit(self):
        """Test queue size limit"""
        config = WorkerConfig(max_queue_size=2, enable_persistent_queue=False)
        queue = TaskQueue(config)
        
        for i in range(2):
            task = Task(
                id=f"task_{i}",
                type=TaskType.IQ_PROCESSING,
                priority=TaskPriority.NORMAL,
                data={}
            )
            await queue.put(task)
        
        # Third task should block or be rejected
        task3 = Task(
            id="task_3",
            type=TaskType.IQ_PROCESSING,
            priority=TaskPriority.NORMAL,
            data={}
        )
        
        # Queue should be full
        self.assertEqual(queue._queue.qsize(), 2)
    
    async def test_get_stats(self):
        """Test queue statistics"""
        for i in range(3):
            task = Task(
                id=f"task_{i}",
                type=TaskType.IQ_PROCESSING,
                priority=TaskPriority.NORMAL,
                data={}
            )
            await self.queue.put(task)
        
        stats = await self.queue.get_stats()
        
        self.assertEqual(stats['queue_size'], 3)
        self.assertEqual(stats['pending_tasks'], 3)


# ============================================================================
# BaseWorker Tests
# ============================================================================

class TestBaseWorker(unittest.IsolatedAsyncioTestCase):
    """Test BaseWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = BaseWorker(self.queue, None, None)
    
    async def test_worker_run_stop(self):
        """Test worker run and stop"""
        # Start worker
        asyncio.create_task(self.worker.run())
        await asyncio.sleep(0.1)
        
        self.assertEqual(self.worker.status, WorkerStatus.RUNNING)
        
        # Stop worker
        await self.worker.stop()
        self.assertEqual(self.worker.status, WorkerStatus.STOPPED)
    
    async def test_worker_process_task(self):
        """Test worker processing task"""
        # This should raise NotImplementedError
        with self.assertRaises(NotImplementedError):
            await self.worker.process_task(Task(
                id="test",
                type=TaskType.IQ_PROCESSING,
                priority=TaskPriority.NORMAL,
                data={}
            ))


# ============================================================================
# IQProcessingWorker Tests
# ============================================================================

class TestIQProcessingWorker(unittest.IsolatedAsyncioTestCase):
    """Test IQProcessingWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = IQProcessingWorker(self.queue, None, None)
    
    async def test_process_iq_task(self):
        """Test processing IQ task"""
        samples = TestDataGenerator.generate_test_samples(1000)
        
        task = Task(
            id="iq_task_001",
            type=TaskType.IQ_PROCESSING,
            priority=TaskPriority.NORMAL,
            data={
                'samples': samples.tolist(),
                'sample_rate': 10e6,
                'fft_size': 1024
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertIsNotNone(result)
        self.assertIn('fft', result)
        self.assertIn('psd', result)
        self.assertIn('statistics', result)
    
    async def test_process_empty_samples(self):
        """Test processing empty samples"""
        task = Task(
            id="iq_task_002",
            type=TaskType.IQ_PROCESSING,
            priority=TaskPriority.NORMAL,
            data={
                'samples': [],
                'sample_rate': 10e6,
                'fft_size': 1024
            }
        )
        
        with self.assertRaises(ValueError):
            await self.worker.process_task(task)


# ============================================================================
# DetectionBatchWorker Tests
# ============================================================================

class TestDetectionBatchWorker(unittest.IsolatedAsyncioTestCase):
    """Test DetectionBatchWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = DetectionBatchWorker(self.queue, None, None)
    
    async def test_process_batch_task(self):
        """Test processing detection batch"""
        detections = TestDataGenerator.generate_test_detection_batch(20)
        
        task = Task(
            id="batch_task_001",
            type=TaskType.DETECTION_BATCH,
            priority=TaskPriority.NORMAL,
            data={
                'detections': detections,
                'batch_id': 'batch_001'
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['batch_id'], 'batch_001')
        self.assertEqual(len(result['results']), 20)
        self.assertIn('summary', result)
    
    async def test_process_empty_batch(self):
        """Test processing empty batch"""
        task = Task(
            id="batch_task_002",
            type=TaskType.DETECTION_BATCH,
            priority=TaskPriority.NORMAL,
            data={
                'detections': [],
                'batch_id': 'batch_empty'
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertEqual(result['summary']['total'], 0)


# ============================================================================
# DataExportWorker Tests
# ============================================================================

class TestDataExportWorker(unittest.IsolatedAsyncioTestCase):
    """Test DataExportWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = DataExportWorker(self.queue, None, None)
        self.temp_dir = tempfile.mkdtemp()
    
    async def test_export_json(self):
        """Test JSON export"""
        data = TestDataGenerator.generate_test_export_data(50)
        
        task = Task(
            id="export_task_001",
            type=TaskType.DATA_EXPORT,
            priority=TaskPriority.NORMAL,
            data={
                'export_type': 'json',
                'data': data,
                'export_dir': self.temp_dir
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertEqual(result['export_type'], 'json')
        self.assertEqual(result['record_count'], 50)
        self.assertTrue(result['filepath'].endswith('.json'))
    
    async def test_export_csv(self):
        """Test CSV export"""
        data = TestDataGenerator.generate_test_export_data(50)
        
        task = Task(
            id="export_task_002",
            type=TaskType.DATA_EXPORT,
            priority=TaskPriority.NORMAL,
            data={
                'export_type': 'csv',
                'data': data,
                'export_dir': self.temp_dir
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertEqual(result['export_type'], 'csv')
        self.assertTrue(result['filepath'].endswith('.csv'))


# ============================================================================
# DatabaseCleanupWorker Tests
# ============================================================================

class TestDatabaseCleanupWorker(unittest.IsolatedAsyncioTestCase):
    """Test DatabaseCleanupWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = DatabaseCleanupWorker(self.queue, None, None)
    
    @patch('app.workers.DatabaseManager')
    async def test_cleanup_task(self, MockDB):
        """Test database cleanup task"""
        mock_db = AsyncMock()
        MockDB.return_value = mock_db
        mock_db.delete_old_detections.return_value = 100
        mock_db.vacuum.return_value = None
        
        task = Task(
            id="cleanup_task_001",
            type=TaskType.DATABASE_CLEANUP,
            priority=TaskPriority.LOW,
            data={
                'retention_days': 30,
                'vacuum': True
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertEqual(result['deleted_detections'], 100)
        self.assertTrue(result['vacuum_performed'])


# ============================================================================
# NotificationWorker Tests
# ============================================================================

class TestNotificationWorker(unittest.IsolatedAsyncioTestCase):
    """Test NotificationWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = NotificationWorker(self.queue, None, None)
    
    async def test_webhook_notification(self):
        """Test webhook notification"""
        notification = TestDataGenerator.generate_test_notification()
        notification['type'] = 'webhook'
        notification['webhook_url'] = 'http://localhost:9999/webhook'
        
        task = Task(
            id="notify_task_001",
            type=TaskType.NOTIFICATION,
            priority=TaskPriority.NORMAL,
            data=notification
        )
        
        # Mock the webhook call
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await self.worker.process_task(task)
            
            self.assertEqual(result['notification_type'], 'webhook')
            self.assertEqual(result['sent_count'], 1)
    
    async def test_email_notification(self):
        """Test email notification"""
        notification = TestDataGenerator.generate_test_notification()
        notification['type'] = 'email'
        
        task = Task(
            id="notify_task_002",
            type=TaskType.NOTIFICATION,
            priority=TaskPriority.NORMAL,
            data=notification
        )
        
        # Mock email sending
        with patch('smtplib.SMTP') as mock_smtp:
            result = await self.worker.process_task(task)
            
            self.assertEqual(result['notification_type'], 'email')


# ============================================================================
# MetricsAggregationWorker Tests
# ============================================================================

class TestMetricsAggregationWorker(unittest.IsolatedAsyncioTestCase):
    """Test MetricsAggregationWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = MetricsAggregationWorker(self.queue, None, None)
    
    @patch('app.workers.DatabaseManager')
    async def test_aggregate_metrics(self, MockDB):
        """Test metrics aggregation"""
        mock_db = AsyncMock()
        MockDB.return_value = mock_db
        
        # Mock metrics data
        mock_metrics = [
            {'timestamp': datetime.now(), 'confidence': 0.95, 'threat_level': 'HIGH', 'processing_time_ms': 45},
            {'timestamp': datetime.now() - timedelta(hours=1), 'confidence': 0.87, 'threat_level': 'MEDIUM', 'processing_time_ms': 52},
            {'timestamp': datetime.now() - timedelta(hours=2), 'confidence': 0.76, 'threat_level': 'LOW', 'processing_time_ms': 38}
        ]
        mock_db.get_metrics.return_value = mock_metrics
        
        task = Task(
            id="metrics_task_001",
            type=TaskType.METRICS_AGGREGATION,
            priority=TaskPriority.LOW,
            data={
                'period': 'hourly'
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertEqual(result['period'], 'hourly')
        self.assertIn('intervals', result)


# ============================================================================
# ModelRetrainingWorker Tests
# ============================================================================

class TestModelRetrainingWorker(unittest.IsolatedAsyncioTestCase):
    """Test ModelRetrainingWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = ModelRetrainingWorker(self.queue, None, None)
    
    @patch('app.workers.joblib')
    @patch('app.workers.RandomForestClassifier')
    async def test_retrain_model(self, MockClassifier, MockJoblib):
        """Test model retraining"""
        mock_model = Mock()
        MockClassifier.return_value = mock_model
        mock_model.fit.return_value = None
        mock_model.score.return_value = 0.95
        
        task = Task(
            id="train_task_001",
            type=TaskType.MODEL_RETRAINING,
            priority=TaskPriority.LOW,
            data={
                'training_data_path': '/tmp/training',
                'model_path': '/tmp/model.pkl'
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertIn('model_path', result)
        self.assertIn('train_accuracy', result)
        self.assertIn('test_accuracy', result)


# ============================================================================
# IQRecordingWorker Tests
# ============================================================================

class TestIQRecordingWorker(unittest.IsolatedAsyncioTestCase):
    """Test IQRecordingWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = IQRecordingWorker(self.queue, None, None)
        self.temp_dir = tempfile.mkdtemp()
    
    async def test_record_iq(self):
        """Test IQ recording"""
        samples = TestDataGenerator.generate_test_samples(10000)
        
        task = Task(
            id="record_task_001",
            type=TaskType.IQ_RECORDING,
            priority=TaskPriority.NORMAL,
            data={
                'samples': samples.tolist(),
                'sample_rate': 10e6,
                'center_freq': 2.44e9,
                'duration': 1.0
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertIsNotNone(result)
        self.assertIn('session_id', result)
        self.assertIn('iq_file', result)
        self.assertIn('metadata_file', result)


# ============================================================================
# ReportGenerationWorker Tests
# ============================================================================

class TestReportGenerationWorker(unittest.IsolatedAsyncioTestCase):
    """Test ReportGenerationWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = ReportGenerationWorker(self.queue, None, None)
        self.temp_dir = tempfile.mkdtemp()
    
    @patch('app.workers.DatabaseManager')
    async def test_generate_report(self, MockDB):
        """Test report generation"""
        mock_db = AsyncMock()
        MockDB.return_value = mock_db
        
        mock_db.get_detections.return_value = [
            {'timestamp': datetime.now(), 'threat_level': 'HIGH'},
            {'timestamp': datetime.now(), 'threat_level': 'MEDIUM'},
            {'timestamp': datetime.now() - timedelta(hours=1), 'threat_level': 'LOW'}
        ]
        
        task = Task(
            id="report_task_001",
            type=TaskType.REPORT_GENERATION,
            priority=TaskPriority.NORMAL,
            data={
                'report_type': 'daily',
                'format': 'json'
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertEqual(result['report_type'], 'daily')
        self.assertEqual(result['detection_count'], 3)


# ============================================================================
# SpectrumAnalysisWorker Tests
# ============================================================================

class TestSpectrumAnalysisWorker(unittest.IsolatedAsyncioTestCase):
    """Test SpectrumAnalysisWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = SpectrumAnalysisWorker(self.queue, None, None)
    
    async def test_analyze_spectrum(self):
        """Test spectrum analysis"""
        frequencies = np.linspace(2.4e9, 2.5e9, 1000)
        psd = -80 + 20 * np.random.randn(1000)
        # Add a peak
        psd[500] = -45
        
        task = Task(
            id="spectrum_task_001",
            type=TaskType.SPECTRUM_ANALYSIS,
            priority=TaskPriority.NORMAL,
            data={
                'psd': psd.tolist(),
                'frequencies': frequencies.tolist()
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertIn('total_power', result)
        self.assertIn('peak_frequency', result)
        self.assertIn('signal_to_noise', result)
        self.assertIn('channel_power', result)


# ============================================================================
# RemoteIDProcessingWorker Tests
# ============================================================================

class TestRemoteIDProcessingWorker(unittest.IsolatedAsyncioTestCase):
    """Test RemoteIDProcessingWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = RemoteIDProcessingWorker(self.queue, None, None)
    
    async def test_process_remote_id(self):
        """Test Remote ID processing"""
        packet = TestDataGenerator.generate_test_remote_id_packet()
        
        task = Task(
            id="remoteid_task_001",
            type=TaskType.REMOTE_ID_PROCESSING,
            priority=TaskPriority.NORMAL,
            data={
                'packet': packet.hex(),
                'rssi': -65,
                'frequency': 2.402e9
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertIsNotNone(result)
        self.assertIn('uas_id', result)
        self.assertIn('latitude', result)
        self.assertIn('longitude', result)
        self.assertEqual(result['rssi'], -65)


# ============================================================================
# TDOACalculationWorker Tests
# ============================================================================

class TestTDOACalculationWorker(unittest.IsolatedAsyncioTestCase):
    """Test TDOACalculationWorker functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig, TaskQueue
        config = WorkerConfig(max_queue_size=10)
        self.queue = TaskQueue(config)
        self.worker = TDOACalculationWorker(self.queue, None, None)
    
    async def test_tdoa_calculation(self):
        """Test TDOA calculation"""
        signals = [
            (0.0, (0, 0, 0)),
            (1e-6, (100, 0, 0)),
            (0.5e-6, (50, 86.6, 0))
        ]
        receiver_positions = [(0, 0, 0), (100, 0, 0), (50, 86.6, 0)]
        
        task = Task(
            id="tdoa_task_001",
            type=TaskType.TDOA_CALCULATION,
            priority=TaskPriority.NORMAL,
            data={
                'signals': signals,
                'receiver_positions': receiver_positions
            }
        )
        
        result = await self.worker.process_task(task)
        
        self.assertIsNotNone(result)
        self.assertIn('latitude', result)
        self.assertIn('longitude', result)


# ============================================================================
# WorkerManager Tests
# ============================================================================

class TestWorkerManager(unittest.IsolatedAsyncioTestCase):
    """Test WorkerManager functionality"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        from app.workers import WorkerConfig
        self.manager = WorkerManager()
    
    async def test_start_stop(self):
        """Test starting and stopping manager"""
        await self.manager.start()
        self.assertTrue(self.manager._started)
        
        await self.manager.stop()
        self.assertFalse(self.manager._started)
    
    async def test_submit_task(self):
        """Test submitting task"""
        await self.manager.start()
        
        task_id = await self.manager.submit_task(
            TaskType.IQ_PROCESSING,
            {'samples': [1, 2, 3]},
            priority=TaskPriority.NORMAL
        )
        
        self.assertIsNotNone(task_id)
        
        await self.manager.stop()
    
    async def test_get_status(self):
        """Test getting manager status"""
        await self.manager.start()
        
        status = await self.manager.get_status()
        
        self.assertTrue(status['started'])
        self.assertIn('worker_pool_status', status)
        self.assertIn('queue_stats', status)
        
        await self.manager.stop()


# ============================================================================
# Global Functions Tests
# ============================================================================

class TestGlobalFunctions(unittest.IsolatedAsyncioTestCase):
    """Test global convenience functions"""
    
    async def test_get_worker_manager_singleton(self):
        """Test getting worker manager singleton"""
        manager1 = await get_worker_manager()
        manager2 = await get_worker_manager()
        
        self.assertIs(manager1, manager2)
    
    async def test_submit_background_task(self):
        """Test submitting background task via convenience function"""
        task_id = await submit_background_task(
            TaskType.IQ_PROCESSING,
            {'samples': [1, 2, 3]},
            priority=TaskPriority.NORMAL
        )
        
        self.assertIsNotNone(task_id)
    
    async def test_shutdown_workers(self):
        """Test shutting down workers"""
        await get_worker_manager()  # Ensure manager exists
        await shutdown_workers()
        
        # Manager should be reset
        from app.workers import _worker_manager
        self.assertIsNone(_worker_manager)


# ============================================================================
# Run Tests
# ============================================================================

async def run_async_tests():
    """Run async test methods"""
    test_classes = [
        TestTask,
        TestTaskQueue,
        TestIQProcessingWorker,
        TestDetectionBatchWorker,
        TestDataExportWorker,
        TestDatabaseCleanupWorker,
        TestNotificationWorker,
        TestMetricsAggregationWorker,
        TestModelRetrainingWorker,
        TestIQRecordingWorker,
        TestReportGenerationWorker,
        TestSpectrumAnalysisWorker,
        TestRemoteIDProcessingWorker,
        TestTDOACalculationWorker,
        TestWorkerManager,
        TestGlobalFunctions
    ]
    
    for test_class in test_classes:
        print(f"\nRunning {test_class.__name__}...")
        
        # For TestCase classes, run normally
        if issubclass(test_class, unittest.TestCase):
            suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            unittest.TextTestRunner(verbosity=2).run(suite)
        else:
            # For IsolatedAsyncioTestCase classes
            instance = test_class()
            await instance.asyncSetUp()
            
            # Run async methods
            for method_name in dir(instance):
                if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(instance, method_name)):
                    method = getattr(instance, method_name)
                    await method()
            
            await instance.asyncTearDown()


if __name__ == '__main__':
    # Run async tests
    import asyncio
    asyncio.run(run_async_tests())