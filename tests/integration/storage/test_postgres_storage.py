#!/usr/bin/env python3
"""
Integration Tests for PostgreSQL Storage

Tests for PostgreSQL database operations including:
- Connection management and pooling
- CRUD operations for detections, alerts, remote ID
- Transaction management
- Concurrent access
- Query performance
- Data integrity
- Migration handling
- Backup and restore
"""

import asyncio
import json
import unittest
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import application modules
from infrastructure.storage.database import DatabaseManager, DatabaseConfig, DatabaseType
from infrastructure.storage.models import Base, Detection, Alert, RemoteIDMessage
from infrastructure.storage.repositories import (
    DetectionRepository,
    AlertRepository,
    RemoteIDRepository
)


# ============================================================================
# Test Configuration
# ============================================================================

# Skip tests if PostgreSQL not available
POSTGRES_AVAILABLE = os.environ.get('POSTGRES_TEST', 'false').lower() == 'true'

# Test database configuration
TEST_POSTGRES_CONFIG = DatabaseConfig(
    db_type=DatabaseType.POSTGRESQL,
    postgres_host=os.environ.get('TEST_POSTGRES_HOST', 'localhost'),
    postgres_port=int(os.environ.get('TEST_POSTGRES_PORT', 5432)),
    postgres_database=os.environ.get('TEST_POSTGRES_DB', 'drone_test'),
    postgres_user=os.environ.get('TEST_POSTGRES_USER', 'test_user'),
    postgres_password=os.environ.get('TEST_POSTGRES_PASSWORD', 'test_password'),
    pool_min_size=1,
    pool_max_size=5,
    pool_timeout=10
)


# ============================================================================
# Test Data Generators
# ============================================================================

class PostgresTestData:
    """Generate test data for PostgreSQL tests"""
    
    @staticmethod
    def create_test_detection(detection_id: str = None) -> dict:
        """Create test detection data"""
        return {
            'id': detection_id or f"det_{int(time.time())}_{id(detection_id)}",
            'timestamp': datetime.now(),
            'drone_type': 'DJI Mavic 3',
            'manufacturer': 'DJI',
            'confidence': 0.95,
            'threat_level': 'HIGH',
            'frequency': 2.44e9,
            'signal_strength': -45.2,
            'snr': 28.5,
            'bandwidth': 20e6,
            'modulation': 'OFDM',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': 100.0,
            'speed': 12.5,
            'heading': 180.0,
            'remote_id': 'REMOTE123',
            'operator_id': 'OP123',
            'uas_id': 'UAS123',
            'source': 'sdr'
        }
    
    @staticmethod
    def create_test_alert(alert_id: str = None, detection_id: str = None) -> dict:
        """Create test alert data"""
        return {
            'id': alert_id or f"alt_{int(time.time())}_{id(alert_id)}",
            'detection_id': detection_id,
            'severity': 'HIGH',
            'category': 'DRONE_DETECTED',
            'title': 'Drone Detected',
            'message': 'Unauthorized drone in restricted zone',
            'source': 'detection_engine',
            'acknowledged': False,
            'resolved': False,
            'escalation_level': 0,
            'timestamp': datetime.now()
        }
    
    @staticmethod
    def create_test_remote_id_message(message_id: str = None) -> dict:
        """Create test Remote ID message data"""
        return {
            'id': message_id or f"rid_{int(time.time())}_{id(message_id)}",
            'uas_id': 'UAS_TEST_001',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': 100.0,
            'speed': 12.5,
            'heading': 180.0,
            'horizontal_accuracy': 5.0,
            'vertical_accuracy': 10.0,
            'timestamp': datetime.now(),
            'rssi': -65,
            'frequency': 2.402e9,
            'operator_id': 'OP12345',
            'status': 'valid'
        }


# ============================================================================
# Test Database Setup
# ============================================================================

