#!/usr/bin/env python3
# drone-detector/infrastructure/storage/__init__.py
"""
Infrastructure Storage Module

This module provides comprehensive data storage capabilities for the Drone Detection System,
including:
- Database connection management (SQLite, PostgreSQL, MySQL)
- ORM models for all entities
- Repository pattern implementation
- Database migration management (Alembic)
- Complex query builder
- Data persistence operations
- Transaction management
- Connection pooling
- Backup and restore operations
- Health monitoring

The storage layer abstracts database operations and provides a clean interface
for the application layer to interact with persistent data.
"""

from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime

# ============================================================================
# Database Connection and Management
# ============================================================================

from .database import (
    DatabaseManager,
    DatabaseConfig,
    DatabaseType,
    DatabaseAdapter,
    SQLiteAdapter,
    PostgreSQLAdapter,
    MySQLAdapter,
    ConnectionStats,
    PoolState,
    create_database_manager,
    create_sqlite_manager
)

# ============================================================================
# Models (SQLAlchemy ORM for schema definition)
# ============================================================================

from .models import (
    Base,
    Detection,
    DetectionEvent,
    Alert,
    SystemMetric,
    DroneSignature,
    SpectrumSignature,
    RemoteIDMessage,
    RemoteIDSession,
    RemoteIDTrack,
    AlertEscalation,
    Notification,
    AlertRule,
    SpectrumMeasurement,
    InterferenceMeasurement,
    ModulationAnalysis,
    Recording,
    RecordingSession,
    RecordingEvent,
    GeofenceZone,
    GeofenceViolation,
    GeolocationHistory,
    AuditLog,
    SystemEvent,
    UserActivity,
    ConfigurationHistory,
    MLTrainingSample,
    MLModel,
    MLPrediction,
    MLTrainingJob
)

# ============================================================================
# Repositories (Data Access Layer)
# ============================================================================

from .repositories import (
    DetectionRepository,
    AlertRepository,
    RemoteIDRepository,
    DroneSignatureRepository,
    SpectrumRepository,
    RecordingRepository,
    GeofenceRepository,
    MLRepository,
    AuditRepository
)

# ============================================================================
# Query Builder
# ============================================================================

from .query_builder import (
    QueryBuilder,
    DetectionQueryBuilder,
    AlertQueryBuilder,
    RemoteIDQueryBuilder,
    SpectrumQueryBuilder,
    RecordingQueryBuilder,
    Condition,
    ConditionGroup,
    Operator,
    LogicalOperator,
    OrderDirection,
    JoinType,
    AggregateFunction,
    QueryExecutor
)

# ============================================================================
# Migrations
# ============================================================================

from .migrations import (
    # Migration management functions
    get_migration_list,
    get_migration_info,
    get_latest_migration,
    get_migrations_summary,
    MIGRATIONS_INFO
)

# ============================================================================
# Version and Metadata
# ============================================================================

__version__ = "2.0.0"
__author__ = "Drone Detection System Team"
__copyright__ = "Copyright 2024-2025, Drone Detection System"
__license__ = "MIT"

# ============================================================================
# Public API - Explicit Exports
# ============================================================================

__all__ = [
    # Database Management
    "DatabaseManager",
    "DatabaseConfig",
    "DatabaseType",
    "DatabaseAdapter",
    "SQLiteAdapter",
    "PostgreSQLAdapter",
    "MySQLAdapter",
    "ConnectionStats",
    "PoolState",
    "create_database_manager",
    "create_sqlite_manager",
    
    # Models
    "Base",
    "Detection",
    "DetectionEvent",
    "Alert",
    "SystemMetric",
    "DroneSignature",
    "SpectrumSignature",
    "RemoteIDMessage",
    "RemoteIDSession",
    "RemoteIDTrack",
    "AlertEscalation",
    "Notification",
    "AlertRule",
    "SpectrumMeasurement",
    "InterferenceMeasurement",
    "ModulationAnalysis",
    "Recording",
    "RecordingSession",
    "RecordingEvent",
    "GeofenceZone",
    "GeofenceViolation",
    "GeolocationHistory",
    "AuditLog",
    "SystemEvent",
    "UserActivity",
    "ConfigurationHistory",
    "MLTrainingSample",
    "MLModel",
    "MLPrediction",
    "MLTrainingJob",
    
    # Repositories
    "DetectionRepository",
    "AlertRepository",
    "RemoteIDRepository",
    "DroneSignatureRepository",
    "SpectrumRepository",
    "RecordingRepository",
    "GeofenceRepository",
    "MLRepository",
    "AuditRepository",
    
    # Query Builder
    "QueryBuilder",
    "DetectionQueryBuilder",
    "AlertQueryBuilder",
    "RemoteIDQueryBuilder",
    "SpectrumQueryBuilder",
    "RecordingQueryBuilder",
    "Condition",
    "ConditionGroup",
    "Operator",
    "LogicalOperator",
    "OrderDirection",
    "JoinType",
    "AggregateFunction",
    "QueryExecutor",
    
    # Migrations
    "get_migration_list",
    "get_migration_info",
    "get_latest_migration",
    "get_migrations_summary",
    "MIGRATIONS_INFO"
]