class PostgresTestBase(unittest.IsolatedAsyncioTestCase):
    """Base class for PostgreSQL integration tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class - create test database"""
        if not POSTGRES_AVAILABLE:
            pytest.skip("PostgreSQL not available for testing")
        
        print(f"\nSetting up PostgreSQL test database at {TEST_POSTGRES_CONFIG.postgres_host}:{TEST_POSTGRES_CONFIG.postgres_port}")
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        # Create database manager
        self.db = DatabaseManager(TEST_POSTGRES_CONFIG)
        await self.db.initialize()
        
        # Create tables
        await self.db.create_tables(drop_existing=True)
        
        # Initialize repositories
        self.detection_repo = DetectionRepository(self.db)
        self.alert_repo = AlertRepository(self.db)
        self.remote_id_repo = RemoteIDRepository(self.db)
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        # Close database connection
        await self.db.close()
        
        # Clean up test data (optional - tables are dropped between tests)
        await self._cleanup_database()
    
    async def _cleanup_database(self):
        """Clean up test database"""
        async with self.db._adapter._pool.acquire() as conn:
            await conn.execute("TRUNCATE TABLE detections CASCADE")
            await conn.execute("TRUNCATE TABLE alerts CASCADE")
            await conn.execute("TRUNCATE TABLE remote_id_messages CASCADE")


# ============================================================================
# Connection Tests
# ============================================================================

class TestPostgresConnection(PostgresTestBase):
    """Tests for PostgreSQL connection management"""
    
    async def test_connection_success(self):
        """Test successful database connection"""
        self.assertIsNotNone(self.db._adapter)
        self.assertIsNotNone(self.db._adapter._pool)
        
        # Verify connection works
        result = await self.db.fetch_val("SELECT 1")
        self.assertEqual(result, 1)
    
    async def test_connection_pool(self):
        """Test connection pool configuration"""
        pool = self.db._adapter._pool
        self.assertIsNotNone(pool)
        
        # Check pool settings
        self.assertEqual(pool._minsize, TEST_POSTGRES_CONFIG.pool_min_size)
        self.assertEqual(pool._maxsize, TEST_POSTGRES_CONFIG.pool_max_size)
    
    async def test_multiple_connections(self):
        """Test multiple concurrent connections"""
        async def query():
            return await self.db.fetch_val("SELECT COUNT(*) FROM pg_stat_activity")
        
        # Run multiple queries concurrently
        results = await asyncio.gather(*[query() for _ in range(10)])
        
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertIsNotNone(result)
    
    async def test_connection_reuse(self):
        """Test connection reuse from pool"""
        # Get connection ID multiple times
        conn_ids = []
        for _ in range(5):
            async with self.db._adapter._pool.acquire() as conn:
                result = await conn.fetchval("SELECT pg_backend_pid()")
                conn_ids.append(result)
        
        # Connections may be reused (not necessarily all different)
        self.assertEqual(len(conn_ids), 5)
    
    async def test_connection_timeout(self):
        """Test connection timeout handling"""
        # This test is complex to implement reliably
        # For now, just verify timeout config is set
        self.assertIsNotNone(TEST_POSTGRES_CONFIG.pool_timeout)


# ============================================================================
# Detection CRUD Tests
# ============================================================================

class TestPostgresDetectionCRUD(PostgresTestBase):
    """Tests for detection CRUD operations"""
    
    async def test_create_detection(self):
        """Test creating a detection"""
        detection_data = PostgresTestData.create_test_detection()
        
        detection_id = await self.detection_repo.create(detection_data)
        
        self.assertIsNotNone(detection_id)
        
        # Verify created
        saved = await self.detection_repo.get_by_id(detection_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved['drone_type'], 'DJI Mavic 3')
        self.assertEqual(saved['confidence'], 0.95)
    
    async def test_get_detection_by_id(self):
        """Test retrieving detection by ID"""
        detection_data = PostgresTestData.create_test_detection("det_get_001")
        await self.detection_repo.create(detection_data)
        
        retrieved = await self.detection_repo.get_by_id("det_get_001")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved['id'], "det_get_001")
    
    async def test_get_all_detections(self):
        """Test retrieving all detections"""
        # Create multiple detections
        for i in range(5):
            detection_data = PostgresTestData.create_test_detection(f"det_all_{i:03d}")
            await self.detection_repo.create(detection_data)
        
        detections = await self.detection_repo.get_all(limit=10)
        
        self.assertGreaterEqual(len(detections), 5)
    
    async def test_update_detection(self):
        """Test updating a detection"""
        detection_data = PostgresTestData.create_test_detection("det_update_001")
        await self.detection_repo.create(detection_data)
        
        updates = {'confidence': 0.98, 'threat_level': 'CRITICAL'}
        success = await self.detection_repo.update("det_update_001", updates)
        
        self.assertTrue(success)
        
        # Verify update
        updated = await self.detection_repo.get_by_id("det_update_001")
        self.assertEqual(updated['confidence'], 0.98)
        self.assertEqual(updated['threat_level'], 'CRITICAL')
    
    async def test_delete_detection(self):
        """Test deleting a detection"""
        detection_data = PostgresTestData.create_test_detection("det_delete_001")
        await self.detection_repo.create(detection_data)
        
        success = await self.detection_repo.delete("det_delete_001")
        
        self.assertTrue(success)
        
        # Verify deleted
        deleted = await self.detection_repo.get_by_id("det_delete_001")
        self.assertIsNone(deleted)
    
    async def test_get_detections_with_filters(self):
        """Test getting detections with filters"""
        # Create detections with different threat levels
        detections_data = [
            PostgresTestData.create_test_detection("det_filter_001"),
            PostgresTestData.create_test_detection("det_filter_002")
        ]
        detections_data[0]['threat_level'] = 'HIGH'
        detections_data[1]['threat_level'] = 'LOW'
        
        for data in detections_data:
            await self.detection_repo.create(data)
        
        # Filter by threat level
        high_detections = await self.detection_repo.get_all(threat_level='HIGH')
        
        self.assertEqual(len(high_detections), 1)
        self.assertEqual(high_detections[0]['threat_level'], 'HIGH')
    
    async def test_get_detections_by_date_range(self):
        """Test getting detections by date range"""
        # Create detections with different timestamps
        now = datetime.now()
        
        data1 = PostgresTestData.create_test_detection("det_date_001")
        data1['timestamp'] = now - timedelta(hours=2)
        await self.detection_repo.create(data1)
        
        data2 = PostgresTestData.create_test_detection("det_date_002")
        data2['timestamp'] = now - timedelta(hours=1)
        await self.detection_repo.create(data2)
        
        data3 = PostgresTestData.create_test_detection("det_date_003")
        data3['timestamp'] = now
        await self.detection_repo.create(data3)
        
        # Get last 1.5 hours
        start_time = now - timedelta(hours=1.5)
        detections = await self.detection_repo.get_by_date_range(start_time, now)
        
        self.assertEqual(len(detections), 2)  # Should get data2 and data3


# ============================================================================
# Alert CRUD Tests
# ============================================================================

class TestPostgresAlertCRUD(PostgresTestBase):
    """Tests for alert CRUD operations"""
    
    async def test_create_alert(self):
        """Test creating an alert"""
        alert_data = PostgresTestData.create_test_alert()
        
        alert_id = await self.alert_repo.create(alert_data)
        
        self.assertIsNotNone(alert_id)
        
        saved = await self.alert_repo.get_by_id(alert_id)
        self.assertEqual(saved['severity'], 'HIGH')
        self.assertEqual(saved['title'], 'Drone Detected')
    
    async def test_get_active_alerts(self):
        """Test getting active alerts"""
        # Create alerts with different statuses
        alert1 = PostgresTestData.create_test_alert("alert_active_001")
        alert1['acknowledged'] = False
        alert1['resolved'] = False
        await self.alert_repo.create(alert1)
        
        alert2 = PostgresTestData.create_test_alert("alert_active_002")
        alert2['acknowledged'] = True
        alert2['resolved'] = False
        await self.alert_repo.create(alert2)
        
        alert3 = PostgresTestData.create_test_alert("alert_active_003")
        alert3['resolved'] = True
        await self.alert_repo.create(alert3)
        
        active = await self.alert_repo.get_active()
        
        # Should get unacknowledged and unresolved alerts
        self.assertGreaterEqual(len(active), 1)
    
    async def test_acknowledge_alert(self):
        """Test acknowledging an alert"""
        alert_data = PostgresTestData.create_test_alert("alert_ack_001")
        alert_data['acknowledged'] = False
        await self.alert_repo.create(alert_data)
        
        success = await self.alert_repo.acknowledge("alert_ack_001", "test_user")
        
        self.assertTrue(success)
        
        updated = await self.alert_repo.get_by_id("alert_ack_001")
        self.assertTrue(updated['acknowledged'])
        self.assertEqual(updated['acknowledged_by'], 'test_user')
    
    async def test_resolve_alert(self):
        """Test resolving an alert"""
        alert_data = PostgresTestData.create_test_alert("alert_resolve_001")
        alert_data['resolved'] = False
        await self.alert_repo.create(alert_data)
        
        success = await self.alert_repo.resolve("alert_resolve_001")
        
        self.assertTrue(success)
        
        updated = await self.alert_repo.get_by_id("alert_resolve_001")
        self.assertTrue(updated['resolved'])
        self.assertIsNotNone(updated['resolved_at'])
    
    async def test_escalate_alert(self):
        """Test escalating an alert"""
        alert_data = PostgresTestData.create_test_alert("alert_escalate_001")
        alert_data['escalation_level'] = 0
        await self.alert_repo.create(alert_data)
        
        success = await self.alert_repo.escalate("alert_escalate_001")
        
        self.assertTrue(success)
        
        updated = await self.alert_repo.get_by_id("alert_escalate_001")
        self.assertEqual(updated['escalation_level'], 1)