# ============================================================================
# Unified Storage Manager
# ============================================================================

class StorageManager:
    """
    Unified storage manager that provides a single interface for all data operations
    
    This class orchestrates database connections, repositories, and provides
    high-level data access methods for the application layer.
    
    Usage:
        storage = StorageManager()
        await storage.initialize()
        
        # Save a detection
        detection_id = await storage.save_detection(detection_data)
        
        # Query detections
        detections = await storage.get_detections(
            threat_level="HIGH",
            start_time=datetime.now() - timedelta(hours=1)
        )
        
        # Get statistics
        stats = storage.get_stats()
    """
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize storage manager
        
        Args:
            config: Database configuration (uses defaults if None)
        """
        self.config = config or DatabaseConfig()
        self.db: Optional[DatabaseManager] = None
        self._initialized = False
        
        # Repositories
        self.detections: Optional[DetectionRepository] = None
        self.alerts: Optional[AlertRepository] = None
        self.remote_id: Optional[RemoteIDRepository] = None
        self.drone_signatures: Optional[DroneSignatureRepository] = None
        self.spectrum: Optional[SpectrumRepository] = None
        self.recordings: Optional[RecordingRepository] = None
        self.geofence: Optional[GeofenceRepository] = None
        self.ml: Optional[MLRepository] = None
        self.audit: Optional[AuditRepository] = None
        
        # Statistics
        self.stats = {
            'initialized': False,
            'queries_executed': 0,
            'transactions': 0,
            'errors': 0
        }
    
    async def initialize(self, create_tables: bool = True, 
                        run_migrations: bool = True) -> None:
        """
        Initialize storage manager
        
        Args:
            create_tables: Whether to create tables if they don't exist
            run_migrations: Whether to run pending migrations
        """
        if self._initialized:
            logger.warning("Storage manager already initialized")
            return
        
        # Create database manager
        self.db = DatabaseManager(self.config)
        await self.db.initialize()
        
        # Create tables if needed
        if create_tables:
            await self.db.create_tables()
        
        # Run migrations if needed
        if run_migrations:
            await self._run_migrations()
        
        # Initialize repositories
        self.detections = DetectionRepository(self.db)
        self.alerts = AlertRepository(self.db)
        self.remote_id = RemoteIDRepository(self.db)
        self.drone_signatures = DroneSignatureRepository(self.db)
        self.spectrum = SpectrumRepository(self.db)
        self.recordings = RecordingRepository(self.db)
        self.geofence = GeofenceRepository(self.db)
        self.ml = MLRepository(self.db)
        self.audit = AuditRepository(self.db)
        
        self._initialized = True
        self.stats['initialized'] = True
        
        logger.info(f"Storage manager initialized with {self.config.db_type.value}")
    
    async def _run_migrations(self) -> None:
        """Run database migrations"""
        # This would integrate with Alembic
        # For now, just log
        logger.info("Migrations would run here (Alembic integration)")
    
    async def close(self) -> None:
        """Close all database connections"""
        if self.db:
            await self.db.close()
        self._initialized = False
        logger.info("Storage manager closed")
    
    # ========================================================================
    # High-level Detection Operations
    # ========================================================================
    
    async def save_detection(self, detection_data: Dict[str, Any]) -> str:
        """Save a detection record"""
        self.stats['queries_executed'] += 1
        return await self.detections.create(detection_data)
    
    async def get_detection(self, detection_id: str) -> Optional[Dict[str, Any]]:
        """Get a detection by ID"""
        return await self.detections.get_by_id(detection_id)
    
    async def get_detections(self, **filters) -> List[Dict[str, Any]]:
        """Get detections with filters"""
        self.stats['queries_executed'] += 1
        return await self.detections.get_all(**filters)
    
    async def get_detections_by_threat(self, threat_level: str,
                                       limit: int = 100) -> List[Dict[str, Any]]:
        """Get detections by threat level"""
        return await self.detections.get_by_threat_level(threat_level, limit)
    
    async def get_recent_detections(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get recent detections"""
        return await self.detections.get_recent(minutes)
    
    async def get_detection_count(self, **filters) -> int:
        """Get count of detections"""
        return await self.detections.count(**filters)
    
    async def update_detection(self, detection_id: str, 
                               updates: Dict[str, Any]) -> bool:
        """Update a detection"""
        return await self.detections.update(detection_id, updates)
    
    async def delete_detection(self, detection_id: str) -> bool:
        """Delete a detection"""
        return await self.detections.delete(detection_id)
    
    # ========================================================================
    # High-level Alert Operations
    # ========================================================================
    
    async def save_alert(self, alert_data: Dict[str, Any]) -> str:
        """Save an alert"""
        self.stats['queries_executed'] += 1
        return await self.alerts.create(alert_data)
    
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts"""
        return await self.alerts.get_active()
    
    async def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        """Acknowledge an alert"""
        return await self.alerts.acknowledge(alert_id, user)
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        return await self.alerts.resolve(alert_id)
    
    async def escalate_alert(self, alert_id: str) -> bool:
        """Escalate an alert"""
        return await self.alerts.escalate(alert_id)
    
    # ========================================================================
    # High-level Remote ID Operations
    # ========================================================================
    
    async def save_remote_id_message(self, message_data: Dict[str, Any]) -> str:
        """Save a Remote ID message"""
        return await self.remote_id.save_message(message_data)
    
    async def get_drone_track(self, uas_id: str, 
                              start_time: datetime,
                              end_time: datetime) -> List[Dict[str, Any]]:
        """Get drone track for time range"""
        return await self.remote_id.get_track(uas_id, start_time, end_time)
    
    async def get_active_drones(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """Get currently active drones"""
        return await self.remote_id.get_active_drones(minutes)
    
    async def get_drone_session(self, uas_id: str) -> Optional[Dict[str, Any]]:
        """Get drone session information"""
        return await self.remote_id.get_session(uas_id)
    
    # ========================================================================
    # High-level Recording Operations
    # ========================================================================
    
    async def save_recording(self, recording_data: Dict[str, Any]) -> str:
        """Save recording metadata"""
        return await self.recordings.create(recording_data)
    
    async def get_recordings(self, **filters) -> List[Dict[str, Any]]:
        """Get recordings with filters"""
        return await self.recordings.get_all(**filters)
    
    async def get_recording_file_path(self, recording_id: str) -> Optional[str]:
        """Get file path for a recording"""
        recording = await self.recordings.get_by_id(recording_id)
        return recording.get('file_path') if recording else None
    
    # ========================================================================
    # High-level Geofence Operations
    # ========================================================================
    
    async def check_geofence_violation(self, latitude: float, longitude: float,
                                       altitude: float = 0) -> Dict[str, Any]:
        """Check if position violates any geofence"""
        return await self.geofence.check_violation(latitude, longitude, altitude)
    
    async def get_geofence_zones(self, zone_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get geofence zones"""
        filters = {}
        if zone_type:
            filters['zone_type'] = zone_type
        return await self.geofence.get_all(**filters)
    
    # ========================================================================
    # High-level ML Operations
    # ========================================================================
    
    async def save_training_sample(self, sample_data: Dict[str, Any]) -> str:
        """Save a training sample"""
        return await self.ml.save_training_sample(sample_data)
    
    async def get_active_model(self) -> Optional[Dict[str, Any]]:
        """Get the currently active ML model"""
        return await self.ml.get_active_model()
    
    async def save_prediction(self, prediction_data: Dict[str, Any]) -> str:
        """Save a prediction result"""
        return await self.ml.save_prediction(prediction_data)
    
    # ========================================================================
    # High-level Audit Operations
    # ========================================================================
    
    async def log_audit_event(self, event_data: Dict[str, Any]) -> str:
        """Log an audit event"""
        return await self.audit.log_event(event_data)
    
    async def get_audit_logs(self, **filters) -> List[Dict[str, Any]]:
        """Get audit logs with filters"""
        return await self.audit.get_logs(**filters)
    
    # ========================================================================
    # Statistics and Health
    # ========================================================================
    
    async def health_check(self) -> bool:
        """Check database health"""
        if not self.db:
            return False
        return await self.db.health_check()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage manager statistics"""
        db_stats = self.db.get_stats() if self.db else {}
        
        return {
            **self.stats,
            'database': db_stats.to_dict() if hasattr(db_stats, 'to_dict') else {},
            'config': self.config.to_dict() if hasattr(self.config, 'to_dict') else {}
        }
    
    async def backup(self, backup_path: Optional[str] = None) -> str:
        """Backup the database"""
        if not self.db:
            raise RuntimeError("Database not initialized")
        path = await self.db.backup(Path(backup_path) if backup_path else None)
        return str(path)
    
    async def restore(self, backup_path: str) -> bool:
        """Restore database from backup"""
        if not self.db:
            raise RuntimeError("Database not initialized")
        return await self.db.restore(Path(backup_path))


# ============================================================================
# Convenience Functions
# ============================================================================

def get_storage_info() -> Dict[str, Any]:
    """
    Get information about storage components
    
    Returns:
        Dictionary with component information
    """
    return {
        "version": __version__,
        "components": {
            "database": {
                "backends": ["sqlite", "postgresql", "mysql"],
                "features": ["connection_pooling", "async", "transactions"]
            },
            "repositories": [
                "DetectionRepository",
                "AlertRepository",
                "RemoteIDRepository",
                "DroneSignatureRepository",
                "SpectrumRepository",
                "RecordingRepository",
                "GeofenceRepository",
                "MLRepository",
                "AuditRepository"
            ],
            "query_builder": {
                "operators": ["eq", "ne", "gt", "gte", "lt", "lte", "like", "in", "between"],
                "joins": ["inner", "left", "right", "full"],
                "aggregations": ["count", "sum", "avg", "min", "max"]
            },
            "migrations": {
                "total": len(MIGRATIONS_INFO),
                "latest": get_latest_migration()
            }
        }
    }


# ============================================================================
# Singleton Manager
# ============================================================================

_default_storage_manager: Optional[StorageManager] = None


async def get_storage_manager(config: Optional[DatabaseConfig] = None) -> StorageManager:
    """
    Get or create the default storage manager singleton
    
    Args:
        config: Database configuration (used only on first creation)
        
    Returns:
        StorageManager instance
    """
    global _default_storage_manager
    
    if _default_storage_manager is None:
        _default_storage_manager = StorageManager(config)
        await _default_storage_manager.initialize()
    
    return _default_storage_manager


async def reset_storage_manager() -> None:
    """Reset the default storage manager"""
    global _default_storage_manager
    
    if _default_storage_manager:
        await _default_storage_manager.close()
        _default_storage_manager = None


# ============================================================================
# Module Documentation
# ============================================================================

__doc__ = """
Infrastructure Storage Package
==============================