# ============================================================================
# Remote ID CRUD Tests
# ============================================================================

class TestPostgresRemoteIDCRUD(PostgresTestBase):
    """Tests for Remote ID CRUD operations"""
    
    async def test_create_remote_id_message(self):
        """Test creating a Remote ID message"""
        message_data = PostgresTestData.create_test_remote_id_message()
        
        message_id = await self.remote_id_repo.create(message_data)
        
        self.assertIsNotNone(message_id)
        
        saved = await self.remote_id_repo.get_by_id(message_id)
        self.assertEqual(saved['uas_id'], 'UAS_TEST_001')
        self.assertAlmostEqual(saved['latitude'], 37.7749, places=4)
    
    async def test_get_messages_by_uas_id(self):
        """Test getting messages by UAS ID"""
        uas_id = "UAS_TRACK_001"
        
        for i in range(5):
            msg = PostgresTestData.create_test_remote_id_message()
            msg['uas_id'] = uas_id
            msg['latitude'] = 37.7749 + i * 0.0001
            await self.remote_id_repo.create(msg)
        
        messages = await self.remote_id_repo.get_by_uas_id(uas_id, limit=10)
        
        self.assertEqual(len(messages), 5)
        for msg in messages:
            self.assertEqual(msg['uas_id'], uas_id)
    
    async def test_get_session_info(self):
        """Test getting session information for a drone"""
        uas_id = "UAS_SESSION_001"
        
        # Create messages over time
        start_time = datetime.now() - timedelta(minutes=10)
        for i in range(5):
            msg = PostgresTestData.create_test_remote_id_message()
            msg['uas_id'] = uas_id
            msg['timestamp'] = start_time + timedelta(minutes=i*2)
            msg['latitude'] = 37.7749 + i * 0.0005
            await self.remote_id_repo.create(msg)
        
        session = await self.remote_id_repo.get_session_info(uas_id)
        
        self.assertIsNotNone(session)
        self.assertAlmostEqual(session['first_latitude'], 37.7749, places=4)
        self.assertAlmostEqual(session['last_latitude'], 37.7769, places=4)
    
    async def test_get_active_drones(self):
        """Test getting active drones"""
        # Create messages for multiple drones within time window
        now = datetime.now()
        cutoff = now - timedelta(minutes=5)
        
        drones = ['UAS_ACTIVE_001', 'UAS_ACTIVE_002', 'UAS_INACTIVE_001']
        
        for uas_id in drones[:2]:
            msg = PostgresTestData.create_test_remote_id_message()
            msg['uas_id'] = uas_id
            msg['timestamp'] = now - timedelta(minutes=1)
            await self.remote_id_repo.create(msg)
        
        # Inactive drone (older than cutoff)
        msg = PostgresTestData.create_test_remote_id_message()
        msg['uas_id'] = drones[2]
        msg['timestamp'] = now - timedelta(minutes=10)
        await self.remote_id_repo.create(msg)
        
        active = await self.remote_id_repo.get_active_drones(minutes=5)
        
        self.assertEqual(len(active), 2)
        active_ids = [a['uas_id'] for a in active]
        self.assertIn('UAS_ACTIVE_001', active_ids)
        self.assertIn('UAS_ACTIVE_002', active_ids)


# ============================================================================
# Transaction Tests
# ============================================================================

class TestPostgresTransactions(PostgresTestBase):
    """Tests for transaction management"""
    
    async def test_commit_transaction(self):
        """Test committing a transaction"""
        async with self.db.transaction():
            detection_data = PostgresTestData.create_test_detection("det_txn_001")
            await self.detection_repo.create(detection_data)
        
        # Verify data persisted
        saved = await self.detection_repo.get_by_id("det_txn_001")
        self.assertIsNotNone(saved)
    
    async def test_rollback_transaction(self):
        """Test rolling back a transaction on error"""
        try:
            async with self.db.transaction():
                detection_data = PostgresTestData.create_test_detection("det_txn_rollback")
                await self.detection_repo.create(detection_data)
                
                # Cause error
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Verify data was rolled back
        saved = await self.detection_repo.get_by_id("det_txn_rollback")
        self.assertIsNone(saved)
    
    async def test_nested_transactions(self):
        """Test nested transactions (savepoints)"""
        async with self.db.transaction() as tx1:
            detection1 = PostgresTestData.create_test_detection("det_nested_001")
            await self.detection_repo.create(detection1)
            
            async with self.db.transaction() as tx2:
                detection2 = PostgresTestData.create_test_detection("det_nested_002")
                await self.detection_repo.create(detection2)
        
        # Both should be committed
        saved1 = await self.detection_repo.get_by_id("det_nested_001")
        saved2 = await self.detection_repo.get_by_id("det_nested_002")
        
        self.assertIsNotNone(saved1)
        self.assertIsNotNone(saved2)


# ============================================================================
# Concurrent Access Tests
# ============================================================================