This package provides comprehensive data storage capabilities for the Drone Detection System.

Components:
-----------
1. **Database Manager** - Connection pooling and database operations
2. **Models** - SQLAlchemy ORM models for all entities
3. **Repositories** - Data access layer with CRUD operations
4. **Query Builder** - Fluent SQL query construction
5. **Migrations** - Alembic-based schema version control

Quick Start:
-----------
```python
from infrastructure.storage import (
    StorageManager,
    DatabaseConfig,
    DatabaseType,
    get_storage_manager
)

# Method 1: Use unified manager
storage = await get_storage_manager()

# Save a detection
detection_id = await storage.save_detection({
    'drone_type': 'DJI Mavic 3',
    'confidence': 0.95,
    'threat_level': 'HIGH'
})

# Query detections
detections = await storage.get_detections(
    threat_level='HIGH',
    start_time=datetime.now() - timedelta(hours=1)
)

# Get active alerts
alerts = await storage.get_active_alerts()

# Method 2: Use specific repository
from infrastructure.storage import DetectionRepository

repo = DetectionRepository(db)
detection = await repo.get_by_id(detection_id)

# Method 3: Use query builder
from infrastructure.storage import DetectionQueryBuilder

builder = DetectionQueryBuilder()
sql, params = (builder
               .select('id', 'drone_type')
               .by_threat_level('HIGH')
               .recent(30)
               .build())