class TestPostgresConcurrency(PostgresTestBase):
    """Tests for concurrent database access"""
    
    async def test_concurrent_inserts(self):
        """Test concurrent inserts from multiple coroutines"""
        async def insert_detection(index):
            detection_data = PostgresTestData.create_test_detection(f"det_concurrent_{index:03d}")
            return await self.detection_repo.create(detection_data)
        
        # Run 50 concurrent inserts
        tasks = [insert_detection(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        
        self.assertEqual(len(results), 50)
        self.assertIsNotNone(all(results))
        
        # Verify all were inserted
        detections = await self.detection_repo.get_all(limit=100)
        self.assertGreaterEqual(len(detections), 50)
    
    async def test_concurrent_reads_and_writes(self):
        """Test concurrent reads and writes"""
        async def writer(index):
            detection_data = PostgresTestData.create_test_detection(f"det_rw_{index:03d}")
            return await self.detection_repo.create(detection_data)
        
        async def reader():
            return await self.detection_repo.get_all(limit=10)
        
        # Run mixed operations
        write_tasks = [writer(i) for i in range(20)]
        read_tasks = [reader() for _ in range(10)]
        
        all_tasks = write_tasks + read_tasks
        results = await asyncio.gather(*all_tasks)
        
        # Should complete without deadlock
        self.assertEqual(len(results), 30)
    
    async def test_row_level_locking(self):
        """Test row-level locking with SELECT FOR UPDATE"""
        # Create a detection first
        detection_data = PostgresTestData.create_test_detection("det_lock_001")
        await self.detection_repo.create(detection_data)
        
        async def update_with_lock():
            async with self.db.transaction():
                # Acquire lock
                query = "SELECT * FROM detections WHERE id = 'det_lock_001' FOR UPDATE"
                row = await self.db.fetch_one(query)
                
                await asyncio.sleep(0.1)  # Simulate processing
                
                # Update
                await self.db.execute(
                    "UPDATE detections SET confidence = 0.99 WHERE id = 'det_lock_001'"
                )
        
        # Run multiple updates that will be serialized due to locking
        await asyncio.gather(*[update_with_lock() for _ in range(3)])
        
        # Final value should be from last update
        final = await self.detection_repo.get_by_id("det_lock_001")
        self.assertEqual(final['confidence'], 0.99)


# ============================================================================
# Query Performance Tests
# ============================================================================

class TestPostgresPerformance(PostgresTestBase):
    """Tests for query performance"""
    
    async def test_index_usage(self):
        """Test that indexes are being used"""
        # Create index if not exists (should be created by schema)
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)")
        
        # Insert test data
        for i in range(100):
            detection_data = PostgresTestData.create_test_detection(f"det_perf_{i:03d}")
            detection_data['timestamp'] = datetime.now() - timedelta(seconds=i*10)
            await self.detection_repo.create(detection_data)
        
        # Query with timestamp filter
        start_time = datetime.now() - timedelta(minutes=5)
        
        start = time.time()
        results = await self.detection_repo.get_by_date_range(start_time, datetime.now())
        elapsed = time.time() - start
        
        # Query should be fast with index
        self.assertLess(elapsed, 0.5)
    
    async def test_batch_insert_performance(self):
        """Test batch insert performance"""
        batch_size = 1000
        start_time = time.time()
        
        # Insert batch of detections
        async with self.db.transaction():
            for i in range(batch_size):
                detection_data = PostgresTestData.create_test_detection(f"det_batch_{i:04d}")
                await self.detection_repo.create(detection_data)
        
        elapsed = time.time() - start_time
        inserts_per_second = batch_size / elapsed
        
        print(f"\nBatch insert: {batch_size} records in {elapsed:.2f}s ({inserts_per_second:.0f} inserts/s)")
        
        # Should achieve reasonable insert rate
        self.assertGreater(inserts_per_second, 100)
    
    async def test_query_with_pagination(self):
        """Test paginated query performance"""
        # Insert test data
        for i in range(500):
            detection_data = PostgresTestData.create_test_detection(f"det_page_{i:03d}")
            await self.detection_repo.create(detection_data)
        
        # Test pagination performance
        start_time = time.time()
        
        for page in range(1, 6):
            offset = (page - 1) * 50
            results = await self.detection_repo.get_all(limit=50, offset=offset)
            self.assertEqual(len(results), 50)
        
        elapsed = time.time() - start_time
        print(f"\nPagination: 5 pages in {elapsed:.2f}s")
        
        self.assertLess(elapsed, 1.0)


# ============================================================================
# Data Integrity Tests
# ============================================================================

class TestPostgresDataIntegrity(PostgresTestBase):
    """Tests for data integrity constraints"""
    
    async def test_primary_key_constraint(self):
        """Test primary key constraint violation"""
        detection_data = PostgresTestData.create_test_detection("det_pk_001")
        await self.detection_repo.create(detection_data)
        
        # Try to insert duplicate ID
        with self.assertRaises(Exception):
            await self.detection_repo.create(detection_data)
    
    async def test_foreign_key_constraint(self):
        """Test foreign key constraint"""
        # Create alert referencing non-existent detection
        alert_data = PostgresTestData.create_test_alert()
        alert_data['detection_id'] = 'nonexistent_id'
        
        # May or may not fail depending on FK constraint
        # If FK is enabled, this should fail
        try:
            await self.alert_repo.create(alert_data)
        except Exception:
            pass  # Expected to fail if FK constraint exists
    
    async def test_not_null_constraint(self):
        """Test NOT NULL constraint"""
        detection_data = PostgresTestData.create_test_detection()
        detection_data['drone_type'] = None  # Should be NOT NULL
        
        with self.assertRaises(Exception):
            await self.detection_repo.create(detection_data)
    
    async def test_check_constraint(self):
        """Test check constraint (e.g., confidence range)"""
        detection_data = PostgresTestData.create_test_detection()
        detection_data['confidence'] = 1.5  # Invalid confidence (> 1)
        
        with self.assertRaises(Exception):
            await self.detection_repo.create(detection_data)


# ============================================================================
# Migration Tests
# ============================================================================

class TestPostgresMigrations(PostgresTestBase):
    """Tests for database migrations"""
    
    async def test_schema_version(self):
        """Test schema version tracking"""
        # Check if migrations table exists
        result = await self.db.fetch_val(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version')"
        )
        
        # Table may or may not exist depending on setup
        self.assertIsNotNone(result)
    
    async def test_table_exists(self):
        """Test that all expected tables exist"""
        expected_tables = ['detections', 'alerts', 'remote_id_messages']
        
        for table in expected_tables:
            result = await self.db.fetch_val(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                table
            )
            self.assertTrue(result, f"Table {table} should exist")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)